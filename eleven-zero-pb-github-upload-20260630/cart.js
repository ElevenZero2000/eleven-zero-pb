const cartHeroCardNode = document.querySelector("[data-cart-hero-card]");
const cartItemsPanelNode = document.querySelector("[data-cart-items-panel]");
const cartCheckoutPanelNode = document.querySelector("[data-cart-checkout-panel]");
const CART_ITEMS_STORAGE_KEY = "elevenZeroPbCartItems";
const LEGACY_CART_DRAFT_STORAGE_KEY = "elevenZeroPbCartDraft";
const SHIPPING_DRAFT_STORAGE_KEY = "elevenZeroPbShippingAddressDraft";
const PENDING_CHECKOUT_LISTING_KEY = "elevenZeroPbPendingCheckoutListing";

const cartState = {
  cartItems: [],
  listings: [],
  selectedListingId: 0,
  shipping: createDefaultShippingState(),
  busy: false,
  statusMessage: "Choose a paddle, confirm shipping, then continue to secure checkout.",
  statusTone: "neutral",
};

function createDefaultShippingState() {
  return {
    line1: "",
    line2: "",
    city: "",
    state: "",
    postalCode: "",
    country: "US",
    quote: null,
    busy: false,
    statusMessage: "Add the delivery address to estimate shipping.",
    statusTone: "neutral",
  };
}

function safeParseJson(value) {
  if (!value) return null;

  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function readStorageJson(key) {
  try {
    return safeParseJson(window.localStorage.getItem(key));
  } catch {
    return null;
  }
}

function writeStorageJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

function removeStorageItem(key) {
  try {
    window.localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

function formatMoneyFromCents(cents) {
  return ElevenZeroApp.formatMoney(Number(cents || 0) / 100);
}

function formatThickness(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "";
  return `${numeric.toFixed(numeric % 1 === 0 ? 0 : 1)} mm`;
}

function normalizeCartItem(rawItem) {
  const listingId = Number(rawItem?.listingId || rawItem?.id || 0);
  if (!listingId) return null;

  return {
    listingId,
    title: String(rawItem?.title || "").trim(),
    brand: String(rawItem?.brand || "").trim(),
    model: String(rawItem?.model || "").trim(),
    condition: String(rawItem?.condition || "").trim(),
    color: String(rawItem?.color || "").trim(),
    thicknessMm: rawItem?.thicknessMm || rawItem?.thickness_mm || "",
    location: String(rawItem?.location || "").trim(),
    priceUsd: Number(rawItem?.priceUsd || rawItem?.price_usd || 0),
    image: String(rawItem?.image || rawItem?.primary_image || "").trim(),
    updatedAt: String(rawItem?.updatedAt || new Date().toISOString()),
  };
}

function loadCartItemsFromStorage() {
  const savedItems = readStorageJson(CART_ITEMS_STORAGE_KEY);
  const legacyItem = readStorageJson(LEGACY_CART_DRAFT_STORAGE_KEY);
  const rawItems = [
    ...(Array.isArray(savedItems) ? savedItems : []),
    ...(legacyItem ? [legacyItem] : []),
  ];
  const uniqueItems = [];
  const seen = new Set();

  rawItems.forEach((rawItem) => {
    const item = normalizeCartItem(rawItem);
    if (!item || seen.has(item.listingId)) return;
    seen.add(item.listingId);
    uniqueItems.push(item);
  });

  return uniqueItems.slice(0, 12);
}

function saveCartItems() {
  writeStorageJson(CART_ITEMS_STORAGE_KEY, cartState.cartItems);
}

function getRequestedListingId() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("listingId") || "";
  return /^\d+$/.test(raw) ? Number(raw) : 0;
}

function replaceCartUrl(listingId = cartState.selectedListingId) {
  const url = new URL(window.location.href);
  url.searchParams.delete("checkout");
  url.searchParams.delete("session_id");

  if (listingId) {
    url.searchParams.set("listingId", String(listingId));
  } else {
    url.searchParams.delete("listingId");
  }

  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash || ""}`);
}

function clearCheckoutParams() {
  replaceCartUrl(cartState.selectedListingId);
}

function getSelectedListing() {
  return getDisplayItem(cartState.selectedListingId);
}

function getSnapshotForListing(listingId) {
  return cartState.cartItems.find((item) => Number(item.listingId) === Number(listingId)) || null;
}

function getDisplayItem(listingId) {
  const listing = cartState.listings.find((item) => Number(item.id) === Number(listingId));
  const snapshot = getSnapshotForListing(listingId);
  if (listing) return listing;

  return snapshot
    ? {
        id: snapshot.listingId,
        brand: snapshot.brand,
        model: snapshot.model || snapshot.title,
        condition: snapshot.condition,
        color: snapshot.color,
        thickness_mm: snapshot.thicknessMm,
        location: snapshot.location,
        price_usd: snapshot.priceUsd,
        images: snapshot.image ? [snapshot.image] : [],
        checkout_available: false,
        checkout_reason: "This saved item could not be refreshed. Open the listing to check if it is still available.",
      }
    : null;
}

function getListingImages(item) {
  if (!item) return [];
  return Array.isArray(item.images) ? item.images.filter(Boolean) : item.primary_image ? [item.primary_image] : [];
}

function getCartSubtotalCents() {
  return cartState.cartItems.reduce((sum, cartItem) => {
    const item = getDisplayItem(cartItem.listingId);
    return sum + Math.max(0, Number(item?.price_usd || cartItem.priceUsd || 0)) * 100;
  }, 0);
}

function getSelectedSubtotalCents(item = getSelectedListing()) {
  return Math.max(0, Number(item?.price_usd || 0)) * 100;
}

function getSelectedTotalCents(item = getSelectedListing()) {
  return getSelectedSubtotalCents(item) + Number(cartState.shipping.quote?.amountCents || 0);
}

function getShippingAddressPayload() {
  const shipping = cartState.shipping || createDefaultShippingState();
  return {
    line1: shipping.line1,
    line2: shipping.line2,
    city: shipping.city,
    state: shipping.state,
    postalCode: shipping.postalCode,
    country: shipping.country || "US",
  };
}

function getShippingDraftSnapshot() {
  return {
    line1: String(cartState.shipping?.line1 || "").trim(),
    line2: String(cartState.shipping?.line2 || "").trim(),
    city: String(cartState.shipping?.city || "").trim(),
    state: String(cartState.shipping?.state || "").trim(),
    postalCode: String(cartState.shipping?.postalCode || "").trim(),
    country: String(cartState.shipping?.country || "US").trim() || "US",
  };
}

function shippingDraftHasContent(snapshot = getShippingDraftSnapshot()) {
  return Boolean(
    snapshot.line1 || snapshot.line2 || snapshot.city || snapshot.state || snapshot.postalCode
  );
}

function restoreShippingDraftState() {
  const savedDraft = readStorageJson(SHIPPING_DRAFT_STORAGE_KEY);
  const defaults = createDefaultShippingState();

  if (!savedDraft || typeof savedDraft !== "object") {
    return defaults;
  }

  return {
    ...defaults,
    line1: String(savedDraft.line1 || "").trim(),
    line2: String(savedDraft.line2 || "").trim(),
    city: String(savedDraft.city || "").trim(),
    state: String(savedDraft.state || "").trim(),
    postalCode: String(savedDraft.postalCode || "").trim(),
    country: String(savedDraft.country || "US").trim() || "US",
  };
}

function persistShippingDraft() {
  const snapshot = getShippingDraftSnapshot();

  if (!shippingDraftHasContent(snapshot)) {
    removeStorageItem(SHIPPING_DRAFT_STORAGE_KEY);
    return;
  }

  writeStorageJson(SHIPPING_DRAFT_STORAGE_KEY, snapshot);
}

function getShippingPolicy(item) {
  const shipping = item?.shipping || {};
  const mode = shipping.mode || "calculated";
  const label =
    shipping.label ||
    (mode === "free"
      ? "Free shipping"
      : mode === "flat"
        ? "Flat shipping"
        : "Calculated shipping at checkout");

  return {
    mode,
    label,
    note: shipping.note || "",
    explanation:
      shipping.explanation ||
      (mode === "free"
        ? "Seller is covering shipping on this listing."
        : mode === "flat"
          ? "Seller set one shipping amount for every U.S. destination."
          : "Enter your delivery address and we’ll estimate the delivered total before checkout."),
  };
}

function getBaseActionState(item) {
  const currentUserId = Number(ElevenZeroApp.session?.user?.id || 0);
  const sellerUserId = Number(item?.seller_user_id || 0);
  const isOwner = currentUserId && sellerUserId && currentUserId === sellerUserId;
  const approvalStatus = item?.approval_status || "approved";

  if (!item) {
    return {
      action: "disabled",
      buttonLabel: "Choose a paddle",
      statusLabel: "No paddle selected",
      reason: "Select a paddle from your cart to see checkout options.",
      tone: "neutral",
    };
  }

  if (isOwner) {
    return {
      action: "disabled",
      buttonLabel: "Your listing",
      statusLabel: "Seller view",
      reason: "You can’t purchase your own listing.",
      tone: "neutral",
    };
  }

  if (approvalStatus === "pending") {
    return {
      action: "disabled",
      buttonLabel: "Under review",
      statusLabel: "Pending review",
      reason: "This listing is waiting for Eleven Zero PB approval before checkout can begin.",
      tone: "pending",
    };
  }

  if (approvalStatus === "rejected") {
    return {
      action: "disabled",
      buttonLabel: "Needs changes",
      statusLabel: "Needs changes",
      reason: "This listing is paused until the seller updates it.",
      tone: "neutral",
    };
  }

  if (item.checkout_available) {
    if (ElevenZeroApp.session?.authenticated) {
      return {
        action: "checkout",
        buttonLabel: "Checkout securely",
        statusLabel: "Secure checkout ready",
        reason: "This paddle can move into secure checkout.",
        tone: "ready",
      };
    }

    return {
      action: "auth",
      buttonLabel: "Sign in to checkout",
      statusLabel: "Secure checkout ready",
      reason: "Sign in first, then continue checkout from this cart.",
      tone: "ready",
    };
  }

  return {
    action: "disabled",
    buttonLabel: item.checkout_available === false ? "Checkout not ready" : "Checkout soon",
    statusLabel: item.seller_has_connected_account ? "Seller setup pending" : "Payouts not connected",
    reason:
      item.checkout_reason ||
      "This seller still needs to complete payout setup before checkout can go live.",
    tone: "pending",
  };
}

function getCartActionState(item) {
  const baseActionState = getBaseActionState(item);
  const shippingPolicy = getShippingPolicy(item);
  const shippingQuote = cartState.shipping.quote;

  if ((baseActionState.action === "checkout" || baseActionState.action === "auth") && !shippingQuote) {
    return {
      ...baseActionState,
      action: "estimate-needed",
      buttonLabel:
        shippingPolicy.mode === "calculated" ? "Estimate shipping first" : "Confirm shipping first",
      statusLabel: "Shipping needed",
      reason:
        shippingPolicy.mode === "calculated"
          ? "Add your delivery address so we can estimate shipping before checkout."
          : "Add your delivery address so we can confirm the delivered total before checkout.",
      tone: "pending",
    };
  }

  if (baseActionState.action === "checkout" && shippingQuote) {
    return {
      ...baseActionState,
      buttonLabel: "Checkout securely",
      statusLabel: shippingQuote.isEstimate ? "Estimated total ready" : "Delivered total ready",
      reason: `${formatMoneyFromCents(shippingQuote.amountCents)} ${
        shippingQuote.isEstimate ? "estimated shipping" : "shipping"
      } to ${shippingQuote.destinationSummary}. Total ${formatMoneyFromCents(getSelectedTotalCents(item))}.`,
      tone: "ready",
    };
  }

  if (baseActionState.action === "auth" && shippingQuote) {
    return {
      ...baseActionState,
      buttonLabel: "Sign in to checkout",
      reason: `${formatMoneyFromCents(
        shippingQuote.amountCents
      )} shipping to ${shippingQuote.destinationSummary}. Sign in to continue.`,
    };
  }

  return baseActionState;
}

function setCartStatus(message, tone = "neutral") {
  cartState.statusMessage = message;
  cartState.statusTone = tone;
  const statusNode = cartCheckoutPanelNode?.querySelector("[data-cart-status]");
  ElevenZeroApp.setStatus(statusNode, message, tone);
}

function setShippingStatus(message, tone = "neutral") {
  cartState.shipping.statusMessage = message;
  cartState.shipping.statusTone = tone;
  const statusNode = cartCheckoutPanelNode?.querySelector("[data-shipping-status]");
  ElevenZeroApp.setStatus(statusNode, message, tone);
}

function renderHeroCard() {
  if (!cartHeroCardNode) return;

  const itemCount = cartState.cartItems.length;
  const subtotal = getCartSubtotalCents();
  const selectedItem = getSelectedListing();

  cartHeroCardNode.innerHTML = `
    <span>${ElevenZeroApp.escapeHtml(`${itemCount} ${itemCount === 1 ? "paddle" : "paddles"} saved`)}</span>
    <strong>${ElevenZeroApp.escapeHtml(formatMoneyFromCents(subtotal))} in saved gear</strong>
    <p>${ElevenZeroApp.escapeHtml(
      selectedItem
        ? `Selected: ${selectedItem.brand} ${selectedItem.model}`
        : "Pick a paddle below to continue."
    )}</p>
  `;
}

function renderEmptyCart() {
  if (cartItemsPanelNode) {
    cartItemsPanelNode.innerHTML = `
      <div class="cart-panel-head">
        <div>
          <p class="eyebrow">Cart items</p>
          <h2>Your cart is empty.</h2>
        </div>
      </div>
      <div class="cart-empty-state">
        <strong>No paddles saved yet</strong>
        <span>Open the shop, choose a paddle, and click Buy now to add it here.</span>
        <a class="button button-dark" href="./shop.html">Shop paddles</a>
      </div>
    `;
  }

  if (cartCheckoutPanelNode) {
    cartCheckoutPanelNode.innerHTML = `
      <p class="eyebrow">Checkout</p>
      <h2>Nothing to checkout yet.</h2>
      <p class="cart-muted-copy">Your checkout summary will appear once you add a paddle.</p>
    `;
  }

  renderHeroCard();
}

function renderCartItems() {
  if (!cartItemsPanelNode) return;

  if (!cartState.cartItems.length) {
    renderEmptyCart();
    return;
  }

  const itemsMarkup = cartState.cartItems
    .map((cartItem) => {
      const item = getDisplayItem(cartItem.listingId);
      if (!item) return "";
      const images = getListingImages(item);
      const image = images[0] || cartItem.image || "";
      const title = `${item.brand || ""} ${item.model || cartItem.title || ""}`.trim();
      const meta = [item.condition, formatThickness(item.thickness_mm), item.color, item.location]
        .filter(Boolean)
        .join(" · ");
      const isSelected = Number(cartState.selectedListingId) === Number(cartItem.listingId);

      return `
        <article class="cart-product-row${isSelected ? " is-selected" : ""}">
          <button
            class="cart-product-select"
            type="button"
            data-select-listing="${ElevenZeroApp.escapeHtml(cartItem.listingId)}"
            aria-label="Select ${ElevenZeroApp.escapeHtml(title)}"
          >
            <span class="cart-product-image">
              ${
                image
                  ? `<img src="${ElevenZeroApp.escapeHtml(image)}" alt="${ElevenZeroApp.escapeHtml(title)}" />`
                  : `<span class="cart-product-image-empty">11Z</span>`
              }
            </span>
            <span class="cart-product-info">
              <strong>${ElevenZeroApp.escapeHtml(title || "Saved paddle")}</strong>
              <em>${ElevenZeroApp.escapeHtml(meta || "Details available on listing page")}</em>
              <small>${ElevenZeroApp.escapeHtml(isSelected ? "Selected for checkout" : "Saved in cart")}</small>
            </span>
            <span class="cart-product-price">${ElevenZeroApp.escapeHtml(
              ElevenZeroApp.formatMoney(item.price_usd || cartItem.priceUsd)
            )}</span>
          </button>
          <div class="cart-product-actions">
            <a class="text-link" href="./listing.html?id=${encodeURIComponent(cartItem.listingId)}">
              View
            </a>
            <button class="text-link-button" type="button" data-remove-listing="${ElevenZeroApp.escapeHtml(
              cartItem.listingId
            )}">
              Remove
            </button>
          </div>
        </article>
      `;
    })
    .join("");

  cartItemsPanelNode.innerHTML = `
    <div class="cart-panel-head">
      <div>
        <p class="eyebrow">Cart items</p>
        <h2>${ElevenZeroApp.escapeHtml(
          `${cartState.cartItems.length} ${cartState.cartItems.length === 1 ? "paddle" : "paddles"} saved`
        )}</h2>
      </div>
      <div class="cart-panel-actions">
        <a class="text-link" href="./shop.html">Continue shopping</a>
        <button class="text-link-button" type="button" data-clear-cart>Clear cart</button>
      </div>
    </div>
    <div class="cart-product-list">
      ${itemsMarkup}
    </div>
    <p class="cart-muted-copy">
      Checkout currently runs one paddle at a time. Saved paddles stay here so buyers can compare before choosing.
    </p>
  `;

  cartItemsPanelNode.querySelectorAll("[data-select-listing]").forEach((button) => {
    button.addEventListener("click", () => {
      cartState.selectedListingId = Number(button.dataset.selectListing || 0);
      cartState.shipping.quote = null;
      replaceCartUrl(cartState.selectedListingId);
      renderCart();
    });
  });

  cartItemsPanelNode.querySelectorAll("[data-remove-listing]").forEach((button) => {
    button.addEventListener("click", () => {
      removeCartItem(Number(button.dataset.removeListing || 0));
    });
  });

  cartItemsPanelNode.querySelector("[data-clear-cart]")?.addEventListener("click", () => {
    cartState.cartItems = [];
    cartState.listings = [];
    cartState.selectedListingId = 0;
    cartState.shipping.quote = null;
    saveCartItems();
    removeStorageItem(LEGACY_CART_DRAFT_STORAGE_KEY);
    replaceCartUrl(0);
    renderCart();
  });
}

function renderCheckoutPanel() {
  if (!cartCheckoutPanelNode) return;

  const selectedItem = getSelectedListing();
  if (!cartState.cartItems.length || !selectedItem) {
    renderEmptyCart();
    return;
  }

  const quote = cartState.shipping.quote;
  const shippingPolicy = getShippingPolicy(selectedItem);
  const actionState = getCartActionState(selectedItem);
  const shippingLine = quote
    ? formatMoneyFromCents(quote.amountCents)
    : shippingPolicy.mode === "free"
      ? "$0"
      : shippingPolicy.mode === "flat"
        ? shippingPolicy.label
        : "Estimate needed";
  const totalLine = quote ? formatMoneyFromCents(getSelectedTotalCents(selectedItem)) : "Calculated after shipping";
  const estimateButtonLabel = cartState.shipping.busy
    ? shippingPolicy.mode === "calculated"
      ? "Calculating..."
      : "Confirming..."
    : shippingPolicy.mode === "calculated"
      ? "Estimate shipping"
      : "Confirm shipping";
  const checkoutDisabled = actionState.action === "disabled" || cartState.busy || cartState.shipping.busy;
  const checkoutLabel = cartState.busy ? "Opening checkout..." : actionState.buttonLabel;

  cartCheckoutPanelNode.innerHTML = `
    <div class="cart-panel-head">
      <div>
        <p class="eyebrow">Checkout</p>
        <h2>Selected paddle</h2>
      </div>
      <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(actionState.tone)}">
        ${ElevenZeroApp.escapeHtml(actionState.statusLabel)}
      </span>
    </div>

    <div class="cart-summary-card">
      <div class="cart-summary-row">
        <span>${ElevenZeroApp.escapeHtml(selectedItem.brand)} ${ElevenZeroApp.escapeHtml(selectedItem.model)}</span>
        <strong>${ElevenZeroApp.escapeHtml(ElevenZeroApp.formatMoney(selectedItem.price_usd))}</strong>
      </div>
      <div class="cart-summary-row">
        <span>Shipping</span>
        <strong>${ElevenZeroApp.escapeHtml(shippingLine)}</strong>
      </div>
      <div class="cart-summary-row cart-summary-total">
        <span>Total</span>
        <strong>${ElevenZeroApp.escapeHtml(totalLine)}</strong>
      </div>
    </div>

    <form class="cart-shipping-form" data-cart-shipping-form>
      <div class="cart-form-head">
        <strong>Delivery address</strong>
        <span>${ElevenZeroApp.escapeHtml(shippingPolicy.label)}</span>
      </div>
      <label>
        Street address
        <input
          type="text"
          name="line1"
          autocomplete="shipping address-line1"
          value="${ElevenZeroApp.escapeHtml(cartState.shipping.line1)}"
          placeholder="123 Court Ave"
        />
      </label>
      <label>
        Apartment, suite, etc.
        <input
          type="text"
          name="line2"
          autocomplete="shipping address-line2"
          value="${ElevenZeroApp.escapeHtml(cartState.shipping.line2)}"
          placeholder="Optional"
        />
      </label>
      <div class="cart-address-grid">
        <label>
          City
          <input
            type="text"
            name="city"
            autocomplete="shipping address-level2"
            value="${ElevenZeroApp.escapeHtml(cartState.shipping.city)}"
            placeholder="Arlington"
          />
        </label>
        <label>
          State
          <input
            type="text"
            name="state"
            autocomplete="shipping address-level1"
            value="${ElevenZeroApp.escapeHtml(cartState.shipping.state)}"
            placeholder="VA"
            maxlength="2"
          />
        </label>
        <label>
          ZIP
          <input
            type="text"
            name="postalCode"
            autocomplete="shipping postal-code"
            value="${ElevenZeroApp.escapeHtml(cartState.shipping.postalCode)}"
            placeholder="22201"
          />
        </label>
      </div>
      <input type="hidden" name="country" value="US" />
      <button class="button button-secondary" type="submit" ${cartState.shipping.busy ? "disabled" : ""}>
        ${ElevenZeroApp.escapeHtml(estimateButtonLabel)}
      </button>
      <div class="seller-status listing-detail-status" aria-live="polite" data-shipping-status>
        ${ElevenZeroApp.escapeHtml(cartState.shipping.statusMessage)}
      </div>
    </form>

    <div class="cart-checkout-action">
      <button
        class="${actionState.action === "checkout" || actionState.action === "auth" ? "button button-dark" : "button button-secondary"}"
        type="button"
        data-cart-checkout
        data-cart-action="${ElevenZeroApp.escapeHtml(actionState.action)}"
        ${checkoutDisabled ? "disabled" : ""}
      >
        ${ElevenZeroApp.escapeHtml(checkoutLabel)}
      </button>
      <p>${ElevenZeroApp.escapeHtml(actionState.reason)}</p>
    </div>

    <div class="seller-status listing-detail-status" aria-live="polite" data-cart-status>
      ${ElevenZeroApp.escapeHtml(cartState.statusMessage)}
    </div>
  `;

  ElevenZeroApp.setStatus(
    cartCheckoutPanelNode.querySelector("[data-shipping-status]"),
    cartState.shipping.statusMessage,
    cartState.shipping.statusTone
  );
  ElevenZeroApp.setStatus(
    cartCheckoutPanelNode.querySelector("[data-cart-status]"),
    cartState.statusMessage,
    cartState.statusTone
  );
  bindShippingForm();
  bindCheckoutButton();
}

function renderCart() {
  renderHeroCard();
  renderCartItems();
  renderCheckoutPanel();
}

function updateShippingDraftFromForm(form) {
  const formData = new FormData(form);
  cartState.shipping = {
    ...cartState.shipping,
    line1: String(formData.get("line1") || "").trim(),
    line2: String(formData.get("line2") || "").trim(),
    city: String(formData.get("city") || "").trim(),
    state: String(formData.get("state") || "").trim(),
    postalCode: String(formData.get("postalCode") || "").trim(),
    country: String(formData.get("country") || "US").trim() || "US",
  };
  persistShippingDraft();
}

function bindShippingForm() {
  const form = cartCheckoutPanelNode?.querySelector("[data-cart-shipping-form]");
  if (!form) return;

  form.addEventListener("submit", handleShippingQuoteSubmit);
  form.querySelectorAll("input").forEach((input) => {
    const handleDraftUpdate = () => {
      updateShippingDraftFromForm(form);
      if (!cartState.shipping.quote) return;
      cartState.shipping.quote = null;
      cartState.shipping.statusMessage = "Address updated. Estimate shipping again before checkout.";
      cartState.shipping.statusTone = "warning";
      renderCart();
    };

    input.addEventListener("input", handleDraftUpdate);
    input.addEventListener("change", handleDraftUpdate);
  });
}

function bindCheckoutButton() {
  cartCheckoutPanelNode?.querySelector("[data-cart-checkout]")?.addEventListener("click", () => {
    const action = cartCheckoutPanelNode.querySelector("[data-cart-checkout]")?.dataset.cartAction || "disabled";

    if (action === "estimate-needed") {
      setCartStatus("Add your delivery address, then estimate shipping first.", "warning");
      cartCheckoutPanelNode.querySelector("[data-cart-shipping-form] input[name='line1']")?.focus();
      return;
    }

    if (action === "auth") {
      setCartStatus("Please sign in first, then your cart will bring you back here.", "warning");
      window.setTimeout(() => {
        ElevenZeroApp.redirectToAuth(`${window.location.pathname}${window.location.search}#cart`);
      }, 700);
      return;
    }

    if (action === "checkout") {
      handleCheckout();
      return;
    }

    setCartStatus(getCartActionState(getSelectedListing()).reason, getCartActionState(getSelectedListing()).tone);
  });
}

async function handleShippingQuoteSubmit(event) {
  event.preventDefault();
  const selectedItem = getSelectedListing();
  if (!selectedItem) return;

  updateShippingDraftFromForm(event.currentTarget);
  cartState.shipping.busy = true;
  renderCart();

  try {
    const response = await ElevenZeroApp.request("/api/shipping/quote", {
      method: "POST",
      body: {
        listingId: selectedItem.id,
        shippingAddress: getShippingAddressPayload(),
      },
    });

    cartState.shipping.quote = response.quote || null;
    setShippingStatus(
      response.message || "Shipping estimate is ready. Your total is updated below.",
      "success"
    );
  } catch (error) {
    cartState.shipping.quote = null;
    setShippingStatus(error.message, "error");
  } finally {
    cartState.shipping.busy = false;
    renderCart();
  }
}

async function handleCheckout() {
  const selectedItem = getSelectedListing();
  if (!selectedItem) return;

  if (!cartState.shipping.quote) {
    setCartStatus("Estimate shipping before checkout.", "warning");
    return;
  }

  cartState.busy = true;
  renderCart();

  try {
    const response = await ElevenZeroApp.request("/api/checkout/create-session", {
      method: "POST",
      body: {
        listingId: selectedItem.id,
        shippingAddress: getShippingAddressPayload(),
      },
    });

    writeStorageJson(PENDING_CHECKOUT_LISTING_KEY, {
      listingId: selectedItem.id,
      checkoutUrl: response.checkoutUrl,
      updatedAt: new Date().toISOString(),
    });
    setCartStatus(`Opening checkout for ${response.listing?.title || "this paddle"}.`, "success");
    window.location.href = response.checkoutUrl;
  } catch (error) {
    setCartStatus(error.message, "error");
    cartState.busy = false;
    renderCart();
  }
}

function removeCartItem(listingId) {
  cartState.cartItems = cartState.cartItems.filter((item) => Number(item.listingId) !== Number(listingId));
  cartState.listings = cartState.listings.filter((item) => Number(item.id) !== Number(listingId));

  if (Number(cartState.selectedListingId) === Number(listingId)) {
    cartState.selectedListingId = cartState.cartItems[0]?.listingId || 0;
    cartState.shipping.quote = null;
  }

  saveCartItems();
  replaceCartUrl(cartState.selectedListingId);
  renderCart();
}

async function hydrateCartListings() {
  const listingIds = cartState.cartItems.map((item) => Number(item.listingId)).filter(Boolean);
  const responses = await Promise.allSettled(
    listingIds.map((listingId) => ElevenZeroApp.request(`/api/listings/${listingId}`))
  );

  cartState.listings = responses
    .map((result) => (result.status === "fulfilled" ? result.value?.item : null))
    .filter(Boolean);
}

function pickInitialSelectedListing() {
  const requestedListingId = getRequestedListingId();
  const cartHasRequested = cartState.cartItems.some(
    (item) => Number(item.listingId) === Number(requestedListingId)
  );
  cartState.selectedListingId =
    requestedListingId && cartHasRequested ? requestedListingId : cartState.cartItems[0]?.listingId || 0;
  replaceCartUrl(cartState.selectedListingId);
}

async function handleCheckoutReturn() {
  const params = new URLSearchParams(window.location.search);
  const checkoutState = params.get("checkout");
  const sessionId = params.get("session_id");

  if (!checkoutState) return;

  if (checkoutState === "cancel") {
    setCartStatus("Checkout was canceled. Your cart is still here when you’re ready.", "warning");
    clearCheckoutParams();
    return;
  }

  if (checkoutState !== "success") return;

  if (!ElevenZeroApp.session?.authenticated || !sessionId) {
    setCartStatus("Checkout finished. Sign in if you want to confirm the order details here.", "warning");
    clearCheckoutParams();
    return;
  }

  try {
    const response = await ElevenZeroApp.request(
      `/api/checkout/session-status?sessionId=${encodeURIComponent(sessionId)}`
    );
    const order = response.order || {};
    const amountLabel = order.amountTotalCents ? formatMoneyFromCents(order.amountTotalCents) : "";
    const summary = [response.message, order.listingTitle, amountLabel].filter(Boolean).join(" · ");
    setCartStatus(summary, order.status === "paid" ? "success" : "warning");

    if (order.status === "paid") {
      const pending = readStorageJson(PENDING_CHECKOUT_LISTING_KEY);
      if (pending?.listingId) {
        cartState.cartItems = cartState.cartItems.filter(
          (item) => Number(item.listingId) !== Number(pending.listingId)
        );
        saveCartItems();
        removeStorageItem(PENDING_CHECKOUT_LISTING_KEY);
      }
    }
  } catch (error) {
    setCartStatus(error.message, "error");
  } finally {
    clearCheckoutParams();
    renderCart();
  }
}

async function loadCartPage() {
  cartState.cartItems = loadCartItemsFromStorage();
  cartState.shipping = restoreShippingDraftState();

  if (!cartState.cartItems.length) {
    renderEmptyCart();
    return;
  }

  pickInitialSelectedListing();
  renderCart();
  await hydrateCartListings();
  renderCart();
  await handleCheckoutReturn();
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  await loadCartPage();
});

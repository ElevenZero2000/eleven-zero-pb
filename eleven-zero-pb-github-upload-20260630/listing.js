const galleryNode = document.querySelector("[data-listing-gallery]");
const contentNode = document.querySelector("[data-listing-content]");
const storyNode = document.querySelector("[data-listing-story]");
const relatedNode = document.querySelector("[data-related-shell]");
const SHIPPING_DRAFT_STORAGE_KEY = "elevenZeroPbShippingAddressDraft";
const CART_DRAFT_STORAGE_KEY = "elevenZeroPbCartDraft";
const CART_ITEMS_STORAGE_KEY = "elevenZeroPbCartItems";

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
    statusMessage: "Add your delivery address below so we can estimate shipping before checkout.",
    statusTone: "neutral",
  };
}

const listingDetailState = {
  item: null,
  relatedItems: [],
  selectedImageIndex: 0,
  lightboxOpen: false,
  busy: false,
  statusMessage: "We’ll show checkout messages and seller setup updates here.",
  statusTone: "neutral",
  shipping: createDefaultShippingState(),
};

let listingLightboxElements = null;

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

function getShippingDraftSnapshot() {
  return {
    line1: String(listingDetailState.shipping?.line1 || "").trim(),
    line2: String(listingDetailState.shipping?.line2 || "").trim(),
    city: String(listingDetailState.shipping?.city || "").trim(),
    state: String(listingDetailState.shipping?.state || "").trim(),
    postalCode: String(listingDetailState.shipping?.postalCode || "").trim(),
    country: String(listingDetailState.shipping?.country || "US").trim() || "US",
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

function saveCartDraft(item) {
  if (!item) return;

  const cartItem = {
    listingId: item.id,
    title: `${item.brand || ""} ${item.model || ""}`.trim(),
    brand: item.brand || "",
    model: item.model || "",
    condition: item.condition || "",
    color: item.color || "",
    thicknessMm: item.thickness_mm || "",
    location: item.location || "",
    priceUsd: item.price_usd,
    image: item.images?.[0] || "",
    updatedAt: new Date().toISOString(),
  };
  const existingItems = readStorageJson(CART_ITEMS_STORAGE_KEY);
  const currentItems = Array.isArray(existingItems) ? existingItems : [];
  const nextItems = [
    cartItem,
    ...currentItems.filter((entry) => Number(entry?.listingId) !== Number(item.id)),
  ].slice(0, 12);

  writeStorageJson(CART_ITEMS_STORAGE_KEY, nextItems);
  writeStorageJson(CART_DRAFT_STORAGE_KEY, cartItem);
}

function formatThickness(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "";
  return `${numeric.toFixed(1).replace(/\.0$/, "")} mm`;
}

function formatPostedDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently added";

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatPostedAge(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently added";

  const deltaDays = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86400000));
  if (deltaDays <= 0) return "Today";
  if (deltaDays === 1) return "1 day ago";
  if (deltaDays < 7) return `${deltaDays} days ago`;
  if (deltaDays < 30) return `${Math.floor(deltaDays / 7)} week${Math.floor(deltaDays / 7) === 1 ? "" : "s"} ago`;
  return formatPostedDate(value);
}

function listingPhotoLabel(item) {
  const total = Array.isArray(item.images) ? item.images.length : 0;
  if (!total) return "No photos";
  if (total === 1) return "1 photo";
  return `${total} photos`;
}

function getListingImages(item = listingDetailState.item) {
  return item?.images?.length ? item.images : [];
}

function normalizeSelectedImageIndex(images, requestedIndex = listingDetailState.selectedImageIndex) {
  const total = images.length;
  if (!total) return 0;

  const numericIndex = Number(requestedIndex || 0);
  const normalizedIndex = Number.isFinite(numericIndex) ? numericIndex : 0;
  return ((normalizedIndex % total) + total) % total;
}

function ensureLightbox() {
  if (listingLightboxElements) return listingLightboxElements;

  const modal = document.createElement("div");
  modal.className = "listing-lightbox";
  modal.hidden = true;
  modal.innerHTML = `
    <div class="listing-lightbox-backdrop" data-lightbox-backdrop></div>
    <div class="listing-lightbox-dialog" role="dialog" aria-modal="true" aria-label="Listing photo viewer">
      <button class="listing-lightbox-close" type="button" data-lightbox-close aria-label="Close photo viewer">
        ×
      </button>
      <div class="listing-lightbox-stage">
        <button
          class="listing-lightbox-nav listing-lightbox-nav-prev"
          type="button"
          data-lightbox-prev
          aria-label="Previous photo"
        >
          ‹
        </button>
        <figure class="listing-lightbox-figure">
          <img class="listing-lightbox-image" src="" alt="" />
          <figcaption class="listing-lightbox-meta">
            <strong data-lightbox-counter></strong>
            <span data-lightbox-caption></span>
          </figcaption>
        </figure>
        <button
          class="listing-lightbox-nav listing-lightbox-nav-next"
          type="button"
          data-lightbox-next
          aria-label="Next photo"
        >
          ›
        </button>
      </div>
    </div>
  `;

  document.body.append(modal);

  const elements = {
    modal,
    image: modal.querySelector(".listing-lightbox-image"),
    counter: modal.querySelector("[data-lightbox-counter]"),
    caption: modal.querySelector("[data-lightbox-caption]"),
    prev: modal.querySelector("[data-lightbox-prev]"),
    next: modal.querySelector("[data-lightbox-next]"),
  };

  modal.querySelector("[data-lightbox-backdrop]")?.addEventListener("click", () => closeLightbox());
  modal.querySelector("[data-lightbox-close]")?.addEventListener("click", () => closeLightbox());
  elements.prev?.addEventListener("click", () => stepSelectedImage(-1, { keepLightboxOpen: true }));
  elements.next?.addEventListener("click", () => stepSelectedImage(1, { keepLightboxOpen: true }));

  listingLightboxElements = elements;
  return listingLightboxElements;
}

function renderLightbox(item = listingDetailState.item) {
  const elements = ensureLightbox();
  const images = getListingImages(item);

  if (!listingDetailState.lightboxOpen || !images.length || !item) {
    elements.modal.hidden = true;
    document.body.classList.remove("has-modal-open");
    return;
  }

  listingDetailState.selectedImageIndex = normalizeSelectedImageIndex(images);
  const selectedImage = images[listingDetailState.selectedImageIndex];
  const title = `${item.brand} ${item.model}`;

  elements.image.src = selectedImage;
  elements.image.alt = title;
  elements.counter.textContent = `Photo ${listingDetailState.selectedImageIndex + 1} of ${images.length}`;
  elements.caption.textContent = title;
  elements.prev.hidden = images.length <= 1;
  elements.next.hidden = images.length <= 1;
  elements.modal.hidden = false;
  document.body.classList.add("has-modal-open");
}

function openLightbox() {
  const images = getListingImages();
  if (!images.length) return;
  listingDetailState.lightboxOpen = true;
  renderLightbox(listingDetailState.item);
}

function closeLightbox() {
  listingDetailState.lightboxOpen = false;
  renderLightbox(listingDetailState.item);
}

function setSelectedImage(index, options = {}) {
  const item = listingDetailState.item;
  const images = getListingImages(item);
  if (!images.length || !item) return;

  listingDetailState.selectedImageIndex = normalizeSelectedImageIndex(images, index);
  if (options.openLightbox) {
    listingDetailState.lightboxOpen = true;
  }
  renderGallery(item);
  renderLightbox(item);
}

function stepSelectedImage(delta, options = {}) {
  const item = listingDetailState.item;
  const images = getListingImages(item);
  if (!images.length || !item) return;

  const nextIndex = normalizeSelectedImageIndex(
    images,
    listingDetailState.selectedImageIndex + Number(delta || 0)
  );

  listingDetailState.selectedImageIndex = nextIndex;
  if (options.keepLightboxOpen) {
    listingDetailState.lightboxOpen = true;
  }
  renderGallery(item);
  renderLightbox(item);
}

function handleListingKeyboard(event) {
  if (!listingDetailState.lightboxOpen) return;

  if (event.key === "Escape") {
    event.preventDefault();
    closeLightbox();
    return;
  }

  if (event.key === "ArrowRight") {
    event.preventDefault();
    stepSelectedImage(1, { keepLightboxOpen: true });
    return;
  }

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    stepSelectedImage(-1, { keepLightboxOpen: true });
  }
}

function currentListingUrl() {
  return window.location.href;
}

function getListingIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("id") || "";
  return /^\d+$/.test(raw) ? Number(raw) : 0;
}

function getListingActionState(item) {
  const currentUserId = Number(ElevenZeroApp.session?.user?.id || 0);
  const sellerUserId = Number(item.seller_user_id || 0);
  const isOwner = currentUserId && sellerUserId && currentUserId === sellerUserId;
  const approvalStatus = item.approval_status || "approved";
  const saleStatus = item.sale_status || "available";

  if (saleStatus === "pending") {
    return {
      action: "disabled",
      buttonLabel: "Sale pending",
      statusLabel: "Sale pending",
      reason: "A buyer has purchased this paddle and the order is being finalized.",
      tone: "pending",
    };
  }

  if (saleStatus === "sold") {
    return {
      action: "disabled",
      buttonLabel: "Sold",
      statusLabel: "Sold",
      reason: "This paddle is no longer available.",
      tone: "neutral",
    };
  }

  if (isOwner) {
    if (approvalStatus === "pending") {
      return {
        action: "disabled",
        buttonLabel: "Under review",
        statusLabel: "Pending review",
        reason: "This listing is waiting for Eleven Zero PB approval before it appears in the public shop.",
        tone: "pending",
      };
    }

    if (approvalStatus === "rejected") {
      return {
        action: "disabled",
        buttonLabel: "Needs changes",
        statusLabel: "Needs changes",
        reason: "This listing is paused until the seller updates it and resubmits it for review.",
        tone: "neutral",
      };
    }

    return {
      action: "disabled",
      buttonLabel: "Your listing",
      statusLabel: "Seller view",
      reason: "You’re looking at your own listing.",
      tone: "neutral",
    };
  }

  if (item.checkout_available) {
    if (ElevenZeroApp.session?.authenticated) {
      return {
        action: "checkout",
        buttonLabel: "Buy with Stripe",
        statusLabel: "Secure checkout ready",
        reason: "This listing is eligible for secure buyer checkout.",
        tone: "ready",
      };
    }

    return {
      action: "auth",
      buttonLabel: "Sign in to buy",
      statusLabel: "Secure checkout ready",
      reason: "Sign in first and we’ll send you straight into checkout.",
      tone: "ready",
    };
  }

  if (!ElevenZeroApp.config.stripeConfigured) {
    return {
      action: "disabled",
      buttonLabel: "Checkout soon",
      statusLabel: "Platform setup",
      reason: item.checkout_reason || "Stripe is still being connected for live marketplace checkout.",
      tone: "neutral",
    };
  }

  return {
    action: "disabled",
    buttonLabel: "Seller setup pending",
    statusLabel: item.seller_has_connected_account ? "Seller setup pending" : "Payouts not connected",
    reason:
      item.checkout_reason ||
      "This seller still needs to complete payout setup before the purchase flow can turn on.",
    tone: "pending",
  };
}

function getProductCartEntryState(item) {
  const currentUserId = Number(ElevenZeroApp.session?.user?.id || 0);
  const sellerUserId = Number(item.seller_user_id || 0);
  const isOwner = currentUserId && sellerUserId && currentUserId === sellerUserId;
  const approvalStatus = item.approval_status || "approved";
  const saleStatus = item.sale_status || "available";

  if (saleStatus === "pending") {
    return {
      action: "disabled",
      buttonLabel: "Sale pending",
      statusLabel: "Sale pending",
      reason: "A buyer has purchased this paddle and the order is being finalized.",
      tone: "pending",
    };
  }

  if (saleStatus === "sold") {
    return {
      action: "disabled",
      buttonLabel: "Sold",
      statusLabel: "Sold",
      reason: "This paddle is no longer available.",
      tone: "neutral",
    };
  }

  if (isOwner) {
    return {
      action: "disabled",
      buttonLabel: "Your listing",
      statusLabel: "Seller view",
      reason: "You’re looking at your own listing.",
      tone: "neutral",
    };
  }

  if (approvalStatus === "pending") {
    return {
      action: "disabled",
      buttonLabel: "Under review",
      statusLabel: "Pending review",
      reason: "This listing is waiting for Eleven Zero PB approval before it can be purchased.",
      tone: "pending",
    };
  }

  if (approvalStatus === "rejected") {
    return {
      action: "disabled",
      buttonLabel: "Needs changes",
      statusLabel: "Needs changes",
      reason: "This listing is paused until the seller updates it and resubmits it for review.",
      tone: "neutral",
    };
  }

  return {
    action: "cart",
    buttonLabel: "Add to cart",
    statusLabel: "Ready to buy",
    reason: "Add this paddle to your cart, then review shipping before secure checkout.",
    tone: "ready",
  };
}

function setDetailStatus(message, tone = "neutral") {
  listingDetailState.statusMessage = message;
  listingDetailState.statusTone = tone;
  const statusNode = contentNode?.querySelector("[data-detail-status]");
  if (!statusNode) return;
  ElevenZeroApp.setStatus(statusNode, message, tone);
}

function setShippingStatus(message, tone = "neutral") {
  listingDetailState.shipping.statusMessage = message;
  listingDetailState.shipping.statusTone = tone;
  const statusNode = storyNode?.querySelector("[data-shipping-status]");
  if (!statusNode) return;
  ElevenZeroApp.setStatus(statusNode, message, tone);
}

function formatMoneyFromCents(cents) {
  return ElevenZeroApp.formatMoney(Number(cents || 0) / 100);
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
    originZip: shipping.originZip || "",
    weightOz: shipping.weightOz || null,
    lengthIn: shipping.lengthIn || null,
    widthIn: shipping.widthIn || null,
    heightIn: shipping.heightIn || null,
    explanation:
      shipping.explanation ||
      (mode === "free"
        ? "Seller is covering shipping on this listing."
        : mode === "flat"
          ? "Seller set one shipping amount for every U.S. destination."
          : "Enter your delivery address below and we’ll estimate the delivered total before checkout."),
  };
}

function getCartActionState(item) {
  const baseActionState = getListingActionState(item);
  const shippingPolicy = getShippingPolicy(item);
  const shippingQuote = listingDetailState.shipping.quote;
  const shippingEstimatedTotal = shippingQuote ? getEstimatedTotalCents(item) : 0;

  if ((baseActionState.action === "checkout" || baseActionState.action === "auth") && !shippingQuote) {
    return {
      ...baseActionState,
      action: "estimate-needed",
      buttonLabel:
        shippingPolicy.mode === "calculated" ? "Estimate shipping first" : "Confirm shipping first",
      statusLabel: "Cart ready",
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
      } to ${shippingQuote.destinationSummary}. ${
        shippingQuote.isEstimate ? "Estimated" : "Delivered"
      } total ${formatMoneyFromCents(shippingEstimatedTotal)}.`,
      tone: "ready",
    };
  }

  if (baseActionState.action === "auth" && shippingQuote) {
    return {
      ...baseActionState,
      buttonLabel: "Sign in to checkout",
      reason: `${formatMoneyFromCents(
        shippingQuote.amountCents
      )} ${shippingQuote.isEstimate ? "estimated shipping" : "shipping"} to ${
        shippingQuote.destinationSummary
      }. Sign in to continue to secure checkout.`,
    };
  }

  return baseActionState;
}

function getShippingAddressPayload() {
  const shipping = listingDetailState.shipping || createDefaultShippingState();
  return {
    line1: shipping.line1,
    line2: shipping.line2,
    city: shipping.city,
    state: shipping.state,
    postalCode: shipping.postalCode,
    country: shipping.country || "US",
  };
}

function shippingQuoteReady() {
  return Boolean(listingDetailState.shipping?.quote);
}

function getEstimatedTotalCents(item) {
  const baseCents = Math.max(0, Number(item?.price_usd || 0)) * 100;
  return baseCents + Number(listingDetailState.shipping?.quote?.amountCents || 0);
}

function scrollToCartPanel() {
  const target = document.getElementById("cart") || document.getElementById("shipping");
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToShippingPanel() {
  scrollToCartPanel();
}

function buildRelatedListings(item, allItems) {
  return [...(allItems || [])]
    .filter((candidate) => Number(candidate.id) !== Number(item.id))
    .map((candidate) => {
      let score = 0;
      if (candidate.brand === item.brand) score += 5;
      if (candidate.category === item.category) score += 4;
      if (candidate.condition === item.condition) score += 2;
      if (candidate.color && candidate.color === item.color) score += 1;
      const priceGap = Math.abs(Number(candidate.price_usd || 0) - Number(item.price_usd || 0));
      score += Math.max(0, 4 - Math.min(4, Math.floor(priceGap / 40)));
      return { score, candidate };
    })
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      return new Date(right.candidate.created_at).getTime() - new Date(left.candidate.created_at).getTime();
    })
    .slice(0, 3)
    .map((entry) => entry.candidate);
}

function renderGallery(item) {
  if (!galleryNode) return;

  const images = getListingImages(item);
  listingDetailState.selectedImageIndex = normalizeSelectedImageIndex(images);
  const selectedImage = images[listingDetailState.selectedImageIndex] || images[0] || "";

  if (!selectedImage) {
    galleryNode.innerHTML = `
      <div class="listing-detail-gallery-empty">
        This listing doesn’t have photos yet, but the full specs are still available below.
      </div>
    `;
    return;
  }

  const thumbnails = images
    .map(
      (image, index) => `
        <button
          class="listing-thumb${index === listingDetailState.selectedImageIndex ? " is-active" : ""}"
          type="button"
          data-thumb-index="${index}"
        >
          <img src="${ElevenZeroApp.escapeHtml(image)}" alt="Listing photo ${index + 1}" />
        </button>
      `
    )
    .join("");

  galleryNode.innerHTML = `
    <div class="listing-gallery-toolbar">
      <span class="listing-gallery-count">
        ${ElevenZeroApp.escapeHtml(`Photo ${listingDetailState.selectedImageIndex + 1} of ${images.length}`)}
      </span>
      <button class="text-link-button listing-gallery-open" type="button" data-open-lightbox>
        Open full photo
      </button>
    </div>
    <div class="listing-main-photo">
      <button class="listing-main-photo-button" type="button" data-open-lightbox>
        <img
          src="${ElevenZeroApp.escapeHtml(selectedImage)}"
          alt="${ElevenZeroApp.escapeHtml(`${item.brand} ${item.model}`)}"
        />
        <span class="listing-main-photo-hint">Tap to enlarge</span>
      </button>
      ${
        images.length > 1
          ? `
            <button class="listing-gallery-nav listing-gallery-nav-prev" type="button" data-gallery-prev aria-label="Previous photo">
              ‹
            </button>
            <button class="listing-gallery-nav listing-gallery-nav-next" type="button" data-gallery-next aria-label="Next photo">
              ›
            </button>
          `
          : ""
      }
    </div>
    <div class="listing-thumb-row">
      ${thumbnails}
    </div>
  `;

  galleryNode.querySelectorAll("[data-open-lightbox]").forEach((button) => {
    button.addEventListener("click", () => openLightbox());
  });

  galleryNode.querySelector("[data-gallery-prev]")?.addEventListener("click", () => {
    stepSelectedImage(-1);
  });

  galleryNode.querySelector("[data-gallery-next]")?.addEventListener("click", () => {
    stepSelectedImage(1);
  });

  galleryNode.querySelectorAll("[data-thumb-index]").forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedImage(Number(button.dataset.thumbIndex || 0));
    });
  });
}

function renderContent(item) {
  if (!contentNode) return;

  const productActionState = getProductCartEntryState(item);
  const thickness = formatThickness(item.thickness_mm);
  const canOpenCart = productActionState.action === "cart";
  const busyLabel = listingDetailState.busy ? "Opening cart..." : productActionState.buttonLabel;
  const productNote = String(item.notes || "").trim();
  const needsBuyerNote = productActionState.tone !== "ready";

  contentNode.innerHTML = `
    <div class="listing-product-heading">
      <p class="eyebrow">Marketplace paddle</p>
      <p class="product-brand">${ElevenZeroApp.escapeHtml(item.brand)}</p>
      <h1>${ElevenZeroApp.escapeHtml(item.model)}</h1>
    </div>
    <div class="listing-simple-purchase">
      <div class="listing-detail-price-block listing-detail-price-block-simple">
        <span class="listing-detail-price">${ElevenZeroApp.escapeHtml(ElevenZeroApp.formatMoney(item.price_usd))}</span>
        <span class="listing-detail-total-note">Shipping calculated in cart</span>
      </div>
      <button
        class="${canOpenCart ? "button button-dark" : "button button-secondary"} listing-buy-button"
        type="button"
        data-detail-buy
        data-buy-action="${ElevenZeroApp.escapeHtml(productActionState.action)}"
        ${!canOpenCart || listingDetailState.busy ? "disabled" : ""}
      >
        ${ElevenZeroApp.escapeHtml(busyLabel)}
      </button>
    </div>
    ${
      needsBuyerNote
        ? `
          <div class="listing-product-buy-note">
            <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(
              productActionState.tone
            )}">${ElevenZeroApp.escapeHtml(productActionState.statusLabel)}</span>
            <p>${ElevenZeroApp.escapeHtml(productActionState.reason)}</p>
          </div>
        `
        : ""
    }
    <div class="listing-product-summary-grid" aria-label="Paddle summary">
      <article>
        <span>Condition</span>
        <strong>${ElevenZeroApp.escapeHtml(item.condition || "Not listed")}</strong>
      </article>
      <article>
        <span>Play style</span>
        <strong>${ElevenZeroApp.escapeHtml(item.category || "Not listed")}</strong>
      </article>
      <article>
        <span>Thickness</span>
        <strong>${ElevenZeroApp.escapeHtml(thickness || "Not listed")}</strong>
      </article>
    </div>
    ${
      productNote
        ? `
          <section class="listing-product-about" aria-label="About this paddle">
            <strong>About this paddle</strong>
            <p class="listing-detail-copy">${ElevenZeroApp.escapeHtml(productNote)}</p>
          </section>
        `
        : ""
    }
    <p class="listing-product-location">
      Ships from <strong>${ElevenZeroApp.escapeHtml(item.location || "location not listed")}</strong>
    </p>
    ${
      listingDetailState.statusTone === "neutral"
        ? ""
        : `
          <div class="seller-status listing-detail-status" data-detail-status>
            ${ElevenZeroApp.escapeHtml(listingDetailState.statusMessage)}
          </div>
        `
    }
  `;

  ElevenZeroApp.setStatus(
    contentNode.querySelector("[data-detail-status]"),
    listingDetailState.statusMessage,
    listingDetailState.statusTone
  );

  contentNode.querySelector("[data-detail-buy]")?.addEventListener("click", async () => {
    const action = contentNode.querySelector("[data-detail-buy]")?.dataset.buyAction || "disabled";
    if (action === "disabled") return;

    if (action === "cart") {
      saveCartDraft(item);
      listingDetailState.busy = true;
      listingDetailState.statusMessage = "Added to cart. Opening your cart now.";
      listingDetailState.statusTone = "success";
      renderContent(item);
      window.setTimeout(() => {
        window.location.href = `./cart.html?listingId=${encodeURIComponent(item.id)}`;
      }, 300);
      return;
    }

    setDetailStatus(productActionState.reason, productActionState.tone);
  });

  contentNode.querySelector("[data-copy-listing-link]")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(currentListingUrl());
      setDetailStatus("Listing link copied. You can paste it anywhere to share this paddle.", "success");
    } catch {
      setDetailStatus("Copy did not work in this browser. You can still copy the page URL from the address bar.", "warning");
    }
  });
}

function renderStory(item) {
  if (!storyNode) return;

  const thickness = formatThickness(item.thickness_mm);
  const sellerName = item.seller_name || "Community seller";

  storyNode.innerHTML = `
    <article class="listing-detail-panel listing-detail-panel-soft listing-simple-details" id="details">
      <p class="eyebrow">Paddle info</p>
      <h2>Paddle details</h2>
      <div class="listing-detail-bullets">
        <div>
          <strong>Seller</strong>
          <span>${ElevenZeroApp.escapeHtml(sellerName)}</span>
        </div>
        <div>
          <strong>Ships from</strong>
          <span>${ElevenZeroApp.escapeHtml(item.location || "Not listed")}</span>
        </div>
        <div>
          <strong>Color</strong>
          <span>${ElevenZeroApp.escapeHtml(item.color || "Not listed")}</span>
        </div>
        <div>
          <strong>Thickness</strong>
          <span>${ElevenZeroApp.escapeHtml(thickness || "Not listed")}</span>
        </div>
        <div>
          <strong>Play style</strong>
          <span>${ElevenZeroApp.escapeHtml(item.category || "Not listed")}</span>
        </div>
        <div>
          <strong>Posted</strong>
          <span>${ElevenZeroApp.escapeHtml(formatPostedAge(item.created_at))}</span>
        </div>
      </div>
    </article>

    <article class="listing-detail-panel listing-review-panel" id="reviews">
      <p class="eyebrow">Buyer feedback</p>
      <h2>Reviews</h2>
      <div class="listing-review-empty">
        <strong>No reviews yet</strong>
        <span>Verified buyer reviews will appear here after completed purchases.</span>
      </div>
    </article>
  `;
}

function renderRelatedListings() {
  if (!relatedNode) return;

  relatedNode.hidden = true;
  relatedNode.innerHTML = "";
}

function renderNotFound() {
  closeLightbox();

  if (galleryNode) {
    galleryNode.innerHTML = `
      <div class="listing-detail-gallery-empty">
        We couldn’t find that listing anymore.
      </div>
    `;
  }

  if (contentNode) {
    contentNode.innerHTML = `
      <p class="eyebrow">Marketplace listing</p>
      <h1>Listing not found</h1>
      <p class="listing-detail-copy">
        This listing may have been removed, or the link is incomplete.
      </p>
      <a class="button button-dark" href="./shop.html">Return to marketplace</a>
    `;
  }

  if (storyNode) {
    storyNode.innerHTML = "";
  }

  if (relatedNode) {
    relatedNode.hidden = true;
    relatedNode.innerHTML = "";
  }
}

function updateShippingDraftFromForm(form) {
  const formData = new FormData(form);
  listingDetailState.shipping = {
    ...listingDetailState.shipping,
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
  const form = storyNode?.querySelector("[data-shipping-form]");
  if (!form) return;

  form.addEventListener("submit", handleShippingQuoteSubmit);

  form.querySelectorAll("input").forEach((input) => {
    const handleDraftUpdate = () => {
      updateShippingDraftFromForm(form);

      if (!listingDetailState.shipping.quote || !listingDetailState.item) {
        return;
      }

      listingDetailState.shipping.quote = null;
      listingDetailState.shipping.statusMessage =
        "Address updated. Estimate shipping again so the final total stays accurate.";
      listingDetailState.shipping.statusTone = "warning";
      renderContent(listingDetailState.item);
      renderStory(listingDetailState.item);
    };

    input.addEventListener("input", handleDraftUpdate);
    input.addEventListener("change", handleDraftUpdate);
  });
}

async function handleShippingQuoteSubmit(event) {
  event.preventDefault();
  if (!listingDetailState.item) return;

  const form = event.currentTarget;
  updateShippingDraftFromForm(form);
  listingDetailState.shipping.busy = true;
  renderStory(listingDetailState.item);

  try {
    const response = await ElevenZeroApp.request("/api/shipping/quote", {
      method: "POST",
      body: {
        listingId: listingDetailState.item.id,
        shippingAddress: getShippingAddressPayload(),
      },
    });

    listingDetailState.shipping.quote = response.quote || null;
    setShippingStatus(
      response.message ||
        "Shipping estimate is ready. Your delivered total will carry into checkout.",
      "success"
    );
    renderContent(listingDetailState.item);
    renderStory(listingDetailState.item);
  } catch (error) {
    listingDetailState.shipping.quote = null;
    setShippingStatus(error.message, "error");
    renderContent(listingDetailState.item);
    renderStory(listingDetailState.item);
  } finally {
    listingDetailState.shipping.busy = false;
    renderStory(listingDetailState.item);
  }
}

async function handleBuyListing(listingId) {
  if (!listingDetailState.item) {
    return;
  }

  if (!shippingQuoteReady()) {
    setDetailStatus("Add your delivery address below and estimate shipping first.", "warning");
    scrollToShippingPanel();
    return;
  }

  listingDetailState.busy = true;
  renderContent(listingDetailState.item);

  try {
    const response = await ElevenZeroApp.request("/api/checkout/create-session", {
      method: "POST",
      body: {
        listingId,
        shippingAddress: getShippingAddressPayload(),
      },
    });

    setDetailStatus(
      `Opening secure checkout for ${response.listing?.title || "this listing"}.`,
      "success"
    );
    window.location.href = response.checkoutUrl;
  } catch (error) {
    setDetailStatus(error.message, "error");
  } finally {
    listingDetailState.busy = false;
    renderContent(listingDetailState.item);
  }
}

async function loadListingDetail() {
  const listingId = getListingIdFromUrl();
  if (!listingId) {
    renderNotFound();
    return;
  }

  try {
    const response = await ElevenZeroApp.request(`/api/listings/${listingId}`);
    const item = response.item;
    if (!item) {
      renderNotFound();
      return;
    }

    listingDetailState.item = item;
    listingDetailState.relatedItems = [];
    listingDetailState.selectedImageIndex = 0;
    listingDetailState.lightboxOpen = false;
    listingDetailState.shipping = restoreShippingDraftState();
    document.title = `${item.brand} ${item.model} · Eleven Zero PB`;
    renderGallery(item);
    renderLightbox(item);
    renderContent(item);
    renderStory(item);
    renderRelatedListings();
    if (window.location.hash === "#shipping" || window.location.hash === "#cart") {
      window.setTimeout(() => scrollToCartPanel(), 120);
    }
  } catch {
    renderNotFound();
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  document.addEventListener("keydown", handleListingKeyboard);
  await ElevenZeroApp.boot;
  await loadListingDetail();
});

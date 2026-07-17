const galleryNode = document.querySelector("[data-listing-gallery]");
const contentNode = document.querySelector("[data-listing-content]");
const storyNode = document.querySelector("[data-listing-story]");
const relatedNode = document.querySelector("[data-related-shell]");
const SHIPPING_DRAFT_STORAGE_KEY = "elevenZeroPbShippingAddressDraft";
const CART_DRAFT_STORAGE_KEY = "elevenZeroPbCartDraft";

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

  writeStorageJson(CART_DRAFT_STORAGE_KEY, {
    listingId: item.id,
    title: `${item.brand || ""} ${item.model || ""}`.trim(),
    priceUsd: item.price_usd,
    image: item.images?.[0] || "",
    updatedAt: new Date().toISOString(),
  });
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
    buttonLabel: "Buy now",
    statusLabel: "Ready to buy",
    reason: "Add this paddle to your cart, then confirm shipping before secure checkout.",
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

  const shippingPolicy = getShippingPolicy(item);
  const shippingQuote = listingDetailState.shipping.quote;
  const shippingEstimatedTotal = shippingQuote ? getEstimatedTotalCents(item) : 0;
  const productActionState = getProductCartEntryState(item);

  const sellerName = item.seller_name || "Community seller";
  const thickness = formatThickness(item.thickness_mm);
  const specPills = [
    item.color ? `<span>${ElevenZeroApp.escapeHtml(item.color)}</span>` : "",
    thickness ? `<span>${ElevenZeroApp.escapeHtml(thickness)}</span>` : "",
    `<span>${ElevenZeroApp.escapeHtml(item.condition)}</span>`,
    `<span>${ElevenZeroApp.escapeHtml(item.category)}</span>`,
  ]
    .filter(Boolean)
    .join("");

  const canOpenCart = productActionState.action === "cart";
  const busyLabel = listingDetailState.busy
    ? "Opening checkout..."
    : productActionState.buttonLabel;
  const totalNote = shippingQuote
    ? `${shippingQuote.isEstimate ? "Estimated" : "Delivered"} total ${formatMoneyFromCents(
        shippingEstimatedTotal
      )}`
    : shippingPolicy.mode === "calculated"
      ? "Enter your delivery address below to estimate shipping."
      : "Enter your delivery address below to confirm the delivered total.";

  contentNode.innerHTML = `
    <p class="eyebrow">Marketplace listing</p>
    <div class="listing-detail-head">
      <div>
        <p class="product-brand">${ElevenZeroApp.escapeHtml(item.brand)}</p>
        <h1>${ElevenZeroApp.escapeHtml(item.model)}</h1>
      </div>
      <div class="listing-detail-price-block">
        <span class="listing-detail-price">${ElevenZeroApp.formatMoney(item.price_usd)}</span>
        <span class="listing-detail-total-note${shippingQuote ? "" : " is-muted"}">
          ${ElevenZeroApp.escapeHtml(totalNote)}
        </span>
      </div>
    </div>
    <div class="listing-detail-specs">${specPills}</div>
    <p class="listing-detail-copy listing-product-note">${ElevenZeroApp.escapeHtml(item.notes)}</p>
    <div class="listing-detail-facts">
      <article>
        <strong>Condition</strong>
        <span>${ElevenZeroApp.escapeHtml(item.condition)}</span>
      </article>
      <article>
        <strong>Thickness</strong>
        <span>${ElevenZeroApp.escapeHtml(thickness || "Not listed")}</span>
      </article>
      <article>
        <strong>Ships from</strong>
        <span>${ElevenZeroApp.escapeHtml(item.location)}</span>
      </article>
      <article>
        <strong>Seller</strong>
        <span>${ElevenZeroApp.escapeHtml(sellerName)}</span>
      </article>
    </div>
    <div class="listing-purchase-row listing-purchase-row-detail listing-product-buy-box">
      <div class="listing-purchase-copy">
        <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(
          productActionState.tone
        )}">${ElevenZeroApp.escapeHtml(productActionState.statusLabel)}</span>
        <p class="listing-status-copy">${ElevenZeroApp.escapeHtml(productActionState.reason)}</p>
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
    <div class="listing-detail-actions-bar listing-detail-actions-subtle">
      <a class="text-link" href="./shop.html">Back to shop</a>
      <button class="text-link-button" type="button" data-copy-listing-link>
        Copy listing link
      </button>
    </div>
    <div class="seller-status listing-detail-status" data-detail-status>
      ${ElevenZeroApp.escapeHtml(listingDetailState.statusMessage)}
    </div>
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
      setDetailStatus("Added to cart. Review shipping and checkout below.", "success");
      scrollToCartPanel();
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
  const actionState = getCartActionState(item);
  const shippingPolicy = getShippingPolicy(item);
  const shipping = listingDetailState.shipping;
  const quote = shipping.quote;
  const estimatedTotalCents = quote ? getEstimatedTotalCents(item) : 0;
  const estimateButtonLabel = shipping.busy
    ? shippingPolicy.mode === "calculated"
      ? "Calculating..."
      : "Confirming..."
    : shippingPolicy.mode === "calculated"
      ? "Estimate shipping"
      : "Confirm shipping";
  const shippingIntro =
    shippingPolicy.mode === "free"
      ? "This seller offers free shipping. Confirm the buyer address before checkout."
      : shippingPolicy.mode === "flat"
        ? "This seller uses one flat shipping fee. Confirm the buyer address before checkout."
        : "Enter the buyer address and we’ll estimate U.S. shipping before checkout.";
  const shippingLine = quote
    ? formatMoneyFromCents(quote.amountCents)
    : shippingPolicy.mode === "free"
      ? "$0"
      : shippingPolicy.mode === "flat"
        ? shippingPolicy.label
        : "Estimate needed";
  const totalLine = quote ? formatMoneyFromCents(estimatedTotalCents) : "Calculated in cart";
  const cartButtonDisabled =
    actionState.action === "disabled" || listingDetailState.busy || shipping.busy;
  const cartButtonLabel = listingDetailState.busy ? "Opening checkout..." : actionState.buttonLabel;
  const shippingMeta = [
    shippingPolicy.originZip ? `Origin ZIP ${shippingPolicy.originZip}` : "",
    shippingPolicy.weightOz ? `${Number(shippingPolicy.weightOz).toFixed(1).replace(/\.0$/, "")} oz packed weight` : "",
    shippingPolicy.lengthIn && shippingPolicy.widthIn && shippingPolicy.heightIn
      ? `${Number(shippingPolicy.lengthIn).toFixed(1).replace(/\.0$/, "")} × ${Number(
          shippingPolicy.widthIn
        ).toFixed(1).replace(/\.0$/, "")} × ${Number(shippingPolicy.heightIn).toFixed(1).replace(/\.0$/, "")} in`
      : "",
  ].filter(Boolean);
  const shippingNote = shippingPolicy.note || "";

  storyNode.innerHTML = `
    <article class="listing-detail-panel listing-detail-panel-wide listing-shipping-panel listing-cart-panel" id="cart">
      <div class="listing-cart-head">
        <div>
          <p class="eyebrow">Your cart</p>
          <h2>Review before checkout.</h2>
        </div>
        <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(
          actionState.tone
        )}">${ElevenZeroApp.escapeHtml(actionState.statusLabel)}</span>
      </div>

      <div class="listing-cart-summary">
        <article class="listing-cart-item">
          <div>
            <strong>${ElevenZeroApp.escapeHtml(item.brand)} ${ElevenZeroApp.escapeHtml(item.model)}</strong>
            <span>${ElevenZeroApp.escapeHtml(
              [item.condition, thickness, item.color].filter(Boolean).join(" · ")
            )}</span>
          </div>
          <strong>${ElevenZeroApp.escapeHtml(ElevenZeroApp.formatMoney(item.price_usd))}</strong>
        </article>
        <div class="listing-cart-row">
          <span>Subtotal</span>
          <strong>${ElevenZeroApp.escapeHtml(ElevenZeroApp.formatMoney(item.price_usd))}</strong>
        </div>
        <div class="listing-cart-row">
          <span>Shipping</span>
          <strong>${ElevenZeroApp.escapeHtml(shippingLine)}</strong>
        </div>
        <div class="listing-cart-row listing-cart-total">
          <span>Total</span>
          <strong>${ElevenZeroApp.escapeHtml(totalLine)}</strong>
        </div>
      </div>

      <p class="listing-cart-intro">${ElevenZeroApp.escapeHtml(shippingIntro)}</p>
      <div class="listing-shipping-policy">
        <div>
          <strong>Seller shipping setup</strong>
          <span>${ElevenZeroApp.escapeHtml(shippingPolicy.label)}</span>
        </div>
        <p>${ElevenZeroApp.escapeHtml(shippingPolicy.explanation)}</p>
        ${
          shippingMeta.length || shippingNote
            ? `
              <div class="listing-shipping-policy-meta">
                ${shippingMeta.map((itemLabel) => `<span>${ElevenZeroApp.escapeHtml(itemLabel)}</span>`).join("")}
                ${shippingNote ? `<span>${ElevenZeroApp.escapeHtml(shippingNote)}</span>` : ""}
              </div>
            `
            : ""
        }
      </div>
      <form class="listing-shipping-form" data-shipping-form>
        <div class="listing-shipping-grid">
          <label>
            <span>Street address</span>
            <input
              type="text"
              name="line1"
              placeholder="123 Main Street"
              value="${ElevenZeroApp.escapeHtml(shipping.line1)}"
            />
          </label>
          <label>
            <span>Apartment, suite, etc. (optional)</span>
            <input
              type="text"
              name="line2"
              placeholder="Suite 4B"
              value="${ElevenZeroApp.escapeHtml(shipping.line2)}"
            />
          </label>
          <label>
            <span>City</span>
            <input
              type="text"
              name="city"
              placeholder="Miami"
              value="${ElevenZeroApp.escapeHtml(shipping.city)}"
            />
          </label>
          <label>
            <span>State</span>
            <input
              type="text"
              name="state"
              placeholder="FL"
              value="${ElevenZeroApp.escapeHtml(shipping.state)}"
            />
          </label>
          <label>
            <span>ZIP code</span>
            <input
              type="text"
              name="postalCode"
              inputmode="numeric"
              placeholder="33101"
              value="${ElevenZeroApp.escapeHtml(shipping.postalCode)}"
            />
          </label>
          <label>
            <span>Country</span>
            <input type="text" name="country" value="US" readonly />
          </label>
        </div>
        <div class="listing-shipping-actions">
          <button class="button button-dark" type="submit" ${shipping.busy ? "disabled" : ""}>
            ${ElevenZeroApp.escapeHtml(estimateButtonLabel)}
          </button>
          <span class="listing-shipping-help">
            ${
              shippingPolicy.mode === "calculated"
                ? "Carrier-ready estimates are using the seller shipping setup right now."
                : "This shipping policy will carry into checkout after you confirm the address."
            }
          </span>
        </div>
        <div class="seller-status listing-detail-status" aria-live="polite" data-shipping-status>
          ${ElevenZeroApp.escapeHtml(shipping.statusMessage)}
        </div>
        ${
          quote
            ? `
              <div class="listing-shipping-quote-grid">
                <article>
                  <strong>${quote.isEstimate ? "Estimated shipping" : "Shipping"}</strong>
                  <span>${ElevenZeroApp.escapeHtml(formatMoneyFromCents(quote.amountCents))}</span>
                </article>
                <article>
                  <strong>Destination</strong>
                  <span>${ElevenZeroApp.escapeHtml(quote.destinationSummary)}</span>
                </article>
                <article>
                  <strong>Service level</strong>
                  <span>${ElevenZeroApp.escapeHtml(quote.serviceLevel)}</span>
                </article>
                <article>
                  <strong>${quote.isEstimate ? "Estimated total" : "Delivered total"}</strong>
                  <span>${ElevenZeroApp.escapeHtml(
                    formatMoneyFromCents(quote.estimatedTotalCents)
                  )}</span>
                </article>
              </div>
            `
            : ""
        }
      </form>

      <div class="listing-cart-checkout">
        <button
          class="${actionState.action === "checkout" || actionState.action === "auth" ? "button button-dark" : "button button-secondary"} listing-buy-button"
          type="button"
          data-cart-checkout
          data-cart-action="${ElevenZeroApp.escapeHtml(actionState.action)}"
          ${cartButtonDisabled ? "disabled" : ""}
        >
          ${ElevenZeroApp.escapeHtml(cartButtonLabel)}
        </button>
        <p>${ElevenZeroApp.escapeHtml(actionState.reason)}</p>
      </div>
    </article>

    <article class="listing-detail-panel listing-review-panel" id="reviews">
      <p class="eyebrow">Reviews</p>
      <h2>Buyer reviews</h2>
      <div class="listing-review-empty">
        <strong>No reviews yet</strong>
        <span>Reviews will appear here after buyers complete purchases through Eleven Zero PB.</span>
      </div>
      <p class="listing-review-note">
        For now, use the photos, condition, seller notes, and shipping details to decide if this paddle is right for you.
      </p>
    </article>

    <article class="listing-detail-panel listing-detail-panel-soft">
      <p class="eyebrow">Paddle info</p>
      <h2>Details at a glance</h2>
      <div class="listing-detail-bullets">
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
  `;

  ElevenZeroApp.setStatus(
    storyNode.querySelector("[data-shipping-status]"),
    shipping.statusMessage,
    shipping.statusTone
  );
  bindShippingForm();

  storyNode.querySelector("[data-cart-checkout]")?.addEventListener("click", () => {
    const cartAction = storyNode.querySelector("[data-cart-checkout]")?.dataset.cartAction || "disabled";

    if (cartAction === "estimate-needed") {
      setShippingStatus("Add your delivery address, then estimate shipping first.", "warning");
      storyNode.querySelector("[data-shipping-form] input[name='line1']")?.focus();
      return;
    }

    if (cartAction === "auth") {
      setDetailStatus("Please sign in first so we can open secure checkout for this listing.", "warning");
      window.setTimeout(() => {
        ElevenZeroApp.redirectToAuth(`${window.location.pathname}${window.location.search}#cart`);
      }, 700);
      return;
    }

    if (cartAction === "checkout") {
      handleBuyListing(item.id);
      return;
    }

    setShippingStatus(actionState.reason, actionState.tone);
  });
}

function renderRelatedListings(item) {
  if (!relatedNode) return;

  if (!listingDetailState.relatedItems.length) {
    relatedNode.innerHTML = `
      <article class="listing-detail-panel">
        <p class="eyebrow">You may also like</p>
        <h2>More listings are coming soon.</h2>
        <p>As more paddles go live, this page will suggest similar options here.</p>
      </article>
    `;
    return;
  }

  relatedNode.innerHTML = `
    <article class="listing-detail-panel">
      <div class="listing-related-head">
        <div>
          <p class="eyebrow">You may also like</p>
          <h2>Similar paddles from the marketplace</h2>
        </div>
        <p class="listing-related-copy">
          Buyers looking at ${ElevenZeroApp.escapeHtml(item.brand)} ${ElevenZeroApp.escapeHtml(
            item.model
          )} often want nearby prices, matching play styles, or the same brand family.
        </p>
      </div>

      <div class="listing-related-grid">
        ${listingDetailState.relatedItems
          .map(
            (related) => `
              <a class="listing-related-card" href="./listing.html?id=${encodeURIComponent(related.id)}">
                <div class="listing-related-card-top">
                  <strong>${ElevenZeroApp.escapeHtml(related.brand)} ${ElevenZeroApp.escapeHtml(
                    related.model
                  )}</strong>
                  <span>${ElevenZeroApp.formatMoney(related.price_usd)}</span>
                </div>
                <p>${ElevenZeroApp.escapeHtml(
                  [related.category, related.condition, related.location].filter(Boolean).join(" · ")
                )}</p>
                <div class="listing-related-meta">
                  <span>${ElevenZeroApp.escapeHtml(listingPhotoLabel(related))}</span>
                  <span>${ElevenZeroApp.escapeHtml(formatPostedAge(related.created_at))}</span>
                </div>
              </a>
            `
          )
          .join("")}
      </div>
    </article>
  `;
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
    const [response, listingFeed] = await Promise.all([
      ElevenZeroApp.request(`/api/listings/${listingId}`),
      ElevenZeroApp.request("/api/listings"),
    ]);
    const item = response.item;
    if (!item) {
      renderNotFound();
      return;
    }

    listingDetailState.item = item;
    listingDetailState.relatedItems = buildRelatedListings(item, listingFeed.items || []);
    listingDetailState.selectedImageIndex = 0;
    listingDetailState.lightboxOpen = false;
    listingDetailState.shipping = restoreShippingDraftState();
    document.title = `${item.brand} ${item.model} · Eleven Zero PB`;
    renderGallery(item);
    renderLightbox(item);
    renderContent(item);
    renderStory(item);
    renderRelatedListings(item);
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

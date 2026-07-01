const galleryNode = document.querySelector("[data-listing-gallery]");
const contentNode = document.querySelector("[data-listing-content]");
const storyNode = document.querySelector("[data-listing-story]");
const relatedNode = document.querySelector("[data-related-shell]");

const listingDetailState = {
  item: null,
  relatedItems: [],
  selectedImageIndex: 0,
  busy: false,
  statusMessage: "We’ll show checkout messages and seller setup updates here.",
  statusTone: "neutral",
};

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

function getListingIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("id") || "";
  return /^\d+$/.test(raw) ? Number(raw) : 0;
}

function getListingActionState(item) {
  const currentUserId = Number(ElevenZeroApp.session?.user?.id || 0);
  const sellerUserId = Number(item.seller_user_id || 0);
  const isOwner = currentUserId && sellerUserId && currentUserId === sellerUserId;

  if (isOwner) {
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

function setDetailStatus(message, tone = "neutral") {
  listingDetailState.statusMessage = message;
  listingDetailState.statusTone = tone;
  const statusNode = contentNode?.querySelector("[data-detail-status]");
  if (!statusNode) return;
  ElevenZeroApp.setStatus(statusNode, message, tone);
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

  const images = item.images?.length ? item.images : [];
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
    <div class="listing-main-photo">
      <img
        src="${ElevenZeroApp.escapeHtml(selectedImage)}"
        alt="${ElevenZeroApp.escapeHtml(`${item.brand} ${item.model}`)}"
      />
    </div>
    <div class="listing-thumb-row">
      ${thumbnails}
    </div>
  `;

  galleryNode.querySelectorAll("[data-thumb-index]").forEach((button) => {
    button.addEventListener("click", () => {
      listingDetailState.selectedImageIndex = Number(button.dataset.thumbIndex || 0);
      renderGallery(item);
    });
  });
}

function renderContent(item) {
  if (!contentNode) return;

  const actionState = getListingActionState(item);
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

  const busyLabel = listingDetailState.busy ? "Opening checkout..." : actionState.buttonLabel;

  contentNode.innerHTML = `
    <p class="eyebrow">Marketplace listing</p>
    <div class="listing-detail-head">
      <div>
        <p class="product-brand">${ElevenZeroApp.escapeHtml(item.brand)}</p>
        <h1>${ElevenZeroApp.escapeHtml(item.model)}</h1>
      </div>
      <span class="listing-detail-price">${ElevenZeroApp.formatMoney(item.price_usd)}</span>
    </div>
    <div class="listing-detail-specs">${specPills}</div>
    <p class="listing-detail-copy">${ElevenZeroApp.escapeHtml(item.notes)}</p>
    <div class="listing-detail-facts">
      <article>
        <strong>Ships from</strong>
        <span>${ElevenZeroApp.escapeHtml(item.location)}</span>
      </article>
      <article>
        <strong>Seller</strong>
        <span>${ElevenZeroApp.escapeHtml(sellerName)}</span>
      </article>
      <article>
        <strong>Posted</strong>
        <span>${ElevenZeroApp.escapeHtml(formatPostedDate(item.created_at))}</span>
      </article>
      <article>
        <strong>Photos</strong>
        <span>${ElevenZeroApp.escapeHtml(listingPhotoLabel(item))}</span>
      </article>
    </div>
    <div class="listing-purchase-row listing-purchase-row-detail">
      <div class="listing-purchase-copy">
        <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(
          actionState.tone
        )}">${ElevenZeroApp.escapeHtml(actionState.statusLabel)}</span>
        <p class="listing-status-copy">${ElevenZeroApp.escapeHtml(actionState.reason)}</p>
      </div>
      <button
        class="${
          actionState.action === "checkout" || actionState.action === "auth"
            ? "button button-dark"
            : "button button-secondary"
        } listing-buy-button"
        type="button"
        data-detail-buy
        data-buy-action="${ElevenZeroApp.escapeHtml(actionState.action)}"
        ${actionState.action === "disabled" || listingDetailState.busy ? "disabled" : ""}
      >
        ${ElevenZeroApp.escapeHtml(busyLabel)}
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

    if (action === "auth") {
      setDetailStatus("Please sign in first so we can open secure checkout for this listing.", "warning");
      window.setTimeout(() => {
        ElevenZeroApp.redirectToAuth(`${window.location.pathname}${window.location.search}`);
      }, 700);
      return;
    }

    await handleBuyListing(item.id);
  });
}

function renderStory(item) {
  if (!storyNode) return;

  const thickness = formatThickness(item.thickness_mm);
  const actionState = getListingActionState(item);

  storyNode.innerHTML = `
    <article class="listing-detail-panel">
      <p class="eyebrow">Listing notes</p>
      <h2>${ElevenZeroApp.escapeHtml(item.brand)} ${ElevenZeroApp.escapeHtml(item.model)}</h2>
      <p>${ElevenZeroApp.escapeHtml(item.notes)}</p>
    </article>
    <article class="listing-detail-panel listing-detail-panel-soft">
      <p class="eyebrow">Buyer snapshot</p>
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
          <strong>Condition</strong>
          <span>${ElevenZeroApp.escapeHtml(item.condition)}</span>
        </div>
        <div>
          <strong>Location</strong>
          <span>${ElevenZeroApp.escapeHtml(item.location)}</span>
        </div>
      </div>
    </article>
    <article class="listing-detail-panel">
      <p class="eyebrow">Marketplace snapshot</p>
      <h2>What buyers should know first</h2>
      <div class="listing-detail-bullets">
        <div>
          <strong>Checkout</strong>
          <span>${ElevenZeroApp.escapeHtml(actionState.statusLabel)}</span>
        </div>
        <div>
          <strong>Listing age</strong>
          <span>${ElevenZeroApp.escapeHtml(formatPostedAge(item.created_at))}</span>
        </div>
        <div>
          <strong>Seller payouts</strong>
          <span>${ElevenZeroApp.escapeHtml(
            item.seller_ready_for_payouts ? "Ready for live buyer payments" : "Still finishing seller setup"
          )}</span>
        </div>
        <div>
          <strong>Gallery</strong>
          <span>${ElevenZeroApp.escapeHtml(listingPhotoLabel(item))}</span>
        </div>
      </div>
    </article>
  `;
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
      <a class="button button-dark" href="./index.html#listings">Return to marketplace</a>
    `;
  }

  if (storyNode) {
    storyNode.innerHTML = "";
  }
}

async function handleBuyListing(listingId) {
  listingDetailState.busy = true;
  renderContent(listingDetailState.item);

  try {
    const response = await ElevenZeroApp.request("/api/checkout/create-session", {
      method: "POST",
      body: { listingId },
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
    document.title = `${item.brand} ${item.model} · Eleven Zero PB`;
    renderGallery(item);
    renderContent(item);
    renderStory(item);
    renderRelatedListings(item);
  } catch {
    renderNotFound();
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  await loadListingDetail();
});

const listingThemes = {
  control: { artClass: "art-sand", paddleClass: "paddle-carbon", label: "Control" },
  power: { artClass: "art-charcoal", paddleClass: "paddle-sunset", label: "Power" },
  hybrid: { artClass: "art-green", paddleClass: "paddle-lime", label: "Hybrid" },
};

const listingState = {
  filter: "all",
  items: [],
  buyingListingId: null,
  query: "",
  brand: "",
  color: "",
  thickness: "",
  condition: "",
  maxPrice: "",
  sortMode: "relevance",
  draftImages: [],
  imageProcessing: false,
};

const listingGrid = document.querySelector("[data-listings-grid]");
const listingHeading = document.querySelector("[data-listings-heading]");
const listingNote = document.querySelector("[data-listings-note]");
const listingCount = document.querySelector("[data-listing-count]");
const listingForm = document.querySelector("[data-seller-form]");
const listingStatus = document.querySelector("[data-seller-status]");
const marketplaceStatus = document.querySelector("[data-marketplace-status]");
const filterButtons = Array.from(document.querySelectorAll("[data-filter]"));
const searchForm = document.querySelector("[data-listing-search-form]");
const searchInput = searchForm?.querySelector('input[name="query"]');
const brandSelect = searchForm?.querySelector('select[name="brand"]');
const colorSelect = searchForm?.querySelector('select[name="color"]');
const thicknessSelect = searchForm?.querySelector('select[name="thickness"]');
const conditionSelect = searchForm?.querySelector('select[name="condition"]');
const maxPriceInput = searchForm?.querySelector('input[name="maxPrice"]');
const sortSelect = searchForm?.querySelector('select[name="sort"]');
const resetSearchButton = document.querySelector("[data-listing-reset]");
const listingSearchSummary = document.querySelector("[data-listing-search-summary]");
const photoInput = listingForm?.querySelector('input[name="photos"]');
const photoPreview = document.querySelector("[data-photo-preview]");

function clearCheckoutParams() {
  const url = new URL(window.location.href);
  url.searchParams.delete("checkout");
  url.searchParams.delete("session_id");
  const query = url.searchParams.toString();
  const nextUrl = `${url.pathname}${query ? `?${query}` : ""}${url.hash}`;
  window.history.replaceState({}, document.title, nextUrl);
}

function setMarketplaceStatus(message, tone = "neutral") {
  if (!marketplaceStatus) return;
  ElevenZeroApp.setStatus(marketplaceStatus, message, tone);
}

function formatThickness(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "";
  return `${numeric.toFixed(1).replace(/\.0$/, "")} mm`;
}

function normalizeFilterValue(value) {
  return String(value || "").trim().toLowerCase();
}

function truncateCopy(value, maxLength = 140) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trimEnd()}…`;
}

function formatPostedLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently posted";

  const deltaMs = Date.now() - date.getTime();
  const deltaDays = Math.max(0, Math.floor(deltaMs / 86400000));

  if (deltaDays <= 0) return "Posted today";
  if (deltaDays === 1) return "Posted 1 day ago";
  if (deltaDays < 7) return `Posted ${deltaDays} days ago`;

  return `Posted ${new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date)}`;
}

function listingPhotoLabel(item) {
  const total = Array.isArray(item.images) ? item.images.length : 0;
  if (!total) return "No photos";
  if (total === 1) return "1 photo";
  return `${total} photos`;
}

function searchTokens(query) {
  return normalizeFilterValue(query)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function listingSearchScore(item, query) {
  const normalizedQuery = normalizeFilterValue(query);
  if (!normalizedQuery) return 0;

  const tokens = searchTokens(normalizedQuery);
  if (!tokens.length) return 0;

  const fields = {
    brand: normalizeFilterValue(item.brand),
    model: normalizeFilterValue(item.model),
    color: normalizeFilterValue(item.color),
    category: normalizeFilterValue(item.category),
    condition: normalizeFilterValue(item.condition),
    location: normalizeFilterValue(item.location),
    notes: normalizeFilterValue(item.notes),
    seller: normalizeFilterValue(item.seller_name),
    thickness: normalizeFilterValue(formatThickness(item.thickness_mm)),
  };

  const brandModel = [fields.brand, fields.model].filter(Boolean).join(" ").trim();

  let score = 0;

  if (brandModel === normalizedQuery) score += 180;
  else if (brandModel.startsWith(normalizedQuery)) score += 120;

  if (fields.brand === normalizedQuery) score += 95;
  if (fields.model === normalizedQuery) score += 90;
  if (fields.location === normalizedQuery) score += 70;

  for (const token of tokens) {
    let tokenMatched = false;

    if (fields.brand.includes(token)) {
      score += 26;
      tokenMatched = true;
    }
    if (fields.model.includes(token)) {
      score += 24;
      tokenMatched = true;
    }
    if (fields.color.includes(token)) {
      score += 16;
      tokenMatched = true;
    }
    if (fields.category.includes(token)) {
      score += 14;
      tokenMatched = true;
    }
    if (fields.condition.includes(token)) {
      score += 14;
      tokenMatched = true;
    }
    if (fields.location.includes(token)) {
      score += 16;
      tokenMatched = true;
    }
    if (fields.seller.includes(token)) {
      score += 12;
      tokenMatched = true;
    }
    if (fields.thickness.includes(token)) {
      score += 12;
      tokenMatched = true;
    }
    if (fields.notes.includes(token)) {
      score += 9;
      tokenMatched = true;
    }

    if (!tokenMatched) {
      return -1;
    }
  }

  return score;
}

function getPrimaryImage(item) {
  return item.primary_image || item.images?.[0] || "";
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
      reason: "You’re viewing your own listing from the buyer side.",
      tone: "neutral",
    };
  }

  if (item.checkout_available) {
    if (ElevenZeroApp.session?.authenticated) {
      return {
        action: "checkout",
        buttonLabel: "Buy with Stripe",
        statusLabel: "Secure checkout ready",
        reason: "Buyer payment and seller payout can route through Stripe automatically.",
        tone: "ready",
      };
    }

    return {
      action: "auth",
      buttonLabel: "Sign in to buy",
      statusLabel: "Secure checkout ready",
      reason: "Create your buyer account first, then secure checkout will open.",
      tone: "ready",
    };
  }

  if (!ElevenZeroApp.config.stripeConfigured) {
    return {
      action: "disabled",
      buttonLabel: "Checkout soon",
      statusLabel: "Platform setup",
      reason: item.checkout_reason || "Stripe keys still need to be connected in the live app.",
      tone: "neutral",
    };
  }

  if (!item.seller_user_id) {
    return {
      action: "disabled",
      buttonLabel: "Demo listing",
      statusLabel: "Sample inventory",
      reason: item.checkout_reason || "This listing is for marketplace preview right now.",
      tone: "neutral",
    };
  }

  return {
    action: "disabled",
    buttonLabel: "Seller setup pending",
    statusLabel: item.seller_has_connected_account ? "Seller setup pending" : "Payouts not connected",
    reason:
      item.checkout_reason ||
      "This seller needs to finish Stripe payout setup before checkout can go live.",
    tone: "pending",
  };
}

function renderListingArt(item, theme) {
  const primaryImage = getPrimaryImage(item);
  if (primaryImage) {
    return `
      <img
        class="listing-photo"
        src="${ElevenZeroApp.escapeHtml(primaryImage)}"
        alt="${ElevenZeroApp.escapeHtml(`${item.brand} ${item.model}`)}"
      />
    `;
  }

  return `<div class="paddle-graphic ${ElevenZeroApp.escapeHtml(theme.paddleClass)}"></div>`;
}

function buildListingSpecs(item) {
  const specs = [];

  if (item.color) {
    specs.push(`<span>${ElevenZeroApp.escapeHtml(item.color)}</span>`);
  }

  const thicknessLabel = formatThickness(item.thickness_mm);
  if (thicknessLabel) {
    specs.push(`<span>${ElevenZeroApp.escapeHtml(thicknessLabel)}</span>`);
  }

  specs.push(`<span>${ElevenZeroApp.escapeHtml(item.condition)}</span>`);

  return `<div class="listing-spec-pills">${specs.join("")}</div>`;
}

function sortListings(items) {
  const sorted = [...items];

  sorted.sort((left, right) => {
    if (listingState.sortMode === "price-asc") {
      return Number(left.price_usd || 0) - Number(right.price_usd || 0);
    }

    if (listingState.sortMode === "price-desc") {
      return Number(right.price_usd || 0) - Number(left.price_usd || 0);
    }

    if (listingState.sortMode === "photos") {
      const photoDelta = (right.images?.length || 0) - (left.images?.length || 0);
      if (photoDelta !== 0) return photoDelta;
    }

    if (listingState.sortMode === "newest") {
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    }

    const rightScore = listingSearchScore(right, listingState.query);
    const leftScore = listingSearchScore(left, listingState.query);
    if (rightScore !== leftScore) return rightScore - leftScore;

    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  });

  return sorted;
}

function renderListingCard(item) {
  const theme = listingThemes[item.category] || listingThemes.control;
  const sellerName = item.seller_name || "Community seller";
  const actionState = getListingActionState(item);
  const isBusy = Number(listingState.buyingListingId) === Number(item.id);
  const buttonLabel = isBusy ? "Opening checkout..." : actionState.buttonLabel;
  const buttonClass =
    actionState.action === "checkout" || actionState.action === "auth"
      ? "button button-dark"
      : "button button-secondary";
  const detailHref = `./listing.html?id=${encodeURIComponent(item.id)}`;

  return `
    <article class="product-card reveal is-visible" data-category="${ElevenZeroApp.escapeHtml(
      item.category
    )}">
      <div class="card-art ${ElevenZeroApp.escapeHtml(theme.artClass)}">
        ${renderListingArt(item, theme)}
        <span class="condition-tag">${ElevenZeroApp.escapeHtml(item.condition)}</span>
        ${
          item.images?.length > 1
            ? `<span class="listing-photo-count">${ElevenZeroApp.escapeHtml(
                `${item.images.length} photos`
              )}</span>`
            : ""
        }
      </div>
      <div class="card-body">
        <div class="card-headline">
          <div>
            <p class="product-brand">${ElevenZeroApp.escapeHtml(item.brand)}</p>
            <h3>${ElevenZeroApp.escapeHtml(item.model)}</h3>
          </div>
          <span class="price">${ElevenZeroApp.formatMoney(item.price_usd)}</span>
        </div>
        ${buildListingSpecs(item)}
        <p class="product-copy">${ElevenZeroApp.escapeHtml(truncateCopy(item.notes))}</p>
        <div class="card-footer">
          <span>${ElevenZeroApp.escapeHtml(theme.label)}</span>
          <span>${ElevenZeroApp.escapeHtml(item.location)}</span>
          <span>${ElevenZeroApp.escapeHtml(sellerName)}</span>
          <span>${ElevenZeroApp.escapeHtml(formatPostedLabel(item.created_at))}</span>
          <span>${ElevenZeroApp.escapeHtml(listingPhotoLabel(item))}</span>
        </div>
        <div class="listing-purchase-row">
          <div class="listing-purchase-copy">
            <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(
              actionState.tone
            )}">${ElevenZeroApp.escapeHtml(actionState.statusLabel)}</span>
            <p class="listing-status-copy">${ElevenZeroApp.escapeHtml(actionState.reason)}</p>
          </div>
          <div class="listing-cta-stack">
            <a class="button button-secondary listing-detail-button" href="${detailHref}">
              View details
            </a>
            <button
              class="${buttonClass} listing-buy-button"
              type="button"
              data-buy-listing="${ElevenZeroApp.escapeHtml(item.id)}"
              data-buy-action="${ElevenZeroApp.escapeHtml(actionState.action)}"
              ${actionState.action === "disabled" || isBusy ? "disabled" : ""}
            >
              ${ElevenZeroApp.escapeHtml(buttonLabel)}
            </button>
          </div>
        </div>
      </div>
    </article>
  `;
}

function renderListingEmptyState() {
  if (!listingGrid) return;

  const filterSummary = [
    listingState.filter !== "all" ? listingState.filter : "",
    listingState.brand,
    listingState.color,
    listingState.thickness ? `${listingState.thickness} mm` : "",
    listingState.condition,
    listingState.maxPrice ? `up to $${listingState.maxPrice}` : "",
    listingState.query,
  ]
    .filter(Boolean)
    .join(" · ");

  listingGrid.innerHTML = `
    <article class="empty-state reveal is-visible">
      <p class="eyebrow">No matches</p>
      <h3>No listings match this search yet.</h3>
      <p>${
        filterSummary
          ? `Nothing matched ${ElevenZeroApp.escapeHtml(filterSummary)}. Try widening the filters or publish a new listing.`
          : "Try another filter or publish a new paddle listing after signing in."
      }</p>
    </article>
  `;
}

function getVisibleListings() {
  const query = listingState.query;
  const normalizedQuery = normalizeFilterValue(query);
  const selectedBrand = normalizeFilterValue(listingState.brand);
  const selectedColor = normalizeFilterValue(listingState.color);
  const selectedThickness = String(listingState.thickness || "").trim();
  const selectedCondition = normalizeFilterValue(listingState.condition);
  const maxPrice = Number(listingState.maxPrice);

  const filtered = listingState.items.filter((item) => {
    if (listingState.filter !== "all" && item.category !== listingState.filter) {
      return false;
    }

    if (selectedBrand && normalizeFilterValue(item.brand) !== selectedBrand) {
      return false;
    }

    if (selectedColor && normalizeFilterValue(item.color) !== selectedColor) {
      return false;
    }

    if (selectedThickness) {
      const thickness = Number(item.thickness_mm);
      const normalizedThickness = Number.isFinite(thickness)
        ? thickness.toFixed(1)
        : "";
      if (normalizedThickness !== selectedThickness) {
        return false;
      }
    }

    if (selectedCondition && normalizeFilterValue(item.condition) !== selectedCondition) {
      return false;
    }

    if (Number.isFinite(maxPrice) && maxPrice > 0 && Number(item.price_usd || 0) > maxPrice) {
      return false;
    }

    if (!normalizedQuery) return true;

    return listingSearchScore(item, query) >= 0;
  });

  return sortListings(filtered);
}

function describeSortMode(mode) {
  const labels = {
    relevance: "Best match",
    newest: "Newest first",
    "price-asc": "Price: low to high",
    "price-desc": "Price: high to low",
    photos: "Most photos",
  };

  return labels[mode] || "Best match";
}

function populateSelect(select, values, placeholder, currentValue = "") {
  if (!select) return;

  const current = String(currentValue || "");
  const options = [
    `<option value="">${ElevenZeroApp.escapeHtml(placeholder)}</option>`,
    ...values.map(
      (value) =>
        `<option value="${ElevenZeroApp.escapeHtml(value)}"${
          value === current ? " selected" : ""
        }>${ElevenZeroApp.escapeHtml(value)}</option>`
    ),
  ];

  select.innerHTML = options.join("");
}

function refreshSearchOptions() {
  const brands = [...new Set(listingState.items.map((item) => item.brand).filter(Boolean))].sort();
  const colors = [...new Set(listingState.items.map((item) => item.color).filter(Boolean))].sort();
  const conditions = [
    ...new Set(listingState.items.map((item) => item.condition).filter(Boolean)),
  ].sort();
  const thicknesses = [
    ...new Set(
      listingState.items
        .map((item) => {
          const numeric = Number(item.thickness_mm);
          return Number.isFinite(numeric) ? numeric.toFixed(1) : "";
        })
        .filter(Boolean)
    ),
  ].sort((left, right) => Number(left) - Number(right));

  populateSelect(brandSelect, brands, "All brands", listingState.brand);
  populateSelect(colorSelect, colors, "All colors", listingState.color);
  populateSelect(thicknessSelect, thicknesses, "Any thickness", listingState.thickness);
  populateSelect(conditionSelect, conditions, "Any condition", listingState.condition);
  if (sortSelect) sortSelect.value = listingState.sortMode;
  if (maxPriceInput) maxPriceInput.value = listingState.maxPrice;
}

function bindListingActions() {
  document.querySelectorAll("[data-buy-listing]").forEach((button) => {
    button.addEventListener("click", async () => {
      const listingId = Number(button.dataset.buyListing || 0);
      const action = button.dataset.buyAction || "disabled";

      if (!listingId || action === "disabled") {
        return;
      }

      if (action === "auth") {
        setMarketplaceStatus(
          "Please sign in first so we can open a secure buyer checkout for you.",
          "warning"
        );
        window.setTimeout(() => {
          ElevenZeroApp.redirectToAuth(`${window.location.pathname}#listings`);
        }, 700);
        return;
      }

      await handleBuyListing(listingId);
    });
  });
}

function renderPhotoPreview() {
  if (!photoPreview) return;

  if (listingState.imageProcessing) {
    photoPreview.innerHTML = `
      <div class="seller-photo-placeholder">
        Preparing your photo previews…
      </div>
    `;
    return;
  }

  if (!listingState.draftImages.length) {
    photoPreview.innerHTML = `
      <div class="seller-photo-placeholder">
        Photo previews will show up here before the listing goes live.
      </div>
    `;
    return;
  }

  photoPreview.innerHTML = listingState.draftImages
    .map(
      (image, index) => `
        <figure class="seller-photo-thumb">
          <button
            class="seller-photo-remove"
            type="button"
            data-remove-photo="${index}"
            aria-label="Remove selected photo ${index + 1}"
          >
            ×
          </button>
          <span class="seller-photo-badge">${index === 0 ? "Cover photo" : `Photo ${index + 1}`}</span>
          <img src="${ElevenZeroApp.escapeHtml(image)}" alt="Listing photo preview ${index + 1}" />
          <figcaption>${index === 0 ? "This image shows first in the marketplace." : "Included in the listing gallery."}</figcaption>
        </figure>
      `
    )
    .join("");
}

function renderSearchSummary(visible) {
  if (!listingSearchSummary) return;

  const activeFilters = [
    listingState.filter !== "all" ? `style: ${listingState.filter}` : "",
    listingState.brand ? `brand: ${listingState.brand}` : "",
    listingState.color ? `color: ${listingState.color}` : "",
    listingState.thickness ? `thickness: ${listingState.thickness} mm` : "",
    listingState.condition ? `condition: ${listingState.condition}` : "",
    listingState.maxPrice ? `max price: $${listingState.maxPrice}` : "",
    listingState.query ? `search: “${listingState.query}”` : "",
  ].filter(Boolean);

  const filtersLabel = activeFilters.length ? activeFilters.join(" · ") : "all live listings";
  const sortedLabel = describeSortMode(listingState.sortMode);

  listingSearchSummary.textContent = `Showing ${visible.length} of ${listingState.items.length} listings for ${filtersLabel}. Sorted by ${sortedLabel}.`;
}

function renderListings() {
  const visible = getVisibleListings();

  filterButtons.forEach((button) => {
    const isActive = button.dataset.filter === listingState.filter;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  if (listingCount) {
    listingCount.textContent = `${listingState.items.length} listings`;
  }

  if (listingHeading) {
    listingHeading.textContent = `${visible.length} live listing${visible.length === 1 ? "" : "s"}`;
  }

  renderSearchSummary(visible);

  const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;

  if (listingNote) {
    if (listingState.query || listingState.brand || listingState.color || listingState.thickness) {
      const activeFilters = [
        listingState.brand || "all brands",
        listingState.color || "all colors",
        listingState.thickness ? `${listingState.thickness} mm` : "any thickness",
      ].join(" · ");
      listingNote.textContent = `Search results update live while you browse. Current filters: ${activeFilters}.`;
    } else {
      listingNote.textContent = !ElevenZeroApp.session?.authenticated
        ? "Sign in to publish your own paddle into the live feed and unlock buyer checkout."
        : !sellerProfile?.connectConfigured
          ? "You can publish listings now. Stripe seller payouts are built in, but this app still needs Stripe keys before checkout can go live."
          : !sellerProfile?.readyForPayouts
            ? "You can publish listings now. Finish seller payouts in Account before buyers can pay you through the marketplace."
            : "You’re signed in and payout-ready on Stripe, so buyers can use secure checkout on your eligible listings.";
    }
  }

  if (!visible.length) {
    renderListingEmptyState();
    return;
  }

  if (listingGrid) {
    listingGrid.innerHTML = visible.map(renderListingCard).join("");
    bindListingActions();
  }
}

async function loadListings() {
  const response = await ElevenZeroApp.request("/api/listings");
  listingState.items = response.items || [];
  refreshSearchOptions();
  renderListings();
}

async function handleCheckoutReturn() {
  const params = new URLSearchParams(window.location.search);
  const checkoutState = params.get("checkout");
  const sessionId = params.get("session_id");

  if (!checkoutState) {
    return;
  }

  if (checkoutState === "cancel") {
    setMarketplaceStatus(
      "Checkout was canceled. Your marketplace browsing is still right here when you’re ready.",
      "warning"
    );
    clearCheckoutParams();
    return;
  }

  if (checkoutState !== "success") {
    return;
  }

  if (!ElevenZeroApp.session?.authenticated || !sessionId) {
    setMarketplaceStatus(
      "Stripe sent you back successfully. Sign in again if you want us to confirm the order details here.",
      "warning"
    );
    clearCheckoutParams();
    return;
  }

  try {
    const response = await ElevenZeroApp.request(
      `/api/checkout/session-status?sessionId=${encodeURIComponent(sessionId)}`
    );
    const order = response.order || {};
    const amountLabel = order.amountTotalCents
      ? ElevenZeroApp.formatMoney(order.amountTotalCents / 100)
      : "";
    const summary = [response.message, order.listingTitle, amountLabel].filter(Boolean).join(" · ");
    setMarketplaceStatus(summary, order.status === "paid" ? "success" : "warning");
  } catch (error) {
    setMarketplaceStatus(error.message, "error");
  } finally {
    clearCheckoutParams();
  }
}

async function handleBuyListing(listingId) {
  const listing = listingState.items.find((item) => Number(item.id) === Number(listingId));
  if (!listing) {
    setMarketplaceStatus("That listing could not be found anymore.", "error");
    return;
  }

  listingState.buyingListingId = listingId;
  renderListings();

  try {
    const response = await ElevenZeroApp.request("/api/checkout/create-session", {
      method: "POST",
      body: { listingId },
    });

    setMarketplaceStatus(
      `Opening secure checkout for ${response.listing?.title || "your listing"}.`,
      "success"
    );
    window.location.href = response.checkoutUrl;
  } catch (error) {
    setMarketplaceStatus(error.message, "error");
  } finally {
    listingState.buyingListingId = null;
    renderListings();
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

function optimizeImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const maxSide = 1400;
      const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
      const width = Math.max(1, Math.round(image.width * scale));
      const height = Math.max(1, Math.round(image.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");

      if (!context) {
        reject(new Error("Could not prepare the image for upload."));
        return;
      }

      context.drawImage(image, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", 0.84));
    };
    image.onerror = () => reject(new Error("One of the selected photos could not be processed."));
    image.src = dataUrl;
  });
}

async function prepareListingPhotos(fileList) {
  const files = Array.from(fileList || [])
    .filter((file) => file.type.startsWith("image/"))
    .slice(0, 4);

  const images = [];

  for (const file of files) {
    const rawDataUrl = await readFileAsDataUrl(file);
    const optimized = await optimizeImage(rawDataUrl);
    images.push(optimized);
  }

  return images;
}

async function handlePhotoSelection() {
  if (!photoInput) return;

  if (!photoInput.files?.length) {
    listingState.draftImages = [];
    renderPhotoPreview();
    return;
  }

  listingState.imageProcessing = true;
  renderPhotoPreview();
  ElevenZeroApp.setStatus(
    listingStatus,
    "Preparing your listing photos for upload...",
    "warning"
  );

  try {
    listingState.draftImages = await prepareListingPhotos(photoInput.files);
    renderPhotoPreview();
    ElevenZeroApp.setStatus(
      listingStatus,
      `${listingState.draftImages.length} photo${
        listingState.draftImages.length === 1 ? "" : "s"
      } ready for publishing. The first photo will be used as the cover image.`,
      "success"
    );
  } catch (error) {
    listingState.draftImages = [];
    renderPhotoPreview();
    ElevenZeroApp.setStatus(listingStatus, error.message, "error");
  } finally {
    listingState.imageProcessing = false;
  }
}

async function handleListingSubmit(event) {
  event.preventDefault();

  if (!ElevenZeroApp.requireAuth(listingStatus, "Please sign in first to publish a listing.")) {
    return;
  }

  if (listingState.imageProcessing) {
    ElevenZeroApp.setStatus(
      listingStatus,
      "Your photos are still finishing up. Give it one second and try again.",
      "warning"
    );
    return;
  }

  if (!listingState.draftImages.length) {
    ElevenZeroApp.setStatus(
      listingStatus,
      "Please add at least one paddle photo before publishing.",
      "warning"
    );
    photoInput?.focus();
    return;
  }

  const formData = new FormData(listingForm);
  const payload = Object.fromEntries(formData.entries());
  payload.images = listingState.draftImages;

  try {
    await ElevenZeroApp.request("/api/listings", {
      method: "POST",
      body: payload,
    });

    listingForm.reset();
    listingState.draftImages = [];
    renderPhotoPreview();

    const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;
    ElevenZeroApp.setStatus(
      listingStatus,
      sellerProfile?.readyForPayouts
        ? `${payload.brand} ${payload.model} is now live in the marketplace with its own detail page.`
        : `${payload.brand} ${payload.model} is now live in the marketplace. Next step: finish seller payouts in Account before live checkout turns on.`,
      "success"
    );
    await loadListings();
  } catch (error) {
    ElevenZeroApp.setStatus(listingStatus, error.message, "error");
  }
}

function syncSearchState() {
  listingState.query = searchInput?.value?.trim() || "";
  listingState.brand = brandSelect?.value || "";
  listingState.color = colorSelect?.value || "";
  listingState.thickness = thicknessSelect?.value || "";
  listingState.condition = conditionSelect?.value || "";
  listingState.maxPrice = maxPriceInput?.value?.trim() || "";
  listingState.sortMode = sortSelect?.value || "relevance";
  renderListings();
}

function resetSearchState() {
  listingState.filter = "all";
  listingState.query = "";
  listingState.brand = "";
  listingState.color = "";
  listingState.thickness = "";
  listingState.condition = "";
  listingState.maxPrice = "";
  listingState.sortMode = "relevance";

  if (searchInput) searchInput.value = "";
  if (brandSelect) brandSelect.value = "";
  if (colorSelect) colorSelect.value = "";
  if (thicknessSelect) thicknessSelect.value = "";
  if (conditionSelect) conditionSelect.value = "";
  if (maxPriceInput) maxPriceInput.value = "";
  if (sortSelect) sortSelect.value = "relevance";

  renderListings();
}

function removeDraftPhoto(index) {
  listingState.draftImages = listingState.draftImages.filter((_, itemIndex) => itemIndex !== index);
  if (!listingState.draftImages.length && photoInput) {
    photoInput.value = "";
  }
  renderPhotoPreview();
  ElevenZeroApp.setStatus(
    listingStatus,
    listingState.draftImages.length
      ? `${listingState.draftImages.length} photo${listingState.draftImages.length === 1 ? "" : "s"} ready for publishing.`
      : "Photo previews cleared. Add images to continue.",
    listingState.draftImages.length ? "success" : "warning"
  );
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  renderPhotoPreview();
  await loadListings();
  await handleCheckoutReturn();

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      listingState.filter = button.dataset.filter || "all";
      renderListings();
    });
  });

  searchInput?.addEventListener("input", syncSearchState);
  brandSelect?.addEventListener("change", syncSearchState);
  colorSelect?.addEventListener("change", syncSearchState);
  thicknessSelect?.addEventListener("change", syncSearchState);
  conditionSelect?.addEventListener("change", syncSearchState);
  maxPriceInput?.addEventListener("input", syncSearchState);
  sortSelect?.addEventListener("change", syncSearchState);
  resetSearchButton?.addEventListener("click", resetSearchState);
  searchForm?.addEventListener("submit", (event) => event.preventDefault());
  photoInput?.addEventListener("change", handlePhotoSelection);
  listingForm?.addEventListener("submit", handleListingSubmit);
  photoPreview?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-photo]");
    if (!button) return;
    removeDraftPhoto(Number(button.dataset.removePhoto || -1));
  });
});

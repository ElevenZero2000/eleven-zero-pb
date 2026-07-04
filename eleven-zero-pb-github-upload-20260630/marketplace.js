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
  location: "",
  brand: "",
  color: "",
  thickness: "",
  condition: "",
  minPrice: "",
  maxPrice: "",
  photoMode: "",
  sortMode: "relevance",
  draftImages: [],
  imageProcessing: false,
  sellerDraftSavedAt: "",
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
const locationInput = searchForm?.querySelector('input[name="location"]');
const brandSelect = searchForm?.querySelector('select[name="brand"]');
const colorSelect = searchForm?.querySelector('select[name="color"]');
const thicknessSelect = searchForm?.querySelector('select[name="thickness"]');
const conditionSelect = searchForm?.querySelector('select[name="condition"]');
const minPriceInput = searchForm?.querySelector('input[name="minPrice"]');
const maxPriceInput = searchForm?.querySelector('input[name="maxPrice"]');
const photoSelect = searchForm?.querySelector('select[name="photos"]');
const sortSelect = searchForm?.querySelector('select[name="sort"]');
const resetSearchButton = document.querySelector("[data-listing-reset]");
const listingSearchSummary = document.querySelector("[data-listing-search-summary]");
const listingBrandPills = document.querySelector("[data-listing-brand-pills]");
const listingActiveFilters = document.querySelector("[data-listing-active-filters]");
const photoInput = listingForm?.querySelector('input[name="photos"]');
const photoPreview = document.querySelector("[data-photo-preview]");
const photoDropzone = document.querySelector("[data-photo-dropzone]");
const photoMeta = document.querySelector("[data-photo-meta]");
const sellerReadinessTitle = document.querySelector("[data-seller-readiness-title]");
const sellerReadinessPill = document.querySelector("[data-seller-readiness-pill]");
const sellerReadinessCopy = document.querySelector("[data-seller-readiness-copy]");
const sellerReadinessGrid = document.querySelector("[data-seller-readiness-grid]");
const sellerLivePreview = document.querySelector("[data-seller-live-preview]");
const sellerNotesCounter = document.querySelector("[data-seller-notes-counter]");
const sellerDraftStatus = document.querySelector("[data-seller-draft-status]");
const clearSellerDraftButton = document.querySelector("[data-clear-seller-draft]");
const shippingModeInput = listingForm?.querySelector('select[name="shippingMode"]');
const shippingFlatField = listingForm?.querySelector("[data-shipping-flat-field]");

const MARKETPLACE_BROWSE_STORAGE_KEY = "elevenZeroPbMarketplaceBrowseState";
const SELLER_DRAFT_STORAGE_KEY = "elevenZeroPbSellerDraft";
const MARKETPLACE_QUERY_KEYS = {
  filter: "shopStyle",
  query: "shopQuery",
  location: "shopLocation",
  brand: "shopBrand",
  color: "shopColor",
  thickness: "shopThickness",
  condition: "shopCondition",
  minPrice: "shopMin",
  maxPrice: "shopMax",
  photoMode: "shopPhotos",
  sortMode: "shopSort",
};
const MARKETPLACE_FILTERS = new Set(["all", ...Object.keys(listingThemes)]);
const MARKETPLACE_SORT_MODES = new Set(["relevance", "newest", "price-asc", "price-desc", "photos"]);
const MARKETPLACE_PHOTO_MODES = new Set(["", "1", "2", "3"]);
const SELLER_DRAFT_DEFAULTS = {
  category: "control",
  condition: "Excellent",
  shippingMode: "calculated",
};

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

function normalizeBrowseState(raw = {}) {
  const nextFilter = String(raw.filter || "all").trim().toLowerCase();
  const nextPhotoMode = String(raw.photoMode || "").trim();
  const nextSortMode = String(raw.sortMode || "relevance").trim();

  return {
    filter: MARKETPLACE_FILTERS.has(nextFilter) ? nextFilter : "all",
    query: String(raw.query || "").trim(),
    location: String(raw.location || "").trim(),
    brand: String(raw.brand || "").trim(),
    color: String(raw.color || "").trim(),
    thickness: String(raw.thickness || "").trim(),
    condition: String(raw.condition || "").trim(),
    minPrice: String(raw.minPrice || "").trim(),
    maxPrice: String(raw.maxPrice || "").trim(),
    photoMode: MARKETPLACE_PHOTO_MODES.has(nextPhotoMode) ? nextPhotoMode : "",
    sortMode: MARKETPLACE_SORT_MODES.has(nextSortMode) ? nextSortMode : "relevance",
  };
}

function getMarketplaceBrowseState() {
  return normalizeBrowseState({
    filter: listingState.filter,
    query: listingState.query,
    location: listingState.location,
    brand: listingState.brand,
    color: listingState.color,
    thickness: listingState.thickness,
    condition: listingState.condition,
    minPrice: listingState.minPrice,
    maxPrice: listingState.maxPrice,
    photoMode: listingState.photoMode,
    sortMode: listingState.sortMode,
  });
}

function marketplaceBrowseStateHasValues(state = getMarketplaceBrowseState()) {
  return Boolean(
    state.filter !== "all" ||
      state.query ||
      state.location ||
      state.brand ||
      state.color ||
      state.thickness ||
      state.condition ||
      state.minPrice ||
      state.maxPrice ||
      state.photoMode ||
      state.sortMode !== "relevance"
  );
}

function syncSearchInputsFromState() {
  if (searchInput) searchInput.value = listingState.query;
  if (locationInput) locationInput.value = listingState.location;
  if (brandSelect) brandSelect.value = listingState.brand;
  if (colorSelect) colorSelect.value = listingState.color;
  if (thicknessSelect) thicknessSelect.value = listingState.thickness;
  if (conditionSelect) conditionSelect.value = listingState.condition;
  if (minPriceInput) minPriceInput.value = listingState.minPrice;
  if (maxPriceInput) maxPriceInput.value = listingState.maxPrice;
  if (photoSelect) photoSelect.value = listingState.photoMode;
  if (sortSelect) sortSelect.value = listingState.sortMode;
}

function applyMarketplaceBrowseState(rawState = {}) {
  const nextState = normalizeBrowseState(rawState);
  Object.assign(listingState, nextState);
  syncSearchInputsFromState();
}

function readMarketplaceBrowseStateFromUrl() {
  const url = new URL(window.location.href);
  const nextState = {};
  let hasValue = false;

  Object.entries(MARKETPLACE_QUERY_KEYS).forEach(([stateKey, queryKey]) => {
    if (!url.searchParams.has(queryKey)) return;
    nextState[stateKey] = url.searchParams.get(queryKey) || "";
    hasValue = true;
  });

  return hasValue ? normalizeBrowseState(nextState) : null;
}

function writeMarketplaceBrowseStateToUrl(state = getMarketplaceBrowseState()) {
  const url = new URL(window.location.href);

  Object.values(MARKETPLACE_QUERY_KEYS).forEach((queryKey) => {
    url.searchParams.delete(queryKey);
  });

  if (state.filter !== "all") {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.filter, state.filter);
  }
  if (state.query) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.query, state.query);
  }
  if (state.location) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.location, state.location);
  }
  if (state.brand) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.brand, state.brand);
  }
  if (state.color) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.color, state.color);
  }
  if (state.thickness) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.thickness, state.thickness);
  }
  if (state.condition) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.condition, state.condition);
  }
  if (state.minPrice) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.minPrice, state.minPrice);
  }
  if (state.maxPrice) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.maxPrice, state.maxPrice);
  }
  if (state.photoMode) {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.photoMode, state.photoMode);
  }
  if (state.sortMode !== "relevance") {
    url.searchParams.set(MARKETPLACE_QUERY_KEYS.sortMode, state.sortMode);
  }

  const query = url.searchParams.toString();
  const nextUrl = `${url.pathname}${query ? `?${query}` : ""}${url.hash}`;
  window.history.replaceState({}, document.title, nextUrl);
}

function persistMarketplaceBrowseState() {
  const state = getMarketplaceBrowseState();

  if (marketplaceBrowseStateHasValues(state)) {
    writeStorageJson(MARKETPLACE_BROWSE_STORAGE_KEY, state);
  } else {
    removeStorageItem(MARKETPLACE_BROWSE_STORAGE_KEY);
  }

  writeMarketplaceBrowseStateToUrl(state);
}

function restoreMarketplaceBrowseState() {
  const urlState = readMarketplaceBrowseStateFromUrl();
  const storedState = readStorageJson(MARKETPLACE_BROWSE_STORAGE_KEY);
  const nextState = urlState || storedState;

  if (!nextState) {
    syncSearchInputsFromState();
    return;
  }

  applyMarketplaceBrowseState(nextState);
}

function getActiveMarketplaceFilters() {
  const photoLabels = {
    "1": "Has photos",
    "2": "2+ photos",
    "3": "3+ photos",
  };

  const activeFilters = [
    listingState.filter !== "all"
      ? {
          key: "filter",
          label: "Style",
          value: listingThemes[listingState.filter]?.label || listingState.filter,
        }
      : null,
    listingState.brand ? { key: "brand", label: "Brand", value: listingState.brand } : null,
    listingState.color ? { key: "color", label: "Color", value: listingState.color } : null,
    listingState.thickness
      ? { key: "thickness", label: "Thickness", value: `${listingState.thickness} mm` }
      : null,
    listingState.condition
      ? { key: "condition", label: "Condition", value: listingState.condition }
      : null,
    listingState.location
      ? { key: "location", label: "Location", value: listingState.location }
      : null,
    listingState.minPrice ? { key: "minPrice", label: "Min", value: `$${listingState.minPrice}` } : null,
    listingState.maxPrice ? { key: "maxPrice", label: "Max", value: `$${listingState.maxPrice}` } : null,
    listingState.photoMode
      ? { key: "photoMode", label: "Photos", value: photoLabels[listingState.photoMode] || listingState.photoMode }
      : null,
    listingState.query ? { key: "query", label: "Search", value: listingState.query } : null,
    listingState.sortMode !== "relevance"
      ? { key: "sortMode", label: "Sort", value: describeSortMode(listingState.sortMode) }
      : null,
  ].filter(Boolean);

  return activeFilters;
}

function clearMarketplaceFilter(filterKey) {
  const resetValues = {
    filter: "all",
    brand: "",
    color: "",
    thickness: "",
    condition: "",
    location: "",
    minPrice: "",
    maxPrice: "",
    photoMode: "",
    query: "",
    sortMode: "relevance",
  };

  if (!(filterKey in resetValues)) return;

  listingState[filterKey] = resetValues[filterKey];
  syncSearchInputsFromState();
  persistMarketplaceBrowseState();
  renderListings();
}

function renderActiveFilters() {
  if (!listingActiveFilters) return;

  const activeFilters = getActiveMarketplaceFilters();
  listingActiveFilters.classList.toggle("is-empty", activeFilters.length === 0);

  if (!activeFilters.length) {
    listingActiveFilters.innerHTML = "";
    return;
  }

  listingActiveFilters.innerHTML = `
    <span class="listing-active-filters-label">Active filters</span>
    ${activeFilters
      .map(
        (filter) => `
          <button
            class="listing-active-filter-chip"
            type="button"
            data-remove-filter="${ElevenZeroApp.escapeHtml(filter.key)}"
            aria-label="${ElevenZeroApp.escapeHtml(`Remove ${filter.label} filter`)}"
          >
            <span>${ElevenZeroApp.escapeHtml(`${filter.label}: ${filter.value}`)}</span>
            <strong>×</strong>
          </button>
        `
      )
      .join("")}
    <button class="listing-active-filter-clear" type="button" data-clear-all-filters>
      Clear all
    </button>
  `;

  listingActiveFilters.querySelectorAll("[data-remove-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      clearMarketplaceFilter(button.dataset.removeFilter || "");
    });
  });

  listingActiveFilters.querySelector("[data-clear-all-filters]")?.addEventListener("click", () => {
    resetSearchState();
  });
}

function getSellerDraftFieldSnapshot() {
  if (!listingForm) return {};

  const snapshot = {};
  const formData = new FormData(listingForm);

  for (const [key, value] of formData.entries()) {
    if (key === "photos") continue;
    snapshot[key] = String(value || "").trim();
  }

  return snapshot;
}

function sellerDraftHasContent(fields = getSellerDraftFieldSnapshot()) {
  return Object.entries(fields).some(([key, value]) => {
    const normalizedValue = String(value || "").trim();

    if (key === "category") {
      return normalizedValue && normalizedValue !== SELLER_DRAFT_DEFAULTS.category;
    }

    if (key === "condition") {
      return normalizedValue && normalizedValue !== SELLER_DRAFT_DEFAULTS.condition;
    }

    if (key === "shippingMode") {
      return normalizedValue && normalizedValue !== SELLER_DRAFT_DEFAULTS.shippingMode;
    }

    return Boolean(normalizedValue);
  });
}

function formatSavedTimeLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "recently";

  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function updateSellerNotesCounter() {
  if (!sellerNotesCounter || !listingForm) return;

  const notes = listingForm.querySelector('textarea[name="notes"]')?.value?.trim() || "";
  const count = notes.length;

  if (!count) {
    sellerNotesCounter.textContent =
      "0 characters · buyers respond best to clear wear, grip, and edge-guard details.";
    return;
  }

  if (count < 60) {
    sellerNotesCounter.textContent = `${count} characters · add a little more detail so buyers trust the condition faster.`;
    return;
  }

  if (count <= 320) {
    sellerNotesCounter.textContent = `${count} characters · great length for a clear, buyer-friendly listing.`;
    return;
  }

  sellerNotesCounter.textContent = `${count} characters · strong detail. Keep it skimmable so buyers can scan it quickly.`;
}

function renderSellerDraftStatus(overrideMessage = "") {
  if (!sellerDraftStatus) return;

  const formHasContent = sellerDraftHasContent();
  const hasPhotos = listingState.draftImages.length > 0;
  const hasAnythingToClear = formHasContent || hasPhotos;

  if (clearSellerDraftButton) {
    clearSellerDraftButton.disabled = !hasAnythingToClear;
  }

  if (overrideMessage) {
    sellerDraftStatus.textContent = overrideMessage;
    return;
  }

  if (listingState.sellerDraftSavedAt && formHasContent) {
    sellerDraftStatus.textContent = `Draft saved on this device · updated ${formatSavedTimeLabel(
      listingState.sellerDraftSavedAt
    )}. ${hasPhotos ? "Photos stay in this tab until you submit for review." : "Add photos whenever you’re ready."}`;
    return;
  }

  if (hasPhotos) {
    sellerDraftStatus.textContent =
      "Photos are ready in this tab. Listing details save automatically on this device while you work.";
    return;
  }

  sellerDraftStatus.textContent = "Your listing details can be saved on this device while you work.";
}

function saveSellerDraft() {
  const fields = getSellerDraftFieldSnapshot();

  if (!sellerDraftHasContent(fields)) {
    listingState.sellerDraftSavedAt = "";
    removeStorageItem(SELLER_DRAFT_STORAGE_KEY);
    renderSellerDraftStatus();
    return;
  }

  const payload = {
    fields,
    savedAt: new Date().toISOString(),
  };

  const saved = writeStorageJson(SELLER_DRAFT_STORAGE_KEY, payload);
  listingState.sellerDraftSavedAt = saved ? payload.savedAt : "";
  renderSellerDraftStatus();
}

function restoreSellerDraft() {
  if (!listingForm) return;

  const draft = readStorageJson(SELLER_DRAFT_STORAGE_KEY);
  if (!draft?.fields || typeof draft.fields !== "object") {
    renderSellerDraftStatus();
    return;
  }

  Object.entries(draft.fields).forEach(([name, value]) => {
    const field = listingForm.elements?.namedItem?.(name);
    if (!field || !("value" in field)) return;
    field.value = String(value || "");
  });

  listingState.sellerDraftSavedAt = String(draft.savedAt || "");
  syncShippingFormState();
  updateSellerNotesCounter();
  renderSellerDraftStatus();
}

function clearSellerDraft() {
  if (listingForm) {
    listingForm.reset();
  }

  if (photoInput) {
    photoInput.value = "";
  }

  listingState.draftImages = [];
  listingState.sellerDraftSavedAt = "";
  removeStorageItem(SELLER_DRAFT_STORAGE_KEY);
  syncShippingFormState();
  updateSellerNotesCounter();
  renderPhotoPreview();
  renderSellerReadiness();
  renderSellerLivePreview();
  renderSellerDraftStatus("Saved draft cleared from this device. Start a fresh listing anytime.");
}

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

function buildListingGalleryPreview(item) {
  const images = Array.isArray(item.images) ? item.images.slice(0, 3) : [];
  if (images.length <= 1) return "";

  const overflowCount = Math.max(0, (item.images?.length || 0) - images.length);

  return `
    <div class="listing-card-preview-strip" aria-hidden="true">
      ${images
        .map(
          (image, index) => `
            <span class="listing-card-preview-thumb${index === 0 ? " is-active" : ""}">
              <img src="${ElevenZeroApp.escapeHtml(image)}" alt="" />
            </span>
          `
        )
        .join("")}
      ${
        overflowCount
          ? `<span class="listing-card-preview-more">+${ElevenZeroApp.escapeHtml(
              overflowCount
            )}</span>`
          : ""
      }
    </div>
  `;
}

function formatWeightLabel(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "";
  return `${numeric.toFixed(1).replace(/\.0$/, "")} oz`;
}

function formatMoneyLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return raw.startsWith("$") ? raw : `$${raw}`;
}

function formatDimensionsLabel(length, width, height) {
  const values = [length, width, height].map((value) => String(value || "").trim()).filter(Boolean);
  if (values.length !== 3) return "";
  return `${values.join(" × ")} in`;
}

function getDraftShippingConfig() {
  if (!listingForm) {
    return {
      mode: "calculated",
      flat: "",
      originZip: "",
      originStreet1: "",
      weight: "",
      length: "",
      width: "",
      height: "",
      note: "",
    };
  }

  return {
    mode: listingForm.querySelector('select[name="shippingMode"]')?.value || "calculated",
    flat: listingForm.querySelector('input[name="shippingFlat"]')?.value?.trim() || "",
    originZip: listingForm.querySelector('input[name="shippingOriginZip"]')?.value?.trim() || "",
    originStreet1: listingForm.querySelector('input[name="shippingOriginStreet1"]')?.value?.trim() || "",
    weight: listingForm.querySelector('input[name="shippingWeightOz"]')?.value?.trim() || "",
    length: listingForm.querySelector('input[name="shippingLengthIn"]')?.value?.trim() || "",
    width: listingForm.querySelector('input[name="shippingWidthIn"]')?.value?.trim() || "",
    height: listingForm.querySelector('input[name="shippingHeightIn"]')?.value?.trim() || "",
    note: listingForm.querySelector('input[name="shippingNote"]')?.value?.trim() || "",
  };
}

function getDraftShippingLabel(config = getDraftShippingConfig()) {
  if (config.mode === "free") {
    return "Free shipping";
  }

  if (config.mode === "flat") {
    return config.flat ? `Flat shipping · ${formatMoneyLabel(config.flat)}` : "Flat shipping";
  }

  return "Calculated shipping at checkout";
}

function shippingModeHelp(config = getDraftShippingConfig()) {
  if (config.mode === "free") {
    return "Seller is covering shipping on this listing.";
  }

  if (config.mode === "flat") {
    return config.flat
      ? `Buyer will see the same ${formatMoneyLabel(config.flat)} shipping fee before checkout.`
      : "Add the flat shipping amount buyers should see.";
  }

  if (ElevenZeroApp.config?.shippoConfigured) {
    return config.originZip
      ? "Buyer address will be used to estimate shipping at checkout. Exact carrier details can be refined later."
      : "Add the shipping ZIP code so buyers can see a better delivery estimate.";
  }

  return config.originZip
    ? "Buyer address will be used to estimate the delivered total at checkout."
    : "Add the shipping ZIP code so the address-based estimate is more accurate.";
}

function syncShippingFormState() {
  const mode = shippingModeInput?.value || "calculated";
  shippingFlatField?.classList.toggle("is-hidden", mode !== "flat");
}

function updatePhotoMeta() {
  if (!photoMeta) return;

  const total = listingState.draftImages.length;
  const remaining = Math.max(0, 4 - total);

  photoMeta.textContent =
    total === 0
      ? "0 of 4 photos selected."
      : total >= 4
        ? "4 of 4 photos selected · upload limit reached."
        : `${total} of 4 photos selected · ${remaining} more available.`;
}

function searchTokens(query) {
  return normalizeFilterValue(query)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function valueIncludesAllTokens(value, query) {
  const haystack = normalizeFilterValue(value);
  const tokens = searchTokens(query);
  if (!tokens.length) return true;
  return tokens.every((token) => haystack.includes(token));
}

function sellerChecklistItem(label, ready, helper) {
  return `
    <article class="seller-launch-item ${ready ? "is-ready" : "is-pending"}">
      <strong>${ElevenZeroApp.escapeHtml(label)}</strong>
      <span>${ElevenZeroApp.escapeHtml(helper)}</span>
    </article>
  `;
}

function renderSellerLivePreview() {
  if (!sellerLivePreview || !listingForm) return;

  const brand = listingForm.querySelector('input[name="brand"]')?.value?.trim() || "Your brand";
  const model = listingForm.querySelector('input[name="model"]')?.value?.trim() || "Your paddle model";
  const color = listingForm.querySelector('input[name="color"]')?.value?.trim() || "";
  const thickness = listingForm.querySelector('input[name="thickness"]')?.value?.trim() || "";
  const category = listingForm.querySelector('select[name="category"]')?.value || "control";
  const condition = listingForm.querySelector('select[name="condition"]')?.value || "Excellent";
  const price = listingForm.querySelector('input[name="price"]')?.value?.trim() || "";
  const location = listingForm.querySelector('input[name="location"]')?.value?.trim() || "Your city";
  const notes = listingForm.querySelector('textarea[name="notes"]')?.value?.trim() || "";
  const shippingConfig = getDraftShippingConfig();
  const shippingLabel = getDraftShippingLabel(shippingConfig);
  const shippingMeta = [
    shippingConfig.originZip ? `ZIP ${shippingConfig.originZip}` : "",
    shippingConfig.originStreet1 ? "Private origin ready" : "",
    shippingConfig.weight ? formatWeightLabel(shippingConfig.weight) : "",
    formatDimensionsLabel(shippingConfig.length, shippingConfig.width, shippingConfig.height),
  ]
    .filter(Boolean)
    .join(" · ");
  const theme = listingThemes[category] || listingThemes.control;
  const coverImage = listingState.draftImages[0] || "";
  const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;
  const statusLabel = sellerProfile?.readyForPayouts ? "Seller setup ready" : "Listing ready · payout setup later";

  const specs = [
    color ? `<span>${ElevenZeroApp.escapeHtml(color)}</span>` : "",
    thickness ? `<span>${ElevenZeroApp.escapeHtml(`${thickness} mm`)}</span>` : "",
    `<span>${ElevenZeroApp.escapeHtml(condition)}</span>`,
    `<span>${ElevenZeroApp.escapeHtml(theme.label)}</span>`,
  ]
    .filter(Boolean)
    .join("");

  const previewArt = coverImage
    ? `<img class="seller-preview-photo" src="${ElevenZeroApp.escapeHtml(
        coverImage
      )}" alt="Draft listing preview" />`
    : `<div class="seller-preview-graphic ${ElevenZeroApp.escapeHtml(theme.artClass)}">
         <div class="paddle-graphic ${ElevenZeroApp.escapeHtml(theme.paddleClass)}"></div>
       </div>`;

  sellerLivePreview.innerHTML = `
    <article class="seller-preview-market-card">
      <div class="seller-preview-art">
        ${previewArt}
        <span class="seller-preview-badge">${ElevenZeroApp.escapeHtml(statusLabel)}</span>
      </div>
      <div class="seller-preview-body">
        <div class="seller-preview-head">
          <div>
            <p class="product-brand">${ElevenZeroApp.escapeHtml(brand)}</p>
            <h3>${ElevenZeroApp.escapeHtml(model)}</h3>
          </div>
          <span class="price">${ElevenZeroApp.escapeHtml(formatMoneyLabel(price) || "Add price")}</span>
        </div>
        <div class="seller-preview-specs">${specs}</div>
        <p class="seller-preview-copy">${ElevenZeroApp.escapeHtml(
          notes || "Your condition notes and buyer details will appear here as you type."
        )}</p>
        <div class="seller-preview-meta">
          <span>${ElevenZeroApp.escapeHtml(location)}</span>
          <span>${ElevenZeroApp.escapeHtml(shippingLabel)}</span>
          ${shippingMeta ? `<span>${ElevenZeroApp.escapeHtml(shippingMeta)}</span>` : ""}
          <span>${ElevenZeroApp.escapeHtml(
            listingState.draftImages.length
              ? `${listingState.draftImages.length} photo${listingState.draftImages.length === 1 ? "" : "s"}`
              : "No photos yet"
          )}</span>
        </div>
      </div>
    </article>
  `;
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
  const approvalStatus = item.approval_status || "approved";

  if (isOwner) {
    if (approvalStatus === "pending") {
      return {
        action: "disabled",
        buttonLabel: "Under review",
        statusLabel: "Pending review",
        reason: "This listing is waiting for Eleven Zero PB approval before shoppers can see it.",
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
      reason: "You’re viewing your own listing from the buyer side.",
      tone: "neutral",
    };
  }

  if (item.checkout_available) {
    if (ElevenZeroApp.session?.authenticated) {
      return {
        action: "checkout",
        buttonLabel: "View shipping + buy",
        statusLabel: "Secure checkout ready",
        reason: "Open the full listing to enter the delivery address and see the delivered total before checkout.",
        tone: "ready",
      };
    }

    return {
      action: "auth",
      buttonLabel: "Sign in to buy",
      statusLabel: "Secure checkout ready",
      reason: "Sign in first, then the full listing page will guide the shipping estimate before checkout.",
      tone: "ready",
    };
  }

  if (!ElevenZeroApp.config.stripeConfigured) {
    return {
      action: "disabled",
      buttonLabel: "Checkout coming soon",
      statusLabel: "Checkout update",
      reason: item.checkout_reason || "This listing can be viewed now while online checkout is being finalized.",
      tone: "neutral",
    };
  }

  if (!item.seller_user_id) {
    return {
      action: "disabled",
      buttonLabel: "Preview listing",
      statusLabel: "Featured listing",
      reason: item.checkout_reason || "Open the listing page to see more details while more seller inventory comes online.",
      tone: "neutral",
    };
  }

  return {
    action: "disabled",
    buttonLabel: "Checkout pending",
      statusLabel: "Seller setup pending",
    reason:
      item.checkout_reason ||
      "This seller is finishing the final account steps before online checkout is enabled.",
    tone: "pending",
  };
}

function renderListingArt(item, theme, detailHref) {
  const primaryImage = getPrimaryImage(item);
  const title = `${item.brand} ${item.model}`;
  const hintLabel = item.images?.length > 1 ? "Open photo gallery" : "View details";
  const galleryPreview = buildListingGalleryPreview(item);

  if (primaryImage) {
    return `
      <a
        class="listing-photo-link"
        href="${ElevenZeroApp.escapeHtml(detailHref)}"
        aria-label="${ElevenZeroApp.escapeHtml(`View details for ${title}`)}"
      >
        <img
          class="listing-photo"
          src="${ElevenZeroApp.escapeHtml(primaryImage)}"
          alt="${ElevenZeroApp.escapeHtml(title)}"
        />
        <span class="listing-photo-hint">${ElevenZeroApp.escapeHtml(hintLabel)}</span>
      </a>
      ${galleryPreview}
    `;
  }

  return `
    <a
      class="listing-photo-link listing-photo-link-fallback"
      href="${ElevenZeroApp.escapeHtml(detailHref)}"
      aria-label="${ElevenZeroApp.escapeHtml(`View details for ${title}`)}"
    >
      <div class="paddle-graphic ${ElevenZeroApp.escapeHtml(theme.paddleClass)}"></div>
      <span class="listing-photo-hint">${ElevenZeroApp.escapeHtml(hintLabel)}</span>
    </a>
  `;
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
        ${renderListingArt(item, theme, detailHref)}
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
            <a class="listing-title-link" href="${detailHref}">
              <p class="product-brand">${ElevenZeroApp.escapeHtml(item.brand)}</p>
              <h3>${ElevenZeroApp.escapeHtml(item.model)}</h3>
            </a>
          </div>
          <span class="price">${ElevenZeroApp.formatMoney(item.price_usd)}</span>
        </div>
        ${buildListingSpecs(item)}
        <p class="product-copy">${ElevenZeroApp.escapeHtml(truncateCopy(item.notes))}</p>
        <div class="card-footer">
          <span>${ElevenZeroApp.escapeHtml(theme.label)}</span>
          <span>${ElevenZeroApp.escapeHtml(item.location)}</span>
          <span>${ElevenZeroApp.escapeHtml(item.shipping_policy_label || item.shipping?.label || "Shipping at checkout")}</span>
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
    listingState.location,
    listingState.brand,
    listingState.color,
    listingState.thickness ? `${listingState.thickness} mm` : "",
    listingState.condition,
    listingState.minPrice ? `from $${listingState.minPrice}` : "",
    listingState.maxPrice ? `up to $${listingState.maxPrice}` : "",
    listingState.photoMode ? `${listingState.photoMode}+ photos` : "",
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
          ? `Nothing matched ${ElevenZeroApp.escapeHtml(filterSummary)}. Try widening the filters or checking a different brand, color, or price range.`
          : "Try another filter or sign in to create a new paddle listing."
      }</p>
    </article>
  `;
}

function getVisibleListings() {
  const query = listingState.query;
  const normalizedQuery = normalizeFilterValue(query);
  const locationQuery = listingState.location;
  const selectedBrand = normalizeFilterValue(listingState.brand);
  const selectedColor = normalizeFilterValue(listingState.color);
  const selectedThickness = String(listingState.thickness || "").trim();
  const selectedCondition = normalizeFilterValue(listingState.condition);
  const minPrice = Number(listingState.minPrice);
  const maxPrice = Number(listingState.maxPrice);
  const photoMinimum = Number(listingState.photoMode || 0);

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

    if (locationQuery && !valueIncludesAllTokens(item.location, locationQuery)) {
      return false;
    }

    if (Number.isFinite(minPrice) && minPrice > 0 && Number(item.price_usd || 0) < minPrice) {
      return false;
    }

    if (Number.isFinite(maxPrice) && maxPrice > 0 && Number(item.price_usd || 0) > maxPrice) {
      return false;
    }

    if (photoMinimum > 0 && (item.images?.length || 0) < photoMinimum) {
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
  if (locationInput) locationInput.value = listingState.location;
  if (minPriceInput) minPriceInput.value = listingState.minPrice;
  if (sortSelect) sortSelect.value = listingState.sortMode;
  if (maxPriceInput) maxPriceInput.value = listingState.maxPrice;
  if (photoSelect) photoSelect.value = listingState.photoMode;
  if (brandSelect) listingState.brand = brandSelect.value || "";
  if (colorSelect) listingState.color = colorSelect.value || "";
  if (thicknessSelect) listingState.thickness = thicknessSelect.value || "";
  if (conditionSelect) listingState.condition = conditionSelect.value || "";
}

function renderBrandPills() {
  if (!listingBrandPills) return;

  const brandCounts = listingState.items.reduce((counts, item) => {
    const brand = String(item.brand || "").trim();
    if (!brand) return counts;
    counts[brand] = (counts[brand] || 0) + 1;
    return counts;
  }, {});

  const brands = Object.entries(brandCounts)
    .sort((left, right) => {
      if (right[1] !== left[1]) return right[1] - left[1];
      return left[0].localeCompare(right[0]);
    })
    .slice(0, 6);

  if (!brands.length) {
    listingBrandPills.innerHTML =
      '<span class="listing-quick-brands-label">Popular brands will appear here as more paddles are added.</span>';
    return;
  }

  listingBrandPills.innerHTML = `
    <span class="listing-quick-brands-label">Quick brand search</span>
    ${brands
      .map(
        ([brand, count]) => `
          <button
            class="listing-quick-brand${listingState.brand === brand ? " is-active" : ""}"
            type="button"
            data-quick-brand="${ElevenZeroApp.escapeHtml(brand)}"
          >
            ${ElevenZeroApp.escapeHtml(brand)}
            <span>${count}</span>
          </button>
        `
      )
      .join("")}
  `;

  listingBrandPills.querySelectorAll("[data-quick-brand]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextBrand = button.dataset.quickBrand || "";
      listingState.brand = listingState.brand === nextBrand ? "" : nextBrand;
      if (brandSelect) brandSelect.value = listingState.brand;
      persistMarketplaceBrowseState();
      renderListings();
    });
  });
}

function renderSellerReadiness() {
  if (!sellerReadinessTitle || !sellerReadinessPill || !sellerReadinessCopy || !sellerReadinessGrid) {
    return;
  }

  const basicsReady = Boolean(
    listingForm?.querySelector('input[name="brand"]')?.value?.trim() &&
      listingForm?.querySelector('input[name="model"]')?.value?.trim() &&
      listingForm?.querySelector('input[name="price"]')?.value?.trim()
  );
  const buyerClarityReady = Boolean(
    listingForm?.querySelector('input[name="location"]')?.value?.trim() &&
      listingForm?.querySelector('textarea[name="notes"]')?.value?.trim()
  );
  const shippingConfig = getDraftShippingConfig();
  const flatShippingAmount = Number((shippingConfig.flat || "").replace(/[^\d]/g, ""));
  const calculatedShippingReady = Boolean(shippingConfig.originZip);
  const shippingReady =
    shippingConfig.mode === "free" ||
    (shippingConfig.mode === "flat" && flatShippingAmount > 0) ||
    (shippingConfig.mode === "calculated" && calculatedShippingReady);
  const photosReady = listingState.draftImages.length > 0;
  const signedIn = Boolean(ElevenZeroApp.session?.authenticated);
  const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;
  const payoutsReady = Boolean(sellerProfile?.readyForPayouts);

  const completedSteps = [signedIn, basicsReady, buyerClarityReady, shippingReady, photosReady].filter(Boolean).length;
  sellerReadinessPill.textContent = `${completedSteps}/5 ready`;

  if (!signedIn) {
    sellerReadinessTitle.textContent = "Sign in to start selling";
    sellerReadinessCopy.textContent =
      "Create or sign in to your account so you can save your listing and submit it for Eleven Zero PB review.";
  } else if (completedSteps < 5) {
    sellerReadinessTitle.textContent = "You are building a strong listing";
    sellerReadinessCopy.textContent =
      payoutsReady
        ? "Finish the remaining listing and shipping details below and this paddle will be ready to submit for review."
        : "Finish the remaining listing and shipping details below. You can submit first and finish payout setup later from the Account page.";
  } else if (payoutsReady) {
    sellerReadinessTitle.textContent = "Ready to submit";
    sellerReadinessCopy.textContent =
      "Your listing, shipping setup, and seller account all look complete. Submit it when you are ready and we’ll review it before it goes live.";
  } else {
    sellerReadinessTitle.textContent = "Ready for review";
    sellerReadinessCopy.textContent =
      "Your listing can be submitted now. Finish payout setup later in Account before online checkout is enabled.";
  }

  sellerReadinessGrid.innerHTML = [
    sellerChecklistItem("Account", signedIn, signedIn ? "Signed in and ready." : "Sign in to continue."),
    sellerChecklistItem("Basics", basicsReady, basicsReady ? "Brand, model, and price added." : "Add brand, model, and price."),
    sellerChecklistItem(
      "Buyer clarity",
      buyerClarityReady,
      buyerClarityReady ? "Location and notes help buyers trust the listing." : "Add shipping location and condition notes."
    ),
    sellerChecklistItem(
      "Shipping",
      shippingReady,
      shippingReady ? shippingModeHelp(shippingConfig) : "Choose free, flat, or calculated shipping."
    ),
    sellerChecklistItem(
      "Photos",
      photosReady,
      photosReady ? `${listingState.draftImages.length} photo${listingState.draftImages.length === 1 ? "" : "s"} ready.` : "Add at least one photo."
    ),
    sellerChecklistItem(
      "Payouts later",
      payoutsReady,
      payoutsReady ? "Seller payments already look ready." : "Finish payout setup later in Account for checkout."
    ),
  ].join("");
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
          "Sign in to view delivery pricing and continue to checkout.",
          "warning"
        );
        window.setTimeout(() => {
          ElevenZeroApp.redirectToAuth(`./listing.html?id=${encodeURIComponent(listingId)}#shipping`);
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
    updatePhotoMeta();
    renderSellerDraftStatus();
    renderSellerReadiness();
    renderSellerLivePreview();
    return;
  }

  if (!listingState.draftImages.length) {
    photoPreview.innerHTML = `
      <div class="seller-photo-placeholder">
        Photo thumbnails will appear here after you upload them.
      </div>
    `;
    updatePhotoMeta();
    renderSellerDraftStatus();
    renderSellerReadiness();
    renderSellerLivePreview();
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
          ${
            index > 0
              ? `<div class="seller-photo-thumb-actions">
                  <button class="seller-photo-cover" type="button" data-make-cover="${index}">
                    Make cover
                  </button>
                </div>`
              : ""
          }
          <figcaption>${index === 0 ? "This image shows first in the marketplace." : "Included in the listing gallery."}</figcaption>
        </figure>
      `
    )
    .join("");

  updatePhotoMeta();
  renderSellerDraftStatus();
  renderSellerReadiness();
  renderSellerLivePreview();
}

function renderSearchSummary(visible) {
  if (!listingSearchSummary) return;

  const activeFilters = [
    listingState.filter !== "all" ? `style: ${listingState.filter}` : "",
    listingState.location ? `location: ${listingState.location}` : "",
    listingState.brand ? `brand: ${listingState.brand}` : "",
    listingState.color ? `color: ${listingState.color}` : "",
    listingState.thickness ? `thickness: ${listingState.thickness} mm` : "",
    listingState.condition ? `condition: ${listingState.condition}` : "",
    listingState.minPrice ? `min price: $${listingState.minPrice}` : "",
    listingState.maxPrice ? `max price: $${listingState.maxPrice}` : "",
    listingState.photoMode ? `${listingState.photoMode}+ photo${listingState.photoMode === "1" ? "" : "s"}` : "",
    listingState.query ? `search: “${listingState.query}”` : "",
  ].filter(Boolean);

  const filtersLabel = activeFilters.length ? activeFilters.join(" · ") : "all marketplace listings";
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
    listingHeading.textContent = `${visible.length} listing${visible.length === 1 ? "" : "s"} found`;
  }

  renderSearchSummary(visible);
  renderBrandPills();
  renderActiveFilters();
  renderSellerReadiness();
  renderSellerLivePreview();

  const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;

  if (listingNote) {
    if (
      listingState.query ||
      listingState.location ||
      listingState.brand ||
      listingState.color ||
      listingState.thickness ||
      listingState.minPrice ||
      listingState.maxPrice ||
      listingState.photoMode
    ) {
      const activeFilters = [
        listingState.location || "all locations",
        listingState.brand || "all brands",
        listingState.color || "all colors",
        listingState.thickness ? `${listingState.thickness} mm` : "any thickness",
        listingState.minPrice ? `from $${listingState.minPrice}` : "",
        listingState.maxPrice ? `up to $${listingState.maxPrice}` : "",
        listingState.photoMode ? `${listingState.photoMode}+ photos` : "",
      ]
        .filter(Boolean)
        .join(" · ");
      listingNote.textContent = `Search results update live while you browse. Current filters: ${activeFilters}.`;
    } else {
      listingNote.textContent = !ElevenZeroApp.session?.authenticated
        ? "Want to sell too? Sign in and submit your own paddle listing for review."
        : !sellerProfile?.connectConfigured
          ? "You can submit listings for review now. Online checkout is being finalized for sellers."
          : !sellerProfile?.readyForPayouts
            ? "You can submit listings for review now. Finish your payout setup in Account before online checkout is enabled on your listings."
            : "You are signed in and ready to manage your marketplace listings.";
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
  persistMarketplaceBrowseState();
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
      "Your checkout step finished successfully. Sign in again if you want us to confirm the order details here.",
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
    window.location.href = `./listing.html?id=${encodeURIComponent(listingId)}#shipping`;
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

async function prepareListingPhotos(fileList, remainingSlots = 4) {
  const incomingFiles = Array.from(fileList || []);
  const imageFiles = incomingFiles.filter((file) => file.type.startsWith("image/"));
  const files = imageFiles.slice(0, Math.max(0, remainingSlots));

  const images = [];

  for (const file of files) {
    const rawDataUrl = await readFileAsDataUrl(file);
    const optimized = await optimizeImage(rawDataUrl);
    images.push(optimized);
  }

  return {
    images,
    skippedCount: Math.max(0, imageFiles.length - files.length),
    ignoredCount: Math.max(0, incomingFiles.length - imageFiles.length),
  };
}

async function handlePhotoSelection(fileList = photoInput?.files) {
  if (!fileList?.length) {
    renderPhotoPreview();
    return;
  }

  const remainingSlots = Math.max(0, 4 - listingState.draftImages.length);
  if (!remainingSlots) {
    ElevenZeroApp.setStatus(
      listingStatus,
      "You already have 4 photos selected. Remove one first if you want to replace it.",
      "warning"
    );
    if (photoInput) photoInput.value = "";
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
    const prepared = await prepareListingPhotos(fileList, remainingSlots);
    listingState.draftImages = [...listingState.draftImages, ...prepared.images];
    renderPhotoPreview();

    const messageBits = [
      `${listingState.draftImages.length} photo${
        listingState.draftImages.length === 1 ? "" : "s"
      } ready for review.`,
      "The first photo will be used as the cover image.",
      prepared.skippedCount
        ? `${prepared.skippedCount} extra photo${prepared.skippedCount === 1 ? " was" : "s were"} skipped because the limit is 4.`
        : "",
      prepared.ignoredCount
        ? `${prepared.ignoredCount} file${prepared.ignoredCount === 1 ? " was" : "s were"} ignored because only image uploads are supported.`
        : "",
    ].filter(Boolean);

    ElevenZeroApp.setStatus(
      listingStatus,
      messageBits.join(" "),
      "success"
    );
  } catch (error) {
    renderPhotoPreview();
    ElevenZeroApp.setStatus(listingStatus, error.message, "error");
  } finally {
    listingState.imageProcessing = false;
    if (photoInput) photoInput.value = "";
    renderPhotoPreview();
  }
}

async function handleListingSubmit(event) {
  event.preventDefault();

  if (!ElevenZeroApp.requireAuth(listingStatus, "Sign in to submit your listing for review.")) {
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
      "Please add at least one paddle photo before submitting the listing for review.",
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
    listingState.sellerDraftSavedAt = "";
    removeStorageItem(SELLER_DRAFT_STORAGE_KEY);
    syncShippingFormState();
    updateSellerNotesCounter();
    renderPhotoPreview();
    renderSellerDraftStatus();

    const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;
    ElevenZeroApp.setStatus(
      listingStatus,
      sellerProfile?.readyForPayouts
        ? `${payload.brand} ${payload.model} was submitted for review. Once approved, it will go live with its own detail page.`
        : `${payload.brand} ${payload.model} was submitted for review. Next step: finish payout setup in Account before online checkout is enabled after approval.`,
      "success"
    );
    await loadListings();
    renderSellerReadiness();
    renderSellerLivePreview();
  } catch (error) {
    ElevenZeroApp.setStatus(listingStatus, error.message, "error");
  }
}

function syncSearchState() {
  listingState.query = searchInput?.value?.trim() || "";
  listingState.location = locationInput?.value?.trim() || "";
  listingState.brand = brandSelect?.value || "";
  listingState.color = colorSelect?.value || "";
  listingState.thickness = thicknessSelect?.value || "";
  listingState.condition = conditionSelect?.value || "";
  listingState.minPrice = minPriceInput?.value?.trim() || "";
  listingState.maxPrice = maxPriceInput?.value?.trim() || "";
  listingState.photoMode = photoSelect?.value || "";
  listingState.sortMode = sortSelect?.value || "relevance";
  persistMarketplaceBrowseState();
  renderListings();
}

function resetSearchState() {
  listingState.filter = "all";
  listingState.query = "";
  listingState.location = "";
  listingState.brand = "";
  listingState.color = "";
  listingState.thickness = "";
  listingState.condition = "";
  listingState.minPrice = "";
  listingState.maxPrice = "";
  listingState.photoMode = "";
  listingState.sortMode = "relevance";

  if (searchInput) searchInput.value = "";
  if (locationInput) locationInput.value = "";
  if (brandSelect) brandSelect.value = "";
  if (colorSelect) colorSelect.value = "";
  if (thicknessSelect) thicknessSelect.value = "";
  if (conditionSelect) conditionSelect.value = "";
  if (minPriceInput) minPriceInput.value = "";
  if (maxPriceInput) maxPriceInput.value = "";
  if (photoSelect) photoSelect.value = "";
  if (sortSelect) sortSelect.value = "relevance";

  persistMarketplaceBrowseState();
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
      ? `${listingState.draftImages.length} photo${listingState.draftImages.length === 1 ? "" : "s"} ready for review.`
      : "Photo previews cleared. Add images to continue.",
    listingState.draftImages.length ? "success" : "warning"
  );
}

function moveDraftPhotoToCover(index) {
  if (index <= 0 || index >= listingState.draftImages.length) return;

  const nextImages = [...listingState.draftImages];
  const [selectedImage] = nextImages.splice(index, 1);
  nextImages.unshift(selectedImage);
  listingState.draftImages = nextImages;
  renderPhotoPreview();
  ElevenZeroApp.setStatus(
    listingStatus,
    "Cover photo updated. Buyers will see this image first in the marketplace.",
    "success"
  );
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  restoreMarketplaceBrowseState();
  restoreSellerDraft();
  syncShippingFormState();
  updateSellerNotesCounter();
  renderPhotoPreview();
  renderSellerReadiness();
  renderSellerLivePreview();
  try {
    await loadListings();
  } catch (error) {
    const previewMessage =
      window.location.protocol === "file:"
        ? "Listings load when this page is opened through the local preview server or live site."
        : error.message;

    setMarketplaceStatus(previewMessage, "warning");
  }

  try {
    await handleCheckoutReturn();
  } catch (error) {
    setMarketplaceStatus(error.message, "warning");
  }

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      listingState.filter = button.dataset.filter || "all";
      persistMarketplaceBrowseState();
      renderListings();
    });
  });

  searchInput?.addEventListener("input", syncSearchState);
  locationInput?.addEventListener("input", syncSearchState);
  brandSelect?.addEventListener("change", syncSearchState);
  colorSelect?.addEventListener("change", syncSearchState);
  thicknessSelect?.addEventListener("change", syncSearchState);
  conditionSelect?.addEventListener("change", syncSearchState);
  minPriceInput?.addEventListener("input", syncSearchState);
  maxPriceInput?.addEventListener("input", syncSearchState);
  photoSelect?.addEventListener("change", syncSearchState);
  sortSelect?.addEventListener("change", syncSearchState);
  resetSearchButton?.addEventListener("click", resetSearchState);
  searchForm?.addEventListener("submit", (event) => event.preventDefault());
  photoInput?.addEventListener("change", handlePhotoSelection);
  listingForm?.addEventListener("submit", handleListingSubmit);
  listingForm?.addEventListener("input", () => {
    updateSellerNotesCounter();
    saveSellerDraft();
    renderSellerReadiness();
    renderSellerLivePreview();
  });
  listingForm?.addEventListener("change", () => {
    syncShippingFormState();
    updateSellerNotesCounter();
    saveSellerDraft();
    renderSellerReadiness();
    renderSellerLivePreview();
  });
  clearSellerDraftButton?.addEventListener("click", clearSellerDraft);
  photoDropzone?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    photoInput?.click();
  });
  ["dragenter", "dragover"].forEach((eventName) => {
    photoDropzone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      photoDropzone.classList.add("is-dragging");
    });
  });
  ["dragleave", "dragend", "drop"].forEach((eventName) => {
    photoDropzone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      photoDropzone.classList.remove("is-dragging");
    });
  });
  photoDropzone?.addEventListener("drop", async (event) => {
    const fileList = event.dataTransfer?.files;
    await handlePhotoSelection(fileList);
  });
  photoPreview?.addEventListener("click", (event) => {
    const coverButton = event.target.closest("[data-make-cover]");
    if (coverButton) {
      moveDraftPhotoToCover(Number(coverButton.dataset.makeCover || -1));
      return;
    }

    const button = event.target.closest("[data-remove-photo]");
    if (!button) return;
    removeDraftPhoto(Number(button.dataset.removePhoto || -1));
  });
});

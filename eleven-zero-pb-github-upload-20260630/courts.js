const SEARCH_PROVIDERS = {
  geocodeUrl: "https://nominatim.openstreetmap.org/search",
  overpassUrl: "https://overpass-api.de/api/interpreter",
};

const CACHE_KEY = "eleven-zero-pb-court-finder-cache-v2";
const PREF_KEY = "eleven-zero-pb-court-search-pref-v1";
const CACHE_TTL_MS = 1000 * 60 * 60 * 12;

const defaultCourts = [
  {
    id: "sample-miami",
    name: "Central Park Community Courts",
    location: "Miami, FL",
    accessKind: "free",
    accessLabel: "Free",
    surfaceKind: "outdoor",
    surfaceLabel: "Outdoor",
    details: ["8 courts", "Open play friendly", "First come, first served"],
    description:
      "Public park courts with steady evening traffic, lights, and a more casual drop-in feel.",
    tags: ["free", "outdoor"],
    source: "sample",
    lat: 25.7617,
    lon: -80.1918,
  },
  {
    id: "sample-austin",
    name: "Northside Pickleball Club",
    location: "Austin, TX",
    accessKind: "paid",
    accessLabel: "Paid",
    surfaceKind: "indoor",
    surfaceLabel: "Indoor",
    details: ["12 courts", "Reservation based", "Day pass available"],
    description:
      "Premium facility layout where players expect memberships, reserved play, clinics, and climate-controlled courts.",
    tags: ["paid", "indoor"],
    source: "sample",
    lat: 30.2672,
    lon: -97.7431,
  },
  {
    id: "sample-charlotte",
    name: "West Rec Center Courts",
    location: "Charlotte, NC",
    accessKind: "free",
    accessLabel: "Free",
    surfaceKind: "indoor",
    surfaceLabel: "Indoor",
    details: ["4 courts", "Community rec center", "Scheduled hours"],
    description:
      "A free indoor option that helps players find weather-safe community courts.",
    tags: ["free", "indoor"],
    source: "sample",
    lat: 35.2271,
    lon: -80.8431,
  },
  {
    id: "sample-scottsdale",
    name: "Desert Paddle Social Club",
    location: "Scottsdale, AZ",
    accessKind: "paid",
    accessLabel: "Paid",
    surfaceKind: "outdoor",
    surfaceLabel: "Outdoor",
    details: ["10 courts", "Booking required", "Open play sessions"],
    description:
      "Outdoor premium club listing with drop-in sessions, coaching, and polished reservation rules.",
    tags: ["paid", "outdoor"],
    source: "sample",
    lat: 33.4942,
    lon: -111.9261,
  },
  {
    id: "sample-nashville",
    name: "Lakeview City Courts",
    location: "Nashville, TN",
    accessKind: "free",
    accessLabel: "Free",
    surfaceKind: "outdoor",
    surfaceLabel: "Outdoor",
    details: ["6 courts", "Lights available", "No reservation"],
    description:
      "Good for after-work play, community ladders, and pickup sessions without a paywall.",
    tags: ["free", "outdoor"],
    source: "sample",
    lat: 36.1627,
    lon: -86.7816,
  },
  {
    id: "sample-denver",
    name: "Elevate Indoor Pickleball",
    location: "Denver, CO",
    accessKind: "paid",
    accessLabel: "Paid",
    surfaceKind: "indoor",
    surfaceLabel: "Indoor",
    details: ["14 courts", "Membership or guest pass", "Leagues and clinics"],
    description:
      "A strong fit for the paid-facility side of the directory, where players expect booking options and a premium experience.",
    tags: ["paid", "indoor"],
    source: "sample",
    lat: 39.7392,
    lon: -104.9903,
  },
  {
    id: "sample-sandiego",
    name: "Harbor Park Pickleball Lines",
    location: "San Diego, CA",
    accessKind: "free",
    accessLabel: "Free",
    surfaceKind: "outdoor",
    surfaceLabel: "Outdoor",
    details: ["4 courts", "Shared public access", "Morning play crowd"],
    description:
      "Public-use lines at a neighborhood park for players searching specifically for free sessions.",
    tags: ["free", "outdoor"],
    source: "sample",
    lat: 32.7157,
    lon: -117.1611,
  },
  {
    id: "sample-tampa",
    name: "Sunset Racquet & Paddle",
    location: "Tampa, FL",
    accessKind: "paid",
    accessLabel: "Paid",
    surfaceKind: "outdoor",
    surfaceLabel: "Outdoor",
    details: ["9 courts", "Guest fee", "Round robins and events"],
    description:
      "A hybrid social-club feel where players pay to access a more organized schedule and stronger event calendar.",
    tags: ["paid", "outdoor"],
    source: "sample",
    lat: 27.9506,
    lon: -82.4572,
  },
];

const filterButtons = Array.from(
  document.querySelectorAll("[data-court-filter]")
);
const quickSearchButtons = Array.from(
  document.querySelectorAll("[data-quick-search]")
);

const finderForm = document.querySelector("[data-court-search-form]");
const finderStatus = document.querySelector("[data-finder-status]");
const resultsHeading = document.querySelector("[data-results-heading]");
const resultsNote = document.querySelector("[data-results-note]");
const resultsGrid = document.querySelector("[data-court-results]");
const mapContainer = document.querySelector("[data-court-map]");
const mapSelection = document.querySelector("[data-map-selection]");
const mapStatus = document.querySelector("[data-map-status]");
const summaryTotal = document.querySelector("[data-summary-total]");
const summaryFree = document.querySelector("[data-summary-free]");
const summaryPaid = document.querySelector("[data-summary-paid]");
const summaryCheck = document.querySelector("[data-summary-check]");
const courtReportSummary = document.querySelector("[data-court-report-summary]");
const courtReportList = document.querySelector("[data-court-report-list]");
const courtReportForm = document.querySelector("[data-court-report-form]");
const courtReportStatus = document.querySelector("[data-court-report-status]");
const courtReportTarget = document.querySelector("[data-court-report-target]");

const searchInput = finderForm?.querySelector('input[name="query"]');
const radiusSelect = finderForm?.querySelector('select[name="radius"]');
const submitButton = finderForm?.querySelector('button[type="submit"]');
const reportSubmitButton = courtReportForm?.querySelector('button[type="submit"]');

const COURT_BUSYNESS_LABELS = {
  1: "Quiet",
  2: "Moderate",
  3: "Busy",
  4: "Packed",
};

const COURT_PLAYER_LEVEL_LABELS = {
  beginner: "Beginner-friendly",
  intermediate: "Intermediate-heavy",
  advanced: "Advanced-heavy",
  mixed: "Mixed levels",
};

const state = {
  courts: [...defaultCourts],
  activeFilter: "all",
  source: "sample",
  locationLabel: "Starter city examples",
  lastQuery: "",
  radiusMiles: Number(radiusSelect?.value || 25),
  isSearching: false,
  visibleCourts: [...defaultCourts],
  activeCourtId: defaultCourts[0]?.id || "",
  courtSummaries: {},
  courtReportsByCourt: {},
  isSubmittingCourtReport: false,
};

const mapState = {
  instance: null,
  tileLayer: null,
  markerLayer: null,
  markers: [],
  mappableCourts: [],
  activeCourtId: "",
  ready: false,
  centerLat: 39.8283,
  centerLon: -98.5795,
  zoom: 4,
  dragStartX: 0,
  dragStartY: 0,
  dragStartLat: 39.8283,
  dragStartLon: -98.5795,
  isDragging: false,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setFinderStatus(message, tone = "neutral") {
  if (!finderStatus) return;

  finderStatus.textContent = message;
  finderStatus.classList.remove("is-success", "is-warning", "is-error");

  if (tone === "success") finderStatus.classList.add("is-success");
  if (tone === "warning") finderStatus.classList.add("is-warning");
  if (tone === "error") finderStatus.classList.add("is-error");
}

function setMapStatus(message, tone = "neutral") {
  if (!mapStatus) return;

  mapStatus.textContent = message;
  mapStatus.classList.remove("is-success", "is-warning", "is-error");

  if (tone === "success") mapStatus.classList.add("is-success");
  if (tone === "warning") mapStatus.classList.add("is-warning");
  if (tone === "error") mapStatus.classList.add("is-error");
}

function setCourtReportStatus(message, tone = "neutral") {
  if (!courtReportStatus) return;

  courtReportStatus.textContent = message;
  courtReportStatus.classList.remove("is-success", "is-warning", "is-error");

  if (tone === "success") courtReportStatus.classList.add("is-success");
  if (tone === "warning") courtReportStatus.classList.add("is-warning");
  if (tone === "error") courtReportStatus.classList.add("is-error");
}

function setCourtReportSubmitting(nextValue) {
  state.isSubmittingCourtReport = nextValue;

  if (!courtReportForm) return;

  courtReportForm.querySelectorAll("select, textarea, button").forEach((field) => {
    field.disabled = nextValue;
  });

  if (reportSubmitButton) {
    reportSubmitButton.textContent = nextValue ? "Posting report..." : "Post court report";
  }
}

function formatCourtStars(value) {
  const rounded = Math.round(Number(value || 0));
  return "★".repeat(Math.max(0, rounded)) || "—";
}

function formatCourtDate(value) {
  if (!value) return "Recently";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}

function getActiveCourt() {
  return (
    state.visibleCourts.find((court) => court.id === state.activeCourtId) ||
    state.courts.find((court) => court.id === state.activeCourtId) ||
    state.visibleCourts[0] ||
    null
  );
}

function buildCourtReportQuickMarkup(court) {
  const summary = state.courtSummaries[court.id];
  if (!summary) {
    return `
      <div class="court-rating-strip">
        <span class="court-rating-pill">No reports yet</span>
        <span class="court-rating-copy">Be the first to share court condition, crowd, and player level.</span>
      </div>
    `;
  }

  return `
    <div class="court-rating-strip">
      <span class="court-rating-pill">${escapeHtml(summary.conditionLabel)}</span>
      <span class="court-rating-copy">${escapeHtml(summary.reportCount)} report${
        summary.reportCount === 1 ? "" : "s"
      } · ${escapeHtml(summary.busynessLabel)} crowd · ${escapeHtml(summary.playerLevelLabel)}</span>
    </div>
  `;
}

function renderCourtCommunity(court) {
  if (!courtReportSummary || !courtReportList || !courtReportTarget) return;

  if (!court) {
    courtReportSummary.innerHTML = `
      <h3>Choose a court from the map or cards.</h3>
      <p class="court-community-empty-copy">
        We’ll show the court condition, crowd level, player mix, and recent player reports here.
      </p>
    `;
    courtReportList.innerHTML = "";
    courtReportTarget.textContent = "Choose a court above first.";
    setCourtReportStatus("Sign in and choose a court if you want to share a court report.");
    return;
  }

  const summary = state.courtSummaries[court.id];
  const reports = state.courtReportsByCourt[court.id] || [];

  if (summary) {
    courtReportSummary.innerHTML = `
      <h3>${escapeHtml(court.name)}</h3>
      <p class="court-community-location">${escapeHtml(court.location)}</p>
      <div class="court-community-stats">
        <article>
          <strong>${escapeHtml(String(summary.conditionAverage))}</strong>
          <span>Condition · ${escapeHtml(summary.conditionLabel)}</span>
        </article>
        <article>
          <strong>${escapeHtml(summary.busynessLabel)}</strong>
          <span>Crowd level</span>
        </article>
        <article>
          <strong>${escapeHtml(summary.playerLevelLabel)}</strong>
          <span>Player mix</span>
        </article>
        <article>
          <strong>${escapeHtml(String(summary.reportCount))}</strong>
          <span>Community report${summary.reportCount === 1 ? "" : "s"}</span>
        </article>
      </div>
    `;
  } else {
    courtReportSummary.innerHTML = `
      <h3>${escapeHtml(court.name)}</h3>
      <p class="court-community-location">${escapeHtml(court.location)}</p>
      <p class="court-community-empty-copy">
        No player reports are live for this court yet. Be the first to rate the condition, crowd level, and player mix.
      </p>
    `;
  }

  if (reports.length) {
    courtReportList.innerHTML = reports
      .slice(0, 4)
      .map(
        (item) => `
          <article class="court-report-card">
            <div class="court-report-card-head">
              <div>
                <h4>${escapeHtml(item.reviewerName)}</h4>
                <p>${escapeHtml(formatCourtDate(item.createdAt))}</p>
              </div>
              <span class="court-report-stars">${escapeHtml(
                formatCourtStars(item.conditionRating)
              )}</span>
            </div>
            <div class="court-report-meta">
              <span>${escapeHtml(item.busynessLabel)}</span>
              <span>${escapeHtml(item.playerLevelLabel)}</span>
            </div>
            <p>${escapeHtml(item.comment)}</p>
          </article>
        `
      )
      .join("");
  } else {
    courtReportList.innerHTML = `
      <div class="court-report-empty">
        <p>No player notes yet for this court.</p>
      </div>
    `;
  }

  courtReportTarget.textContent = `Share a report for ${court.name}`;
  setCourtReportStatus(
    ElevenZeroApp.session?.authenticated
      ? `Sharing a report for ${court.name}.`
      : "Sign in if you want to post a court report for this location."
  );
}

function setSearching(nextValue) {
  state.isSearching = nextValue;

  if (submitButton) {
    submitButton.disabled = nextValue;
    submitButton.textContent = nextValue
      ? "Searching live courts..."
      : "Search live courts";
  }

  if (searchInput) {
    searchInput.disabled = nextValue;
  }

  if (radiusSelect) {
    radiusSelect.disabled = nextValue;
  }

  quickSearchButtons.forEach((button) => {
    button.disabled = nextValue;
  });
}

function loadJsonStorage(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || "{}");
  } catch {
    return {};
  }
}

function saveJsonStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage write failures for private browsing or quota.
  }
}

function readCache(type, key) {
  const cache = loadJsonStorage(CACHE_KEY);
  const entry = cache?.[type]?.[key];

  if (!entry) return null;
  if (Date.now() - entry.savedAt > CACHE_TTL_MS) return null;

  return entry.data;
}

function writeCache(type, key, data) {
  const cache = loadJsonStorage(CACHE_KEY);
  const nextCache = {
    ...cache,
    [type]: {
      ...(cache[type] || {}),
      [key]: {
        savedAt: Date.now(),
        data,
      },
    },
  };

  saveJsonStorage(CACHE_KEY, nextCache);
}

function saveSearchPreference() {
  saveJsonStorage(PREF_KEY, {
    query: searchInput?.value?.trim() || "",
    radius: Number(radiusSelect?.value || 25),
  });
}

function hydrateSearchPreference() {
  const pref = loadJsonStorage(PREF_KEY);

  if (searchInput && typeof pref.query === "string" && pref.query.trim()) {
    searchInput.value = pref.query.trim();
  }

  if (radiusSelect && Number.isFinite(pref.radius) && pref.radius > 0) {
    radiusSelect.value = String(pref.radius);
    state.radiusMiles = Number(pref.radius);
  }
}

function matchesFilter(court, filter) {
  if (filter === "all") return true;
  return court.tags.includes(filter);
}

function buildTagMarkup(court) {
  const tags = [
    `<span class="court-tag court-tag-${court.accessKind}">${escapeHtml(
      court.accessLabel
    )}</span>`,
  ];

  if (court.surfaceKind !== "unknown") {
    tags.push(
      `<span class="court-tag court-tag-surface">${escapeHtml(
        court.surfaceLabel
      )}</span>`
    );
  }

  if (court.source === "live") {
    tags.push('<span class="court-tag court-tag-live">Live data</span>');
  }

  return tags.join("");
}

function buildDetailMarkup(details) {
  return details
    .filter(Boolean)
    .slice(0, 3)
    .map((detail) => `<span>${escapeHtml(detail)}</span>`)
    .join("");
}

function buildLinkMarkup(court) {
  const links = [];

  if (Number.isFinite(court.lat) && Number.isFinite(court.lon)) {
    links.push(
      `<button class="text-link text-link-button" type="button" data-map-focus="${escapeHtml(
        court.id
      )}">Show on map</button>`
    );
  }

  if (court.website) {
    links.push(
      `<a class="text-link" href="${escapeHtml(
        court.website
      )}" target="_blank" rel="noreferrer">Venue website</a>`
    );
  }

  if (court.osmUrl) {
    links.push(
      `<a class="text-link" href="${escapeHtml(
        court.osmUrl
      )}" target="_blank" rel="noreferrer">Open map reference</a>`
    );
  }

  links.push(
    `<button class="text-link text-link-button" type="button" data-rate-court="${escapeHtml(
      court.id
    )}">Rate this court</button>`
  );

  if (!links.length) return "";

  return `<div class="court-links">${links.join("")}</div>`;
}

function renderCourtCard(court) {
  return `
    <article class="court-card reveal is-visible" data-court-id="${escapeHtml(court.id)}">
      <div class="court-card-top">
        ${buildTagMarkup(court)}
      </div>
      <h3>${escapeHtml(court.name)}</h3>
      <p class="court-location">${escapeHtml(court.location)}</p>
      <div class="court-details">
        ${buildDetailMarkup(court.details)}
      </div>
      <p class="court-copy">${escapeHtml(court.description)}</p>
      ${buildCourtReportQuickMarkup(court)}
      ${buildLinkMarkup(court)}
    </article>
  `;
}

function renderEmptyState(totalCount) {
  const copy =
    totalCount > 0
      ? "No listings match the current filter. Try switching back to All or widening the radius."
      : "No pickleball listings came back for this search yet. Try a nearby city or a bigger radius.";

  resultsGrid.innerHTML = `
    <article class="empty-state reveal is-visible">
      <p class="eyebrow">No results</p>
      <h3>Nothing to show just yet.</h3>
      <p>${escapeHtml(copy)}</p>
    </article>
  `;
}

const MAP_TILE_SIZE = 256;
const MAP_MIN_ZOOM = 3;
const MAP_MAX_ZOOM = 16;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function wrapLongitude(lon) {
  if (!Number.isFinite(lon)) return -98.5795;

  let next = lon;
  while (next < -180) next += 360;
  while (next > 180) next -= 360;
  return next;
}

function clampLatitude(lat) {
  return clamp(lat, -85, 85);
}

function latLonToWorld(lat, lon, zoom) {
  const clampedLat = clampLatitude(lat);
  const wrappedLon = wrapLongitude(lon);
  const scale = MAP_TILE_SIZE * 2 ** zoom;
  const x = ((wrappedLon + 180) / 360) * scale;
  const sinLat = Math.sin((clampedLat * Math.PI) / 180);
  const y =
    (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale;

  return { x, y };
}

function worldToLatLon(x, y, zoom) {
  const scale = MAP_TILE_SIZE * 2 ** zoom;
  const lon = (x / scale) * 360 - 180;
  const n = Math.PI - (2 * Math.PI * y) / scale;
  const lat = (180 / Math.PI) * Math.atan(Math.sinh(n));
  return { lat: clampLatitude(lat), lon: wrapLongitude(lon) };
}

function buildMapSelection(court) {
  if (!mapSelection) return;

  if (!court) {
    mapSelection.innerHTML = `
      <p class="eyebrow">Selected court</p>
      <h3>Pick a marker or use a “Show on map” button.</h3>
      <p>
        The map will center the selected court here so players can compare
        the cards with the map view more easily.
      </p>
    `;
    return;
  }

  const detailMarkup = court.details
    .filter(Boolean)
    .slice(0, 3)
    .map((detail) => `<li>${escapeHtml(detail)}</li>`)
    .join("");

  const websiteMarkup = court.website
    ? `<a class="text-link text-link-popup" href="${escapeHtml(
        court.website
      )}" target="_blank" rel="noreferrer">Venue website</a>`
    : "";

  const mapMarkup = court.osmUrl
    ? `<a class="text-link text-link-popup" href="${escapeHtml(
        court.osmUrl
      )}" target="_blank" rel="noreferrer">Open map reference</a>`
    : "";

  const reportMarkup = buildCourtReportQuickMarkup(court);

  mapSelection.innerHTML = `
    <p class="eyebrow">Selected court</p>
    <span class="court-tag court-tag-${escapeHtml(court.accessKind)}">${escapeHtml(
      court.accessLabel
    )}</span>
    <h3>${escapeHtml(court.name)}</h3>
    <p class="court-map-selection-location">${escapeHtml(court.location)}</p>
    <ul>${detailMarkup}</ul>
    <p class="court-map-selection-copy">${escapeHtml(court.description)}</p>
    ${reportMarkup}
    <div class="court-map-popup-links">
      ${websiteMarkup}${mapMarkup}
      <button class="text-link text-link-button text-link-popup" type="button" data-rate-court="${escapeHtml(
        court.id
      )}">Rate this court</button>
    </div>
  `;
}

function highlightCourtCard(courtId) {
  document.querySelectorAll("[data-court-id]").forEach((card) => {
    const isActive = card.dataset.courtId === courtId;
    card.classList.toggle("is-active", isActive);
  });
}

async function loadCourtSummaries(courts) {
  const courtIds = courts.map((court) => court.id).filter(Boolean);
  if (!courtIds.length) {
    state.courtSummaries = {};
    return;
  }

  try {
    const response = await ElevenZeroApp.request(
      `/api/court-reports?courtIds=${encodeURIComponent(courtIds.join(","))}`
    );
    state.courtSummaries = response.summaryByCourt || {};
  } catch {
    state.courtSummaries = {};
  }
}

async function loadCourtReportDetails(court) {
  if (!court) return;

  try {
    const response = await ElevenZeroApp.request(
      `/api/court-reports?courtId=${encodeURIComponent(court.id)}`
    );

    if (state.activeCourtId !== court.id) return;

    if (response.summary) {
      state.courtSummaries[court.id] = response.summary;
    }

    state.courtReportsByCourt[court.id] = response.items || [];
    renderCourtCommunity(court);
  } catch {
    if (state.activeCourtId !== court.id) return;
    state.courtReportsByCourt[court.id] = [];
    renderCourtCommunity(court);
  }
}

function setActiveCourt(courtId, { centerMap = false, scrollMap = false, scrollReport = false } = {}) {
  const court =
    state.visibleCourts.find((entry) => entry.id === courtId) ||
    state.courts.find((entry) => entry.id === courtId);

  if (!court) return;

  state.activeCourtId = court.id;
  mapState.activeCourtId = court.id;
  highlightCourtCard(court.id);
  buildMapSelection(court);
  renderCourtCommunity(court);

  if (mapState.ready) {
    if (centerMap && Number.isFinite(court.lat) && Number.isFinite(court.lon)) {
      setMapView(court.lat, court.lon, Math.max(mapState.zoom, 13));
    } else {
      renderMapSurface();
    }
  }

  if (scrollMap) {
    mapContainer?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (scrollReport) {
    document.querySelector("#court-community")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  loadCourtReportDetails(court);
}

function renderMapSurface() {
  if (!mapState.ready || !mapContainer) return;

  const width = mapContainer.clientWidth;
  const height = mapContainer.clientHeight;

  if (!width || !height) return;

  const zoom = mapState.zoom;
  const centerWorld = latLonToWorld(mapState.centerLat, mapState.centerLon, zoom);
  const leftWorld = centerWorld.x - width / 2;
  const topWorld = centerWorld.y - height / 2;
  const tileCount = 2 ** zoom;
  const maxWorld = MAP_TILE_SIZE * tileCount;
  const minTileX = Math.floor(leftWorld / MAP_TILE_SIZE);
  const maxTileX = Math.floor((leftWorld + width) / MAP_TILE_SIZE);
  const minTileY = Math.floor(topWorld / MAP_TILE_SIZE);
  const maxTileY = Math.floor((topWorld + height) / MAP_TILE_SIZE);

  mapState.tileLayer.innerHTML = "";
  mapState.markerLayer.innerHTML = "";

  for (let tileX = minTileX; tileX <= maxTileX; tileX += 1) {
    for (let tileY = minTileY; tileY <= maxTileY; tileY += 1) {
      if (tileY < 0 || tileY >= tileCount) continue;

      const wrappedX = ((tileX % tileCount) + tileCount) % tileCount;
      const img = document.createElement("img");
      img.className = "court-map-tile";
      img.alt = "";
      img.draggable = false;
      img.src = `https://tile.openstreetmap.org/${zoom}/${wrappedX}/${tileY}.png`;
      img.style.left = `${tileX * MAP_TILE_SIZE - leftWorld}px`;
      img.style.top = `${tileY * MAP_TILE_SIZE - topWorld}px`;
      mapState.tileLayer.appendChild(img);
    }
  }

  mapState.markers.forEach((court) => {
    const markerWorld = latLonToWorld(court.lat, court.lon, zoom);
    let x = markerWorld.x - leftWorld;
    const y = markerWorld.y - topWorld;

    while (x < -32) x += maxWorld;
    while (x > width + 32) x -= maxWorld;

    if (y < -32 || y > height + 32) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = `court-map-marker ${
      court.accessKind
    }${court.id === mapState.activeCourtId ? " is-active" : ""}`;
    button.style.left = `${x}px`;
    button.style.top = `${y}px`;
    button.setAttribute("aria-label", `${court.name}, ${court.location}`);
    button.dataset.courtId = court.id;
    button.innerHTML = `<span class="court-map-pin court-map-pin-${escapeHtml(
      court.accessKind
    )}${court.id === mapState.activeCourtId ? " is-active" : ""}"></span>`;
    button.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });
    button.addEventListener("click", () => {
      focusCourtOnMap(court.id, { scrollIntoView: false });
    });
    mapState.markerLayer.appendChild(button);
  });
}

function setMapView(lat, lon, zoom) {
  mapState.centerLat = clampLatitude(lat);
  mapState.centerLon = wrapLongitude(lon);
  mapState.zoom = clamp(zoom, MAP_MIN_ZOOM, MAP_MAX_ZOOM);
  renderMapSurface();
}

function fitMapToCourts(courts) {
  if (!mapContainer || !courts.length) {
    setMapView(39.8283, -98.5795, 4);
    return;
  }

  if (courts.length === 1) {
    setMapView(courts[0].lat, courts[0].lon, 13);
    return;
  }

  const lats = courts.map((court) => court.lat);
  const lons = courts.map((court) => court.lon);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const centerLat = (minLat + maxLat) / 2;
  const centerLon = (minLon + maxLon) / 2;
  const width = mapContainer.clientWidth || 960;
  const height = mapContainer.clientHeight || 420;

  let bestZoom = MAP_MIN_ZOOM;

  for (let zoom = MAP_MAX_ZOOM; zoom >= MAP_MIN_ZOOM; zoom -= 1) {
    const topLeft = latLonToWorld(maxLat, minLon, zoom);
    const bottomRight = latLonToWorld(minLat, maxLon, zoom);
    const boundsWidth = Math.abs(bottomRight.x - topLeft.x);
    const boundsHeight = Math.abs(bottomRight.y - topLeft.y);

    if (boundsWidth <= width * 0.72 && boundsHeight <= height * 0.58) {
      bestZoom = zoom;
      break;
    }
  }

  setMapView(centerLat, centerLon, bestZoom);
}

function focusCourtOnMap(courtId, { scrollIntoView = true } = {}) {
  if (!mapState.ready) return;
  setActiveCourt(courtId, { centerMap: true, scrollMap: scrollIntoView });
}

function syncMapWithCourts(courts, { fitBounds = false } = {}) {
  if (!mapState.ready) return;

  const mappableCourts = courts.filter(
    (court) => Number.isFinite(court.lat) && Number.isFinite(court.lon)
  );

  mapState.markers = mappableCourts;
  mapState.mappableCourts = mappableCourts;

  if (!mappableCourts.length) {
    state.activeCourtId = "";
    mapState.activeCourtId = "";
    highlightCourtCard("");
    buildMapSelection(null);
    renderCourtCommunity(null);
    setMapView(39.8283, -98.5795, 4);
    setMapStatus(
      "No mappable court coordinates are available in this view yet. Try All, another city, or a wider radius.",
      "warning"
    );
    return;
  }

  if (fitBounds) {
    fitMapToCourts(mappableCourts);
  } else {
    renderMapSurface();
  }

  setMapStatus(
    `Map updated with ${mappableCourts.length} court marker${
      mappableCourts.length === 1 ? "" : "s"
    } for the current view.`,
    "success"
  );
}

function updateMapFromDrag(clientX, clientY) {
  const startWorld = latLonToWorld(
    mapState.dragStartLat,
    mapState.dragStartLon,
    mapState.zoom
  );
  const nextWorld = {
    x: startWorld.x - (clientX - mapState.dragStartX),
    y: startWorld.y - (clientY - mapState.dragStartY),
  };
  const nextCenter = worldToLatLon(nextWorld.x, nextWorld.y, mapState.zoom);
  mapState.centerLat = nextCenter.lat;
  mapState.centerLon = nextCenter.lon;
  renderMapSurface();
}

function initializeCourtMap() {
  if (!mapContainer) return;

  mapContainer.innerHTML = `
    <div class="court-map-surface" data-map-surface>
      <div class="court-map-tile-layer" data-map-tile-layer></div>
      <div class="court-map-marker-layer" data-map-marker-layer></div>
      <div class="court-map-controls" aria-label="Map zoom controls">
        <button type="button" data-map-zoom-in aria-label="Zoom in">+</button>
        <button type="button" data-map-zoom-out aria-label="Zoom out">−</button>
      </div>
    </div>
  `;

  mapState.instance = mapContainer.querySelector("[data-map-surface]");
  mapState.tileLayer = mapContainer.querySelector("[data-map-tile-layer]");
  mapState.markerLayer = mapContainer.querySelector("[data-map-marker-layer]");
  mapState.ready = true;

  mapContainer.addEventListener("pointerdown", (event) => {
    mapState.isDragging = true;
    mapState.dragStartX = event.clientX;
    mapState.dragStartY = event.clientY;
    mapState.dragStartLat = mapState.centerLat;
    mapState.dragStartLon = mapState.centerLon;
    mapContainer.classList.add("is-dragging");
  });

  window.addEventListener("pointermove", (event) => {
    if (!mapState.isDragging) return;
    updateMapFromDrag(event.clientX, event.clientY);
  });

  window.addEventListener("pointerup", () => {
    if (!mapState.isDragging) return;
    mapState.isDragging = false;
    mapContainer.classList.remove("is-dragging");
  });

  mapContainer.addEventListener("wheel", (event) => {
    event.preventDefault();
    const nextZoom = mapState.zoom + (event.deltaY < 0 ? 1 : -1);
    setMapView(mapState.centerLat, mapState.centerLon, nextZoom);
  });

  mapContainer
    .querySelector("[data-map-zoom-in]")
    ?.addEventListener("click", () => {
      setMapView(mapState.centerLat, mapState.centerLon, mapState.zoom + 1);
    });

  mapContainer
    .querySelector("[data-map-zoom-out]")
    ?.addEventListener("click", () => {
      setMapView(mapState.centerLat, mapState.centerLon, mapState.zoom - 1);
    });

  mapContainer.querySelectorAll(".court-map-controls button").forEach((button) => {
    button.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });
  });

  window.addEventListener("resize", () => {
    if (mapState.ready) {
      renderMapSurface();
    }
  });

  buildMapSelection(null);
  setMapView(39.8283, -98.5795, 4);
  setMapStatus(
    "Map ready. Drag to move, use the zoom buttons, or choose a court from the cards below.",
    "success"
  );
}

function updateFilterUi() {
  filterButtons.forEach((button) => {
    const isActive = button.dataset.courtFilter === state.activeFilter;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
}

function updateSummary(allCourts) {
  const counts = allCourts.reduce(
    (totals, court) => {
      totals.total += 1;
      if (court.accessKind === "free") totals.free += 1;
      if (court.accessKind === "paid") totals.paid += 1;
      if (court.accessKind === "check") totals.check += 1;
      return totals;
    },
    { total: 0, free: 0, paid: 0, check: 0 }
  );

  if (summaryTotal) summaryTotal.textContent = String(counts.total);
  if (summaryFree) summaryFree.textContent = String(counts.free);
  if (summaryPaid) summaryPaid.textContent = String(counts.paid);
  if (summaryCheck) summaryCheck.textContent = String(counts.check);
}

function updateResultsMeta(visibleCourts, allCourts) {
  if (resultsHeading) {
    const suffix =
      state.source === "live"
        ? `${state.locationLabel} · ${state.radiusMiles} mi radius`
        : "Starter city examples";
    resultsHeading.textContent = suffix;
  }

  if (!resultsNote) return;

  if (state.source === "sample") {
    resultsNote.textContent =
      "Showing a branded starter set until you run a live search.";
    return;
  }

  if (!allCourts.length) {
    resultsNote.textContent =
      "No live listings were found in this radius. Try another city or widen the search.";
    return;
  }

  resultsNote.textContent = `Showing ${visibleCourts.length} of ${allCourts.length} live listings from community map data.`;
}

function renderResults({ fitMap = false } = {}) {
  if (!resultsGrid) return;

  updateFilterUi();
  updateSummary(state.courts);

  const visibleCourts = state.courts.filter((court) =>
    matchesFilter(court, state.activeFilter)
  );
  state.visibleCourts = visibleCourts;

  updateResultsMeta(visibleCourts, state.courts);
  syncMapWithCourts(visibleCourts, { fitBounds: fitMap });

  if (!visibleCourts.length) {
    renderEmptyState(state.courts.length);
    renderCourtCommunity(null);
    return;
  }

  resultsGrid.innerHTML = visibleCourts.map(renderCourtCard).join("");

  const nextActiveCourtId = visibleCourts.some((court) => court.id === state.activeCourtId)
    ? state.activeCourtId
    : visibleCourts[0].id;

  setActiveCourt(nextActiveCourtId, { centerMap: false, scrollMap: false });
}

function dedupeCourts(courts) {
  const seen = new Set();

  return courts.filter((court) => {
    const key = `${court.name.toLowerCase()}-${court.location.toLowerCase()}-${court.accessKind}-${court.surfaceKind}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function formatLocationLabel(result) {
  const address = result.address || {};
  const city =
    address.city ||
    address.town ||
    address.village ||
    address.hamlet ||
    address.municipality ||
    address.county;

  const stateName = address.state || address.region;

  return [city, stateName].filter(Boolean).join(", ") || result.display_name;
}

function formatCourtLocation(tags, fallbackLabel) {
  const city =
    tags["addr:city"] ||
    tags["addr:town"] ||
    tags["addr:village"] ||
    tags["addr:suburb"] ||
    tags.city ||
    tags.town ||
    tags.village;

  const stateName =
    tags["addr:state"] || tags.state || tags.region || tags.province;

  return [city, stateName].filter(Boolean).join(", ") || fallbackLabel;
}

function buildFallbackName(tags, location) {
  const street =
    tags["addr:street"] || tags["addr:full"] || tags["addr:housename"] || "";
  const venueType = formatVenueType(tags);

  if (street) {
    return `Pickleball courts · ${street}`;
  }

  if (venueType) {
    return `${venueType.replace(" tagged", "")} · ${location}`;
  }

  return `Pickleball courts · ${location}`;
}

function classifyAccess(tags) {
  const fee = String(tags.fee || "").toLowerCase();
  const access = String(tags.access || "").toLowerCase();
  const membership = String(tags.membership || "").toLowerCase();

  if (
    fee === "yes" ||
    fee.startsWith("yes") ||
    Boolean(tags.charge) ||
    Boolean(tags["charge:conditional"]) ||
    membership === "yes" ||
    access === "private" ||
    access === "customers"
  ) {
    return { kind: "paid", label: "Paid" };
  }

  if (
    fee === "no" ||
    fee === "free" ||
    access === "public" ||
    access === "permissive"
  ) {
    return { kind: "free", label: "Free" };
  }

  return { kind: "check", label: "Check access" };
}

function classifySurface(tags) {
  const indoor = String(tags.indoor || "").toLowerCase();
  const location = String(tags.location || "").toLowerCase();
  const leisure = String(tags.leisure || "").toLowerCase();

  if (indoor === "yes" || location === "indoor" || leisure === "sports_hall") {
    return { kind: "indoor", label: "Indoor" };
  }

  if (
    indoor === "no" ||
    location === "outdoor" ||
    leisure === "park" ||
    leisure === "pitch"
  ) {
    return { kind: "outdoor", label: "Outdoor" };
  }

  return { kind: "unknown", label: "Surface not tagged" };
}

function formatCourtCount(tags) {
  const possibleCount =
    tags.courts || tags.capacity || tags["sports_centre:courts"];

  if (!possibleCount) return null;

  return `${possibleCount} courts`;
}

function formatOpening(tags) {
  if (!tags.opening_hours) return null;
  if (tags.opening_hours === "24/7") return "Open 24/7";
  return "Hours listed";
}

function formatVenueType(tags) {
  if (tags.leisure === "park") return "Public park tagged";
  if (tags.leisure === "sports_centre") return "Sports centre tagged";
  if (tags.leisure === "sports_hall") return "Sports hall tagged";
  if (tags.club === "sport") return "Club tagged";
  return null;
}

function formatAccessDetail(tags, accessKind) {
  const access = String(tags.access || "").toLowerCase();
  const fee = String(tags.fee || "").toLowerCase();

  if (access === "public") return "Public access tagged";
  if (access === "private") return "Private access tagged";
  if (access === "permissive") return "Permissive access tagged";
  if (fee === "yes") return "Fee tagged";
  if (fee === "no" || fee === "free") return "No fee tagged";
  if (accessKind === "check") return "Verify fee details";
  return null;
}

function buildDescription(access, surface, locationLabel) {
  const accessCopy =
    access.kind === "free"
      ? "The current tags suggest this is a free or public play option."
      : access.kind === "paid"
        ? "The current tags suggest a fee, membership, or private-access setup."
        : "This listing does not clearly publish fee or access tags yet.";

  const surfaceCopy =
    surface.kind === "unknown"
      ? "Surface details are not clearly tagged in the source data."
      : `${surface.label} play is tagged in the source data.`;

  return `Live community-map listing near ${locationLabel}. ${accessCopy} ${surfaceCopy}`;
}

function buildCourtLinks(tags, type, id) {
  return {
    website: tags.website || tags["contact:website"] || tags.url || "",
    osmUrl: `https://www.openstreetmap.org/${type}/${id}`,
  };
}

function normalizeCourtElement(element, fallbackLabel) {
  const tags = element.tags || {};
  const access = classifyAccess(tags);
  const surface = classifySurface(tags);
  const lat = element.lat ?? element.center?.lat;
  const lon = element.lon ?? element.center?.lon;

  if (!lat || !lon) return null;

  const links = buildCourtLinks(tags, element.type, element.id);
  const details = [
    formatCourtCount(tags),
    formatVenueType(tags),
    formatAccessDetail(tags, access.kind),
    formatOpening(tags),
  ]
    .filter(Boolean)
    .slice(0, 3);

  const location = formatCourtLocation(tags, fallbackLabel);
  const name =
    tags.name ||
    tags["name:en"] ||
    tags.operator ||
    tags.official_name ||
    buildFallbackName(tags, location);

  return {
    id: `${element.type}-${element.id}`,
    name,
    location,
    lat: Number(lat),
    lon: Number(lon),
    accessKind: access.kind,
    accessLabel: access.label,
    surfaceKind: surface.kind,
    surfaceLabel: surface.label,
    details,
    description: buildDescription(access, surface, fallbackLabel),
    tags: [
      access.kind,
      ...(surface.kind !== "unknown" ? [surface.kind] : []),
    ],
    source: "live",
    website: links.website,
    osmUrl: links.osmUrl,
  };
}

function sortCourts(courts) {
  const accessOrder = { free: 0, paid: 1, check: 2 };

  return [...courts].sort((left, right) => {
    const accessDelta = accessOrder[left.accessKind] - accessOrder[right.accessKind];
    if (accessDelta !== 0) return accessDelta;
    return left.name.localeCompare(right.name);
  });
}

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = 25000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    return await response.json();
  } finally {
    window.clearTimeout(timer);
  }
}

async function geocodeQuery(query) {
  const cacheKey = query.trim().toLowerCase();
  const cached = readCache("geocode", cacheKey);
  if (cached) return cached;

  const url = new URL(SEARCH_PROVIDERS.geocodeUrl);
  url.search = new URLSearchParams({
    q: query,
    countrycodes: "us",
    format: "jsonv2",
    addressdetails: "1",
    limit: "1",
  }).toString();

  const results = await fetchJsonWithTimeout(url.toString());

  if (!Array.isArray(results) || !results.length) {
    throw new Error("No location match found.");
  }

  const topMatch = results[0];
  const normalized = {
    lat: Number(topMatch.lat),
    lon: Number(topMatch.lon),
    label: formatLocationLabel(topMatch),
    raw: topMatch,
  };

  writeCache("geocode", cacheKey, normalized);
  return normalized;
}

async function fetchLiveCourts(geo, radiusMiles) {
  const cacheKey = `${geo.label.toLowerCase()}-${radiusMiles}`;
  const cached = readCache("courts", cacheKey);
  if (cached) return cached;

  const radiusMeters = Math.round(radiusMiles * 1609.34);
  const overpassQuery = `
[out:json][timeout:25];
(
  node["sport"="pickleball"](around:${radiusMeters},${geo.lat},${geo.lon});
  way["sport"="pickleball"](around:${radiusMeters},${geo.lat},${geo.lon});
  relation["sport"="pickleball"](around:${radiusMeters},${geo.lat},${geo.lon});
);
out center tags;
  `.trim();

  const payload = await fetchJsonWithTimeout(
    SEARCH_PROVIDERS.overpassUrl,
    {
      method: "POST",
      headers: {
        "Content-Type": "text/plain;charset=UTF-8",
      },
      body: overpassQuery,
    },
    30000
  );

  const elements = Array.isArray(payload?.elements) ? payload.elements : [];
  const normalizedCourts = sortCourts(
    dedupeCourts(
      elements
        .map((element) => normalizeCourtElement(element, geo.label))
        .filter(Boolean)
    )
  );

  writeCache("courts", cacheKey, normalizedCourts);
  return normalizedCourts;
}

async function runLiveSearch(query, radiusMiles) {
  setSearching(true);
  setFinderStatus(`Searching ${query}...`, "warning");

  try {
    const geo = await geocodeQuery(query);
    const liveCourts = await fetchLiveCourts(geo, radiusMiles);

    state.courts = liveCourts;
    state.source = "live";
    state.locationLabel = geo.label;
    state.lastQuery = query;
    state.radiusMiles = radiusMiles;

    await loadCourtSummaries(liveCourts);

    if (liveCourts.length) {
      setFinderStatus(
        `Found ${liveCourts.length} live pickleball listings near ${geo.label}.`,
        "success"
      );
    } else {
      setFinderStatus(
        `No pickleball listings were found within ${radiusMiles} miles of ${geo.label}.`,
        "warning"
      );
    }

    renderResults({ fitMap: true });
    saveSearchPreference();
  } catch (error) {
    state.courts = [...defaultCourts];
    state.source = "sample";
    state.locationLabel = "Starter city examples";
    await loadCourtSummaries(state.courts);

    renderResults({ fitMap: true });
    setFinderStatus(
      "Live search hit a hiccup, so the page switched back to the branded starter directory.",
      "error"
    );
  } finally {
    setSearching(false);
  }
}

function handleSearchSubmit(event) {
  event.preventDefault();

  const query = searchInput?.value?.trim() || "";
  const radiusMiles = Number(radiusSelect?.value || 25);

  if (!query) {
    setFinderStatus(
      "Add a city, state, or zip code first so I know where to search.",
      "warning"
    );
    searchInput?.focus();
    return;
  }

  runLiveSearch(query, radiusMiles);
}

function initializeFilters() {
  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      state.activeFilter = button.dataset.courtFilter || "all";
      renderResults({ fitMap: true });
    });
  });
}

function initializeQuickSearch() {
  quickSearchButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const quickQuery = button.dataset.quickSearch || "";
      if (!quickQuery || !searchInput) return;

      searchInput.value = quickQuery;
      finderForm?.requestSubmit();
    });
  });
}

function initializeReveal() {
  const revealItems = Array.from(document.querySelectorAll(".reveal"));

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.16 }
    );

    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }
}

function handleResultInteraction(event) {
  const focusButton = event.target.closest("[data-map-focus]");
  if (focusButton) {
    focusCourtOnMap(focusButton.dataset.mapFocus || "");
    return;
  }

  const rateButton = event.target.closest("[data-rate-court]");
  if (rateButton) {
    setActiveCourt(rateButton.dataset.rateCourt || "", {
      centerMap: true,
      scrollMap: false,
      scrollReport: true,
    });
    return;
  }

  const card = event.target.closest("[data-court-id]");
  if (card) {
    setActiveCourt(card.dataset.courtId || "", { centerMap: false, scrollMap: false });
  }
}

async function handleCourtReportSubmit(event) {
  event.preventDefault();

  await ElevenZeroApp.boot;

  if (!ElevenZeroApp.requireAuth(courtReportStatus, "Please sign in first to post a court report.")) {
    return;
  }

  const activeCourt = getActiveCourt();
  if (!activeCourt) {
    setCourtReportStatus("Choose a court first so we know where to post your report.", "warning");
    return;
  }

  const formData = new FormData(courtReportForm);
  const payload = {
    courtId: activeCourt.id,
    courtName: activeCourt.name,
    courtLocation: activeCourt.location,
    conditionRating: Number(formData.get("conditionRating") || 0),
    busynessRating: Number(formData.get("busynessRating") || 0),
    playerLevel: String(formData.get("playerLevel") || ""),
    comment: String(formData.get("comment") || "").trim(),
  };

  try {
    setCourtReportSubmitting(true);
    const response = await ElevenZeroApp.request("/api/court-reports", {
      method: "POST",
      body: payload,
    });
    courtReportForm.reset();
    courtReportForm.querySelector('select[name="conditionRating"]').value = "3";
    courtReportForm.querySelector('select[name="busynessRating"]').value = "2";
    courtReportForm.querySelector('select[name="playerLevel"]').value = "intermediate";
    state.courtSummaries[activeCourt.id] = response.summary || state.courtSummaries[activeCourt.id];
    state.courtReportsByCourt[activeCourt.id] = response.items || [];
    renderResults({ fitMap: false });
    setActiveCourt(activeCourt.id, { centerMap: false, scrollMap: false });
    setCourtReportStatus(response.message || "Your court report is now live.", "success");
  } catch (error) {
    setCourtReportStatus(error.message, "error");
  } finally {
    setCourtReportSubmitting(false);
  }
}

async function initializeFinder() {
  await ElevenZeroApp.boot;
  hydrateSearchPreference();
  initializeReveal();
  initializeCourtMap();
  initializeFilters();
  initializeQuickSearch();
  await loadCourtSummaries(state.courts);
  finderForm?.addEventListener("submit", handleSearchSubmit);
  resultsGrid?.addEventListener("click", handleResultInteraction);
  mapSelection?.addEventListener("click", handleResultInteraction);
  courtReportForm?.addEventListener("submit", handleCourtReportSubmit);
  renderResults({ fitMap: true });
}

initializeFinder();

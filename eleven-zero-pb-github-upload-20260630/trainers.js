const trainerPageState = {
  search: "",
  level: "all",
  format: "all",
  activeFilter: "all",
  visibleLimit: window.matchMedia("(max-width: 760px)").matches ? 4 : 6,
  trainers: [],
  reviews: [],
};

const trainerForm = document.querySelector("[data-trainer-search-form]");
const trainerSearchInput = trainerForm?.querySelector('input[name="query"]');
const trainerLevelSelect = trainerForm?.querySelector('select[name="level"]');
const trainerFormatSelect = trainerForm?.querySelector('select[name="format"]');
const trainerStatus = document.querySelector("[data-trainer-status]");
const trainerResultsHeading = document.querySelector("[data-trainer-results-heading]");
const trainerResultsNote = document.querySelector("[data-trainer-results-note]");
const trainerResults = document.querySelector("[data-trainer-results]");
const trainerFilterButtons = Array.from(document.querySelectorAll("[data-trainer-filter]"));
const trainerCityButtons = Array.from(document.querySelectorAll("[data-trainer-city]"));
const trainerTotal = document.querySelector("[data-trainer-total]");
const trainerRating = document.querySelector("[data-trainer-rating]");
const trainerReviews = document.querySelector("[data-trainer-reviews]");
const trainerTenure = document.querySelector("[data-trainer-tenure]");
const trainerJoinForm = document.querySelector("[data-trainer-join-form]");
const trainerJoinStatus = document.querySelector("[data-trainer-join-status]");
const trainerReviewForm = document.querySelector("[data-trainer-review-form]");
const trainerReviewStatus = document.querySelector("[data-review-status]");
const trainerReviewList = document.querySelector("[data-review-list]");
const trainerReviewSelect = document.querySelector("[data-review-trainer-select]");
const trainerLoadMore = document.querySelector("[data-trainer-load-more]");
const trainerPhotoInput = document.querySelector("[data-trainer-photo-input]");
const trainerPhotoDropzone = document.querySelector("[data-trainer-photo-dropzone]");
const trainerPhotoPreview = document.querySelector("[data-trainer-photo-preview]");
const trainerPhotoPreviewImage = document.querySelector("[data-trainer-photo-preview-image]");
const trainerPhotoReplaceButton = document.querySelector("[data-trainer-photo-replace]");
const trainerPhotoRemoveButton = document.querySelector("[data-trainer-photo-remove]");
const trainerPhotoStatus = document.querySelector("[data-trainer-photo-status]");
const trainerJoinSubmitButton = trainerJoinForm?.querySelector('button[type="submit"]');

const TRAINER_PHOTO_MAX_SOURCE_BYTES = 10 * 1024 * 1024;
const TRAINER_PHOTO_MAX_DATA_URL_LENGTH = 1_500_000;
const TRAINER_PHOTO_DEFAULT_STATUS = "JPG, PNG or WebP · 10 MB max";
const TRAINER_PHOTO_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp"]);

let trainerImageDraft = "";
let trainerImageProcessing = false;

const formatLabels = {
  private: "Private lessons",
  group: "Group clinics",
  clinic: "Drill sessions",
  virtual: "Virtual analysis",
};

const levelLabels = {
  beginner: "Beginner focus",
  intermediate: "Intermediate focus",
  advanced: "Advanced focus",
};

function buildInitials(name) {
  return String(name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function trainerPhotoFileExtension(file) {
  const name = String(file?.name || "");
  return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
}

function isSupportedTrainerPhoto(file) {
  const type = String(file?.type || "").toLowerCase();
  const extension = trainerPhotoFileExtension(file);
  return (
    ["image/jpeg", "image/png", "image/webp"].includes(type) ||
    TRAINER_PHOTO_EXTENSIONS.has(extension)
  );
}

function readTrainerPhotoAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("That photo could not be read."));
    reader.readAsDataURL(file);
  });
}

function loadTrainerPhoto(source) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("That photo could not be opened."));
    image.src = source;
  });
}

function renderTrainerPhotoCrop(image, width, height, quality) {
  const targetRatio = width / height;
  const sourceRatio = image.naturalWidth / image.naturalHeight;
  let sourceWidth = image.naturalWidth;
  let sourceHeight = image.naturalHeight;
  let sourceX = 0;
  let sourceY = 0;

  if (sourceRatio > targetRatio) {
    sourceWidth = image.naturalHeight * targetRatio;
    sourceX = (image.naturalWidth - sourceWidth) / 2;
  } else {
    sourceHeight = image.naturalWidth / targetRatio;
    sourceY = (image.naturalHeight - sourceHeight) / 2;
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("That photo could not be prepared.");
  }

  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);
  context.drawImage(
    image,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    0,
    0,
    width,
    height
  );
  return canvas.toDataURL("image/jpeg", quality);
}

async function prepareTrainerPhoto(file) {
  if (!file || !isSupportedTrainerPhoto(file)) {
    throw new Error("Choose a JPG, PNG, or WebP photo.");
  }
  if (file.size > TRAINER_PHOTO_MAX_SOURCE_BYTES) {
    throw new Error("Choose a photo smaller than 10 MB.");
  }

  const source = await readTrainerPhotoAsDataUrl(file);
  const image = await loadTrainerPhoto(source);
  const steps = [
    [1600, 1000, 0.82],
    [1280, 800, 0.76],
    [960, 600, 0.7],
  ];

  for (const [width, height, quality] of steps) {
    const candidate = renderTrainerPhotoCrop(image, width, height, quality);
    if (candidate.length <= TRAINER_PHOTO_MAX_DATA_URL_LENGTH) {
      return candidate;
    }
  }

  throw new Error("That photo is still too large. Try a smaller image.");
}

function setTrainerPhotoProcessing(isProcessing) {
  trainerImageProcessing = isProcessing;
  trainerPhotoDropzone?.setAttribute("aria-busy", String(isProcessing));
  if (trainerJoinSubmitButton) {
    trainerJoinSubmitButton.disabled = isProcessing;
  }
}

function renderTrainerPhotoDraft() {
  const hasPhoto = Boolean(trainerImageDraft);
  if (trainerPhotoDropzone) trainerPhotoDropzone.hidden = hasPhoto;
  if (trainerPhotoPreview) trainerPhotoPreview.hidden = !hasPhoto;

  if (trainerPhotoPreviewImage) {
    if (hasPhoto) {
      trainerPhotoPreviewImage.src = trainerImageDraft;
    } else {
      trainerPhotoPreviewImage.removeAttribute("src");
    }
  }
}

function clearTrainerPhoto() {
  trainerImageDraft = "";
  if (trainerPhotoInput) trainerPhotoInput.value = "";
  renderTrainerPhotoDraft();
  ElevenZeroApp.setStatus(trainerPhotoStatus, TRAINER_PHOTO_DEFAULT_STATUS);
}

async function handleTrainerPhotoSelection(file) {
  if (!file || trainerImageProcessing) return;

  setTrainerPhotoProcessing(true);
  ElevenZeroApp.setStatus(trainerPhotoStatus, "Preparing photo…", "warning");
  try {
    trainerImageDraft = await prepareTrainerPhoto(file);
    renderTrainerPhotoDraft();
    ElevenZeroApp.setStatus(trainerPhotoStatus, "Photo ready.", "success");
  } catch (error) {
    ElevenZeroApp.setStatus(trainerPhotoStatus, error.message, "error");
  } finally {
    if (trainerPhotoInput) trainerPhotoInput.value = "";
    setTrainerPhotoProcessing(false);
  }
}

function slugTokens(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function enrichTrainer(item) {
  const locationTokens = slugTokens(item.location);
  return {
    ...item,
    initials: buildInitials(item.name),
    tags: [...new Set([item.level, item.format, ...locationTokens])],
  };
}

function getMonthsOnPlatform(joinedDate) {
  const joined = new Date(`${joinedDate}T00:00:00`);
  const now = new Date();

  let months =
    (now.getFullYear() - joined.getFullYear()) * 12 +
    (now.getMonth() - joined.getMonth());

  if (now.getDate() < joined.getDate()) {
    months -= 1;
  }

  return Math.max(months, 0);
}

function formatTenureShort(months) {
  if (months >= 24) {
    const years = Math.round((months / 12) * 10) / 10;
    return `${years} yr`;
  }

  if (months >= 12) {
    const years = Math.floor(months / 12);
    const remMonths = months % 12;
    return remMonths ? `${years} yr ${remMonths} mo` : `${years} yr`;
  }

  return `${months} mo`;
}

function formatTenureLong(months) {
  if (months === 1) return "On 11Z for 1 month";
  if (months < 12) return `On 11Z for ${months} months`;

  const years = Math.floor(months / 12);
  const remMonths = months % 12;
  const yearLabel = `${years} year${years === 1 ? "" : "s"}`;
  const monthLabel = remMonths
    ? ` ${remMonths} month${remMonths === 1 ? "" : "s"}`
    : "";

  return `On 11Z for ${yearLabel}${monthLabel}`;
}

function matchesSearch(trainer, query) {
  if (!query) return true;

  const haystack = [
    trainer.name,
    trainer.location,
    trainer.bio,
    trainer.experience,
    trainer.level,
    trainer.format,
  ]
    .join(" ")
    .toLowerCase();

  return haystack.includes(query.toLowerCase());
}

function getVisibleTrainers() {
  return trainerPageState.trainers.filter((trainer) => {
    const levelMatch =
      trainerPageState.level === "all" || trainer.level === trainerPageState.level;
    const formatMatch =
      trainerPageState.format === "all" || trainer.format === trainerPageState.format;
    const chipMatch =
      trainerPageState.activeFilter === "all" ||
      trainer.tags.includes(trainerPageState.activeFilter);
    const searchMatch = matchesSearch(trainer, trainerPageState.search);

    return levelMatch && formatMatch && chipMatch && searchMatch;
  });
}

function renderTrainerRatingPill(trainer) {
  if (!trainer.review_count || Number(trainer.rating || 0) <= 0) {
    return `
      <div class="trainer-rating-pill trainer-rating-pill-new">
        <strong>New profile</strong>
        <span>No reviews yet</span>
      </div>
    `;
  }

  return `
    <div
      class="trainer-rating-pill"
      aria-label="${ElevenZeroApp.escapeHtml(
        `${Number(trainer.rating).toFixed(1)} out of 5 stars from ${trainer.review_count} reviews`
      )}"
    >
      <span class="trainer-rating-star" aria-hidden="true">★</span>
      <strong>${ElevenZeroApp.escapeHtml(Number(trainer.rating).toFixed(1))}</strong>
      <span>${ElevenZeroApp.escapeHtml(
        `${trainer.review_count} review${trainer.review_count === 1 ? "" : "s"}`
      )}</span>
    </div>
  `;
}

function renderTrainerCard(trainer) {
  const tenureMonths = getMonthsOnPlatform(trainer.joined_at);
  const levelLabel = levelLabels[trainer.level] || "Player focus";
  const formatLabel = formatLabels[trainer.format] || "Coaching";
  const imageUrl = String(trainer.imageUrl || "").trim();
  const contactHref = trainer.email
    ? `mailto:${ElevenZeroApp.escapeHtml(trainer.email)}`
    : "./auth.html?next=./trainers.html";

  return `
    <article class="trainer-profile-card reveal is-visible" data-trainer-card>
      <div class="trainer-profile-media ${imageUrl ? "has-photo" : "is-fallback"}">
        <span class="trainer-profile-photo-fallback" aria-hidden="true">${ElevenZeroApp.escapeHtml(
          trainer.initials
        )}</span>
        ${
          imageUrl
            ? `<img
                class="trainer-profile-photo"
                src="${ElevenZeroApp.escapeHtml(imageUrl)}"
                alt="${ElevenZeroApp.escapeHtml(
                  `Photo of ${trainer.name}, pickleball trainer in ${trainer.location}`
                )}"
                loading="lazy"
                decoding="async"
              />`
            : ""
        }
        <div class="trainer-profile-media-badges">
          <span class="trainer-profile-rate">${ElevenZeroApp.escapeHtml(trainer.rate)}</span>
          <span class="trainer-profile-verified">${trainer.verified ? "Verified" : "New"}</span>
        </div>
      </div>

      <div class="trainer-profile-body">
        <header class="trainer-profile-heading">
          <div>
            <h3>${ElevenZeroApp.escapeHtml(trainer.name)}</h3>
            <p>${ElevenZeroApp.escapeHtml(trainer.location)}</p>
          </div>
          ${renderTrainerRatingPill(trainer)}
        </header>

        <div class="trainer-profile-facts" aria-label="Trainer details">
          <span>${ElevenZeroApp.escapeHtml(formatTenureLong(tenureMonths))}</span>
          <span>${ElevenZeroApp.escapeHtml(formatLabel)}</span>
          <span>${ElevenZeroApp.escapeHtml(levelLabel)}</span>
        </div>

        <p class="trainer-profile-bio">${ElevenZeroApp.escapeHtml(trainer.bio)}</p>

        <dl class="trainer-profile-details">
          <div>
            <dt>Experience</dt>
            <dd>${ElevenZeroApp.escapeHtml(trainer.experience)}</dd>
          </div>
          <div>
            <dt>Availability</dt>
            <dd>${ElevenZeroApp.escapeHtml(trainer.availability)}</dd>
          </div>
        </dl>

        <a class="button button-dark trainer-profile-contact" href="${contactHref}">
          Contact trainer
        </a>
      </div>
    </article>
  `;
}

function renderTrainerResults() {
  const visible = getVisibleTrainers();
  const displayed = visible.slice(0, trainerPageState.visibleLimit);

  trainerFilterButtons.forEach((button) => {
    const isActive = button.dataset.trainerFilter === trainerPageState.activeFilter;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  const totalReviewsValue = visible.reduce(
    (sum, trainer) => sum + Number(trainer.review_count || 0),
    0
  );
  const ratedTrainers = visible.filter((trainer) => Number(trainer.review_count || 0) > 0);
  const averageRatingValue = ratedTrainers.length
    ? ratedTrainers.reduce((sum, trainer) => sum + Number(trainer.rating || 0), 0) /
      ratedTrainers.length
    : 0;
  const averageTenureValue = visible.length
    ? visible.reduce((sum, trainer) => sum + getMonthsOnPlatform(trainer.joined_at), 0) /
      visible.length
    : 0;

  if (trainerTotal) trainerTotal.textContent = String(visible.length);
  if (trainerRating) {
    trainerRating.textContent = ratedTrainers.length ? `${averageRatingValue.toFixed(1)}★` : "New";
  }
  if (trainerReviews) trainerReviews.textContent = String(totalReviewsValue);
  if (trainerTenure) trainerTenure.textContent = formatTenureShort(Math.round(averageTenureValue));
  if (trainerResultsHeading) {
    trainerResultsHeading.textContent = `${visible.length} trainer match${visible.length === 1 ? "" : "es"}`;
  }
  if (trainerResultsNote) {
    trainerResultsNote.textContent = ElevenZeroApp.session?.authenticated
      ? "Compare experience, ratings, and availability. You can also leave a review."
      : "Compare experience, ratings, availability, and time on Eleven Zero.";
  }

  if (!visible.length) {
    if (trainerLoadMore) trainerLoadMore.hidden = true;
    trainerResults.innerHTML = `
      <article class="empty-state reveal is-visible">
        <p class="eyebrow">${trainerPageState.trainers.length ? "No matches" : "Directory opening"}</p>
        <h3>${
          trainerPageState.trainers.length
            ? "No trainers match that search yet."
            : "Trainer applications are open."
        }</h3>
        <p>${
          trainerPageState.trainers.length
            ? "Try a broader city search or switch back to All."
            : 'We are reviewing the first trainer profiles now. <a class="text-link" href="#join">Apply to join the directory</a>.'
        }</p>
      </article>
    `;
    ElevenZeroApp.setStatus(
      trainerStatus,
      trainerPageState.trainers.length
        ? "No trainers matched that filter."
        : "The reviewed trainer directory is opening soon.",
      "warning"
    );
    return;
  }

  trainerResults.innerHTML = displayed.map(renderTrainerCard).join("");
  trainerResults.querySelectorAll(".trainer-profile-photo").forEach((image) => {
    image.addEventListener(
      "error",
      () => {
        image.remove();
      },
      { once: true }
    );
  });
  if (trainerLoadMore) {
    const hasMore = displayed.length < visible.length;
    trainerLoadMore.hidden = !hasMore;
    trainerLoadMore.textContent = hasMore
      ? `Show all ${visible.length} trainers`
      : "All trainers are showing";
  }
  ElevenZeroApp.setStatus(
    trainerStatus,
    `Showing ${visible.length} trainer match${visible.length === 1 ? "" : "es"}.`,
    "success"
  );
}

function renderReviewFeed() {
  if (!trainerReviewList) return;

  if (!trainerPageState.reviews.length) {
    trainerReviewList.innerHTML = `
      <article class="empty-state reveal is-visible">
        <p class="eyebrow">No reviews yet</p>
        <h3>Player reviews will appear here.</h3>
        <p>Be the first player to leave a trainer review.</p>
      </article>
    `;
    return;
  }

  trainerReviewList.innerHTML = trainerPageState.reviews.slice(0, 4).map((review) => {
    const stars = "★".repeat(Number(review.rating || 0));
    const dateLabel = new Date(review.created_at).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });

    return `
      <article class="trainer-review-card reveal is-visible">
        <div class="trainer-review-head">
          <div>
            <p class="eyebrow">${ElevenZeroApp.escapeHtml(review.trainer_name)}</p>
            <h3>${ElevenZeroApp.escapeHtml(review.reviewer_name)}</h3>
          </div>
          <span class="trainer-review-stars">${ElevenZeroApp.escapeHtml(stars)}</span>
        </div>
        <p class="trainer-review-copy">${ElevenZeroApp.escapeHtml(review.comment)}</p>
        <div class="trainer-review-meta">
          <span>${ElevenZeroApp.escapeHtml(dateLabel)}</span>
        </div>
      </article>
    `;
  }).join("");
}

function populateTrainerSelect() {
  if (!trainerReviewSelect) return;

  const previousValue = trainerReviewSelect.value;
  const options = trainerPageState.trainers
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((trainer) => {
      return `<option value="${trainer.id}">${ElevenZeroApp.escapeHtml(trainer.name)}</option>`;
    })
    .join("");

  trainerReviewSelect.innerHTML = options;
  trainerReviewSelect.disabled = !trainerPageState.trainers.length;

  if (previousValue && trainerPageState.trainers.some((trainer) => String(trainer.id) === previousValue)) {
    trainerReviewSelect.value = previousValue;
  }
}

function readSearchState() {
  trainerPageState.search = trainerSearchInput?.value?.trim() || "";
  trainerPageState.level = trainerLevelSelect?.value || "all";
  trainerPageState.format = trainerFormatSelect?.value || "all";
}

function resetTrainerLimit() {
  trainerPageState.visibleLimit = window.matchMedia("(max-width: 760px)").matches ? 4 : 6;
}

function openTrainerPanelFromHash() {
  const hash = window.location.hash;
  if (!hash) return;

  const panel = document.querySelector(hash);
  if (panel instanceof HTMLDetailsElement) {
    panel.open = true;
  }
}

async function loadTrainerData() {
  const [trainerResponse, reviewResponse] = await Promise.all([
    ElevenZeroApp.request("/api/trainers"),
    ElevenZeroApp.request("/api/trainer-reviews"),
  ]);

  trainerPageState.trainers = (trainerResponse.items || []).map(enrichTrainer);
  trainerPageState.reviews = reviewResponse.items || [];
  populateTrainerSelect();
  renderTrainerResults();
  renderReviewFeed();
}

async function handleTrainerJoin(event) {
  event.preventDefault();

  if (!ElevenZeroApp.requireAuth(trainerJoinStatus, "Please sign in first to publish a trainer profile.")) {
    return;
  }

  if (trainerImageProcessing) {
    ElevenZeroApp.setStatus(trainerPhotoStatus, "Wait for the photo to finish.", "warning");
    return;
  }

  if (!trainerImageDraft) {
    ElevenZeroApp.setStatus(trainerPhotoStatus, "Add one trainer photo.", "error");
    trainerPhotoDropzone?.focus();
    return;
  }

  const payload = Object.fromEntries(new FormData(trainerJoinForm).entries());
  payload.trainerImage = trainerImageDraft;

  try {
    if (trainerJoinSubmitButton) {
      trainerJoinSubmitButton.disabled = true;
      trainerJoinSubmitButton.textContent = "Submitting…";
    }
    const response = await ElevenZeroApp.request("/api/trainers", {
      method: "POST",
      body: payload,
    });
    trainerJoinForm.reset();
    clearTrainerPhoto();
    ElevenZeroApp.setStatus(
      trainerJoinStatus,
      response.message || `${payload.name} was submitted for Eleven Zero PB review.`,
      "success"
    );
    await loadTrainerData();
  } catch (error) {
    ElevenZeroApp.setStatus(trainerJoinStatus, error.message, "error");
  } finally {
    if (trainerJoinSubmitButton) {
      trainerJoinSubmitButton.disabled = false;
      trainerJoinSubmitButton.textContent = "Submit profile for review";
    }
  }
}

async function handleTrainerReview(event) {
  event.preventDefault();

  if (!ElevenZeroApp.requireAuth(trainerReviewStatus, "Please sign in first to publish a trainer review.")) {
    return;
  }

  const payload = Object.fromEntries(new FormData(trainerReviewForm).entries());

  try {
    await ElevenZeroApp.request("/api/trainer-reviews", {
      method: "POST",
      body: payload,
    });
    trainerReviewForm.reset();
    ElevenZeroApp.setStatus(trainerReviewStatus, "Your review is now live.", "success");
    await loadTrainerData();
  } catch (error) {
    ElevenZeroApp.setStatus(trainerReviewStatus, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  await loadTrainerData();
  openTrainerPanelFromHash();

  trainerForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    readSearchState();
    resetTrainerLimit();
    renderTrainerResults();
  });

  trainerSearchInput?.addEventListener("input", () => {
    readSearchState();
    resetTrainerLimit();
    renderTrainerResults();
  });

  trainerLevelSelect?.addEventListener("change", () => {
    readSearchState();
    resetTrainerLimit();
    renderTrainerResults();
  });

  trainerFormatSelect?.addEventListener("change", () => {
    readSearchState();
    resetTrainerLimit();
    renderTrainerResults();
  });

  trainerFilterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      trainerPageState.activeFilter = button.dataset.trainerFilter || "all";
      renderTrainerResults();
    });
  });

  trainerCityButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const city = button.dataset.trainerCity || "";
      if (trainerSearchInput) {
        trainerSearchInput.value = city;
      }
      trainerPageState.search = city;
      renderTrainerResults();
    });
  });

  trainerJoinForm?.addEventListener("submit", handleTrainerJoin);
  trainerPhotoDropzone?.addEventListener("click", () => trainerPhotoInput?.click());
  trainerPhotoInput?.addEventListener("change", (event) => {
    handleTrainerPhotoSelection(event.target.files?.[0]);
  });
  trainerPhotoReplaceButton?.addEventListener("click", () => trainerPhotoInput?.click());
  trainerPhotoRemoveButton?.addEventListener("click", clearTrainerPhoto);
  trainerPhotoDropzone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    trainerPhotoDropzone.classList.add("is-dragging");
  });
  trainerPhotoDropzone?.addEventListener("dragleave", () => {
    trainerPhotoDropzone.classList.remove("is-dragging");
  });
  trainerPhotoDropzone?.addEventListener("drop", (event) => {
    event.preventDefault();
    trainerPhotoDropzone.classList.remove("is-dragging");
    handleTrainerPhotoSelection(event.dataTransfer?.files?.[0]);
  });
  trainerReviewForm?.addEventListener("submit", handleTrainerReview);
  trainerLoadMore?.addEventListener("click", () => {
    trainerPageState.visibleLimit = trainerPageState.trainers.length;
    renderTrainerResults();
  });
  window.addEventListener("hashchange", openTrainerPanelFromHash);
});

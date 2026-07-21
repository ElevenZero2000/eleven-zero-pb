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
  const contactHref = trainer.email
    ? `mailto:${ElevenZeroApp.escapeHtml(trainer.email)}`
    : "./auth.html?next=./trainers.html";

  return `
    <article class="trainer-simple-card reveal is-visible" data-trainer-card>
      <div class="trainer-simple-card-head">
        <div class="trainer-avatar" aria-hidden="true">${ElevenZeroApp.escapeHtml(
          trainer.initials
        )}</div>
        <div class="trainer-heading">
          <h3>${ElevenZeroApp.escapeHtml(trainer.name)}</h3>
          <p>${ElevenZeroApp.escapeHtml(trainer.location)}</p>
        </div>
        <span class="trainer-rate">${ElevenZeroApp.escapeHtml(trainer.rate)}</span>
      </div>

      <div class="trainer-simple-trust">
        ${renderTrainerRatingPill(trainer)}
        <div class="trainer-tenure-pill">
          <span>${ElevenZeroApp.escapeHtml(formatTenureLong(tenureMonths))}</span>
        </div>
      </div>

      <div class="trainer-simple-tags">
        <span>${ElevenZeroApp.escapeHtml(levelLabel)}</span>
        <span>${ElevenZeroApp.escapeHtml(formatLabel)}</span>
        <span>${trainer.verified ? "Verified profile" : "New profile"}</span>
      </div>

      <p class="trainer-simple-bio">${ElevenZeroApp.escapeHtml(trainer.bio)}</p>

      <div class="trainer-simple-card-foot">
        <div>
          <strong>${ElevenZeroApp.escapeHtml(trainer.experience)}</strong>
          <span>${ElevenZeroApp.escapeHtml(trainer.availability)}</span>
        </div>
        <a class="button button-dark" href="${contactHref}">Contact trainer</a>
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
        <p class="eyebrow">No matches</p>
        <h3>No trainers match that search yet.</h3>
        <p>Try a broader city search or switch back to All.</p>
      </article>
    `;
    ElevenZeroApp.setStatus(trainerStatus, "No trainers matched that filter.", "warning");
    return;
  }

  trainerResults.innerHTML = displayed.map(renderTrainerCard).join("");
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

  const payload = Object.fromEntries(new FormData(trainerJoinForm).entries());

  try {
    await ElevenZeroApp.request("/api/trainers", {
      method: "POST",
      body: payload,
    });
    trainerJoinForm.reset();
    ElevenZeroApp.setStatus(
      trainerJoinStatus,
      `${payload.name} is now live in the trainer directory.`,
      "success"
    );
    await loadTrainerData();
  } catch (error) {
    ElevenZeroApp.setStatus(trainerJoinStatus, error.message, "error");
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
  trainerReviewForm?.addEventListener("submit", handleTrainerReview);
  trainerLoadMore?.addEventListener("click", () => {
    trainerPageState.visibleLimit = trainerPageState.trainers.length;
    renderTrainerResults();
  });
  window.addEventListener("hashchange", openTrainerPanelFromHash);
});

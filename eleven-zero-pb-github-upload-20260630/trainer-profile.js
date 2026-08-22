const trainerDetailShell = document.querySelector("[data-trainer-detail-shell]");
const trainerDetailStatus = document.querySelector("[data-trainer-detail-status]");
const trainerRequestDialog = document.querySelector("[data-trainer-request-dialog]");
const trainerRequestForm = document.querySelector("[data-trainer-request-form]");
const trainerRequestMessage = document.querySelector("[data-trainer-request-message]");
const trainerRequestCount = document.querySelector("[data-trainer-request-count]");
const trainerRequestStatus = document.querySelector("[data-trainer-request-status]");
const trainerRequestCopy = document.querySelector("[data-trainer-request-copy]");
const trainerRequestSubmit = document.querySelector("[data-trainer-request-submit]");

const trainerDetailState = {
  trainer: null,
  reviews: [],
  viewerState: {
    isOwner: false,
    relationshipStatus: null,
    relationshipId: null,
  },
};

const trainerDetailFormatLabels = {
  private: "Private lessons",
  group: "Group clinics",
  clinic: "Drill sessions",
  virtual: "Virtual analysis",
};

const trainerDetailLevelLabels = {
  beginner: "Beginner players",
  intermediate: "Intermediate players",
  advanced: "Advanced players",
};

function trainerDetailId() {
  const rawId = new URLSearchParams(window.location.search).get("id") || "";
  return /^\d+$/.test(rawId) && Number(rawId) > 0 ? Number(rawId) : null;
}

function trainerDetailInitials(name) {
  return String(name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function trainerDetailSafeUrl(value) {
  const candidate = String(value || "").trim();
  if (!candidate) return "";

  try {
    const parsed = new URL(candidate);
    return ["http:", "https:"].includes(parsed.protocol) &&
      !parsed.username &&
      !parsed.password
      ? parsed.href
      : "";
  } catch {
    return "";
  }
}

function trainerDetailTenure(joinedDate) {
  const joined = new Date(`${String(joinedDate || "").slice(0, 10)}T00:00:00`);
  if (Number.isNaN(joined.getTime())) return "Eleven Zero member";

  const today = new Date();
  let months =
    (today.getFullYear() - joined.getFullYear()) * 12 +
    (today.getMonth() - joined.getMonth());
  if (today.getDate() < joined.getDate()) months -= 1;
  months = Math.max(months, 0);

  if (months < 1) return "Joined this month";
  if (months < 12) return `${months} month${months === 1 ? "" : "s"} on Eleven Zero`;

  const years = Math.floor(months / 12);
  const remainingMonths = months % 12;
  return `${years} year${years === 1 ? "" : "s"}${
    remainingMonths ? ` ${remainingMonths} month${remainingMonths === 1 ? "" : "s"}` : ""
  } on Eleven Zero`;
}

function trainerDetailRatingMarkup(trainer) {
  const reviewCount = Number(trainer.review_count || 0);
  const rating = Number(trainer.rating || 0);

  if (!reviewCount || rating <= 0) {
    return `
      <div class="trainer-detail-rating trainer-detail-rating-new">
        <strong>New profile</strong>
        <span>No reviews yet</span>
      </div>
    `;
  }

  return `
    <div
      class="trainer-detail-rating"
      aria-label="${ElevenZeroApp.escapeHtml(
        `${rating.toFixed(1)} out of 5 stars from ${reviewCount} reviews`
      )}"
    >
      <span aria-hidden="true">★</span>
      <strong>${ElevenZeroApp.escapeHtml(rating.toFixed(1))}</strong>
      <small>${ElevenZeroApp.escapeHtml(
        `${reviewCount} review${reviewCount === 1 ? "" : "s"}`
      )}</small>
    </div>
  `;
}

function trainerDetailReviewMarkup(reviews) {
  if (!reviews.length) {
    return `
      <div class="trainer-detail-empty-reviews">
        <p class="eyebrow">No reviews yet</p>
        <h3>Be the first player to share an experience.</h3>
        <p>Reviews help other players choose a trainer with confidence.</p>
      </div>
    `;
  }

  return reviews
    .map((review) => {
      const rating = Math.max(1, Math.min(5, Number(review.rating || 0)));
      const date = new Date(review.created_at);
      const dateLabel = Number.isNaN(date.getTime())
        ? "Recent review"
        : new Intl.DateTimeFormat("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          }).format(date);

      return `
        <article class="trainer-detail-review">
          <div class="trainer-detail-review-head">
            <div>
              <strong>${ElevenZeroApp.escapeHtml(review.reviewer_name || "Eleven Zero player")}</strong>
              <span>${ElevenZeroApp.escapeHtml(dateLabel)}</span>
            </div>
            <span
              class="trainer-detail-review-stars"
              aria-label="${rating} out of 5 stars"
            >
              <span aria-hidden="true">${"★".repeat(rating)}</span>
            </span>
          </div>
          <p>${ElevenZeroApp.escapeHtml(review.comment || "Great training experience.")}</p>
        </article>
      `;
    })
    .join("");
}

function updateTrainerDetailMetadata(trainer) {
  const title = `${trainer.name} · Pickleball trainer · Eleven Zero PB`;
  const description = String(
    trainer.bio ||
      `${trainer.name} offers ${trainerDetailFormatLabels[trainer.format] || "pickleball coaching"} in ${
        trainer.location
      }.`
  ).slice(0, 180);
  document.title = title;
  document.querySelector('meta[name="description"]')?.setAttribute("content", description);

  let structuredData = document.getElementById("trainer-structured-data");
  if (!structuredData) {
    structuredData = document.createElement("script");
    structuredData.id = "trainer-structured-data";
    structuredData.type = "application/ld+json";
    document.head.appendChild(structuredData);
  }
  structuredData.textContent = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Person",
    name: trainer.name,
    description,
    image: trainer.imageUrl
      ? new URL(trainer.imageUrl, window.location.href).href
      : undefined,
    jobTitle: "Pickleball trainer",
    address: trainer.location,
  });
}

function trainerDetailPhotoUrls(trainer) {
  return [trainer.imageUrl, ...(Array.isArray(trainer.galleryImageUrls) ? trainer.galleryImageUrls : [])]
    .map((value) => String(value || "").trim())
    .filter((value, index, list) => value && list.indexOf(value) === index);
}

function trainerDetailGalleryMarkup(trainer) {
  const photos = trainerDetailPhotoUrls(trainer);
  if (photos.length < 2) return "";

  return `
    <section class="trainer-detail-gallery" aria-labelledby="trainer-gallery-title">
      <div class="trainer-detail-gallery-head">
        <div>
          <p class="eyebrow">Photo gallery</p>
          <h2 id="trainer-gallery-title">Coaching in action</h2>
        </div>
        <span>${photos.length} photos</span>
      </div>
      <div class="trainer-detail-gallery-grid">
        ${photos
          .map(
            (photo, index) => `
              <button
                class="trainer-detail-gallery-thumb${index === 0 ? " is-active" : ""}"
                type="button"
                data-trainer-gallery-photo="${ElevenZeroApp.escapeHtml(photo)}"
                data-trainer-gallery-index="${index}"
                aria-label="Show ${index === 0 ? "cover photo" : `trainer photo ${index + 1}`}"
                aria-pressed="${index === 0 ? "true" : "false"}"
              >
                <img
                  src="${ElevenZeroApp.escapeHtml(photo)}"
                  alt=""
                  loading="lazy"
                  decoding="async"
                />
                <span>${index === 0 ? "Cover" : String(index + 1).padStart(2, "0")}</span>
              </button>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function trainerDetailPrimaryAction(trainer, viewerState) {
  if (viewerState.isOwner) {
    return '<a class="button button-primary" href="./account.html#training-hub">Manage profile</a>';
  }

  if (viewerState.relationshipStatus === "active") {
    return '<a class="button button-primary" href="./account.html#training-hub">Open conversation</a>';
  }

  if (viewerState.relationshipStatus === "pending") {
    return '<button class="button button-primary" type="button" disabled>Request sent</button>';
  }

  if (!ElevenZeroApp.session?.authenticated) {
    const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
    return `<a class="button button-primary" href="./auth.html?next=${next}">Sign in to request</a>`;
  }

  return `<button class="button button-primary" type="button" data-trainer-request-open>Request a lesson</button>`;
}

function trainerDetailLessonLink(viewerState) {
  if (viewerState.isOwner || viewerState.relationshipStatus === "active") {
    return '<a class="text-link" href="./account.html#training-hub">Open Training Hub →</a>';
  }
  if (viewerState.relationshipStatus === "pending") {
    return '<span class="trainer-detail-request-note">Your request is waiting for the trainer.</span>';
  }
  if (!ElevenZeroApp.session?.authenticated) {
    const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
    return `<a class="text-link" href="./auth.html?next=${next}">Sign in to request a lesson →</a>`;
  }
  return '<button class="trainer-detail-text-button" type="button" data-trainer-request-open>Request a lesson →</button>';
}

function renderTrainerDetail(trainer, reviews, viewerState) {
  const formatLabel = trainerDetailFormatLabels[trainer.format] || "Pickleball coaching";
  const levelLabel = trainerDetailLevelLabels[trainer.level] || "Players of all levels";
  const imageUrl = String(trainer.imageUrl || "").trim();
  const certificationOrg = String(trainer.certificationOrg || "").trim();
  const certificationName = String(trainer.certificationName || "").trim();
  const certificationUrl = trainerDetailSafeUrl(trainer.certificationUrl);
  const hasCertification = Boolean(certificationOrg || certificationName);
  const reviewHref = `./trainers.html?reviewTrainer=${encodeURIComponent(
    trainer.id
  )}#reviews`;

  trainerDetailShell.innerHTML = `
    <section class="trainer-detail-hero">
      <div class="trainer-detail-media ${imageUrl ? "has-photo" : "is-fallback"}">
        <span class="trainer-detail-photo-fallback" aria-hidden="true">
          ${ElevenZeroApp.escapeHtml(trainerDetailInitials(trainer.name))}
        </span>
        ${
          imageUrl
            ? `<img
                src="${ElevenZeroApp.escapeHtml(imageUrl)}"
                alt="${ElevenZeroApp.escapeHtml(
                  `${trainer.name}, pickleball trainer in ${trainer.location}`
                )}"
                data-trainer-detail-image
              />`
            : ""
        }
        <div class="trainer-detail-photo-shade" aria-hidden="true"></div>
        <div class="trainer-detail-photo-badges">
          <span>${trainer.verified ? "Verified trainer" : "New trainer"}</span>
          <strong>${ElevenZeroApp.escapeHtml(trainer.rate || "Contact for rate")}</strong>
        </div>
      </div>

      <div class="trainer-detail-summary">
        <p class="eyebrow">Eleven Zero trainer</p>
        <h1>${ElevenZeroApp.escapeHtml(trainer.name)}</h1>
        <p class="trainer-detail-location">${ElevenZeroApp.escapeHtml(trainer.location)}</p>
        ${trainerDetailRatingMarkup(trainer)}

        <div class="trainer-detail-quick-facts" aria-label="Trainer overview">
          <div>
            <span>Member</span>
            <strong>${ElevenZeroApp.escapeHtml(trainerDetailTenure(trainer.joined_at))}</strong>
          </div>
          <div>
            <span>Lesson format</span>
            <strong>${ElevenZeroApp.escapeHtml(formatLabel)}</strong>
          </div>
          <div>
            <span>Best for</span>
            <strong>${ElevenZeroApp.escapeHtml(levelLabel)}</strong>
          </div>
        </div>

        <div class="trainer-detail-actions">
          ${trainerDetailPrimaryAction(trainer, viewerState)}
          <a class="button button-secondary" href="${reviewHref}">Leave a review</a>
        </div>
      </div>
    </section>

    ${trainerDetailGalleryMarkup(trainer)}

    <section class="trainer-detail-content-grid">
      <article class="trainer-detail-panel trainer-detail-about">
        <p class="eyebrow">About</p>
        <h2>Meet ${ElevenZeroApp.escapeHtml(trainer.name)}</h2>
        <p>${ElevenZeroApp.escapeHtml(trainer.bio || "Trainer profile details are coming soon.")}</p>

        <div class="trainer-detail-experience">
          <span>Experience</span>
          <strong>${ElevenZeroApp.escapeHtml(
            trainer.experience || "Experience details available on request"
          )}</strong>
        </div>
      </article>

      <aside class="trainer-detail-side-stack">
        <section class="trainer-detail-panel trainer-detail-availability">
          <p class="eyebrow">Availability</p>
          <h2>Plan a lesson</h2>
          <p>${ElevenZeroApp.escapeHtml(
            trainer.availability || "Contact this trainer for current availability."
          )}</p>
          ${trainerDetailLessonLink(viewerState)}
        </section>

        ${
          hasCertification
            ? `<section class="trainer-detail-panel trainer-detail-certification">
                <div class="trainer-detail-cert-icon" aria-hidden="true">✓</div>
                <div>
                  <p class="eyebrow">Certification</p>
                  <h2>${ElevenZeroApp.escapeHtml(
                    certificationName || "Trainer credential"
                  )}</h2>
                  ${
                    certificationOrg
                      ? `<p>${ElevenZeroApp.escapeHtml(certificationOrg)}</p>`
                      : ""
                  }
                  ${
                    certificationUrl
                      ? `<a
                          class="text-link"
                          href="${ElevenZeroApp.escapeHtml(certificationUrl)}"
                          target="_blank"
                          rel="noopener noreferrer"
                        >View public credential ↗</a>`
                      : ""
                  }
                </div>
              </section>`
            : ""
        }
      </aside>
    </section>

    <section class="trainer-detail-reviews" id="reviews">
      <div class="trainer-detail-reviews-head">
        <div>
          <p class="eyebrow">Player reviews</p>
          <h2>What players say</h2>
        </div>
        <a class="button button-secondary" href="${reviewHref}">Leave a review</a>
      </div>
      <div class="trainer-detail-review-grid">
        ${trainerDetailReviewMarkup(reviews)}
      </div>
    </section>
  `;

  trainerDetailShell.setAttribute("aria-busy", "false");
  trainerDetailShell.querySelector("[data-trainer-detail-image]")?.addEventListener(
    "error",
    (event) => {
      event.currentTarget.remove();
      trainerDetailShell.querySelector(".trainer-detail-media")?.classList.add("is-fallback");
    },
    { once: true }
  );
  trainerDetailShell.querySelectorAll(".trainer-detail-gallery-thumb img").forEach((image) => {
    image.addEventListener(
      "error",
      () => image.closest(".trainer-detail-gallery-thumb")?.remove(),
      { once: true }
    );
  });
  if (trainerRequestCopy) {
    trainerRequestCopy.textContent = `Introduce yourself to ${trainer.name} and share what you would like to work on.`;
  }
  updateTrainerDetailMetadata(trainer);
}

function renderTrainerDetailError(message) {
  trainerDetailShell.setAttribute("aria-busy", "false");
  trainerDetailShell.innerHTML = `
    <section class="trainer-detail-error">
      <p class="eyebrow">Trainer unavailable</p>
      <h1>We couldn’t open this profile.</h1>
      <p>${ElevenZeroApp.escapeHtml(message)}</p>
      <a class="button button-primary" href="./trainers.html#directory">Browse trainers</a>
    </section>
  `;
}

async function loadTrainerDetail() {
  const id = trainerDetailId();
  if (!id) {
    const message = "Choose a trainer from the directory to view a full profile.";
    ElevenZeroApp.setStatus(trainerDetailStatus, message, "error");
    renderTrainerDetailError(message);
    return;
  }

  try {
    const response = await ElevenZeroApp.request(`/api/trainers/${id}`);
    if (!response.item) {
      throw new Error("That trainer profile is not available.");
    }
    trainerDetailState.trainer = response.item;
    trainerDetailState.reviews = Array.isArray(response.reviews) ? response.reviews : [];
    trainerDetailState.viewerState = {
      isOwner: Boolean(response.viewerState?.isOwner),
      relationshipStatus: response.viewerState?.relationshipStatus || null,
      relationshipId: response.viewerState?.relationshipId || null,
    };
    renderTrainerDetail(
      trainerDetailState.trainer,
      trainerDetailState.reviews,
      trainerDetailState.viewerState
    );
    trainerDetailStatus.hidden = true;
  } catch (error) {
    const message =
      /could not be found|not available/i.test(String(error.message || ""))
        ? "This trainer may still be under review or is no longer available."
        : error.message;
    ElevenZeroApp.setStatus(trainerDetailStatus, message, "error");
    renderTrainerDetailError(message);
  }
}

function updateTrainerRequestCount() {
  if (!trainerRequestCount || !trainerRequestMessage) return;
  trainerRequestCount.textContent = `${trainerRequestMessage.value.length} / 500`;
}

function openTrainerRequestDialog() {
  if (!ElevenZeroApp.session?.authenticated) {
    ElevenZeroApp.redirectToAuth();
    return;
  }
  if (!trainerRequestDialog || !trainerDetailState.trainer) return;

  trainerRequestForm?.reset();
  updateTrainerRequestCount();
  ElevenZeroApp.setStatus(trainerRequestStatus, "");
  if (trainerRequestSubmit) {
    trainerRequestSubmit.disabled = false;
    trainerRequestSubmit.textContent = "Send request";
  }
  if (typeof trainerRequestDialog.showModal === "function") {
    trainerRequestDialog.showModal();
  } else {
    trainerRequestDialog.setAttribute("open", "");
  }
  window.setTimeout(() => trainerRequestMessage?.focus(), 0);
}

function closeTrainerRequestDialog() {
  if (!trainerRequestDialog?.open) return;
  if (typeof trainerRequestDialog.close === "function") {
    trainerRequestDialog.close();
  } else {
    trainerRequestDialog.removeAttribute("open");
  }
}

async function submitTrainerRequest(event) {
  event.preventDefault();
  if (!trainerDetailState.trainer) return;
  if (!ElevenZeroApp.requireAuth(trainerRequestStatus, "Sign in to request a lesson.")) return;

  const introMessage = String(trainerRequestMessage?.value || "").trim();
  if (introMessage.length > 500) {
    ElevenZeroApp.setStatus(
      trainerRequestStatus,
      "Keep your introduction under 500 characters.",
      "error"
    );
    return;
  }

  try {
    if (trainerRequestSubmit) {
      trainerRequestSubmit.disabled = true;
      trainerRequestSubmit.textContent = "Sending…";
    }
    const response = await ElevenZeroApp.request("/api/trainer-client/requests", {
      method: "POST",
      body: {
        trainerId: trainerDetailState.trainer.id,
        introMessage,
      },
    });
    trainerDetailState.viewerState.relationshipStatus = "pending";
    trainerDetailState.viewerState.relationshipId = null;
    renderTrainerDetail(
      trainerDetailState.trainer,
      trainerDetailState.reviews,
      trainerDetailState.viewerState
    );
    ElevenZeroApp.setStatus(
      trainerRequestStatus,
      response.message || "Your request was sent to the trainer.",
      "success"
    );
    if (trainerRequestSubmit) trainerRequestSubmit.textContent = "Request sent";
    window.setTimeout(closeTrainerRequestDialog, 900);
  } catch (error) {
    ElevenZeroApp.setStatus(trainerRequestStatus, error.message, "error");
    if (trainerRequestSubmit) {
      trainerRequestSubmit.disabled = false;
      trainerRequestSubmit.textContent = "Send request";
    }
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  await loadTrainerDetail();

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    if (target.closest("[data-trainer-request-open]")) {
      openTrainerRequestDialog();
      return;
    }

    const galleryButton = target.closest("[data-trainer-gallery-photo]");
    if (galleryButton) {
      const mainImage = trainerDetailShell.querySelector("[data-trainer-detail-image]");
      const photoUrl = galleryButton.dataset.trainerGalleryPhoto || "";
      if (mainImage && photoUrl) {
        mainImage.src = photoUrl;
        mainImage.alt = `${trainerDetailState.trainer?.name || "Trainer"} coaching photo`;
      }
      trainerDetailShell.querySelectorAll("[data-trainer-gallery-photo]").forEach((button) => {
        const isActive = button === galleryButton;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
      });
    }
  });

  trainerRequestMessage?.addEventListener("input", updateTrainerRequestCount);
  trainerRequestForm?.addEventListener("submit", submitTrainerRequest);
  document.querySelector("[data-trainer-request-close]")?.addEventListener(
    "click",
    closeTrainerRequestDialog
  );
  document.querySelector("[data-trainer-request-cancel]")?.addEventListener(
    "click",
    closeTrainerRequestDialog
  );
  trainerRequestDialog?.addEventListener("click", (event) => {
    if (event.target === trainerRequestDialog) closeTrainerRequestDialog();
  });
});

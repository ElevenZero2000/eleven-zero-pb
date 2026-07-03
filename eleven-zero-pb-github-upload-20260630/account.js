const accountName = document.querySelector("[data-account-name]");
const accountCopy = document.querySelector("[data-account-copy]");
const accountEmail = document.querySelector("[data-account-email]");
const accountStatus = document.querySelector("[data-account-status]");
const statListings = document.querySelector("[data-account-stat-listings]");
const statTrainers = document.querySelector("[data-account-stat-trainers]");
const statReviews = document.querySelector("[data-account-stat-reviews]");
const accountListings = document.querySelector("[data-account-listings]");
const accountTrainers = document.querySelector("[data-account-trainers]");
const sellerPill = document.querySelector("[data-seller-pill]");
const sellerSummary = document.querySelector("[data-seller-summary]");
const sellerProgress = document.querySelector("[data-seller-progress]");
const sellerConnectStatus = document.querySelector("[data-seller-connect-status]");
const sellerConnectButton = document.querySelector("[data-seller-connect-button]");
const sellerRefreshButton = document.querySelector("[data-seller-refresh-button]");
const adminPanel = document.querySelector("[data-admin-panel]");
const adminAnchor = document.querySelector("[data-owner-anchor]");
const adminPill = document.querySelector("[data-admin-pill]");
const adminSummary = document.querySelector("[data-admin-summary]");
const adminStats = document.querySelector("[data-admin-stats]");
const adminStatus = document.querySelector("[data-admin-status]");
const adminListings = document.querySelector("[data-admin-listings]");
const adminCourts = document.querySelector("[data-admin-courts]");
const adminTrainers = document.querySelector("[data-admin-trainers]");
const adminTrainerReviews = document.querySelector("[data-admin-trainer-reviews]");
const adminCourtReports = document.querySelector("[data-admin-court-reports]");
const ownerHelpCopy = document.querySelector("[data-owner-help-copy]");

let latestSellerProfile = null;

function renderDashboardList(target, items, renderItem, emptyTitle, emptyCopy) {
  if (!target) return;

  if (!items.length) {
    target.innerHTML = `
      <article class="list-item list-item-empty">
        <strong>${ElevenZeroApp.escapeHtml(emptyTitle)}</strong>
        <span>${ElevenZeroApp.escapeHtml(emptyCopy)}</span>
      </article>
    `;
    return;
  }

  target.innerHTML = items.map(renderItem).join("");
}

function getListingStatusTone(status) {
  if (status === "approved") return "ready";
  if (status === "rejected") return "neutral";
  return "pending";
}

function getListingStatusLabel(item) {
  if (item.approval_label) return item.approval_label;
  if (item.approval_status === "approved") return "Live";
  if (item.approval_status === "rejected") return "Needs changes";
  return "Pending review";
}

function renderListingItem(item) {
  const statusTone = getListingStatusTone(item.approval_status);
  const statusLabel = getListingStatusLabel(item);
  return `
    <article class="list-item">
      <strong>
        <a class="list-item-link" href="./listing.html?id=${ElevenZeroApp.escapeHtml(item.id)}">
          ${ElevenZeroApp.escapeHtml(item.brand)} ${ElevenZeroApp.escapeHtml(item.model)}
        </a>
      </strong>
      <span>${ElevenZeroApp.escapeHtml(item.category)} · ${ElevenZeroApp.formatMoney(
        item.price_usd
      )} · ${ElevenZeroApp.escapeHtml(item.location)}</span>
      <span class="list-item-status list-item-status-${ElevenZeroApp.escapeHtml(statusTone)}">
        ${ElevenZeroApp.escapeHtml(statusLabel)}
      </span>
    </article>
  `;
}

function renderTrainerItem(item) {
  return `
    <article class="list-item">
      <strong>${ElevenZeroApp.escapeHtml(item.name)}</strong>
      <span>${ElevenZeroApp.escapeHtml(item.level)} · ${ElevenZeroApp.escapeHtml(
        item.format
      )} · ${ElevenZeroApp.escapeHtml(item.rate)}</span>
    </article>
  `;
}

function sellerProgressItem(label, isReady, helper) {
  return `
    <article class="seller-progress-item ${isReady ? "is-ready" : "is-pending"}">
      <strong>${ElevenZeroApp.escapeHtml(label)}</strong>
      <span>${ElevenZeroApp.escapeHtml(helper)}</span>
    </article>
  `;
}

function renderSellerProfile(profile) {
  latestSellerProfile = profile || null;

  if (!profile) {
    if (sellerPill) sellerPill.textContent = "Unavailable";
    if (sellerSummary) {
      sellerSummary.textContent =
        "Seller payout details are not available yet for this account.";
    }
    if (sellerProgress) sellerProgress.innerHTML = "";
    return;
  }

  const steps = [
    sellerProgressItem(
      "Stripe connected account",
      profile.hasAccount,
      profile.hasAccount
        ? "Your seller account exists inside Stripe Connect."
        : "Create the connected seller account first."
    ),
    sellerProgressItem(
      "Business details submitted",
      profile.detailsSubmitted,
      profile.detailsSubmitted
        ? "Stripe has the required seller details."
        : "Finish the onboarding form with personal or business details."
    ),
    sellerProgressItem(
      "Charges enabled",
      profile.chargesEnabled,
      profile.chargesEnabled
        ? "This seller account can accept marketplace charges."
        : "Stripe still needs to finish payment checks."
    ),
    sellerProgressItem(
      "Payouts enabled",
      profile.payoutsEnabled,
      profile.payoutsEnabled
        ? "Stripe can send payout transfers to the seller."
        : "Stripe still needs payout readiness checks."
    ),
  ];

  if (sellerProgress) sellerProgress.innerHTML = steps.join("");

  if (!profile.connectConfigured) {
    if (sellerPill) sellerPill.textContent = "Keys needed";
    if (sellerSummary) {
      sellerSummary.textContent =
        "Stripe seller onboarding is built in, but this app still needs your Stripe API keys before sellers can connect.";
    }
    sellerConnectButton?.setAttribute("disabled", "disabled");
    sellerRefreshButton?.setAttribute("disabled", "disabled");
    return;
  }

  sellerConnectButton?.removeAttribute("disabled");
  if (profile.hasAccount) {
    sellerRefreshButton?.removeAttribute("disabled");
  } else {
    sellerRefreshButton?.setAttribute("disabled", "disabled");
  }

  if (profile.readyForPayouts) {
    if (sellerPill) sellerPill.textContent = "Payout ready";
    if (sellerSummary) {
      sellerSummary.textContent = `This account is ready for Stripe payouts. Eleven Zero PB is set to keep a ${profile.platformFeePercent}% platform fee once live checkout is added.`;
    }
    if (sellerConnectButton) sellerConnectButton.textContent = "Stripe ready";
    return;
  }

  if (profile.hasAccount) {
    if (sellerPill) sellerPill.textContent = "In progress";
    if (sellerSummary) {
      const outstanding =
        profile.requirementsDueCount > 0
          ? `${profile.requirementsDueCount} item${
              profile.requirementsDueCount === 1 ? "" : "s"
            } still need attention in Stripe.`
          : "Stripe still needs to finish a few checks before payouts go live.";

      sellerSummary.textContent = `Your seller profile has started. ${outstanding} Eleven Zero PB is set to keep a ${profile.platformFeePercent}% platform fee when payments turn on.`;
    }
    if (sellerConnectButton) sellerConnectButton.textContent = "Continue Stripe onboarding";
    return;
  }

  if (sellerPill) sellerPill.textContent = "Not started";
  if (sellerSummary) {
    sellerSummary.textContent = `Start Stripe onboarding so seller payouts can be connected to your Eleven Zero PB account. The current marketplace fee is set to ${profile.platformFeePercent}%.`;
  }
  if (sellerConnectButton) sellerConnectButton.textContent = "Start Stripe onboarding";
}

async function handleSellerOnboarding() {
  try {
    ElevenZeroApp.setStatus(
      sellerConnectStatus,
      "Preparing your Stripe seller onboarding link...",
      "warning"
    );
    const response = await ElevenZeroApp.request("/api/stripe/connect/onboard", {
      method: "POST",
      body: {},
    });
    if (response.sellerProfile) {
      renderSellerProfile(response.sellerProfile);
    }
    if (response.onboardingUrl) {
      window.location.href = response.onboardingUrl;
      return;
    }

    ElevenZeroApp.setStatus(
      sellerConnectStatus,
      response.message || "Your seller payout profile is already up to date.",
      "success"
    );
  } catch (error) {
    ElevenZeroApp.setStatus(sellerConnectStatus, error.message, "error");
  }
}

async function refreshSellerProfile() {
  try {
    ElevenZeroApp.setStatus(
      sellerConnectStatus,
      "Checking the latest Stripe payout status...",
      "warning"
    );
    const response = await ElevenZeroApp.request(
      "/api/stripe/connect/status/refresh",
      {
        method: "POST",
        body: {},
      }
    );
    renderSellerProfile(response.sellerProfile);
    ElevenZeroApp.setStatus(
      sellerConnectStatus,
      "Stripe payout status refreshed.",
      "success"
    );
  } catch (error) {
    ElevenZeroApp.setStatus(sellerConnectStatus, error.message, "error");
  }
}

function formatStars(count) {
  return "★".repeat(Math.max(1, Number(count || 0)));
}

function formatOwnerDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}

function adminStatCard(label, value, tone = "neutral") {
  return `
    <article class="admin-stat-card admin-stat-${ElevenZeroApp.escapeHtml(tone)}">
      <strong>${ElevenZeroApp.escapeHtml(String(value))}</strong>
      <span>${ElevenZeroApp.escapeHtml(label)}</span>
    </article>
  `;
}

function setAdminStatus(message, tone = "neutral") {
  ElevenZeroApp.setStatus(adminStatus, message, tone);
}

function escapeAttr(value) {
  return ElevenZeroApp.escapeHtml(String(value ?? ""));
}

function optionList(options, selectedValue) {
  return options
    .map(
      (value) =>
        `<option value="${escapeAttr(value)}"${
          String(selectedValue) === String(value) ? " selected" : ""
        }>${escapeAttr(value)}</option>`
    )
    .join("");
}

function checkedAttr(value) {
  return value ? "checked" : "";
}

function renderAdminEmpty(target, title, copy) {
  if (!target) return;
  target.innerHTML = `
    <article class="list-item list-item-empty">
      <strong>${escapeAttr(title)}</strong>
      <span>${escapeAttr(copy)}</span>
    </article>
  `;
}

function renderAdminListings(items) {
  if (!adminListings) return;
  if (!items.length) {
    renderAdminEmpty(adminListings, "No listings yet", "Submitted paddle listings will appear here for review.");
    return;
  }

  adminListings.innerHTML = items
    .map(
      (item) => {
        const statusTone = getListingStatusTone(item.approval_status);
        const statusLabel = getListingStatusLabel(item);

        return `
        <details class="admin-record">
          <summary>
            <div>
              <strong>${escapeAttr(item.brand)} ${escapeAttr(item.model)}</strong>
              <span>${ElevenZeroApp.formatMoney(item.price_usd)} · ${escapeAttr(item.location)}</span>
              <span class="admin-record-badge admin-record-badge-${escapeAttr(statusTone)}">${escapeAttr(statusLabel)}</span>
            </div>
            <span class="admin-record-meta">${escapeAttr(item.seller_email || "No seller email")}</span>
          </summary>

          <form class="admin-editor-form" data-admin-form="listing" data-record-id="${escapeAttr(item.id)}">
            <div class="admin-field-grid">
              <label>Brand <input name="brand" value="${escapeAttr(item.brand)}" /></label>
              <label>Model <input name="model" value="${escapeAttr(item.model)}" /></label>
              <label>Color <input name="color" value="${escapeAttr(item.color || "")}" /></label>
              <label>Thickness (mm) <input name="thickness" type="number" min="8" max="25" step="0.1" value="${escapeAttr(item.thickness_mm || "")}" /></label>
              <label>Category
                <select name="category">${optionList(["control", "power", "hybrid"], item.category)}</select>
              </label>
              <label>Condition
                <select name="condition">${optionList(["Excellent", "Very Good", "Good"], item.condition)}</select>
              </label>
              <label>Price <input name="price" value="${escapeAttr(item.price_usd)}" /></label>
              <label>Location <input name="location" value="${escapeAttr(item.location)}" /></label>
            </div>

            <label class="admin-field-block">
              Notes
              <textarea name="notes" rows="4">${escapeAttr(item.notes)}</textarea>
            </label>

            <div class="admin-review-actions">
              <button class="button button-dark" type="button" data-admin-review="approved" data-record-id="${escapeAttr(item.id)}">
                Approve + publish
              </button>
              <button class="button button-secondary" type="button" data-admin-review="pending" data-record-id="${escapeAttr(item.id)}">
                Move back to review
              </button>
              <button class="button button-secondary" type="button" data-admin-review="rejected" data-record-id="${escapeAttr(item.id)}">
                Mark needs changes
              </button>
            </div>

            <div class="admin-actions">
              <a class="button button-secondary" href="./listing.html?id=${escapeAttr(item.id)}" target="_blank" rel="noreferrer">Open listing</a>
              <button class="button button-dark" type="submit">Save listing</button>
              <button class="button button-secondary admin-delete-button" type="button" data-admin-delete="listing" data-record-id="${escapeAttr(item.id)}">Remove listing</button>
            </div>
          </form>
        </details>
      `;
      }
    )
    .join("");
}

function renderAdminCourts(items) {
  if (!adminCourts) return;
  if (!items.length) {
    renderAdminEmpty(adminCourts, "No courts yet", "Saved courts will show up here for quick moderation.");
    return;
  }

  adminCourts.innerHTML = items
    .map(
      (item) => `
        <details class="admin-record">
          <summary>
            <div>
              <strong>${escapeAttr(item.name)}</strong>
              <span>${escapeAttr(item.location)} · ${escapeAttr(item.accessKind)}</span>
            </div>
            <span class="admin-record-meta">${escapeAttr(item.owner_email || "Directory")}</span>
          </summary>

          <form class="admin-editor-form" data-admin-form="court" data-record-id="${escapeAttr(item.record_id)}">
            <div class="admin-field-grid">
              <label>Name <input name="name" value="${escapeAttr(item.name)}" /></label>
              <label>Location <input name="location" value="${escapeAttr(item.location)}" /></label>
              <label>Address <input name="address" value="${escapeAttr(item.address || "")}" /></label>
              <label>Court count <input name="courtCount" type="number" min="1" value="${escapeAttr(item.court_count)}" /></label>
              <label>Access
                <select name="accessKind">${optionList(["free", "paid", "check"], item.accessKind)}</select>
              </label>
              <label>Surface
                <select name="surfaceKind">${optionList(["indoor", "outdoor"], item.surfaceKind)}</select>
              </label>
              <label>Access note <input name="accessNote" value="${escapeAttr(item.access_note || "")}" /></label>
              <label>Website <input name="website" value="${escapeAttr(item.website || "")}" /></label>
            </div>

            <label class="admin-field-block">
              Amenities
              <input name="amenities" value="${escapeAttr(item.amenities || "")}" />
            </label>

            <label class="admin-field-block">
              Description
              <textarea name="description" rows="4">${escapeAttr(item.description)}</textarea>
            </label>

            <div class="admin-actions">
              <button class="button button-dark" type="submit">Save court</button>
              <button class="button button-secondary admin-delete-button" type="button" data-admin-delete="court" data-record-id="${escapeAttr(item.record_id)}">Remove court</button>
            </div>
          </form>
        </details>
      `
    )
    .join("");
}

function renderAdminTrainers(items) {
  if (!adminTrainers) return;
  if (!items.length) {
    renderAdminEmpty(adminTrainers, "No trainers yet", "Trainer profiles will appear here once they go live.");
    return;
  }

  adminTrainers.innerHTML = items
    .map(
      (item) => `
        <details class="admin-record">
          <summary>
            <div>
              <strong>${escapeAttr(item.name)}</strong>
              <span>${escapeAttr(item.location)} · ${escapeAttr(item.level)} · ${escapeAttr(item.rate)}</span>
            </div>
            <span class="admin-record-meta">${escapeAttr(item.owner_email || item.email)}</span>
          </summary>

          <form class="admin-editor-form" data-admin-form="trainer" data-record-id="${escapeAttr(item.id)}">
            <div class="admin-field-grid">
              <label>Name <input name="name" value="${escapeAttr(item.name)}" /></label>
              <label>Location <input name="location" value="${escapeAttr(item.location)}" /></label>
              <label>Format
                <select name="format">${optionList(["private", "group", "clinic", "virtual"], item.format)}</select>
              </label>
              <label>Level
                <select name="level">${optionList(["beginner", "intermediate", "advanced"], item.level)}</select>
              </label>
              <label>Rate <input name="rate" value="${escapeAttr(item.rate)}" /></label>
              <label>Email <input name="email" value="${escapeAttr(item.email)}" /></label>
              <label>Experience <input name="experience" value="${escapeAttr(item.experience)}" /></label>
              <label>Availability <input name="availability" value="${escapeAttr(item.availability)}" /></label>
            </div>

            <label class="admin-checkbox-row">
              <input name="verified" type="checkbox" ${checkedAttr(item.verified)} />
              <span>Verified trainer</span>
            </label>

            <label class="admin-field-block">
              Bio
              <textarea name="bio" rows="4">${escapeAttr(item.bio)}</textarea>
            </label>

            <div class="admin-actions">
              <button class="button button-dark" type="submit">Save trainer</button>
              <button class="button button-secondary admin-delete-button" type="button" data-admin-delete="trainer" data-record-id="${escapeAttr(item.id)}">Remove trainer</button>
            </div>
          </form>
        </details>
      `
    )
    .join("");
}

function renderAdminReviews(target, items, type) {
  if (!target) return;
  if (!items.length) {
    renderAdminEmpty(
      target,
      "Nothing to moderate yet",
      type === "trainerReview" ? "Trainer reviews will appear here." : "Court reports will appear here."
    );
    return;
  }

  target.innerHTML = items
    .map((item) => {
      const title =
        type === "trainerReview"
          ? `${item.trainer_name} · ${item.reviewer_name}`
          : `${item.court_name} · ${item.reviewer_name}`;
      const meta =
        type === "trainerReview"
          ? `${formatStars(item.rating)} · ${formatOwnerDate(item.created_at)}`
          : `${formatStars(item.condition_rating)} · ${formatOwnerDate(item.created_at)}`;

      return `
        <article class="admin-review-card">
          <strong>${escapeAttr(title)}</strong>
          <span>${escapeAttr(meta)}</span>
          <p>${escapeAttr(item.comment)}</p>
          <button
            class="button button-secondary admin-delete-button"
            type="button"
            data-admin-delete="${type}"
            data-record-id="${escapeAttr(item.id)}"
          >
            Remove
          </button>
        </article>
      `;
    })
    .join("");
}

async function loadAdminDashboard() {
  if (!ElevenZeroApp.session?.user?.isAdmin) {
    adminPanel?.classList.add("is-hidden");
    adminAnchor?.classList.add("is-hidden");
    return;
  }

  adminPanel?.classList.remove("is-hidden");
  adminAnchor?.classList.remove("is-hidden");

  try {
    setAdminStatus("Loading owner tools…", "warning");
    const response = await ElevenZeroApp.request("/api/admin/dashboard");
    const stats = response.stats || {};

    if (adminPill) adminPill.textContent = "Moderator active";
    if (adminSummary) {
      adminSummary.textContent =
        "You are signed in with the owner account, so you can review seller submissions before they go live, plus edit or remove website content here.";
    }

    if (adminStats) {
      adminStats.innerHTML = [
        adminStatCard("Users", stats.users || 0, "neutral"),
        adminStatCard("Listings total", stats.listings || 0, "neutral"),
        adminStatCard("Pending review", stats.listingPending || 0, "pending"),
        adminStatCard("Live listings", stats.listingApproved || 0, "ready"),
        adminStatCard("Needs changes", stats.listingNeedsChanges || 0, "neutral"),
        adminStatCard("Courts", stats.courts || 0, "ready"),
        adminStatCard("Trainers", stats.trainers || 0, "ready"),
        adminStatCard("Trainer reviews", stats.trainerReviews || 0, "pending"),
        adminStatCard("Court reports", stats.courtReports || 0, "pending"),
      ].join("");
    }

    renderAdminListings(response.listings || []);
    renderAdminCourts(response.courts || []);
    renderAdminTrainers(response.trainers || []);
    renderAdminReviews(adminTrainerReviews, response.trainerReviews || [], "trainerReview");
    renderAdminReviews(adminCourtReports, response.courtReports || [], "courtReport");
    setAdminStatus("Owner tools loaded.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

function collectAdminFormPayload(form) {
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  payload.id = Number(form.dataset.recordId || 0);

  if (form.dataset.adminForm === "trainer") {
    payload.verified = form.querySelector('input[name="verified"]')?.checked || false;
  }

  return payload;
}

async function saveAdminRecord(form) {
  const type = form.dataset.adminForm;
  const payload = collectAdminFormPayload(form);

  const routeByType = {
    listing: "/api/admin/listings/update",
    court: "/api/admin/courts/update",
    trainer: "/api/admin/trainers/update",
  };

  const route = routeByType[type];
  if (!route) return;

  try {
    setAdminStatus("Saving your changes…", "warning");
    await ElevenZeroApp.request(route, {
      method: "POST",
      body: payload,
    });
    await loadAdminDashboard();
    setAdminStatus("Changes saved.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

async function reviewAdminListing(recordId, status) {
  const statusLabel =
    status === "approved"
      ? "approve and publish"
      : status === "rejected"
        ? "mark for changes"
        : "move back to review";

  try {
    setAdminStatus(`Updating listing review status…`, "warning");
    await ElevenZeroApp.request("/api/admin/listings/review", {
      method: "POST",
      body: { id: Number(recordId || 0), status },
    });
    await loadAdminDashboard();
    setAdminStatus(`Listing updated: ${statusLabel}.`, "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

async function deleteAdminRecord(type, recordId) {
  const routeByType = {
    listing: "/api/admin/listings/delete",
    court: "/api/admin/courts/delete",
    trainer: "/api/admin/trainers/delete",
    trainerReview: "/api/admin/trainer-reviews/delete",
    courtReport: "/api/admin/court-reports/delete",
  };

  const route = routeByType[type];
  if (!route) return;

  const labels = {
    listing: "listing",
    court: "court",
    trainer: "trainer profile",
    trainerReview: "trainer review",
    courtReport: "court report",
  };

  const confirmed = window.confirm(`Remove this ${labels[type]} from the website?`);
  if (!confirmed) return;

  try {
    setAdminStatus(`Removing ${labels[type]}…`, "warning");
    await ElevenZeroApp.request(route, {
      method: "POST",
      body: { id: Number(recordId || 0) },
    });
    await loadAdminDashboard();
    setAdminStatus(`${labels[type][0].toUpperCase()}${labels[type].slice(1)} removed.`, "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

function bindAdminPanel() {
  adminPanel?.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-admin-form]");
    if (!form) return;
    event.preventDefault();
    await saveAdminRecord(form);
  });

  adminPanel?.addEventListener("click", async (event) => {
    const reviewButton = event.target.closest("[data-admin-review]");
    if (reviewButton) {
      await reviewAdminListing(reviewButton.dataset.recordId, reviewButton.dataset.adminReview);
      return;
    }

    const button = event.target.closest("[data-admin-delete]");
    if (!button) return;
    await deleteAdminRecord(button.dataset.adminDelete, button.dataset.recordId);
  });
}

async function loadDashboard() {
  try {
    const response = await ElevenZeroApp.request("/api/dashboard");
    const user = response.user;
    const stats = response.stats || { listings: 0, trainers: 0, reviews: 0 };

    if (accountName) accountName.textContent = `Welcome back, ${user.name}.`;
    if (accountCopy) {
      accountCopy.textContent = user.isAdmin
        ? "You’re in the owner account. This dashboard now includes moderator tools for live site content."
        : "This dashboard tracks the live activity tied to your Eleven Zero PB account.";
    }
    if (ownerHelpCopy) {
      ownerHelpCopy.innerHTML = user.isAdmin
        ? "You’re already signed in with the owner account, so the moderator tools below are active for live listings, courts, trainers, and reviews."
        : `If you sign in with <strong>${ElevenZeroApp.escapeHtml(
            ElevenZeroApp.config.supportEmail || "11zeropb@gmail.com"
          )}</strong>, this dashboard unlocks the live moderator panel for listings, courts, trainers, and reviews.`;
    }
    if (accountEmail) accountEmail.textContent = user.email;
    if (statListings) statListings.textContent = String(stats.listings);
    if (statTrainers) statTrainers.textContent = String(stats.trainers);
    if (statReviews) statReviews.textContent = String(stats.reviews);

    renderDashboardList(
      accountListings,
      response.recentListings || [],
      renderListingItem,
      "No listings yet",
      "Submit your first paddle from the Sell page."
    );
    renderDashboardList(
      accountTrainers,
      response.recentTrainers || [],
      renderTrainerItem,
      "No trainer profiles yet",
      "Publish your first trainer profile from the trainers page."
    );
    renderSellerProfile(response.sellerProfile || response.user?.sellerProfile);

    ElevenZeroApp.setStatus(accountStatus, "Dashboard loaded successfully.", "success");
  } catch (error) {
    ElevenZeroApp.setStatus(accountStatus, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;

  if (!ElevenZeroApp.session?.authenticated) {
    ElevenZeroApp.setStatus(
      accountStatus,
      "Please sign in to open your dashboard.",
      "warning"
    );
    window.setTimeout(() => {
      ElevenZeroApp.redirectToAuth("./account.html");
    }, 700);
    return;
  }

  bindAdminPanel();
  await loadDashboard();
  await loadAdminDashboard();
  sellerConnectButton?.addEventListener("click", handleSellerOnboarding);
  sellerRefreshButton?.addEventListener("click", refreshSellerProfile);
});

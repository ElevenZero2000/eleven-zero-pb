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

function renderListingItem(item) {
  return `
    <article class="list-item">
      <strong>${ElevenZeroApp.escapeHtml(item.brand)} ${ElevenZeroApp.escapeHtml(
        item.model
      )}</strong>
      <span>${ElevenZeroApp.escapeHtml(item.category)} · ${ElevenZeroApp.formatMoney(
        item.price_usd
      )} · ${ElevenZeroApp.escapeHtml(item.location)}</span>
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

async function loadDashboard() {
  try {
    const response = await ElevenZeroApp.request("/api/dashboard");
    const user = response.user;
    const stats = response.stats || { listings: 0, trainers: 0, reviews: 0 };

    if (accountName) accountName.textContent = `Welcome back, ${user.name}.`;
    if (accountCopy) {
      accountCopy.textContent =
        "This dashboard tracks the live activity tied to your Eleven Zero PB account.";
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
      "Publish your first paddle from the marketplace page."
    );
    renderDashboardList(
      accountTrainers,
      response.recentTrainers || [],
      renderTrainerItem,
      "No trainer profiles yet",
      "Publish your first trainer profile from the trainers page."
    );
    renderSellerProfile(response.sellerProfile || response.user?.sellerProfile);

    ElevenZeroApp.setStatus(
      accountStatus,
      "Dashboard loaded successfully.",
      "success"
    );
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

  await loadDashboard();
  sellerConnectButton?.addEventListener("click", handleSellerOnboarding);
  sellerRefreshButton?.addEventListener("click", refreshSellerProfile);
});

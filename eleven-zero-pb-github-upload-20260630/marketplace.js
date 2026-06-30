const listingThemes = {
  control: { artClass: "art-sand", paddleClass: "paddle-carbon", label: "Control" },
  power: { artClass: "art-charcoal", paddleClass: "paddle-sunset", label: "Power" },
  hybrid: { artClass: "art-green", paddleClass: "paddle-lime", label: "Hybrid" },
};

const listingState = {
  filter: "all",
  items: [],
  buyingListingId: null,
};

const listingGrid = document.querySelector("[data-listings-grid]");
const listingHeading = document.querySelector("[data-listings-heading]");
const listingNote = document.querySelector("[data-listings-note]");
const listingCount = document.querySelector("[data-listing-count]");
const listingForm = document.querySelector("[data-seller-form]");
const listingStatus = document.querySelector("[data-seller-status]");
const marketplaceStatus = document.querySelector("[data-marketplace-status]");
const filterButtons = Array.from(document.querySelectorAll("[data-filter]"));

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

  return `
    <article class="product-card reveal is-visible" data-category="${ElevenZeroApp.escapeHtml(
      item.category
    )}">
      <div class="card-art ${ElevenZeroApp.escapeHtml(theme.artClass)}">
        <div class="paddle-graphic ${ElevenZeroApp.escapeHtml(theme.paddleClass)}"></div>
        <span class="condition-tag">${ElevenZeroApp.escapeHtml(item.condition)}</span>
      </div>
      <div class="card-body">
        <div class="card-headline">
          <div>
            <p class="product-brand">${ElevenZeroApp.escapeHtml(item.brand)}</p>
            <h3>${ElevenZeroApp.escapeHtml(item.model)}</h3>
          </div>
          <span class="price">${ElevenZeroApp.formatMoney(item.price_usd)}</span>
        </div>
        <p class="product-copy">${ElevenZeroApp.escapeHtml(item.notes)}</p>
        <div class="card-footer">
          <span>${ElevenZeroApp.escapeHtml(theme.label)}</span>
          <span>${ElevenZeroApp.escapeHtml(item.location)}</span>
          <span>${ElevenZeroApp.escapeHtml(sellerName)}</span>
        </div>
        <div class="listing-purchase-row">
          <div class="listing-purchase-copy">
            <span class="listing-status-pill listing-status-${ElevenZeroApp.escapeHtml(
              actionState.tone
            )}">${ElevenZeroApp.escapeHtml(actionState.statusLabel)}</span>
            <p class="listing-status-copy">${ElevenZeroApp.escapeHtml(actionState.reason)}</p>
          </div>
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
    </article>
  `;
}

function renderListingEmptyState() {
  if (!listingGrid) return;

  listingGrid.innerHTML = `
    <article class="empty-state reveal is-visible">
      <p class="eyebrow">No matches</p>
      <h3>No listings match that filter yet.</h3>
      <p>Try another filter or publish a new paddle listing after signing in.</p>
    </article>
  `;
}

function getVisibleListings() {
  return listingState.items.filter((item) => {
    return listingState.filter === "all" || item.category === listingState.filter;
  });
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
        setMarketplaceStatus("Please sign in first so we can open a secure buyer checkout for you.", "warning");
        window.setTimeout(() => {
          ElevenZeroApp.redirectToAuth(`${window.location.pathname}#shop`);
        }, 700);
        return;
      }

      await handleBuyListing(listingId);
    });
  });
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

  const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;

  if (listingNote) {
    listingNote.textContent = !ElevenZeroApp.session?.authenticated
      ? "Sign in to publish your own paddle into the live feed and unlock buyer checkout."
      : !sellerProfile?.connectConfigured
        ? "You can publish listings now. Stripe seller payouts are built in, but this app still needs Stripe keys before checkout can go live."
        : !sellerProfile?.readyForPayouts
          ? "You can publish listings now. Finish seller payouts in Account before buyers can pay you through the marketplace."
          : "You’re signed in and payout-ready on Stripe, so buyers can use secure checkout on your eligible listings.";
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
    setMarketplaceStatus("Checkout was canceled. Your marketplace browsing is still right here when you’re ready.", "warning");
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

    setMarketplaceStatus(`Opening secure checkout for ${response.listing?.title || "your listing"}.`, "success");
    window.location.href = response.checkoutUrl;
  } catch (error) {
    setMarketplaceStatus(error.message, "error");
  } finally {
    listingState.buyingListingId = null;
    renderListings();
  }
}

async function handleListingSubmit(event) {
  event.preventDefault();

  if (!ElevenZeroApp.requireAuth(listingStatus, "Please sign in first to publish a listing.")) {
    return;
  }

  const formData = new FormData(listingForm);
  const payload = Object.fromEntries(formData.entries());

  try {
    await ElevenZeroApp.request("/api/listings", {
      method: "POST",
      body: payload,
    });
    listingForm.reset();
    const sellerProfile = ElevenZeroApp.session?.user?.sellerProfile;
    ElevenZeroApp.setStatus(
      listingStatus,
      sellerProfile?.readyForPayouts
        ? `${payload.brand} ${payload.model} is now live in the marketplace. Your seller payouts are already connected.`
        : `${payload.brand} ${payload.model} is now live in the marketplace. Next step: finish seller payouts in Account before live checkout turns on.`,
      "success"
    );
    await loadListings();
  } catch (error) {
    ElevenZeroApp.setStatus(listingStatus, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;
  await loadListings();
  await handleCheckoutReturn();

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      listingState.filter = button.dataset.filter || "all";
      renderListings();
    });
  });

  listingForm?.addEventListener("submit", handleListingSubmit);
});

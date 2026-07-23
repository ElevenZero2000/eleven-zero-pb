const accountName = document.querySelector("[data-account-name]");
const accountCopy = document.querySelector("[data-account-copy]");
const accountEmail = document.querySelector("[data-account-email]");
const accountStatus = document.querySelector("[data-account-status]");
const statListings = document.querySelector("[data-account-stat-listings]");
const statTrainers = document.querySelector("[data-account-stat-trainers]");
const statReviews = document.querySelector("[data-account-stat-reviews]");
const accountListings = document.querySelector("[data-account-listings]");
const accountTrainers = document.querySelector("[data-account-trainers]");
const accountPurchases = document.querySelector("[data-account-purchases]");
const accountSales = document.querySelector("[data-account-sales]");
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
const adminProfiles = document.querySelector("[data-admin-profiles]");
const adminListings = document.querySelector("[data-admin-listings]");
const adminCourts = document.querySelector("[data-admin-courts]");
const adminTrainers = document.querySelector("[data-admin-trainers]");
const adminTrainerReviews = document.querySelector("[data-admin-trainer-reviews]");
const adminCourtReports = document.querySelector("[data-admin-court-reports]");
const adminCommerceNotifications = document.querySelector("[data-admin-commerce-notifications]");
const adminSalesSummary = document.querySelector("[data-admin-sales-summary]");
const adminSalesChart = document.querySelector("[data-admin-sales-chart]");
const adminChartNote = document.querySelector("[data-admin-chart-note]");
const ownerHelpCopy = document.querySelector("[data-owner-help-copy]");
const verificationBanner = document.querySelector("[data-email-verification-banner]");
const verificationBannerStatus = document.querySelector("[data-verification-banner-status]");
const accountModeTag = document.querySelector("[data-account-mode-tag]");
const adminModeBanner = document.querySelector("[data-admin-mode-banner]");
const adminQuickActions = document.querySelector("[data-admin-quick-actions]");
const customerAccountActions = document.querySelector("[data-account-actions]");
const customerAccountPoints = document.querySelector("[data-account-points]");
const accountProfileName = document.querySelector("[data-account-profile-name]");
const accountAvatar = document.querySelector("[data-account-avatar]");
const accountAvatarFallback = document.querySelector("[data-account-avatar-fallback]");
const profileSettingsOpen = document.querySelector("[data-profile-settings-open]");
const profileDialog = document.querySelector("[data-profile-dialog]");
const profileForm = document.querySelector("[data-profile-form]");
const profileNameInput = document.querySelector("[data-profile-name-input]");
const profileEmail = document.querySelector("[data-profile-email]");
const profileImageInput = document.querySelector("[data-profile-image-input]");
const profileImageRemove = document.querySelector("[data-profile-image-remove]");
const profilePreviewImage = document.querySelector("[data-profile-preview-image]");
const profilePreviewFallback = document.querySelector("[data-profile-preview-fallback]");
const profileStatus = document.querySelector("[data-profile-status]");
const profileSaveButton = document.querySelector("[data-profile-save]");
const profileReviewBanner = document.querySelector("[data-profile-review-banner]");

let latestSellerProfile = null;
let latestSalesAnalytics = {};
let activeSalesPeriod = "day";
let latestAccountUser = null;
let profileImageDraft;

function profileInitials(name) {
  const words = String(name || "Eleven Zero")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() || "")
    .join("") || "EZ";
}

function renderAvatar(imageNode, fallbackNode, name, imageSource = "") {
  if (!imageNode || !fallbackNode) return;

  fallbackNode.textContent = profileInitials(name);
  if (!imageSource) {
    imageNode.hidden = true;
    imageNode.removeAttribute("src");
    fallbackNode.hidden = false;
    return;
  }

  imageNode.onload = () => {
    imageNode.hidden = false;
    fallbackNode.hidden = true;
  };
  imageNode.onerror = () => {
    imageNode.hidden = true;
    fallbackNode.hidden = false;
  };
  imageNode.src = imageSource;
}

function renderAccountProfile(user = {}) {
  latestAccountUser = user;
  if (accountProfileName) accountProfileName.textContent = user.name || "Your profile";
  if (accountEmail) accountEmail.textContent = user.email || "";
  renderAvatar(accountAvatar, accountAvatarFallback, user.name, user.profileImageUrl || "");
  renderProfileReviewStatus(user);
}

function renderProfileReviewStatus(user = {}) {
  if (!profileReviewBanner) return;
  const status = user.profileReviewStatus || "approved";
  if (status === "pending") {
    profileReviewBanner.hidden = false;
    profileReviewBanner.className = "profile-review-banner is-pending";
    profileReviewBanner.innerHTML = `
      <strong>Profile changes are waiting for review</strong>
      <span>Your current approved name and photo stay visible until Eleven Zero PB approves the update.</span>
    `;
    return;
  }
  if (status === "rejected") {
    profileReviewBanner.hidden = false;
    profileReviewBanner.className = "profile-review-banner is-rejected";
    profileReviewBanner.innerHTML = `
      <strong>Your last profile update was not approved</strong>
      <span>${escapeAttr(user.profileReviewNote || "Your current approved profile is still visible. You can submit a different name or photo.")}</span>
    `;
    return;
  }
  profileReviewBanner.hidden = true;
  profileReviewBanner.className = "profile-review-banner";
  profileReviewBanner.innerHTML = "";
}

function renderProfilePreview(imageSource = "") {
  const name = profileNameInput?.value || latestAccountUser?.name || "Eleven Zero";
  renderAvatar(profilePreviewImage, profilePreviewFallback, name, imageSource);
}

function openProfileSettings() {
  if (!profileDialog || !latestAccountUser) return;
  profileImageDraft = undefined;
  if (profileNameInput) {
    profileNameInput.value =
      latestAccountUser.profileReviewStatus === "pending" && latestAccountUser.profilePendingName
        ? latestAccountUser.profilePendingName
        : latestAccountUser.name || "";
  }
  if (profileEmail) profileEmail.textContent = latestAccountUser.email || "";
  if (profileImageInput) profileImageInput.value = "";
  ElevenZeroApp.setStatus(profileStatus, "");
  const previewSource =
    latestAccountUser.profileReviewStatus === "pending"
      ? latestAccountUser.profilePendingImageAction === "remove"
        ? ""
        : latestAccountUser.profilePendingImageUrl || latestAccountUser.profileImageUrl || ""
      : latestAccountUser.profileImageUrl || "";
  renderProfilePreview(previewSource);
  profileDialog.showModal();
  document.body.classList.add("has-modal-open");
  window.setTimeout(() => profileNameInput?.focus(), 40);
}

function closeProfileSettings() {
  if (!profileDialog?.open) return;
  profileDialog.close();
  document.body.classList.remove("has-modal-open");
}

function loadImageElement(source) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("That photo could not be opened."));
    image.src = source;
  });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("That photo could not be read."));
    reader.readAsDataURL(file);
  });
}

async function optimizeProfileImage(file) {
  const supportedTypes = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
  ]);
  const fileExtension = String(file.name || "").split(".").pop()?.toLowerCase() || "";
  const supportedExtensions = new Set(["jpg", "jpeg", "png", "webp", "heic", "heif"]);
  if (!supportedTypes.has(file.type) && !supportedExtensions.has(fileExtension)) {
    throw new Error("Choose a JPG, PNG, WebP, or iPhone photo.");
  }
  if (file.size > 10 * 1024 * 1024) {
    throw new Error("Choose a photo smaller than 10 MB.");
  }

  const fileDataUrl = await readFileAsDataUrl(file);
  const image = await loadImageElement(fileDataUrl);
  const sourceSize = Math.min(image.naturalWidth, image.naturalHeight);
  const sourceX = Math.max((image.naturalWidth - sourceSize) / 2, 0);
  const sourceY = Math.max((image.naturalHeight - sourceSize) / 2, 0);

  const createSquare = (size, quality) => {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, size, size);
    context.drawImage(image, sourceX, sourceY, sourceSize, sourceSize, 0, 0, size, size);
    return canvas.toDataURL("image/jpeg", quality);
  };

  let result = createSquare(512, 0.84);
  if (result.length > 1_000_000) result = createSquare(384, 0.76);
  if (result.length > 1_000_000) {
    throw new Error("That photo is still too large. Try a smaller image.");
  }
  return result;
}

async function handleProfileImageSelection(event) {
  const [file] = Array.from(event.target.files || []);
  if (!file) return;

  try {
    ElevenZeroApp.setStatus(profileStatus, "Preparing your photo…", "warning");
    profileImageDraft = await optimizeProfileImage(file);
    renderProfilePreview(profileImageDraft);
    ElevenZeroApp.setStatus(profileStatus, "Photo ready to save.", "success");
  } catch (error) {
    profileImageDraft = undefined;
    event.target.value = "";
    renderProfilePreview(latestAccountUser?.profileImageUrl || "");
    ElevenZeroApp.setStatus(profileStatus, error.message, "error");
  }
}

async function saveProfileSettings(event) {
  event.preventDefault();
  if (!profileNameInput || profileSaveButton?.disabled) return;

  const body = { name: profileNameInput.value.trim() };
  if (profileImageDraft !== undefined) body.profileImage = profileImageDraft;

  if (profileSaveButton) {
    profileSaveButton.disabled = true;
    profileSaveButton.textContent = "Saving…";
  }
  try {
    ElevenZeroApp.setStatus(profileStatus, "Submitting your profile for review…", "warning");
    const response = await ElevenZeroApp.request("/api/account/profile", {
      method: "POST",
      body,
    });
    ElevenZeroApp.session.user = response.user;
    renderAccountProfile(response.user);
    applyAccountMode(response.user);
    ElevenZeroApp.renderAuthSlots();
    if (accountName) {
      accountName.textContent = response.user.isAdmin
        ? "Eleven Zero Account Manager"
        : `Welcome back, ${response.user.name}.`;
    }
    ElevenZeroApp.setStatus(
      profileStatus,
      response.message || "Profile changes submitted for review.",
      "success"
    );
    window.setTimeout(closeProfileSettings, 550);
  } catch (error) {
    ElevenZeroApp.setStatus(profileStatus, error.message, "error");
  } finally {
    if (profileSaveButton) {
      profileSaveButton.disabled = false;
      profileSaveButton.textContent = "Save changes";
    }
  }
}

function applyAccountMode(user = {}) {
  const isAdmin = Boolean(user?.isAdmin);
  document.body.classList.toggle("account-admin-mode", isAdmin);
  adminModeBanner?.classList.toggle("is-hidden", !isAdmin);
  adminQuickActions?.classList.toggle("is-hidden", !isAdmin);
  customerAccountActions?.classList.toggle("is-hidden", isAdmin);
  customerAccountPoints?.classList.toggle("is-hidden", isAdmin);

  if (accountModeTag) {
    accountModeTag.textContent = isAdmin ? "Account Manager" : "Account Dashboard";
  }

  const bannerEmail = adminModeBanner?.querySelector("span:last-child");
  if (bannerEmail && isAdmin) {
    bannerEmail.textContent = user.email || "11zeropb@gmail.com";
  }
}

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
  if (item.sale_status === "sold") return "Sold";
  if (item.sale_status === "pending") return "Sale pending";
  if (item.sale_status === "reserved") return "Checkout in progress";
  if (item.approval_label) return item.approval_label;
  if (item.approval_status === "approved") return "Live";
  if (item.approval_status === "rejected") return "Needs changes";
  return "Pending review";
}

function renderListingItem(item) {
  const statusTone = item.sale_status === "sold" ? "neutral" : ["pending", "reserved"].includes(item.sale_status) ? "pending" : getListingStatusTone(item.approval_status);
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

function formatCents(value) {
  const amount = Number(value || 0) / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function cleanStatus(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function getPayoutState(item, perspective = "seller") {
  const payoutStatus = String(item.payout_status || "");
  const trackingStatus = String(item.tracking_status || "").toUpperCase();
  const hasOpenIssue = item.buyer_issue_status === "open";
  const isBuyer = perspective === "buyer";

  if (item.payment_flow === "legacy_destination_charge") {
    return {
      label: isBuyer ? "Order paid" : "Paid through previous checkout",
      copy: isBuyer
        ? "This order used the earlier Eleven Zero checkout flow."
        : "Stripe routed these proceeds through the previous payout flow.",
      tone: "ready",
    };
  }
  if (hasOpenIssue || payoutStatus === "on_hold") {
    return {
      label: "Problem under review",
      copy: isBuyer
        ? "Your report is open. Seller proceeds remain on hold while Eleven Zero PB reviews it."
        : "Seller proceeds are on hold while Eleven Zero PB reviews the buyer’s report.",
      tone: "attention",
    };
  }
  if (payoutStatus === "released" || item.stripe_transfer_id) {
    return {
      label: isBuyer ? "Order complete" : "Proceeds released",
      copy: isBuyer
        ? "The delivery protection period is complete."
        : "Proceeds were released to your connected Stripe balance. Bank arrival follows your Stripe payout schedule.",
      tone: "ready",
    };
  }
  if (payoutStatus === "releasing") {
    return {
      label: "Releasing proceeds",
      copy: isBuyer
        ? "The order is complete and the seller transfer is processing."
        : "Stripe is processing the transfer to your connected balance.",
      tone: "ready",
    };
  }
  if (payoutStatus === "attention_needed") {
    return {
      label: "Payout needs attention",
      copy: isBuyer
        ? "Eleven Zero PB is checking the seller transfer. Your payment remains recorded."
        : "Eleven Zero PB has been notified and will retry or review this transfer.",
      tone: "attention",
    };
  }
  if (payoutStatus === "release_scheduled" || trackingStatus === "DELIVERED") {
    const releaseDate = formatAdminActivityDate(item.payout_release_at);
    return {
      label: "Delivered · protection period",
      copy: isBuyer
        ? `Report a problem before proceeds are released${releaseDate ? ` on ${releaseDate}` : " after the 24-hour protection period"}.`
        : `Delivery is confirmed. Proceeds release automatically${releaseDate ? ` after ${releaseDate}` : " after the 24-hour buyer protection period"}.`,
      tone: "pending",
    };
  }
  if (
    ["TRANSIT", "OUT_FOR_DELIVERY"].includes(trackingStatus) ||
    item.shipping_status === "in_transit" ||
    item.shipped_at
  ) {
    return {
      label: "Shipped · proceeds held",
      copy: isBuyer
        ? "The package is moving. Seller proceeds stay held until delivery is confirmed."
        : "The package is moving. Proceeds stay held until delivery plus the buyer protection period.",
      tone: "pending",
    };
  }
  if (item.status === "paid") {
    return {
      label: isBuyer ? "Paid · preparing shipment" : "Paid · proceeds held",
      copy: isBuyer
        ? "The seller is preparing your prepaid-label shipment."
        : "Print the prepaid label and ship the paddle. Proceeds remain held until delivery.",
      tone: "pending",
    };
  }
  return {
    label: item.status === "expired" ? "Checkout expired" : "Awaiting payment",
    copy: "No seller proceeds will be released until payment is confirmed.",
    tone: "neutral",
  };
}

function canBuyerReportIssue(item) {
  return (
    item.status === "paid" &&
    item.payment_flow === "separate_charge_transfer" &&
    item.buyer_issue_status !== "open" &&
    !item.stripe_transfer_id &&
    !["released", "releasing"].includes(item.payout_status)
  );
}

function renderPurchaseItem(item) {
  const title = [item.brand, item.model].filter(Boolean).join(" ") || "Paddle order";
  const payoutState = getPayoutState(item, "buyer");
  const shippingLine = [item.shipping_carrier, item.shipping_service].filter(Boolean).join(" · ");
  const actions = [];

  if (item.tracking_url) {
    actions.push(
      `<a href="${escapeAttr(item.tracking_url)}" target="_blank" rel="noopener noreferrer">Track package</a>`
    );
  }
  if (item.listing_id) {
    actions.push(`<a href="./listing.html?id=${escapeAttr(item.listing_id)}">View paddle</a>`);
  }

  const issueContent =
    item.buyer_issue_status === "open"
      ? `
        <div class="order-issue-open" role="status">
          <strong>Report received</strong>
          <span>${escapeAttr(cleanStatus(item.buyer_issue_reason || "Order problem"))}</span>
        </div>
      `
      : canBuyerReportIssue(item)
        ? `
          <details class="order-issue-disclosure">
            <summary>Report a problem</summary>
            <form class="order-issue-form" data-order-issue-form data-order-id="${escapeAttr(item.id)}" data-session-id="${escapeAttr(item.stripe_checkout_session_id)}">
              <label>
                <span>What happened?</span>
                <select name="reason" required>
                  <option value="">Choose one</option>
                  <option value="damaged">Arrived damaged</option>
                  <option value="not_as_described">Not as described</option>
                  <option value="wrong_item">Wrong item</option>
                  <option value="not_received">Not received</option>
                  <option value="other">Something else</option>
                </select>
              </label>
              <label>
                <span>Tell us what happened</span>
                <textarea name="details" rows="3" minlength="10" maxlength="1000" required></textarea>
              </label>
              <button class="button button-secondary" type="submit">Send report</button>
              <p class="order-issue-status" aria-live="polite"></p>
            </form>
          </details>
        `
        : "";

  return `
    <article class="list-item order-history-item">
      <div class="order-history-head">
        <div>
          <strong>${escapeAttr(title)}</strong>
          <span>${escapeAttr(formatCents(item.amount_total_cents))}${item.seller_name ? ` · Sold by ${escapeAttr(item.seller_name)}` : ""}</span>
        </div>
        <span class="list-item-status list-item-status-${escapeAttr(payoutState.tone)}">${escapeAttr(payoutState.label)}</span>
      </div>
      <p class="order-state-copy">${escapeAttr(payoutState.copy)}</p>
      ${shippingLine ? `<span>${escapeAttr(shippingLine)}</span>` : ""}
      ${item.tracking_number ? `<span>Tracking · ${escapeAttr(item.tracking_number)}</span>` : ""}
      ${actions.length ? `<div class="seller-sale-actions">${actions.join("")}</div>` : ""}
      ${issueContent}
    </article>
  `;
}

function renderSaleItem(item) {
  const title = [item.brand, item.model].filter(Boolean).join(" ") || "Paddle order";
  const isLabelReady = Boolean(item.shippo_label_url);
  const isPaid = item.status === "paid";
  const payoutState = getPayoutState(item, "seller");
  const shippingLine = [item.shipping_carrier, item.shipping_service].filter(Boolean).join(" · ");
  const actions = [];
  const salePriceCents = Math.max(
    Number(item.amount_total_cents || 0) - Number(item.shipping_amount_cents || 0),
    0
  );
  const proceedsCents = Number(item.seller_proceeds_cents || 0) ||
    Math.max(salePriceCents - Number(item.platform_fee_cents || 0), 0);

  if (isLabelReady) {
    actions.push(
      `<a href="${ElevenZeroApp.escapeHtml(item.shippo_label_url)}" target="_blank" rel="noopener noreferrer">Print prepaid label</a>`
    );
  }
  if (item.tracking_url) {
    actions.push(
      `<a href="${ElevenZeroApp.escapeHtml(item.tracking_url)}" target="_blank" rel="noopener noreferrer">Track package</a>`
    );
  }
  if (isPaid && ["error", "attention_needed"].includes(item.shipping_status)) {
    actions.push(
      `<button class="seller-sale-retry" type="button" data-retry-shipping="${ElevenZeroApp.escapeHtml(
        item.stripe_checkout_session_id
      )}">Retry prepaid label</button>`
    );
  }
  if (isPaid && item.sale_status === "pending" && item.listing_id) {
    actions.push(
      `<button class="seller-sale-retry" type="button" data-seller-mark-sold="${ElevenZeroApp.escapeHtml(
        item.listing_id
      )}">Mark paddle sold</button>`
    );
  }

  return `
    <article class="list-item order-history-item">
      <div class="order-history-head">
        <div>
          <strong>${ElevenZeroApp.escapeHtml(title)}</strong>
          <span>${ElevenZeroApp.escapeHtml(formatCents(salePriceCents))} sale · ${ElevenZeroApp.escapeHtml(
        formatCents(item.platform_fee_cents)
      )} Eleven Zero fee</span>
        </div>
        <span class="list-item-status list-item-status-${escapeAttr(payoutState.tone)}">
          ${escapeAttr(payoutState.label)}
        </span>
      </div>
      <span><strong>${ElevenZeroApp.escapeHtml(formatCents(proceedsCents))} estimated proceeds</strong></span>
      <p class="order-state-copy">${escapeAttr(payoutState.copy)}</p>
      ${shippingLine ? `<span>${ElevenZeroApp.escapeHtml(shippingLine)}</span>` : ""}
      ${
        item.tracking_number
          ? `<span>Tracking · ${ElevenZeroApp.escapeHtml(item.tracking_number)}</span>`
          : ""
      }
      ${
        item.shipping_error || item.payout_error
          ? `<span class="seller-sale-error">${ElevenZeroApp.escapeHtml(item.shipping_error || item.payout_error)}</span>`
          : ""
      }
      ${actions.length ? `<div class="seller-sale-actions">${actions.join("")}</div>` : ""}
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
      sellerSummary.textContent = `Stripe is ready. Eleven Zero PB keeps a ${profile.platformFeePercent}% marketplace fee, then releases seller proceeds after confirmed delivery and the buyer protection period.`;
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

      sellerSummary.textContent = `Your seller profile has started. ${outstanding} The marketplace fee is ${profile.platformFeePercent}%; proceeds release after confirmed delivery.`;
    }
    if (sellerConnectButton) sellerConnectButton.textContent = "Continue Stripe onboarding";
    return;
  }

  if (sellerPill) sellerPill.textContent = "Not started";
  if (sellerSummary) {
    sellerSummary.textContent = `Start Stripe onboarding before selling. The marketplace fee is ${profile.platformFeePercent}%, and proceeds release after confirmed delivery.`;
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
        const statusTone = item.sale_status === "sold" ? "neutral" : ["pending", "reserved"].includes(item.sale_status) ? "pending" : getListingStatusTone(item.approval_status);
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

            <div class="admin-review-actions admin-sale-actions">
              <button class="button button-dark" type="button" data-admin-sale-status="sold" data-record-id="${escapeAttr(item.id)}">
                Mark sold
              </button>
              <button class="button button-secondary" type="button" data-admin-sale-status="pending" data-record-id="${escapeAttr(item.id)}">
                Mark sale pending
              </button>
              <button class="button button-secondary" type="button" data-admin-sale-status="available" data-record-id="${escapeAttr(item.id)}">
                Make available again
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

function renderAdminProfiles(items) {
  if (!adminProfiles) return;
  if (!items.length) {
    renderAdminEmpty(
      adminProfiles,
      "No member alerts",
      "Pending profile changes and suspended accounts will appear here."
    );
    return;
  }

  adminProfiles.innerHTML = items
    .map((item) => {
      const isPending = item.profileReviewStatus === "pending";
      const isSuspended = item.accountStatus === "suspended";
      const proposedName = item.pendingName || item.name;
      const photoCopy =
        item.pendingImageAction === "replace"
          ? "New profile photo"
          : item.pendingImageAction === "remove"
            ? "Remove current photo"
            : "Keep current photo";
      const badge = isSuspended ? "Suspended" : "Needs review";
      const badgeTone = isSuspended ? "neutral" : "pending";

      return `
        <article class="admin-record admin-profile-review-card">
          <div class="admin-profile-review-head">
            <div class="admin-profile-review-photo">
              ${
                item.pendingImageUrl
                  ? `<img src="${escapeAttr(item.pendingImageUrl)}" alt="Proposed profile photo for ${escapeAttr(proposedName)}" />`
                  : `<span aria-hidden="true">${escapeAttr(profileInitials(proposedName))}</span>`
              }
            </div>
            <div>
              <strong>${escapeAttr(item.name)}</strong>
              <span>${escapeAttr(item.email)}</span>
              <span class="admin-record-badge admin-record-badge-${badgeTone}">${badge}</span>
            </div>
          </div>
          ${
            isPending
              ? `<div class="admin-profile-change-summary">
                  <span>Proposed name</span>
                  <strong>${escapeAttr(proposedName)}</strong>
                  <span>${escapeAttr(photoCopy)}</span>
                </div>`
              : ""
          }
          ${item.accountStatusNote ? `<p class="admin-profile-note">${escapeAttr(item.accountStatusNote)}</p>` : ""}
          <div class="admin-review-actions">
            ${
              isPending
                ? `<button class="button button-dark" type="button" data-admin-profile-action="approve" data-record-id="${escapeAttr(item.id)}">Approve profile</button>
                   <button class="button button-secondary" type="button" data-admin-profile-action="reject" data-record-id="${escapeAttr(item.id)}">Reject changes</button>`
                : ""
            }
            ${
              isSuspended
                ? `<button class="button button-dark" type="button" data-admin-profile-action="restore" data-record-id="${escapeAttr(item.id)}">Restore account</button>`
                : `<button class="button button-secondary admin-delete-button" type="button" data-admin-profile-action="suspend" data-record-id="${escapeAttr(item.id)}">Suspend account</button>`
            }
          </div>
        </article>
      `;
    })
    .join("");
}

function renderAdminCourts(items) {
  if (!adminCourts) return;
  if (!items.length) {
    renderAdminEmpty(adminCourts, "No courts yet", "Saved courts will show up here for quick moderation.");
    return;
  }

  adminCourts.innerHTML = items
    .map((item) => {
      const statusTone = getListingStatusTone(item.approval_status);
      const statusLabel = getListingStatusLabel(item);

      return `
        <details class="admin-record">
          <summary>
            <div>
              <strong>${escapeAttr(item.name)}</strong>
              <span>${escapeAttr(item.location)} · ${escapeAttr(item.accessLabel || item.accessKind)}</span>
              <span class="admin-record-badge admin-record-badge-${escapeAttr(statusTone)}">${escapeAttr(statusLabel)}</span>
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
              <label>Affiliate link <input name="affiliateUrl" value="${escapeAttr(item.affiliateUrl || "")}" /></label>
              <label>Affiliate label <input name="affiliateLabel" value="${escapeAttr(item.affiliateLabel || "")}" /></label>
            </div>

            <label class="admin-field-block">
              Amenities
              <input name="amenities" value="${escapeAttr(item.amenities || "")}" />
            </label>

            <label class="admin-field-block">
              Description
              <textarea name="description" rows="4">${escapeAttr(item.description)}</textarea>
            </label>

            <div class="admin-review-actions">
              <button class="button button-dark" type="button" data-admin-review="approved" data-admin-review-type="court" data-record-id="${escapeAttr(item.record_id)}">
                Approve + publish
              </button>
              <button class="button button-secondary" type="button" data-admin-review="pending" data-admin-review-type="court" data-record-id="${escapeAttr(item.record_id)}">
                Move back to review
              </button>
              <button class="button button-secondary" type="button" data-admin-review="rejected" data-admin-review-type="court" data-record-id="${escapeAttr(item.record_id)}">
                Mark needs changes
              </button>
            </div>

            <div class="admin-actions">
              <button class="button button-dark" type="submit">Save court</button>
              <button class="button button-secondary admin-delete-button" type="button" data-admin-delete="court" data-record-id="${escapeAttr(item.record_id)}">Remove court</button>
            </div>
          </form>
        </details>
      `;
    })
    .join("");
}

function renderAdminTrainers(items) {
  if (!adminTrainers) return;
  if (!items.length) {
    renderAdminEmpty(adminTrainers, "No trainers yet", "Trainer profiles will appear here once they go live.");
    return;
  }

  adminTrainers.innerHTML = items
    .map((item) => {
      const statusTone = getListingStatusTone(item.approval_status);
      const statusLabel = getListingStatusLabel(item);
      return `
        <details class="admin-record">
          <summary>
            <div>
              <strong>${escapeAttr(item.name)}</strong>
              <span>${escapeAttr(item.location)} · ${escapeAttr(item.level)} · ${escapeAttr(item.rate)}</span>
              <span class="admin-record-badge admin-record-badge-${escapeAttr(statusTone)}">${escapeAttr(statusLabel)}</span>
            </div>
            <span class="admin-record-meta">${escapeAttr(item.owner_email || item.email)}</span>
          </summary>

          <form class="admin-editor-form" data-admin-form="trainer" data-record-id="${escapeAttr(item.id)}">
            ${
              item.imageUrl
                ? `<div class="admin-trainer-photo-preview">
                    <img
                      src="${escapeAttr(item.imageUrl)}"
                      alt="Submitted trainer photo for ${escapeAttr(item.name)}"
                      loading="lazy"
                      decoding="async"
                    />
                    <span>Trainer photo submitted with this profile</span>
                  </div>`
                : ""
            }
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

            <div class="admin-review-actions">
              <button class="button button-dark" type="button" data-admin-review="approved" data-admin-review-type="trainer" data-record-id="${escapeAttr(item.id)}">Approve + publish</button>
              <button class="button button-secondary" type="button" data-admin-review="pending" data-admin-review-type="trainer" data-record-id="${escapeAttr(item.id)}">Move back to review</button>
              <button class="button button-secondary" type="button" data-admin-review="rejected" data-admin-review-type="trainer" data-record-id="${escapeAttr(item.id)}">Mark needs changes</button>
            </div>

            <div class="admin-actions">
              <button class="button button-dark" type="submit">Save trainer</button>
              <button class="button button-secondary admin-delete-button" type="button" data-admin-delete="trainer" data-record-id="${escapeAttr(item.id)}">Remove trainer</button>
            </div>
          </form>
        </details>
      `;
    })
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

function formatAdminActivityDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function adminOrderControls(item) {
  const orderId = Number(String(item.id || "").replace(/^purchase-/, ""));
  if (!orderId || item.type !== "purchase") return "";
  const issueIsOpen = item.buyer_issue_status === "open";
  const isSeparateFlow = item.payment_flow === "separate_charge_transfer";
  const isDelivered = String(item.tracking_status || "").toUpperCase() === "DELIVERED";
  const isReleased = Boolean(item.stripe_transfer_id) || item.payout_status === "released";
  const releaseAt = item.payout_release_at
    ? new Date(item.payout_release_at).getTime()
    : Number.NaN;
  const releaseIsDue = Number.isFinite(releaseAt) && releaseAt <= Date.now();
  const controls = [];

  if (issueIsOpen) {
    controls.push(
      `<button type="button" data-admin-issue-action="resume" data-order-id="${escapeAttr(orderId)}">Resolve + resume</button>`,
      `<button type="button" data-admin-issue-action="hold" data-order-id="${escapeAttr(orderId)}">Keep on hold</button>`
    );
  }
  if (
    isSeparateFlow &&
    isDelivered &&
    !issueIsOpen &&
    !isReleased &&
    releaseIsDue
  ) {
    controls.push(
      `<button type="button" data-admin-release-payout="${escapeAttr(orderId)}">${
        item.payout_status === "attention_needed" ? "Retry payout" : "Release proceeds"
      }</button>`
    );
  }
  return controls.join("");
}

function renderAdminCommerceNotifications(items) {
  if (!adminCommerceNotifications) return;
  if (!items.length) {
    renderAdminEmpty(
      adminCommerceNotifications,
      "No buying or selling activity yet",
      "New paddle submissions and completed purchases will appear here automatically."
    );
    return;
  }

  adminCommerceNotifications.innerHTML = items
    .map((item) => {
      const isPurchase = item.type === "purchase";
      const paddleName = [item.brand, item.model].filter(Boolean).join(" ") || "a paddle";
      const personName = isPurchase
        ? item.buyer_name || item.buyer_email || "A buyer"
        : item.seller_name || item.seller_email || "A seller";
      const title = isPurchase ? "Paddle purchased" : "Paddle submitted for sale";
      const detail = isPurchase
        ? `${personName} bought ${paddleName} for ${formatCents(item.amount_total_cents)}.`
        : `${personName} submitted ${paddleName} for review.`;
      const listingId = Number(item.listing_id || 0);
      const confirmationStatus = item.buyer_confirmation_status || "pending";
      const confirmationSent = confirmationStatus === "sent";
      const sellerEmailStatus = item.seller_sale_email_status || "pending";
      const sellerEmailSent = sellerEmailStatus === "sent";
      const sessionId = item.stripe_checkout_session_id || "";
      const payoutState = isPurchase ? getPayoutState(item, "seller") : null;
      const orderControls = adminOrderControls(item);
      const purchaseActions = isPurchase
        ? `
            <div class="admin-notification-actions">
              ${
                confirmationSent
                  ? '<span class="admin-notification-state is-ready">Buyer email sent</span>'
                  : `<button type="button" data-admin-send-confirmation="${escapeAttr(sessionId)}">Send buyer confirmation</button>`
              }
              ${
                sellerEmailSent
                  ? '<span class="admin-notification-state is-ready">Seller email sent</span>'
                  : `<button type="button" data-admin-send-seller-confirmation="${escapeAttr(sessionId)}">Send seller confirmation</button>`
              }
              ${
                ["error", "attention_needed"].includes(item.shipping_status)
                  ? `<button type="button" data-retry-shipping="${escapeAttr(sessionId)}">Retry label</button>`
                  : ""
              }
              ${orderControls}
            </div>
          `
        : "";
      const fulfillmentNote = isPurchase
        ? [
            confirmationSent ? "Buyer confirmation sent" : `Buyer email: ${confirmationStatus.replaceAll("_", " ")}`,
            sellerEmailSent ? "Seller confirmation sent" : `Seller email: ${sellerEmailStatus.replaceAll("_", " ")}`,
            item.shipping_status ? `Label: ${String(item.shipping_status).replaceAll("_", " ")}` : "",
            payoutState ? `Payout: ${payoutState.label}` : "",
          ]
            .filter(Boolean)
            .join(" · ")
        : "";

      return `
        <article class="admin-notification admin-notification-${isPurchase ? "purchase" : "listing"}">
          <span class="admin-notification-icon" aria-hidden="true">${isPurchase ? "✓" : "+"}</span>
          <div>
            <strong>${escapeAttr(title)}</strong>
            <p>${escapeAttr(detail)}</p>
            ${fulfillmentNote ? `<span>${escapeAttr(fulfillmentNote)}</span>` : ""}
            ${
              item.buyer_issue_status === "open"
                ? `<div class="admin-order-issue">
                    <strong>Buyer report · ${escapeAttr(cleanStatus(item.buyer_issue_reason || "Problem"))}</strong>
                    <p>${escapeAttr(item.buyer_issue_details || "No details provided.")}</p>
                  </div>`
                : ""
            }
            ${item.shipping_error ? `<span class="admin-notification-error">${escapeAttr(item.shipping_error)}</span>` : ""}
            ${item.payout_error ? `<span class="admin-notification-error">${escapeAttr(item.payout_error)}</span>` : ""}
            ${item.buyer_confirmation_error ? `<span class="admin-notification-error">${escapeAttr(item.buyer_confirmation_error)}</span>` : ""}
            ${item.seller_sale_email_error ? `<span class="admin-notification-error">${escapeAttr(item.seller_sale_email_error)}</span>` : ""}
            <span>${escapeAttr(formatAdminActivityDate(item.activity_at))}</span>
            ${purchaseActions}
          </div>
          ${
            listingId
              ? `<a href="./listing.html?id=${escapeAttr(listingId)}" aria-label="Open ${escapeAttr(paddleName)} listing">Open</a>`
              : ""
          }
        </article>
      `;
    })
    .join("");
}

function renderAdminSalesChart(period = activeSalesPeriod) {
  if (!adminSalesChart || !adminSalesSummary) return;

  const series = latestSalesAnalytics?.[period] || { buckets: [], summary: {} };
  const buckets = series.buckets || [];
  const summary = series.summary || {};
  const maxBuyers = Math.max(1, ...buckets.map((bucket) => Number(bucket.buyers || 0)));
  const periodCopy = {
    day: "per day for the last 14 days",
    month: "per month for the last 12 months",
    quarter: "per quarter for the last 8 quarters",
    year: "per year for the last 5 years",
  };

  activeSalesPeriod = period;
  document.querySelectorAll("[data-admin-sales-period]").forEach((button) => {
    const isActive = button.dataset.adminSalesPeriod === period;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });

  adminSalesSummary.innerHTML = `
    <div><strong>${escapeAttr(summary.buyers || 0)}</strong><span>Unique buyers</span></div>
    <div><strong>${escapeAttr(summary.orders || 0)}</strong><span>Paid orders</span></div>
    <div><strong>${escapeAttr(formatCents(summary.revenueCents || 0))}</strong><span>Order value</span></div>
  `;

  const columnCount = Math.max(1, buckets.length);
  adminSalesChart.style.gridTemplateColumns = `repeat(${columnCount}, minmax(36px, 1fr))`;
  adminSalesChart.style.minWidth = `${Math.max(420, columnCount * 44)}px`;

  if (!buckets.length) {
    adminSalesChart.innerHTML = '<div class="admin-chart-empty">Sales activity will appear after the first completed purchase.</div>';
  } else {
    adminSalesChart.innerHTML = buckets
      .map((bucket) => {
        const buyers = Number(bucket.buyers || 0);
        const barHeight = buyers ? Math.max(12, Math.round((buyers / maxBuyers) * 100)) : 3;
        const accessibleLabel = `${bucket.label}: ${buyers} unique ${buyers === 1 ? "buyer" : "buyers"}, ${bucket.orders || 0} paid ${Number(bucket.orders || 0) === 1 ? "order" : "orders"}`;
        return `
          <div class="admin-chart-column" title="${escapeAttr(accessibleLabel)}">
            <span class="admin-chart-value">${escapeAttr(buyers)}</span>
            <div class="admin-chart-track">
              <span class="admin-chart-fill" style="height: ${barHeight}%"></span>
            </div>
            <span class="admin-chart-label">${escapeAttr(bucket.label)}</span>
          </div>
        `;
      })
      .join("");
  }

  if (adminChartNote) {
    adminChartNote.textContent = `Each bar shows unique buyers ${periodCopy[period]}.`;
  }
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
        "Review new activity first, then open a content section only when you need it.";
    }

    if (adminStats) {
      adminStats.innerHTML = [
        adminStatCard("Paddles to review", stats.listingPending || 0, "pending"),
        adminStatCard("Live paddles", stats.listingApproved || 0, "ready"),
        adminStatCard("Profiles to review", stats.profilePending || 0, "pending"),
        adminStatCard("Members", stats.users || 0, "neutral"),
        adminStatCard("Courts to review", stats.courtPending || 0, "pending"),
        adminStatCard("Trainers", stats.trainers || 0, "ready"),
        adminStatCard(
          "Community reports",
          (stats.trainerReviews || 0) + (stats.courtReports || 0),
          "neutral"
        ),
      ].join("");
    }

    renderAdminListings(response.listings || []);
    renderAdminProfiles(response.profileReviews || []);
    renderAdminCourts(response.courts || []);
    renderAdminTrainers(response.trainers || []);
    renderAdminReviews(adminTrainerReviews, response.trainerReviews || [], "trainerReview");
    renderAdminReviews(adminCourtReports, response.courtReports || [], "courtReport");
    renderAdminCommerceNotifications(response.commerceNotifications || []);
    latestSalesAnalytics = response.salesAnalytics || {};
    renderAdminSalesChart(activeSalesPeriod);
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

async function reviewAdminRecord(type, recordId, status) {
  const statusLabel =
    status === "approved"
      ? "approve and publish"
      : status === "rejected"
        ? "mark for changes"
        : "move back to review";
  const routeByType = {
    listing: "/api/admin/listings/review",
    court: "/api/admin/courts/review",
    trainer: "/api/admin/trainers/review",
  };
  const labelByType = {
    listing: "listing",
    court: "court",
    trainer: "trainer",
  };

  const route = routeByType[type];
  if (!route) return;

  try {
    setAdminStatus(`Updating ${labelByType[type]} review status…`, "warning");
    await ElevenZeroApp.request(route, {
      method: "POST",
      body: { id: Number(recordId || 0), status },
    });
    await loadAdminDashboard();
    setAdminStatus(`${labelByType[type][0].toUpperCase()}${labelByType[type].slice(1)} updated: ${statusLabel}.`, "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

async function reviewAdminProfile(recordId, action) {
  if (action === "suspend") {
    const confirmed = window.confirm(
      "Suspend this account? The member will be signed out and unable to sign in until you restore it."
    );
    if (!confirmed) return;
  }

  try {
    setAdminStatus("Updating member profile status…", "warning");
    const response = await ElevenZeroApp.request("/api/admin/profiles/review", {
      method: "POST",
      body: { id: Number(recordId || 0), action },
    });
    await loadAdminDashboard();
    setAdminStatus(response.message || "Member profile updated.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

async function updateListingSaleStatus(recordId, status) {
  try {
    setAdminStatus("Updating paddle sale status…", "warning");
    await ElevenZeroApp.request("/api/admin/listings/sale-status", {
      method: "POST",
      body: { id: Number(recordId || 0), status },
    });
    await loadDashboard();
    await loadAdminDashboard();
    setAdminStatus(status === "sold" ? "Listing marked sold." : "Listing sale status updated.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
  }
}

async function sendAdminPurchaseConfirmation(sessionId, button) {
  if (!sessionId || button?.disabled) return;
  if (button) {
    button.disabled = true;
    button.textContent = "Sending…";
  }
  try {
    setAdminStatus("Sending the buyer confirmation…", "warning");
    const response = await ElevenZeroApp.request("/api/admin/orders/send-confirmation", {
      method: "POST",
      body: { sessionId },
    });
    await loadAdminDashboard();
    setAdminStatus(response.message || "Purchase confirmation sent.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = "Send buyer confirmation";
    }
  }
}

async function sendAdminSellerConfirmation(sessionId, button) {
  if (!sessionId || button?.disabled) return;
  if (button) {
    button.disabled = true;
    button.textContent = "Sending…";
  }
  try {
    setAdminStatus("Sending the seller sale confirmation…", "warning");
    const response = await ElevenZeroApp.request(
      "/api/admin/orders/send-seller-confirmation",
      {
        method: "POST",
        body: { sessionId },
      }
    );
    await loadAdminDashboard();
    setAdminStatus(response.message || "Seller confirmation sent.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = "Send seller confirmation";
    }
  }
}

async function reportOrderIssue(form) {
  const submitButton = form.querySelector('button[type="submit"]');
  const statusNode = form.querySelector(".order-issue-status");
  const formData = new FormData(form);
  if (submitButton?.disabled) return;
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Sending…";
  }

  try {
    ElevenZeroApp.setStatus(statusNode, "Sending your report…", "warning");
    const response = await ElevenZeroApp.request("/api/account/orders/report-issue", {
      method: "POST",
      body: {
        orderId: Number(form.dataset.orderId || 0),
        sessionId: form.dataset.sessionId || "",
        reason: formData.get("reason"),
        details: String(formData.get("details") || "").trim(),
      },
    });
    ElevenZeroApp.setStatus(statusNode, response.message || "Your report is open.", "success");
    await loadDashboard();
  } catch (error) {
    ElevenZeroApp.setStatus(statusNode, error.message, "error");
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = "Send report";
    }
  }
}

async function resolveAdminOrderIssue(orderId, action, button) {
  if (!orderId || button?.disabled) return;
  const note = window.prompt(
    action === "hold"
      ? "Why should this payout stay on hold?"
      : "Add a short resolution note:",
    action === "hold" ? "Waiting for more information" : "Issue reviewed and resolved"
  );
  if (note === null) return;
  if (note.trim().length < 5) {
    setAdminStatus("Add at least 5 characters to the resolution note.", "error");
    return;
  }
  if (button) {
    button.disabled = true;
    button.textContent = "Saving…";
  }
  try {
    setAdminStatus("Updating the buyer report and payout hold…", "warning");
    const response = await ElevenZeroApp.request("/api/admin/orders/resolve-issue", {
      method: "POST",
      body: { orderId: Number(orderId), action, note: note.trim() },
    });
    await loadAdminDashboard();
    setAdminStatus(response.message || "Order issue updated.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = action === "hold" ? "Keep on hold" : "Resolve + resume";
    }
  }
}

async function releaseAdminOrderPayout(orderId, button) {
  if (!orderId || button?.disabled) return;
  const confirmed = window.confirm(
    "Release this seller’s proceeds now? Shippo delivery must already be confirmed."
  );
  if (!confirmed) return;
  if (button) {
    button.disabled = true;
    button.textContent = "Releasing…";
  }
  try {
    setAdminStatus("Confirming delivery and releasing seller proceeds…", "warning");
    const response = await ElevenZeroApp.request("/api/admin/orders/release-payout", {
      method: "POST",
      body: { orderId: Number(orderId) },
    });
    await loadAdminDashboard();
    setAdminStatus(response.message || "Seller proceeds released.", "success");
  } catch (error) {
    setAdminStatus(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = "Retry payout";
    }
  }
}

async function retryShippingLabel(sessionId, button) {
  if (!sessionId || button?.disabled) return;
  if (button) {
    button.disabled = true;
    button.textContent = "Retrying…";
  }
  try {
    ElevenZeroApp.setStatus(accountStatus, "Getting a fresh carrier rate and prepaid label…", "warning");
    const response = await ElevenZeroApp.request("/api/orders/shipping/retry", {
      method: "POST",
      body: { sessionId },
    });
    await loadDashboard();
    ElevenZeroApp.setStatus(accountStatus, response.message || "Prepaid label ready.", "success");
  } catch (error) {
    ElevenZeroApp.setStatus(accountStatus, error.message, "error");
    await loadDashboard();
  }
}

async function markSellerListingSold(listingId, button) {
  if (!listingId || button?.disabled) return;
  const confirmed = window.confirm(
    "Mark this paddle sold? It will remain out of the shop."
  );
  if (!confirmed) return;
  if (button) {
    button.disabled = true;
    button.textContent = "Marking…";
  }
  try {
    const response = await ElevenZeroApp.request("/api/account/listings/mark-sold", {
      method: "POST",
      body: { id: Number(listingId) },
    });
    await loadDashboard();
    ElevenZeroApp.setStatus(accountStatus, response.message || "Paddle marked sold.", "success");
  } catch (error) {
    ElevenZeroApp.setStatus(accountStatus, error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = "Mark paddle sold";
    }
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
    const profileButton = event.target.closest("[data-admin-profile-action]");
    if (profileButton) {
      await reviewAdminProfile(
        profileButton.dataset.recordId,
        profileButton.dataset.adminProfileAction
      );
      return;
    }

    const periodButton = event.target.closest("[data-admin-sales-period]");
    if (periodButton) {
      renderAdminSalesChart(periodButton.dataset.adminSalesPeriod || "day");
      return;
    }

    const reviewButton = event.target.closest("[data-admin-review]");
    if (reviewButton) {
      await reviewAdminRecord(
        reviewButton.dataset.adminReviewType || "listing",
        reviewButton.dataset.recordId,
        reviewButton.dataset.adminReview
      );
      return;
    }

    const saleButton = event.target.closest("[data-admin-sale-status]");
    if (saleButton) {
      await updateListingSaleStatus(
        saleButton.dataset.recordId,
        saleButton.dataset.adminSaleStatus
      );
      return;
    }

    const confirmationButton = event.target.closest("[data-admin-send-confirmation]");
    if (confirmationButton) {
      await sendAdminPurchaseConfirmation(
        confirmationButton.dataset.adminSendConfirmation,
        confirmationButton
      );
      return;
    }

    const sellerConfirmationButton = event.target.closest(
      "[data-admin-send-seller-confirmation]"
    );
    if (sellerConfirmationButton) {
      await sendAdminSellerConfirmation(
        sellerConfirmationButton.dataset.adminSendSellerConfirmation,
        sellerConfirmationButton
      );
      return;
    }

    const issueButton = event.target.closest("[data-admin-issue-action]");
    if (issueButton) {
      await resolveAdminOrderIssue(
        issueButton.dataset.orderId,
        issueButton.dataset.adminIssueAction,
        issueButton
      );
      return;
    }

    const payoutButton = event.target.closest("[data-admin-release-payout]");
    if (payoutButton) {
      await releaseAdminOrderPayout(
        payoutButton.dataset.adminReleasePayout,
        payoutButton
      );
      return;
    }

    const shippingRetryButton = event.target.closest("[data-retry-shipping]");
    if (shippingRetryButton) {
      await retryShippingLabel(shippingRetryButton.dataset.retryShipping, shippingRetryButton);
      await loadAdminDashboard();
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
    applyAccountMode(user);
    renderAccountProfile(user);

    if (accountName) {
      accountName.textContent = user.isAdmin ? "Eleven Zero Account Manager" : `Welcome back, ${user.name}.`;
    }
    if (accountCopy) {
      accountCopy.textContent = user.isAdmin
        ? "Review marketplace activity, sales, and website content from your private control center."
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
    renderDashboardList(
      accountPurchases,
      response.recentPurchases || [],
      renderPurchaseItem,
      "No purchases yet",
      "Paddles you buy will appear here with delivery updates."
    );
    renderDashboardList(
      accountSales,
      response.recentSales || [],
      renderSaleItem,
      "No sales yet",
      "Paid orders and prepaid Shippo labels will appear here."
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

  applyAccountMode(ElevenZeroApp.session.user);
  renderAccountProfile(ElevenZeroApp.session.user);

  profileSettingsOpen?.addEventListener("click", openProfileSettings);
  profileForm?.addEventListener("submit", saveProfileSettings);
  profileImageInput?.addEventListener("change", handleProfileImageSelection);
  profileImageRemove?.addEventListener("click", () => {
    profileImageDraft = "";
    if (profileImageInput) profileImageInput.value = "";
    renderProfilePreview("");
    ElevenZeroApp.setStatus(profileStatus, "Photo will be removed when you save.", "warning");
  });
  document.querySelectorAll("[data-profile-settings-close], [data-profile-settings-cancel]").forEach((button) => {
    button.addEventListener("click", closeProfileSettings);
  });
  profileDialog?.addEventListener("click", (event) => {
    if (event.target === profileDialog) closeProfileSettings();
  });
  profileDialog?.addEventListener("close", () => {
    document.body.classList.remove("has-modal-open");
  });
  profileNameInput?.addEventListener("input", () => {
    const imageSource =
      profileImageDraft === undefined
        ? latestAccountUser?.profileImageUrl || ""
        : profileImageDraft;
    renderProfilePreview(imageSource);
  });

  if (verificationBanner && ElevenZeroApp.session.user?.emailVerified === false) {
    verificationBanner.hidden = false;
    verificationBanner.querySelector("[data-resend-verification]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const response = await ElevenZeroApp.request("/api/auth/resend-verification", {
          method: "POST",
          body: {},
        });
        ElevenZeroApp.setStatus(verificationBannerStatus, response.message, "success");
      } catch (error) {
        ElevenZeroApp.setStatus(verificationBannerStatus, error.message, "error");
        button.disabled = false;
      }
    });
  }

  bindAdminPanel();
  accountPurchases?.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-order-issue-form]");
    if (!form) return;
    event.preventDefault();
    await reportOrderIssue(form);
  });
  accountSales?.addEventListener("click", async (event) => {
    const soldButton = event.target.closest("[data-seller-mark-sold]");
    if (soldButton) {
      await markSellerListingSold(soldButton.dataset.sellerMarkSold, soldButton);
      return;
    }
    const retryButton = event.target.closest("[data-retry-shipping]");
    if (!retryButton) return;
    await retryShippingLabel(retryButton.dataset.retryShipping, retryButton);
  });
  await loadDashboard();
  await loadAdminDashboard();
  sellerConnectButton?.addEventListener("click", handleSellerOnboarding);
  sellerRefreshButton?.addEventListener("click", refreshSellerProfile);
});

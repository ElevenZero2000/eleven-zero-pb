// Local-only account regression tests: node --test test_account.cjs
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function createHarness({ url = "http://127.0.0.1:8180/account.html", seller = false } = {}) {
  const button = { disabled: false, textContent: "Log out" };
  const status = { hidden: true, textContent: "" };
  const requests = [];
  const destinations = [];
  let headerUpdates = 0;
  let privateDataClears = 0;
  const node = () => ({ textContent: "", innerHTML: "", disabled: false,
    setAttribute(name) { if (name === "disabled") this.disabled = true; },
    removeAttribute(name) { if (name === "disabled") this.disabled = false; },
  });
  const sellerNodes = Object.fromEntries(["pill", "summary", "progress", "connect-status", "connect-button", "refresh-button"]
    .map(name => [`[data-seller-${name}]`, node()]));
  const adminNotifications = node();
  const historyUpdates = [];
  const app = {
    session: { authenticated: true, user: { id: 44 } },
    renderAuthSlots() { headerUpdates++; },
    clearPrivateSessionData() { privateDataClears++; },
    escapeHtml(value) { return String(value ?? ""); },
    setStatus(node, message, tone) { if (node) { node.textContent = message; node.tone = tone; } },
    request: (path, options) => new Promise((resolve, reject) => {
      requests.push({ path, options, resolve, reject });
    }),
  };
  const context = vm.createContext({
    ElevenZeroApp: app,
    URL,
    document: {
      querySelector: (selector) => ({
        "[data-account-logout]": button,
        "[data-account-logout-status]": status,
        "[data-admin-commerce-notifications]": adminNotifications,
        ...(seller ? sellerNodes : {}),
      })[selector] || null,
      addEventListener() {},
    },
    window: {
      location: { href: url, replace: (url) => destinations.push(url) },
      history: { replaceState: (_state, _title, url) => historyUpdates.push(url) },
    },
  });
  vm.runInContext(readFileSync(join(__dirname, "account.js"), "utf8"), context);
  return {
    logout: context.handleAccountLogout, button, status, app, requests, destinations,
    context, sellerNodes, adminNotifications, historyUpdates,
    get headerUpdates() { return headerUpdates; },
    get privateDataClears() { return privateDataClears; },
  };
}

test("logout waits for the server, prevents duplicate clicks and redirects after success", async () => {
  const h = createHarness();
  const pending = h.logout();
  assert.equal(h.button.disabled, true);
  assert.equal(h.button.textContent, "Logging out…");
  assert.equal(h.requests[0].path, "/api/auth/signout");
  assert.equal(h.requests[0].options.method, "POST");
  await h.logout();
  assert.equal(h.requests.length, 1);
  assert.equal(h.app.session.authenticated, true);
  assert.equal(h.privateDataClears, 0);
  assert.deepEqual(h.destinations, []);
  h.requests[0].resolve({ ok: true });
  await pending;
  assert.equal(h.app.session.authenticated, false);
  assert.equal(h.app.session.user, null);
  assert.equal(h.headerUpdates, 1);
  assert.equal(h.privateDataClears, 1);
  assert.deepEqual(h.destinations, ["./auth.html"]);
});

test("failed logout keeps the session, shows an error and allows a successful retry", async () => {
  const h = createHarness();
  const pending = h.logout();
  h.requests[0].reject(new Error("Connection failed"));
  await pending;
  assert.equal(h.app.session.authenticated, true);
  assert.equal(h.privateDataClears, 0);
  assert.deepEqual(h.destinations, []);
  assert.equal(h.button.disabled, false);
  assert.equal(h.button.textContent, "Log out");
  assert.equal(h.status.hidden, false);
  assert.match(h.status.textContent, /try again/);
  const retry = h.logout();
  assert.equal(h.status.hidden, true);
  assert.equal(h.status.textContent, "");
  h.requests[1].resolve({ ok: true });
  await retry;
  assert.equal(h.app.session.authenticated, false);
  assert.equal(h.privateDataClears, 1);
  assert.deepEqual(h.destinations, ["./auth.html"]);
});

const readyProfile = {
  connectConfigured: true, hasAccount: true, readyForPayouts: true,
  detailsSubmitted: true, chargesEnabled: true, payoutsEnabled: true,
  requirementsDueCount: 0, platformFeePercent: 8.5,
};

test("seller readiness renders one consistent status instead of static not-connected copy", () => {
  const h = createHarness({ seller: true });
  h.sellerNodes["[data-seller-connect-status]"].textContent = "Seller payouts are not connected yet.";
  h.context.renderSellerProfile(readyProfile);
  assert.equal(h.sellerNodes["[data-seller-pill]"].textContent, "Payout ready");
  assert.match(h.sellerNodes["[data-seller-connect-status]"].textContent, /payouts are ready/);
  assert.doesNotMatch(h.sellerNodes["[data-seller-connect-status]"].textContent, /not connected/);
  assert.equal(h.app.session.user.sellerProfile.readyForPayouts, true);

  h.context.renderSellerProfile({ ...readyProfile, readyForPayouts: false, payoutsEnabled: false });
  assert.equal(h.sellerNodes["[data-seller-pill]"].textContent, "In progress");
  assert.match(h.sellerNodes["[data-seller-connect-status]"].textContent, /connected.*not complete/);
});

for (const marker of ["return", "refresh"]) {
  test(`Stripe ${marker} marker triggers provider refresh and preserves other URL state`, async () => {
    const h = createHarness({ seller: true, url: `http://127.0.0.1:8180/account.html?from=sell&stripe_onboarding=${marker}#seller-payouts` });
    const pending = h.context.refreshSellerProfileAfterOnboarding();
    assert.equal(h.requests.length, 1);
    assert.equal(h.requests[0].path, "/api/stripe/connect/status/refresh");
    assert.equal(h.requests[0].options.method, "POST");
    assert.equal(h.historyUpdates.length, 0);
    h.requests[0].resolve({ sellerProfile: readyProfile });
    await pending;
    assert.equal(h.sellerNodes["[data-seller-pill]"].textContent, "Payout ready");
    assert.deepEqual(h.historyUpdates, ["/account.html?from=sell#seller-payouts"]);
  });
}

test("a Stripe return alone never asserts readiness and refresh failures remain retryable", async () => {
  const h = createHarness({ seller: true, url: "http://127.0.0.1:8180/account.html?stripe_onboarding=return#seller-payouts" });
  const incomplete = { ...readyProfile, readyForPayouts: false, detailsSubmitted: false, payoutsEnabled: false };
  h.context.renderSellerProfile(incomplete);
  const pending = h.context.refreshSellerProfileAfterOnboarding();
  assert.equal(h.sellerNodes["[data-seller-pill]"].textContent, "In progress");
  await h.context.refreshSellerProfile();
  assert.equal(h.requests.length, 1, "only one status refresh may be in flight");
  h.requests[0].reject(new Error("Stripe temporarily unavailable"));
  await pending;
  assert.equal(h.sellerNodes["[data-seller-pill]"].textContent, "In progress");
  assert.match(h.sellerNodes["[data-seller-connect-status]"].textContent, /temporarily unavailable/);
  assert.deepEqual(h.historyUpdates, [], "keep marker so reloading retries");
  const retry = h.context.refreshSellerProfileAfterOnboarding();
  h.requests[1].resolve({ sellerProfile: incomplete });
  await retry;
  assert.equal(h.sellerNodes["[data-seller-pill]"].textContent, "In progress");
  assert.match(h.sellerNodes["[data-seller-connect-status]"].textContent, /not complete/);
});

test("ordinary dashboard visits do not make automatic Stripe calls", async () => {
  const h = createHarness();
  await h.context.refreshSellerProfileAfterOnboarding();
  assert.equal(h.requests.length, 0);
});

test("paid admin commerce events do not say awaiting payment", () => {
  const h = createHarness();
  for (const payment of [{ status: "paid", stripe_payment_status: "unpaid" }, { status: "open", stripe_payment_status: "paid" }]) {
    h.context.renderAdminCommerceNotifications([{
      id: "purchase-1", type: "purchase", brand: "JOOLA", model: "Perseus",
      payment_flow: "separate_charge_transfer", payout_status: "held_for_delivery",
      shipping_status: "label_ready", amount_total_cents: 15975, ...payment,
    }]);
    assert.match(h.adminNotifications.innerHTML, /Paid · proceeds held/);
    assert.doesNotMatch(h.adminNotifications.innerHTML, /Awaiting payment/);
  }
  assert.equal(h.context.getPayoutState({ status: "open", stripe_payment_status: "unpaid" }).label, "Awaiting payment");
});

test("in-flight or uncertain label purchases explain their state without unsafe retry actions", () => {
  const h = createHarness();
  for (const shipping_status of ["rate_refreshing", "purchasing", "purchase_unknown"]) {
    const item = { id: "purchase-1", type: "purchase", status: "paid", payment_flow: "separate_charge_transfer",
      payout_status: "held_for_delivery", shipping_status, stripe_checkout_session_id: "cs_test_qa" };
    assert.equal(h.context.getShippingState(item).canRetry, false);
    assert.doesNotMatch(h.context.renderSaleItem(item), /data-retry-shipping/);
    h.context.renderAdminCommerceNotifications([item]);
    assert.doesNotMatch(h.adminNotifications.innerHTML, /data-retry-shipping/);
    if (shipping_status === "purchase_unknown") {
      assert.match(h.context.renderSaleItem(item), /Contact Eleven Zero PB support/);
      assert.match(h.adminNotifications.innerHTML, /Label purchase under review/);
    }
  }
  assert.equal(h.context.getShippingState({ shipping_status: "attention_needed" }).canRetry, true);
});

// Local-only cart regression tests: node --test test_cart.cjs
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(join(__dirname, "cart.js"), "utf8");
const quoteResponse = (amountCents) => ({
  quote: { amountCents, destinationSummary: "Arlington, VA", isEstimate: false },
});
const submitEvent = (fields = {}) => ({
  preventDefault() {},
  currentTarget: {
    line1: "123 Court Ave", city: "Arlington", state: "VA",
    postalCode: "22201", country: "US", ...fields,
  },
});

function createHarness() {
  const makeNode = () => ({
    innerHTML: "", hidden: false, textContent: "",
    classList: { add() {}, toggle() {} },
    querySelector() { return null; },
    querySelectorAll() { return []; },
  });
  const nodes = Object.fromEntries([
    ".cart-page", "[data-cart-status]", "[data-cart-items-panel]", "[data-cart-checkout-panel]",
  ].map((selector) => [selector, makeNode()]));
  const requests = [];
  const storage = new Map();
  const app = {
    session: { authenticated: true, user: { id: 44 } },
    escapeHtml: (value) => String(value ?? "").replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    setStatus: (node, message) => { if (node) node.textContent = message; },
    request: (path, options) => new Promise((resolve, reject) => {
      requests.push({ path, options, resolve, reject });
    }),
  };
  const context = vm.createContext({
    URL, URLSearchParams, Intl, ElevenZeroApp: app,
    FormData: class {
      constructor(form) { this.form = form; }
      get(name) { return this.form[name] ?? ""; }
    },
    document: {
      title: "Your cart", querySelector: (selector) => nodes[selector], addEventListener() {},
    },
    window: {
      location: { href: "http://localhost/cart.html", search: "", pathname: "/cart.html" },
      history: { replaceState() {} },
      localStorage: {
        getItem: (key) => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: (key) => storage.delete(key),
      },
    },
  });
  vm.runInContext(`${source}\nglobalThis.cartTest = {
    cartState, renderCart, handleShippingQuoteSubmit, handleCheckout,
    getCartActionState, getSelectedTotalCents, formatMoneyFromCents,
    invalidateShippingQuote, removeCartItem
  };`, context);
  const cart = context.cartTest;
  const state = cart.cartState;
  state.cartItems = [{ listingId: 1, priceUsd: 160.25 }, { listingId: 2, priceUsd: 90 }];
  state.listings = [
    { id: 1, brand: "Test", model: "Control", price_usd: 160.25, checkout_available: true },
    { id: 2, brand: "Test", model: "Power", price_usd: 90, checkout_available: true },
  ];
  state.selectedListingId = 1;
  return { cart, state, app, nodes, requests };
}

test("cart has a single empty state and an explicit one-paddle selection", () => {
  const { cart, state, nodes } = createHarness();
  cart.renderCart();
  assert.match(nodes["[data-cart-items-panel]"].innerHTML, /Checkout is one paddle at a time/);
  assert.equal((nodes["[data-cart-items-panel]"].innerHTML.match(/aria-pressed="true"/g) || []).length, 1);
  assert.match(nodes["[data-cart-checkout-panel]"].innerHTML, /Order summary/);
  assert.equal(nodes["[data-cart-checkout-panel]"].hidden, false);
  state.cartItems = [];
  cart.renderCart();
  assert.equal(nodes["[data-cart-checkout-panel]"].hidden, true);
  assert.equal(nodes["[data-cart-checkout-panel]"].innerHTML, "");
  assert.equal((nodes["[data-cart-items-panel]"].innerHTML.match(/Shop paddles/g) || []).length, 1);
});

test("summary preserves cents, selected-item pricing, authentication and unavailable states", () => {
  const { cart, state, app } = createHarness();
  state.shipping.quote = quoteResponse(975).quote;
  assert.equal(cart.formatMoneyFromCents(975), "$9.75");
  assert.equal(cart.formatMoneyFromCents(16025), "$160.25");
  assert.equal(cart.getSelectedTotalCents(), 17000);
  assert.equal(cart.getCartActionState(state.listings[0]).action, "checkout");
  app.session.authenticated = false;
  assert.equal(cart.getCartActionState(state.listings[0]).action, "auth");
  assert.equal(cart.getCartActionState({ ...state.listings[0], checkout_available: false }).action, "disabled");
});

test("shipping refresh clears its old quote and cannot open a payment session", async () => {
  const { cart, state, requests } = createHarness();
  state.shipping.quote = quoteResponse(975).quote;
  const pending = cart.handleShippingQuoteSubmit(submitEvent());
  assert.equal(state.shipping.quote, null);
  assert.equal(state.shipping.busy, true);
  await cart.handleCheckout();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].path, "/api/shipping/quote");
  assert.equal(requests[0].options.body.listingId, 1);
  requests[0].resolve(quoteResponse(975));
  await pending;
  assert.equal(state.shipping.quote.amountCents, 975);
  assert.equal(state.shipping.busy, false);
});

test("removed selected paddle cannot receive an in-flight shipping quote", async () => {
  const { cart, state, requests } = createHarness();
  const pending = cart.handleShippingQuoteSubmit(submitEvent());
  cart.removeCartItem(1);
  assert.equal(state.selectedListingId, 2);
  requests[0].resolve(quoteResponse(98765));
  await pending;
  assert.equal(state.shipping.quote, null);
});

test("changed address invalidates an in-flight shipping quote", async () => {
  const { cart, state, requests } = createHarness();
  const pending = cart.handleShippingQuoteSubmit(submitEvent());
  state.shipping.postalCode = "10001";
  cart.invalidateShippingQuote("Address updated. Confirm shipping again before checkout.");
  requests[0].resolve(quoteResponse(88888));
  await pending;
  assert.equal(state.shipping.quote, null);
});

test("obsolete responses cannot replace newer quotes or clear their pending state", async () => {
  const { cart, state, requests } = createHarness();
  const older = cart.handleShippingQuoteSubmit(submitEvent());
  const latest = cart.handleShippingQuoteSubmit(submitEvent({ postalCode: "10001" }));
  requests[0].reject(new Error("Obsolete carrier error"));
  await older;
  assert.equal(state.shipping.busy, true);
  assert.equal(state.shipping.statusTone, "neutral");
  requests[1].resolve(quoteResponse(1234));
  await latest;
  assert.equal(state.shipping.quote.amountCents, 1234);
  assert.equal(state.shipping.busy, false);
});

test("late successful response cannot overwrite a newer completed quote", async () => {
  const { cart, state, requests } = createHarness();
  const older = cart.handleShippingQuoteSubmit(submitEvent());
  const latest = cart.handleShippingQuoteSubmit(submitEvent({ postalCode: "10001" }));
  requests[1].resolve(quoteResponse(1234));
  await latest;
  requests[0].resolve(quoteResponse(98765));
  await older;
  assert.equal(state.shipping.quote.amountCents, 1234);
  assert.equal(state.shipping.busy, false);
});

test("current address errors remain visible and prevent checkout", async () => {
  const { cart, state, requests, nodes } = createHarness();
  const pending = cart.handleShippingQuoteSubmit(submitEvent());
  requests[0].reject(new Error("Enter a valid ZIP code."));
  await pending;
  assert.equal(state.shipping.statusTone, "error");
  assert.match(nodes["[data-cart-checkout-panel]"].innerHTML, /Enter a valid ZIP code/);
  assert.equal(state.shipping.quote, null);
  await cart.handleCheckout();
  assert.equal(requests.length, 1);
});

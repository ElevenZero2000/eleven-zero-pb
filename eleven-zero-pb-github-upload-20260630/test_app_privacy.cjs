// Local-only privacy and confirmed-purchase storage regressions.
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const OWNER = "elevenZeroPbPrivateSessionOwner";
const ADDRESS = "elevenZeroPbShippingAddressDraft";
const PENDING = "elevenZeroPbPendingCheckoutListing";
const CART = "elevenZeroPbCartItems";
const LEGACY = "elevenZeroPbCartDraft";
const signedIn = (id) => ({ authenticated: true, user: { id, name: `Member ${id}` }, csrfToken: "local-token" });

async function harness({ initialStorage = {}, session = signedIn(1), deniedStorage = false } = {}) {
  const data = new Map(Object.entries(initialStorage));
  const listeners = new Map();
  const events = [];
  const button = { disabled: false, textContent: "Sign out", attributes: {}, setAttribute(k, v) { this.attributes[k] = v; } };
  const storage = {
    get length() { return data.size; },
    key(index) { return [...data.keys()][index] ?? null; },
    getItem(key) { return data.get(key) ?? null; },
    setItem(key, value) { data.set(key, String(value)); },
    removeItem(key) { data.delete(key); },
  };
  let reloads = 0;
  const window = {
    location: { origin: "http://localhost", pathname: "/shop.html", search: "", hash: "", href: "/shop.html", reload() { reloads++; } },
    addEventListener(name, fn) { listeners.set(name, fn); },
    dispatchEvent(event) { events.push(event.type); },
  };
  Object.defineProperty(window, "localStorage", { get() { if (deniedStorage) throw new Error("Storage blocked"); return storage; } });
  const node = { setAttribute() {} };
  const context = vm.createContext({
    window, URL, URLSearchParams, Intl, Event: class Event { constructor(type) { this.type = type; } },
    document: {
      body: { dataset: {} }, documentElement: { dataset: {} }, title: "Local test",
      querySelectorAll: () => [], querySelector: () => null,
      head: { querySelector: () => node, appendChild() {} },
    },
    fetch: async (url) => ({ ok: true, json: async () => url === "/api/auth/session" ? session : {} }),
  });
  vm.runInContext(readFileSync(join(__dirname, "app.js"), "utf8"), context);
  const app = vm.runInContext("ElevenZeroApp", context);
  await app.boot;
  return { app, data, storage, button, window, listeners, events, get reloads() { return reloads; } };
}

test("boot discards unowned legacy private drafts while preserving the cart", async () => {
  const h = await harness({ initialStorage: { [ADDRESS]: "old address", [PENDING]: "old checkout", [CART]: "saved items", [LEGACY]: "saved paddle" } });
  assert.equal(h.data.has(ADDRESS), false);
  assert.equal(h.data.has(PENDING), false);
  assert.equal(h.data.get(CART), "saved items");
  assert.equal(h.data.get(LEGACY), "saved paddle");
  assert.equal(h.data.get(OWNER), "user:1");
});

test("same-account reload preserves current address and pending checkout", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1", [ADDRESS]: "current address", [PENDING]: "current checkout" } });
  assert.equal(h.data.get(ADDRESS), "current address");
  assert.equal(h.data.get(PENDING), "current checkout");
  h.app.session = signedIn(1);
  assert.equal(h.data.get(ADDRESS), "current address");
});

test("successful header logout waits for server before clearing private data and preserves cart", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1", [ADDRESS]: "private", [PENDING]: "session", [CART]: "cart", [`${ADDRESS}:user:1`]: "scoped address" } });
  let finish, calls = 0;
  h.app.request = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  const pending = h.app.handleHeaderSignout(h.button);
  assert.equal(h.button.disabled, true);
  assert.equal(h.data.get(ADDRESS), "private");
  assert.equal(h.app.session.authenticated, true);
  await h.app.handleHeaderSignout(h.button);
  assert.equal(calls, 1);
  finish({ ok: true }); await pending;
  assert.equal(h.data.has(ADDRESS), false);
  assert.equal(h.data.has(PENDING), false);
  assert.equal(h.data.has(`${ADDRESS}:user:1`), false);
  assert.equal(h.data.get(CART), "cart");
  assert.equal(h.data.get(OWNER), "anonymous");
  assert.equal(h.app.session.authenticated, false);
  assert.equal(h.window.location.href, "./auth.html");
});

test("failed header logout leaves private data and session intact and allows retry", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1", [ADDRESS]: "private", [PENDING]: "session" } });
  h.app.request = async () => { throw new Error("Network failure"); };
  await h.app.handleHeaderSignout(h.button);
  assert.equal(h.data.get(ADDRESS), "private");
  assert.equal(h.data.get(PENDING), "session");
  assert.equal(h.app.session.authenticated, true);
  assert.equal(h.button.disabled, false);
  assert.match(h.button.textContent, /Retry/);
  assert.equal(h.window.location.href, "/shop.html");
  h.app.request = async () => ({ ok: true });
  await h.app.handleHeaderSignout(h.button);
  assert.equal(h.data.has(ADDRESS), false);
});

test("account changes clear sensitive drafts on direct switch and guest login", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1", [ADDRESS]: "buyer address", [PENDING]: "buyer checkout", [CART]: "cart" } });
  h.app.session = signedIn(2);
  assert.equal(h.data.has(ADDRESS), false);
  assert.equal(h.data.has(PENDING), false);
  assert.equal(h.data.get(CART), "cart");
  assert.equal(h.data.get(OWNER), "user:2");
  h.app.session = { authenticated: false, user: null };
  h.data.set(ADDRESS, "anonymous draft");
  h.app.session = signedIn(1);
  assert.equal(h.data.has(ADDRESS), false);
});

test("other-tab logout or account switch reloads stale UI without deleting new owner's draft", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1" } });
  const onStorage = h.listeners.get("storage");
  onStorage({ key: CART, storageArea: h.storage });
  onStorage({ key: OWNER, storageArea: h.storage });
  assert.equal(h.reloads, 0);
  h.data.set(OWNER, "user:2"); h.data.set(ADDRESS, "new owner's draft");
  onStorage({ key: OWNER, storageArea: h.storage });
  assert.equal(h.reloads, 1);
  assert.equal(h.data.get(ADDRESS), "new owner's draft");
  h.data.set(OWNER, "anonymous");
  onStorage({ key: OWNER, storageArea: h.storage });
  assert.equal(h.reloads, 2);
});

test("restricted browser storage never blocks successful logout", async () => {
  const h = await harness({ deniedStorage: true });
  h.app.request = async () => ({ ok: true });
  await h.app.handleHeaderSignout(h.button);
  assert.equal(h.app.session.authenticated, false);
  assert.equal(h.window.location.href, "./auth.html");
});

test("back-forward cached pages reload when the browser account changed", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1" } });
  const onPageshow = h.listeners.get("pageshow");
  onPageshow({persisted:true});
  assert.equal(h.reloads,0);
  h.data.set(OWNER,"user:2");
  onPageshow({persisted:false});
  assert.equal(h.reloads,0);
  onPageshow({persisted:true});
  assert.equal(h.reloads,1);
});

test("paid authoritative listing removes only matching cart, legacy and pending entries", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1", [CART]: JSON.stringify([{listingId:7}, {listingId:8}]), [LEGACY]: JSON.stringify({listingId:7}), [PENDING]: JSON.stringify({listingId:7}) } });
  assert.equal(h.app.removePurchasedCartItem({status:"paid", listingId:7}), true);
  assert.deepEqual(JSON.parse(h.data.get(CART)), [{listingId:8}]);
  assert.equal(h.data.has(LEGACY), false);
  assert.equal(h.data.has(PENDING), false);
  assert.deepEqual(h.events, ["elevenzero:cart-updated"]);
  assert.equal(h.app.removePurchasedCartItem({status:"paid", listingId:7}), false);
});

test("unpaid, missing and invalid authoritative listing IDs never clear cart data", async () => {
  const initial = { [OWNER]: "user:1", [CART]: '[{"listingId":7}]', [LEGACY]: '{"listingId":7}', [PENDING]: '{"listingId":7}' };
  const h = await harness({ initialStorage: initial });
  for (const order of [{status:"pending",listingId:7},{status:"paid"},{status:"paid",listingId:-1},{status:"paid",listingId:1.5},{status:"paid",listingId:"x"}]) {
    assert.equal(h.app.removePurchasedCartItem(order), false);
  }
  assert.deepEqual(Object.fromEntries(h.data), initial);
  assert.deepEqual(h.events, []);
});

test("unrelated legacy and pending checkout survive another listing purchase", async () => {
  const h = await harness({ initialStorage: { [OWNER]: "user:1", [CART]: '[{"listingId":7},{"listingId":8}]', [LEGACY]: '{"listingId":8}', [PENDING]: '{"listingId":8}' } });
  assert.equal(h.app.removePurchasedCartItem({status:"paid",listingId:"7"}), true);
  assert.equal(h.data.get(LEGACY), '{"listingId":8}');
  assert.equal(h.data.get(PENDING), '{"listingId":8}');
});

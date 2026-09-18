// Local-only account regression tests: node --test test_account.cjs
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function createHarness() {
  const button = { disabled: false, textContent: "Log out" };
  const status = { hidden: true, textContent: "" };
  const requests = [];
  const destinations = [];
  let headerUpdates = 0;
  const app = {
    session: { authenticated: true, user: { id: 44 } },
    renderAuthSlots() { headerUpdates++; },
    request: (path, options) => new Promise((resolve, reject) => {
      requests.push({ path, options, resolve, reject });
    }),
  };
  const context = vm.createContext({
    ElevenZeroApp: app,
    document: {
      querySelector: (selector) => ({
        "[data-account-logout]": button,
        "[data-account-logout-status]": status,
      })[selector] || null,
      addEventListener() {},
    },
    window: { location: { replace: (url) => destinations.push(url) } },
  });
  vm.runInContext(readFileSync(join(__dirname, "account.js"), "utf8"), context);
  return {
    logout: context.handleAccountLogout, button, status, app, requests, destinations,
    get headerUpdates() { return headerUpdates; },
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
  assert.deepEqual(h.destinations, []);
  h.requests[0].resolve({ ok: true });
  await pending;
  assert.equal(h.app.session.authenticated, false);
  assert.equal(h.app.session.user, null);
  assert.equal(h.headerUpdates, 1);
  assert.deepEqual(h.destinations, ["./auth.html"]);
});

test("failed logout keeps the session, shows an error and allows a successful retry", async () => {
  const h = createHarness();
  const pending = h.logout();
  h.requests[0].reject(new Error("Connection failed"));
  await pending;
  assert.equal(h.app.session.authenticated, true);
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
  assert.deepEqual(h.destinations, ["./auth.html"]);
});

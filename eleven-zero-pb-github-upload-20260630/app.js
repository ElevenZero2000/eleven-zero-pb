const ElevenZeroApp = {
  _session: null,
  get session() {
    return this._session;
  },
  set session(value) {
    this._session = value;
    this.syncPrivateSessionData(value);
  },
  privateSessionOwnerKey: "elevenZeroPbPrivateSessionOwner",
  privateSessionDataKeys: [
    "elevenZeroPbShippingAddressDraft",
    "elevenZeroPbPendingCheckoutListing",
  ],
  config: {
    environment: "development",
    siteUrl: "",
    supportEmail: "",
    gaMeasurementId: "",
    googleMapsEnabled: false,
    googleMapsApiKey: "",
    googleMapsMapId: "",
    googlePlacesSearchEnabled: false,
  },
  analyticsLoaded: false,

  clearPrivateSessionData() {
    // Keep the non-sensitive cart, but never carry an address or provider
    // checkout link into another account on a shared browser.
    try {
      const storage = window.localStorage;
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
      keys.forEach((key) => {
        if (this.privateSessionDataKeys.some((base) => key === base || key?.startsWith(`${base}:`))) {
          storage.removeItem(key);
        }
      });
    } catch {
      // Restricted storage must not prevent signing in or signing out.
    }
  },

  removePurchasedCartItem(order) {
    const listingId = Number(order?.listingId);
    if (order?.status !== "paid" || !Number.isSafeInteger(listingId) || listingId < 1) return false;
    let changed = false;
    try {
      const storage = window.localStorage;
      const read = (key) => {
        try { return JSON.parse(storage.getItem(key) || "null"); } catch { return null; }
      };
      const matchesOrder = (item) => Number(item?.listingId || item?.id) === listingId;
      const items = read("elevenZeroPbCartItems");
      if (Array.isArray(items)) {
        const remaining = items.filter((item) => !matchesOrder(item));
        if (remaining.length !== items.length) {
          storage.setItem("elevenZeroPbCartItems", JSON.stringify(remaining));
          changed = true;
        }
      }
      ["elevenZeroPbCartDraft", "elevenZeroPbPendingCheckoutListing"].forEach((key) => {
        if (matchesOrder(read(key))) {
          storage.removeItem(key);
          changed = true;
        }
      });
    } catch {
      // A paid order stays confirmed even when browser storage is unavailable.
    }
    if (changed) window.dispatchEvent?.(new Event("elevenzero:cart-updated"));
    return changed;
  },

  getPrivateSessionOwner(session = this.session) {
    return session?.authenticated && session.user?.id != null
      ? `user:${session.user.id}`
      : "anonymous";
  },

  syncPrivateSessionData(session) {
    const owner = this.getPrivateSessionOwner(session);
    try {
      const previousOwner = window.localStorage.getItem(this.privateSessionOwnerKey);
      // An unmarked legacy draft has no safe owner, including on first boot.
      if (previousOwner !== owner) this.clearPrivateSessionData();
      window.localStorage.setItem(this.privateSessionOwnerKey, owner);
    } catch {
      if (this._privateSessionOwner !== owner) this.clearPrivateSessionData();
    }
    this._privateSessionOwner = owner;
  },

  initSessionPrivacySync() {
    const reloadIfOwnerChanged = () => {
      try {
        const owner = window.localStorage.getItem(this.privateSessionOwnerKey);
        if (owner === this.getPrivateSessionOwner()) return;
        // Another tab changed the cookie's account. Its transition has already
        // removed the drafts; reload this tab instead of keeping old form data
        // and account controls visible or overwriting the new account's data.
        window.location.reload();
      } catch {
        // Storage access can be unavailable in privacy-restricted browsers.
      }
    };
    window.addEventListener("storage", (event) => {
      if (event.key !== this.privateSessionOwnerKey && event.key !== null) return;
      try {
        if (event.storageArea && event.storageArea !== window.localStorage) return;
      } catch { return; }
      reloadIfOwnerChanged();
    });
    window.addEventListener("pageshow", (event) => {
      // Back/forward cache can restore the old account's populated form in the
      // same tab without a storage event or rerunning the initial boot request.
      if (event.persisted) reloadIfOwnerChanged();
    });
  },

  async handleHeaderSignout(button) {
    if (!button || button.disabled) return;
    button.disabled = true;
    button.textContent = "Signing out…";
    try {
      await this.request("/api/auth/signout", { method: "POST" });
      this.clearPrivateSessionData();
      this.session = { authenticated: false, user: null };
      window.location.href = "./auth.html";
    } catch {
      button.disabled = false;
      button.textContent = "Retry sign out";
      button.setAttribute("aria-label", "Sign out failed. Try again.");
    }
  },

  escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  },

  formatMoney(amount) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(Number(amount || 0));
  },

  setStatus(node, message, tone = "neutral") {
    if (!node) return;

    node.textContent = message;
    node.classList.remove("is-success", "is-warning", "is-error");

    if (tone === "success") node.classList.add("is-success");
    if (tone === "warning") node.classList.add("is-warning");
    if (tone === "error") node.classList.add("is-error");
  },

  async request(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const csrfToken = this.session?.csrfToken || "";
    const fetchOptions = {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(method !== "GET" && csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        ...(options.headers || {}),
      },
      ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    };

    const response = await fetch(path, fetchOptions);
    let payload = {};

    try {
      payload = await response.json();
    } catch {
      payload = {};
    }

    if (!response.ok) {
      throw new Error(payload.error || "Something went wrong.");
    }

    return payload;
  },

  normalizePostAuthDestination(next) {
    const destination = String(next || "").trim();

    if (!destination) return "./account.html";

    let parsedDestination;
    try {
      parsedDestination = new URL(destination, window.location.origin);
    } catch {
      return "./account.html";
    }

    if (
      parsedDestination.origin !== window.location.origin ||
      !["http:", "https:"].includes(parsedDestination.protocol)
    ) {
      return "./account.html";
    }

    const safeDestination = `${parsedDestination.pathname}${parsedDestination.search}${parsedDestination.hash}`;

    if (
      parsedDestination.pathname === "/auth.html" ||
      parsedDestination.pathname.endsWith("/auth.html")
    ) {
      return "./account.html";
    }

    return safeDestination || "./account.html";
  },

  redirectToAuth(next = `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    const encoded = encodeURIComponent(this.normalizePostAuthDestination(next));
    window.location.href = `./auth.html?next=${encoded}`;
  },

  getPostAuthDestination() {
    const params = new URLSearchParams(window.location.search);
    return this.normalizePostAuthDestination(params.get("next") || "./account.html");
  },

  requireAuth(statusNode, message = "Please sign in first to use this feature.") {
    if (this.session?.authenticated) return true;

    this.setStatus(statusNode, message, "warning");
    window.setTimeout(() => this.redirectToAuth(), 700);
    return false;
  },

  renderAuthSlots() {
    const slots = Array.from(document.querySelectorAll("[data-auth-slot]"));
    const user = this.session?.user;

    slots.forEach((slot) => {
      if (!slot) return;

      if (user) {
        slot.innerHTML = `
          <div class="auth-slot-group">
            <a class="auth-user-pill" href="./account.html">
              ${this.escapeHtml(user.name)}
            </a>
            <button class="auth-signout" type="button" data-signout-button>
              Sign out
            </button>
          </div>
        `;
      } else {
        slot.innerHTML = `
          <div class="auth-slot-group">
            <a class="auth-link" href="./auth.html">Sign in</a>
            <a class="nav-cta" href="./auth.html">Create account</a>
          </div>
        `;
      }
    });

    document.querySelectorAll("[data-signout-button]").forEach((button) => {
      button.addEventListener("click", () => this.handleHeaderSignout(button));
    });
  },

  setActiveNav() {
    const current = document.body.dataset.nav;
    if (!current) return;

    const links = Array.from(document.querySelectorAll(".site-nav a"));
    links.forEach((link) => {
      const label = (link.textContent || "").trim().toLowerCase();
      const isActive =
        (current === "home" && label === "home") ||
        (current === "shop" && label === "shop") ||
        (current === "courts" && label === "courts") ||
        (current === "trainers" && label === "trainers") ||
        (current === "account" && label === "account") ||
        (current === "sell" && label === "sell");

      link.classList.toggle("is-current", isActive);
    });
  },

  initReveals() {
    const revealItems = Array.from(document.querySelectorAll(".reveal"));
    if (!revealItems.length) return;

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.16 }
      );

      revealItems.forEach((item) => observer.observe(item));
    } else {
      revealItems.forEach((item) => item.classList.add("is-visible"));
    }
  },

  applySiteConfig() {
    document.documentElement.dataset.appEnv = this.config.environment || "development";

    const supportEmail = this.config.supportEmail || "";
    if (supportEmail) {
      document.querySelectorAll("[data-support-email]").forEach((node) => {
        node.textContent = supportEmail;
      });

      document.querySelectorAll("[data-support-email-link]").forEach((node) => {
        node.setAttribute("href", `mailto:${supportEmail}`);
      });
    }

    const siteUrl = this.config.siteUrl || "";
    if (siteUrl) {
      const currentPath = window.location.pathname || "/index.html";
      const canonicalHref = `${siteUrl.replace(/\/$/, "")}${currentPath}`;
      let canonicalLink = document.querySelector('link[rel="canonical"]');

      if (!canonicalLink) {
        canonicalLink = document.createElement("link");
        canonicalLink.setAttribute("rel", "canonical");
        document.head.appendChild(canonicalLink);
      }

      canonicalLink.setAttribute("href", canonicalHref);
    }

    const ensureMeta = (selector, attributes) => {
      let node = document.head.querySelector(selector);
      if (!node) {
        node = document.createElement("meta");
        document.head.appendChild(node);
      }
      Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
    };

    if (!document.head.querySelector('link[rel="icon"]')) {
      const icon = document.createElement("link");
      icon.rel = "icon";
      icon.type = "image/png";
      icon.href = "./assets/brand-shape.png";
      document.head.appendChild(icon);
    }

    const description =
      document.querySelector('meta[name="description"]')?.content ||
      "Buy and sell pickleball paddles through reviewed listings on Eleven Zero PB.";
    ensureMeta('meta[property="og:title"]', { property: "og:title", content: document.title });
    ensureMeta('meta[property="og:description"]', { property: "og:description", content: description });
    ensureMeta('meta[property="og:type"]', { property: "og:type", content: "website" });
    ensureMeta('meta[name="twitter:card"]', { name: "twitter:card", content: "summary_large_image" });
    ensureMeta('meta[name="twitter:title"]', { name: "twitter:title", content: document.title });
    ensureMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description });
  },

  initAnalytics() {
    const measurementId = this.config.gaMeasurementId || "";
    if (!measurementId || this.analyticsLoaded) return;

    window.dataLayer = window.dataLayer || [];
    window.gtag =
      window.gtag ||
      function gtag() {
        window.dataLayer.push(arguments);
      };

    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      anonymize_ip: true,
      page_path: window.location.pathname,
    });

    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(
      measurementId
    )}`;
    document.head.appendChild(script);
    this.analyticsLoaded = true;
  },
};

ElevenZeroApp.boot = (async () => {
  try {
    const [sessionResult, configResult] = await Promise.allSettled([
      ElevenZeroApp.request("/api/auth/session"),
      ElevenZeroApp.request("/api/site-config"),
    ]);

    ElevenZeroApp.session =
      sessionResult.status === "fulfilled"
        ? sessionResult.value
        : { authenticated: false, user: null };

    if (configResult.status === "fulfilled") {
      ElevenZeroApp.config = { ...ElevenZeroApp.config, ...(configResult.value || {}) };
    }
  } catch {
    ElevenZeroApp.session = { authenticated: false, user: null };
  }

  ElevenZeroApp.applySiteConfig();
  ElevenZeroApp.initSessionPrivacySync();
  ElevenZeroApp.initAnalytics();
  ElevenZeroApp.renderAuthSlots();
  ElevenZeroApp.setActiveNav();
  ElevenZeroApp.initReveals();
  return ElevenZeroApp.session;
})();

window.ElevenZeroApp = ElevenZeroApp;

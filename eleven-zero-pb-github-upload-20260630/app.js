const ElevenZeroApp = {
  session: null,
  config: {
    environment: "development",
    siteUrl: "",
    supportEmail: "",
    gaMeasurementId: "",
    googleMapsEnabled: false,
    googleMapsApiKey: "",
    googleMapsMapId: "",
  },
  analyticsLoaded: false,

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
    const fetchOptions = {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
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

  redirectToAuth(next = `${window.location.pathname}${window.location.hash}`) {
    const encoded = encodeURIComponent(next || "./account.html");
    window.location.href = `./auth.html?next=${encoded}`;
  },

  getPostAuthDestination() {
    const params = new URLSearchParams(window.location.search);
    return params.get("next") || "./account.html";
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
      button.addEventListener("click", async () => {
        await this.request("/api/auth/signout", { method: "POST" });
        window.location.href = "./auth.html";
      });
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
  ElevenZeroApp.initAnalytics();
  ElevenZeroApp.renderAuthSlots();
  ElevenZeroApp.setActiveNav();
  ElevenZeroApp.initReveals();
  return ElevenZeroApp.session;
})();

window.ElevenZeroApp = ElevenZeroApp;

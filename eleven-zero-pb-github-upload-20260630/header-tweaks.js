(function initHeaderTweaks() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const enterThreshold = 68;
  const exitThreshold = 24;
  let ticking = false;
  let isCondensed = false;

  const updateHeaderState = (force = false) => {
    const scrollY = window.scrollY || window.pageYOffset || 0;
    const nextState = isCondensed ? scrollY > exitThreshold : scrollY > enterThreshold;

    if (force || nextState !== isCondensed) {
      isCondensed = nextState;
      header.classList.toggle("is-condensed", isCondensed);
    }

    ticking = false;
  };

  updateHeaderState(true);

  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateHeaderState);
    },
    { passive: true }
  );

  window.addEventListener("resize", () => updateHeaderState(true), { passive: true });

  if (document.body?.dataset.nav !== "shop") return;

  const injectShopMobileStyles = () => {
    if (document.getElementById("shop-mobile-header-styles")) return;

    const style = document.createElement("style");
    style.id = "shop-mobile-header-styles";
    style.textContent = `
      .shop-mobile-menu-toggle,
      .shop-mobile-cart-link,
      .shop-mobile-search-toggle,
      .shop-mobile-menu {
        display: none;
      }

      @media (max-width: 720px) {
        body[data-nav="shop"] .site-header::before,
        body[data-nav="shop"] .site-header::after {
          content: none;
        }

        .shop-mobile-menu-toggle,
        .shop-mobile-cart-link,
        .shop-mobile-search-toggle {
          z-index: 3;
          display: inline-grid;
          place-items: center;
          width: 44px;
          height: 44px;
          border: 0;
          border-radius: 999px;
          background: rgba(3, 45, 23, 0.06);
          color: var(--forest);
          font: inherit;
          font-size: 1.65rem;
          font-weight: 900;
          line-height: 1;
          cursor: pointer;
          -webkit-tap-highlight-color: transparent;
        }

        .shop-mobile-menu-toggle {
          position: absolute;
          top: 50%;
          left: 12px;
          transform: translateY(-50%);
        }

        .shop-mobile-cart-link {
          flex: 0 0 auto;
          width: 40px;
          height: 40px;
          margin-left: 4px;
          font-size: 1.3rem;
          text-decoration: none;
        }

        .shop-mobile-search-toggle {
          position: absolute;
          top: 50%;
          right: 12px;
          font-size: 1.9rem;
          transform: translateY(-50%);
        }

        .shop-mobile-menu-toggle:focus-visible,
        .shop-mobile-cart-link:focus-visible,
        .shop-mobile-search-toggle:focus-visible {
          outline: 3px solid rgba(0, 230, 92, 0.35);
          outline-offset: 2px;
        }

        .shop-mobile-menu {
          position: sticky;
          top: 72px;
          z-index: 19;
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
          padding: 12px 16px 16px;
          border-bottom: 1px solid rgba(3, 45, 23, 0.08);
          background: rgba(255, 255, 255, 0.98);
          box-shadow: 0 16px 28px rgba(3, 26, 14, 0.08);
        }

        .shop-mobile-menu[hidden] {
          display: none;
        }

        .shop-mobile-menu a {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 44px;
          padding: 0 14px;
          border: 1px solid rgba(3, 45, 23, 0.1);
          border-radius: 999px;
          background: #fff;
          color: var(--forest);
          font-size: 0.86rem;
          font-weight: 900;
          text-decoration: none;
        }

        .shop-mobile-menu a[aria-current="page"],
        .shop-mobile-menu a:last-child {
          background: var(--forest);
          color: #fff;
        }

        body[data-nav="shop"] .brand-mark {
          min-height: 48px;
          padding: 0 6px;
        }

        body[data-nav="shop"] .brand-logo-header {
          width: min(48vw, 190px);
        }
      }
    `;
    document.head.appendChild(style);
  };

  const buildShopMobileControls = () => {
    injectShopMobileStyles();

    const brand = header.querySelector(".brand-mark");
    const authSlot = header.querySelector(".nav-auth-slot");

    let menu = document.querySelector("[data-shop-mobile-menu]");
    let menuButton = header.querySelector("[data-shop-mobile-menu-toggle]");
    let cartLink = header.querySelector("[data-shop-mobile-cart-link]");
    let searchButton = header.querySelector("[data-shop-mobile-search-toggle]");

    if (!menuButton) {
      menuButton = document.createElement("button");
      menuButton.className = "shop-mobile-menu-toggle";
      menuButton.type = "button";
      menuButton.setAttribute("aria-label", "Open shop menu");
      menuButton.setAttribute("aria-controls", "shop-mobile-menu");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.dataset.shopMobileMenuToggle = "";
      menuButton.textContent = "☰";
      header.insertBefore(menuButton, brand || header.firstChild);
    }

    if (!cartLink) {
      cartLink = document.createElement("a");
      cartLink.className = "shop-mobile-cart-link";
      cartLink.href = "./cart.html";
      cartLink.setAttribute("aria-label", "Open cart");
      cartLink.dataset.shopMobileCartLink = "";
      cartLink.textContent = "🛒";
      if (brand) {
        brand.insertAdjacentElement("afterend", cartLink);
      } else {
        header.appendChild(cartLink);
      }
    }

    if (!searchButton) {
      searchButton = document.createElement("button");
      searchButton.className = "shop-mobile-search-toggle";
      searchButton.type = "button";
      searchButton.setAttribute("aria-label", "Search paddles");
      searchButton.dataset.shopMobileSearchToggle = "";
      searchButton.textContent = "⌕";
      header.insertBefore(searchButton, authSlot ? authSlot.nextSibling : null);
    }

    if (!menu) {
      menu = document.createElement("nav");
      menu.className = "shop-mobile-menu";
      menu.id = "shop-mobile-menu";
      menu.setAttribute("aria-label", "Mobile shop menu");
      menu.dataset.shopMobileMenu = "";
      menu.hidden = true;
      menu.innerHTML = `
        <a href="./index.html">Home</a>
        <a href="./shop.html" aria-current="page">Shop</a>
        <a href="./courts.html">Courts</a>
        <a href="./trainers.html">Trainers</a>
        <a href="./account.html">Account</a>
        <a href="./sell.html">Sell</a>
      `;
      header.insertAdjacentElement("afterend", menu);
    }

    const searchInput = document.querySelector(
      '[data-listing-search-form] input[name="query"]'
    );

    const setMenuOpen = (isOpen) => {
      menu.hidden = !isOpen;
      menuButton.setAttribute("aria-expanded", String(isOpen));
      menuButton.setAttribute("aria-label", isOpen ? "Close shop menu" : "Open shop menu");
      menuButton.textContent = isOpen ? "×" : "☰";
    };

    menuButton.addEventListener("click", () => {
      setMenuOpen(menu.hidden);
    });

    menu.addEventListener("click", (event) => {
      if (event.target.closest("a")) setMenuOpen(false);
    });

    searchButton.addEventListener("click", () => {
      searchInput?.scrollIntoView({ behavior: "smooth", block: "center" });
      window.setTimeout(() => searchInput?.focus({ preventScroll: true }), 220);
    });

    window.addEventListener(
      "resize",
      () => {
        if (window.innerWidth > 720) setMenuOpen(false);
      },
      { passive: true }
    );
  };

  buildShopMobileControls();
})();

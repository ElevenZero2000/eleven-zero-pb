(function initHeaderTweaks() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const CART_ITEMS_STORAGE_KEY = "elevenZeroPbCartItems";
  let ticking = false;
  let isCondensed = false;

  const updateHeaderState = (force = false) => {
    const scrollY = window.scrollY || window.pageYOffset || 0;
    const nextState = isCondensed ? scrollY > 22 : scrollY > 58;
    if (force || nextState !== isCondensed) {
      isCondensed = nextState;
      header.classList.toggle("is-condensed", isCondensed);
    }
    ticking = false;
  };

  const cartIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M3 4h2l1.5 10.2a2 2 0 0 0 2 1.8h7.8a2 2 0 0 0 1.9-1.4L21 7H6" />
      <circle cx="9" cy="20" r="1.25" />
      <circle cx="17" cy="20" r="1.25" />
    </svg>
  `;

  const readCartCount = () => {
    try {
      const value = JSON.parse(window.localStorage.getItem(CART_ITEMS_STORAGE_KEY) || "[]");
      return Array.isArray(value) ? value.length : 0;
    } catch {
      return 0;
    }
  };

  const cartLink = document.createElement("a");
  cartLink.className = "global-cart-link";
  cartLink.href = "./cart.html";
  cartLink.setAttribute("aria-label", "Open cart");
  cartLink.innerHTML = `${cartIcon}<span class="global-cart-badge" data-global-cart-count></span>`;
  const authSlot = header.querySelector(".nav-auth-slot");
  header.insertBefore(cartLink, authSlot || null);

  const updateCartCount = () => {
    const count = readCartCount();
    const badge = cartLink.querySelector("[data-global-cart-count]");
    if (!badge) return;
    badge.textContent = count > 9 ? "9+" : String(count);
    badge.hidden = count === 0;
    cartLink.setAttribute(
      "aria-label",
      count ? `Open cart with ${count} ${count === 1 ? "paddle" : "paddles"}` : "Open empty cart"
    );
  };
  updateCartCount();

  const menuButton = document.createElement("button");
  menuButton.className = "global-mobile-menu-toggle";
  menuButton.type = "button";
  menuButton.setAttribute("aria-label", "Open menu");
  menuButton.setAttribute("aria-expanded", "false");
  menuButton.setAttribute("aria-controls", "global-mobile-menu");
  menuButton.innerHTML = '<span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span>';
  header.insertBefore(menuButton, header.firstChild);

  const activeNav = document.body?.dataset.nav || "";
  const mobileMenu = document.createElement("nav");
  mobileMenu.className = "global-mobile-menu";
  mobileMenu.id = "global-mobile-menu";
  mobileMenu.setAttribute("aria-label", "Mobile navigation");
  mobileMenu.hidden = true;
  const menuItems = [
    ["home", "Home", "./index.html"],
    ["shop", "Shop", "./shop.html"],
    ["sell", "Sell", "./sell.html"],
    ["courts", "Courts", "./courts.html"],
    ["trainers", "Trainers", "./trainers.html"],
    ["account", "Account", "./account.html"],
  ];
  mobileMenu.innerHTML = menuItems
    .map(
      ([key, label, href]) =>
        `<a href="${href}"${activeNav === key ? ' aria-current="page"' : ""}>${label}</a>`
    )
    .join("");
  header.insertAdjacentElement("afterend", mobileMenu);

  const setMenuOpen = (open) => {
    mobileMenu.hidden = !open;
    menuButton.classList.toggle("is-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };

  menuButton.addEventListener("click", () => setMenuOpen(mobileMenu.hidden));
  mobileMenu.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenuOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setMenuOpen(false);
  });
  window.addEventListener("storage", updateCartCount);
  window.addEventListener(
    "pageshow",
    () => {
      updateCartCount();
      updateHeaderState(true);
    },
    { passive: true }
  );
  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateHeaderState);
    },
    { passive: true }
  );
  window.addEventListener(
    "resize",
    () => {
      if (window.innerWidth > 720) setMenuOpen(false);
      updateHeaderState(true);
    },
    { passive: true }
  );

  updateHeaderState(true);
})();

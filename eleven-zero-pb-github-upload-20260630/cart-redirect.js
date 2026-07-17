document.addEventListener(
  "click",
  (event) => {
    const buyButton = event.target.closest("[data-detail-buy]");
    if (!buyButton || buyButton.disabled || buyButton.dataset.buyAction !== "cart") return;

    const listingId = new URLSearchParams(window.location.search).get("id");
    if (!listingId) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    try {
      const cartKey = "elevenZeroPbCartItems";
      const existing = JSON.parse(window.localStorage.getItem(cartKey) || "[]");
      const items = Array.isArray(existing) ? existing : [];
      const cartItem = {
        listingId: Number(listingId),
        updatedAt: new Date().toISOString(),
      };
      const nextItems = [
        cartItem,
        ...items.filter((item) => Number(item?.listingId) !== Number(listingId)),
      ].slice(0, 12);
      window.localStorage.setItem(cartKey, JSON.stringify(nextItems));
      window.localStorage.setItem("elevenZeroPbCartDraft", JSON.stringify(cartItem));
    } catch (error) {
      console.warn("Cart could not be saved locally before redirect.", error);
    }

    window.location.href = `./cart.html?listingId=${encodeURIComponent(listingId)}`;
  },
  true
);

(() => {
  if (document.querySelector('script[data-eleven-zero-header-tweaks]')) return;

  const headerTweaks = document.createElement("script");
  headerTweaks.src = "./header-tweaks.js?v=20260703a";
  headerTweaks.defer = true;
  headerTweaks.dataset.elevenZeroHeaderTweaks = "true";
  document.body.appendChild(headerTweaks);
})();

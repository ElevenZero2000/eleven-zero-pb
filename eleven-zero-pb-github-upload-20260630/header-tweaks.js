(function initHeaderTweaks() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const condensedThreshold = 56;
  let ticking = false;

  const updateHeaderState = () => {
    header.classList.toggle("is-condensed", window.scrollY > condensedThreshold);
    ticking = false;
  };

  updateHeaderState();

  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateHeaderState);
    },
    { passive: true }
  );

  window.addEventListener("resize", updateHeaderState, { passive: true });
})();

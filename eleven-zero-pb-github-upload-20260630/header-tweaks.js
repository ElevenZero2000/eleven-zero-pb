(function initHeaderTweaks() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const enterThreshold = 124;
  const exitThreshold = 72;
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
})();

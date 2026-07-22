const signinForm = document.querySelector("[data-signin-form]");
const signinStatus = document.querySelector("[data-signin-status]");
const signupForm = document.querySelector("[data-signup-form]");
const signupStatus = document.querySelector("[data-signup-status]");
const authModeButtons = Array.from(document.querySelectorAll("[data-auth-mode]"));
const authPanels = Array.from(document.querySelectorAll("[data-auth-panel]"));
const resetRequestForm = document.querySelector("[data-reset-request-form]");
const resetRequestStatus = document.querySelector("[data-reset-request-status]");
const resetConfirmForm = document.querySelector("[data-reset-confirm-form]");
const resetConfirmStatus = document.querySelector("[data-reset-confirm-status]");
const verificationStatus = document.querySelector("[data-verification-status]");

function getInitialAuthMode() {
  const requestedMode = new URLSearchParams(window.location.search).get("mode");
  if (["forgot", "reset", "verify"].includes(requestedMode)) return requestedMode;
  return requestedMode === "signup" || requestedMode === "create" ? "signup" : "signin";
}

function setAuthMode(mode, { updateUrl = false } = {}) {
  const allowedModes = ["signin", "signup", "forgot", "reset", "verify"];
  const nextMode = allowedModes.includes(mode) ? mode : "signin";

  authModeButtons.forEach((button) => {
    const isActive = button.dataset.authMode === nextMode;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
    button.tabIndex = isActive ? 0 : -1;
  });

  authPanels.forEach((panel) => {
    panel.hidden = panel.dataset.authPanel !== nextMode;
  });

  if (updateUrl) {
    const url = new URL(window.location.href);
    if (nextMode !== "signin") {
      url.searchParams.set("mode", nextMode);
    } else {
      url.searchParams.delete("mode");
    }
    window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
  }
}

function setFormPending(form, isPending, idleLabel, pendingLabel) {
  if (!form) return;

  form.setAttribute("aria-busy", isPending ? "true" : "false");

  const button = form.querySelector('button[type="submit"]');
  const fields = Array.from(form.querySelectorAll("input, select, textarea, button"));

  fields.forEach((field) => {
    field.disabled = isPending;
  });

  if (button) {
    button.textContent = isPending ? pendingLabel : idleLabel;
  }
}

function finishAuth(statusNode, message) {
  ElevenZeroApp.setStatus(statusNode, message, "success");
  window.location.replace(ElevenZeroApp.getPostAuthDestination());
}

async function handleSignin(event) {
  event.preventDefault();

  const payload = Object.fromEntries(new FormData(signinForm).entries());
  setFormPending(signinForm, true, "Sign In", "Signing in...");

  try {
    const response = await ElevenZeroApp.request("/api/auth/signin", {
      method: "POST",
      body: payload,
    });
    ElevenZeroApp.session = {
      authenticated: true,
      user: response.user,
      csrfToken: response.csrfToken || "",
    };
    finishAuth(signinStatus, "Signed in — opening your dashboard now.");
  } catch (error) {
    ElevenZeroApp.setStatus(signinStatus, error.message, "error");
    setFormPending(signinForm, false, "Sign In", "Signing in...");
  }
}

async function handleSignup(event) {
  event.preventDefault();

  const payload = Object.fromEntries(new FormData(signupForm).entries());
  setFormPending(signupForm, true, "Create Account", "Creating account...");

  try {
    const response = await ElevenZeroApp.request("/api/auth/signup", {
      method: "POST",
      body: payload,
    });
    ElevenZeroApp.session = {
      authenticated: true,
      user: response.user,
      csrfToken: response.csrfToken || "",
    };
    finishAuth(signupStatus, "Account created — opening your dashboard now.");
  } catch (error) {
    ElevenZeroApp.setStatus(signupStatus, error.message, "error");
    setFormPending(signupForm, false, "Create Account", "Creating account...");
  }
}

async function handleResetRequest(event) {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(resetRequestForm).entries());
  setFormPending(resetRequestForm, true, "Send reset link", "Sending…");
  try {
    const response = await ElevenZeroApp.request("/api/auth/password-reset/request", {
      method: "POST",
      body: payload,
    });
    ElevenZeroApp.setStatus(resetRequestStatus, response.message, "success");
  } catch (error) {
    ElevenZeroApp.setStatus(resetRequestStatus, error.message, "error");
  } finally {
    setFormPending(resetRequestForm, false, "Send reset link", "Sending…");
  }
}

async function handleResetConfirm(event) {
  event.preventDefault();
  const params = new URLSearchParams(window.location.search);
  const payload = Object.fromEntries(new FormData(resetConfirmForm).entries());
  payload.token = params.get("token") || "";
  setFormPending(resetConfirmForm, true, "Update password", "Updating…");
  try {
    const response = await ElevenZeroApp.request("/api/auth/password-reset/confirm", {
      method: "POST",
      body: payload,
    });
    ElevenZeroApp.setStatus(resetConfirmStatus, response.message, "success");
    window.setTimeout(() => setAuthMode("signin", { updateUrl: true }), 900);
  } catch (error) {
    ElevenZeroApp.setStatus(resetConfirmStatus, error.message, "error");
    setFormPending(resetConfirmForm, false, "Update password", "Updating…");
  }
}

async function verifyEmailFromUrl() {
  if (getInitialAuthMode() !== "verify") return;
  const token = new URLSearchParams(window.location.search).get("token") || "";
  try {
    const response = await ElevenZeroApp.request("/api/auth/verify-email", {
      method: "POST",
      body: { token },
    });
    ElevenZeroApp.setStatus(verificationStatus, response.message, "success");
  } catch (error) {
    ElevenZeroApp.setStatus(verificationStatus, error.message, "error");
  }
  document.querySelector('[data-auth-panel="verify"] [data-back-signin]')?.removeAttribute("hidden");
}

document.addEventListener("DOMContentLoaded", async () => {
  setAuthMode(getInitialAuthMode());

  authModeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setAuthMode(button.dataset.authMode, { updateUrl: true });
    });
  });

  document.querySelector("[data-forgot-password]")?.addEventListener("click", () => {
    setAuthMode("forgot", { updateUrl: true });
  });
  document.querySelectorAll("[data-back-signin]").forEach((button) => {
    button.addEventListener("click", () => setAuthMode("signin", { updateUrl: true }));
  });

  await ElevenZeroApp.boot;

  if (ElevenZeroApp.session?.authenticated && !["reset", "verify"].includes(getInitialAuthMode())) {
    setFormPending(signinForm, true, "Sign In", "Opening dashboard...");
    setFormPending(signupForm, true, "Create Account", "Opening dashboard...");
    ElevenZeroApp.setStatus(
      signinStatus,
      `You are already signed in as ${ElevenZeroApp.session.user.name} — opening your dashboard now.`,
      "success"
    );
    ElevenZeroApp.setStatus(
      signupStatus,
      "Your account is already active — taking you straight to the dashboard.",
      "success"
    );
    window.setTimeout(() => {
      window.location.replace(ElevenZeroApp.getPostAuthDestination());
    }, 160);
    return;
  }

  signinForm?.addEventListener("submit", handleSignin);
  signupForm?.addEventListener("submit", handleSignup);
  resetRequestForm?.addEventListener("submit", handleResetRequest);
  resetConfirmForm?.addEventListener("submit", handleResetConfirm);
  await verifyEmailFromUrl();
});

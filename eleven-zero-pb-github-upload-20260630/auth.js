const signinForm = document.querySelector("[data-signin-form]");
const signinStatus = document.querySelector("[data-signin-status]");
const signupForm = document.querySelector("[data-signup-form]");
const signupStatus = document.querySelector("[data-signup-status]");

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
    ElevenZeroApp.session = { authenticated: true, user: response.user };
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
    ElevenZeroApp.session = { authenticated: true, user: response.user };
    finishAuth(signupStatus, "Account created — opening your dashboard now.");
  } catch (error) {
    ElevenZeroApp.setStatus(signupStatus, error.message, "error");
    setFormPending(signupForm, false, "Create Account", "Creating account...");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;

  if (ElevenZeroApp.session?.authenticated) {
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
});

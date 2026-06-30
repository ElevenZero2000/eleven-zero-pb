const signinForm = document.querySelector("[data-signin-form]");
const signinStatus = document.querySelector("[data-signin-status]");
const signupForm = document.querySelector("[data-signup-form]");
const signupStatus = document.querySelector("[data-signup-status]");

async function handleSignin(event) {
  event.preventDefault();

  const payload = Object.fromEntries(new FormData(signinForm).entries());

  try {
    const response = await ElevenZeroApp.request("/api/auth/signin", {
      method: "POST",
      body: payload,
    });
    ElevenZeroApp.session = { authenticated: true, user: response.user };
    ElevenZeroApp.setStatus(signinStatus, "Signed in — taking you to your dashboard.", "success");
    window.setTimeout(() => {
      window.location.href = ElevenZeroApp.getPostAuthDestination();
    }, 400);
  } catch (error) {
    ElevenZeroApp.setStatus(signinStatus, error.message, "error");
  }
}

async function handleSignup(event) {
  event.preventDefault();

  const payload = Object.fromEntries(new FormData(signupForm).entries());

  try {
    const response = await ElevenZeroApp.request("/api/auth/signup", {
      method: "POST",
      body: payload,
    });
    ElevenZeroApp.session = { authenticated: true, user: response.user };
    ElevenZeroApp.setStatus(signupStatus, "Account created — taking you to your dashboard.", "success");
    window.setTimeout(() => {
      window.location.href = ElevenZeroApp.getPostAuthDestination();
    }, 400);
  } catch (error) {
    ElevenZeroApp.setStatus(signupStatus, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await ElevenZeroApp.boot;

  if (ElevenZeroApp.session?.authenticated) {
    ElevenZeroApp.setStatus(
      signinStatus,
      `You are already signed in as ${ElevenZeroApp.session.user.name}.`,
      "success"
    );
    ElevenZeroApp.setStatus(
      signupStatus,
      "Your account is already active — you can head straight to the dashboard.",
      "success"
    );
  }

  signinForm?.addEventListener("submit", handleSignin);
  signupForm?.addEventListener("submit", handleSignup);
});

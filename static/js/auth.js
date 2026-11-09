async function getCsrfToken() {
  const response = await fetch("/api/csrf-token");
  if (!response.ok) throw new Error("Could not start a secure request.");
  const data = await response.json();
  return data.csrf_token;
}

function showFormMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

document.addEventListener("DOMContentLoaded", () => {
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = document.getElementById("registerMessage");
      const button = registerForm.querySelector("button[type='submit']");
      button.disabled = true;
      showFormMessage(message, "Creating your account…");
      try {
        const token = await getCsrfToken();
        const response = await fetch("/api/register", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
          body: JSON.stringify({
            full_name: document.getElementById("fullName").value.trim(),
            email: document.getElementById("registerEmail").value.trim(),
            password: document.getElementById("registerPassword").value,
            role: document.getElementById("registerRole").value
          })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Registration failed.");
        showFormMessage(message, "Account created. Taking you to login…");
        setTimeout(() => window.location.href = "/login", 900);
      } catch (error) {
        showFormMessage(message, error.message, true);
      } finally {
        button.disabled = false;
      }
    });
  }

  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = document.getElementById("loginMessage");
      const button = loginForm.querySelector("button[type='submit']");
      button.disabled = true;
      showFormMessage(message, "Signing you in…");
      try {
        const token = await getCsrfToken();
        const response = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
          body: JSON.stringify({
            email: document.getElementById("loginEmail").value.trim(),
            password: document.getElementById("loginPassword").value
          })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Login failed.");
        showFormMessage(message, "Login successful. Opening your dashboard…");
        setTimeout(() => window.location.href = "/dashboard", 500);
      } catch (error) {
        showFormMessage(message, error.message, true);
      } finally {
        button.disabled = false;
      }
    });
  }
});
document.addEventListener("DOMContentLoaded", () => {
  const logoutButton = document.getElementById("logoutButton");
  if (!logoutButton) return;

  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
      const tokenResponse = await fetch("/api/csrf-token");
      const tokenData = await tokenResponse.json();
      const response = await fetch("/api/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": tokenData.csrf_token }
      });
      if (response.ok) window.location.href = "/";
      else alert("Could not log out. Please try again.");
    } catch (error) {
      alert("A connection error occurred. Please try again.");
    } finally {
      logoutButton.disabled = false;
    }
  });
});
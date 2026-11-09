async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) throw new Error(data.message || `Request failed (${response.status}).`);
  return data;
}

async function csrfHeaders() {
  const data = await apiRequest("/api/csrf-token");
  return { "Content-Type": "application/json", "X-CSRF-Token": data.csrf_token };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function propertyCard(property, ownerMode = false) {
  const actions = ownerMode ? `
    <div class="property-actions">
      <button class="btn btn-outline edit-property" data-id="${property.id}">Edit</button>
      <button class="btn btn-outline delete-property" data-id="${property.id}">Delete</button>
    </div>` : "";
  return `
    <article class="property-card">
      <div class="property-topline"><span class="property-label">PROPERTY LISTING</span><span class="role-pill">Available</span></div>
      <h3>${escapeHtml(property.title)}</h3>
      <div class="property-location">⌖ ${escapeHtml(property.location)}</div>
      <p class="property-description">${escapeHtml(property.description)}</p>
      <div class="property-price">KES ${Number(property.price).toLocaleString("en-KE")} <small>/ month</small></div>
      ${ownerMode ? "" : `<div class="property-owner">Listed by ${escapeHtml(property.owner_name)}</div>`}
      ${actions}
    </article>`;
}

document.addEventListener("DOMContentLoaded", () => {
  const seekerGrid = document.getElementById("propertyGrid");
  const ownerForm = document.getElementById("propertyForm");
  const adminTable = document.getElementById("usersTableBody");

  if (seekerGrid && !ownerForm) loadSeekerProperties();
  if (ownerForm) {
    loadOwnerProperties();
    ownerForm.addEventListener("submit", saveProperty);
    document.getElementById("cancelEditButton").addEventListener("click", resetPropertyForm);
  }
  if (adminTable) loadAdminUsers();

  async function loadSeekerProperties() {
    const grid = document.getElementById("propertyGrid");
    try {
      const properties = await apiRequest("/api/properties");
      renderSeekerProperties(properties);
      document.getElementById("searchLocation").addEventListener("input", () => renderSeekerProperties(properties));
      document.getElementById("searchPrice").addEventListener("input", () => renderSeekerProperties(properties));
      document.getElementById("clearFilters").addEventListener("click", () => {
        document.getElementById("searchLocation").value = "";
        document.getElementById("searchPrice").value = "";
        renderSeekerProperties(properties);
      });
    } catch (error) {
      grid.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
  }

  function renderSeekerProperties(properties) {
    const location = document.getElementById("searchLocation").value.trim().toLowerCase();
    const maxPrice = document.getElementById("searchPrice").value;
    const filtered = properties.filter(item =>
      item.location.toLowerCase().includes(location) &&
      (maxPrice === "" || Number(item.price) <= Number(maxPrice))
    );
    document.getElementById("listingCount").textContent = `${filtered.length} listing(s)`;
    document.getElementById("propertyGrid").innerHTML = filtered.length
      ? filtered.map(item => propertyCard(item)).join("")
      : '<div class="empty-state">No properties match your search yet. Try changing your filters.</div>';
  }

  async function loadOwnerProperties() {
    try {
      const properties = await apiRequest("/api/properties");
      const ownProperties = properties;
      document.getElementById("listingCount").textContent = `${ownProperties.length} listing(s)`;
      const grid = document.getElementById("propertyGrid");
      grid.innerHTML = ownProperties.length
        ? ownProperties.map(item => propertyCard(item, true)).join("")
        : '<div class="empty-state">You have not added any properties yet. Use the form to publish your first listing.</div>';

      grid.querySelectorAll(".edit-property").forEach(button => {
        button.addEventListener("click", () => {
          const item = ownProperties.find(property => property.id === Number(button.dataset.id));
          if (!item) return;
          document.getElementById("propertyId").value = item.id;
          document.getElementById("propertyTitle").value = item.title;
          document.getElementById("propertyDescription").value = item.description;
          document.getElementById("propertyLocation").value = item.location;
          document.getElementById("propertyPrice").value = item.price;
          document.getElementById("propertyFormTitle").textContent = "Edit property";
          document.getElementById("propertyFormEyebrow").textContent = "UPDATE LISTING";
          document.getElementById("savePropertyButton").textContent = "Save changes";
          document.getElementById("cancelEditButton").classList.remove("hidden");
          document.getElementById("propertyForm").scrollIntoView({ behavior: "smooth" });
        });
      });
      grid.querySelectorAll(".delete-property").forEach(button => {
        button.addEventListener("click", async () => {
          if (!confirm("Delete this property listing? This cannot be undone.")) return;
          try {
            const headers = await csrfHeaders();
            await apiRequest(`/api/properties/${button.dataset.id}`, { method: "DELETE", headers });
            loadOwnerProperties();
          } catch (error) {
            showOwnerMessage(error.message, true);
          }
        });
      });
    } catch (error) {
      document.getElementById("propertyGrid").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
  }

  async function saveProperty(event) {
    event.preventDefault();
    const message = document.getElementById("ownerMessage");
    const id = document.getElementById("propertyId").value;
    const payload = {
      title: document.getElementById("propertyTitle").value.trim(),
      description: document.getElementById("propertyDescription").value.trim(),
      location: document.getElementById("propertyLocation").value.trim(),
      price: document.getElementById("propertyPrice").value
    };
    const button = document.getElementById("savePropertyButton");
    button.disabled = true;
    try {
      const headers = await csrfHeaders();
      const result = await apiRequest(id ? `/api/properties/${id}` : "/api/properties", {
        method: id ? "PUT" : "POST",
        headers,
        body: JSON.stringify(payload)
      });
      showOwnerMessage(result.message || "Property saved successfully.");
      resetPropertyForm();
      loadOwnerProperties();
    } catch (error) {
      showOwnerMessage(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function resetPropertyForm() {
    ownerForm.reset();
    document.getElementById("propertyId").value = "";
    document.getElementById("propertyFormTitle").textContent = "Add a property";
    document.getElementById("propertyFormEyebrow").textContent = "NEW LISTING";
    document.getElementById("savePropertyButton").textContent = "Publish listing →";
    document.getElementById("cancelEditButton").classList.add("hidden");
  }

  function showOwnerMessage(text, isError = false) {
    const message = document.getElementById("ownerMessage");
    message.textContent = text;
    message.classList.toggle("error", isError);
  }

  async function loadAdminUsers() {
    try {
      const users = await apiRequest("/api/admin/users");
      document.getElementById("userTotal").textContent = users.length;
      document.getElementById("seekerTotal").textContent = users.filter(user => user.role === "seeker").length;
      document.getElementById("ownerTotal").textContent = users.filter(user => user.role === "owner").length;
      document.getElementById("adminMessage").textContent = `${users.length} account(s)`;
      const body = document.getElementById("usersTableBody");
      body.innerHTML = users.length ? users.map(user => `
        <tr>
          <td>${escapeHtml(user.full_name)}</td>
          <td>${escapeHtml(user.email)}</td>
          <td><span class="role-tag">${escapeHtml(user.role)}</span></td>
          <td>${escapeHtml(user.created_at || "—")}</td>
        </tr>`).join("") : '<tr><td colspan="4">No registered users yet.</td></tr>';
    } catch (error) {
      document.getElementById("usersTableBody").innerHTML =
        `<tr><td colspan="4">${escapeHtml(error.message)}</td></tr>`;
    }
  }
});
// Shared helpers used by register.js, identify.js and manage.js.

const TOKEN_KEY = "admin_token";

function getAdminToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function setAdminToken(value) {
  localStorage.setItem(TOKEN_KEY, value);
}

// Wraps fetch() and attaches the admin token header for admin-only routes.
// Not a security boundary by itself (that's enforced server-side) - just
// convenience so callers don't repeat the header wiring.
async function apiFetch(url, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (options.admin) {
    headers["X-Admin-Token"] = getAdminToken();
  }
  const resp = await fetch(url, { ...options, headers });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch (_) {
      /* response wasn't JSON - keep statusText */
    }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  return resp.json();
}

function initTokenField(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = getAdminToken();
  input.addEventListener("change", () => setAdminToken(input.value.trim()));
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

initTokenField("admin-token");

const rosterArea = document.getElementById("roster-area");
document.getElementById("btn-refresh").addEventListener("click", loadRoster);

async function loadRoster() {
  if (!getAdminToken()) {
    rosterArea.innerHTML = '<div class="empty-state">Enter your admin token first.</div>';
    return;
  }
  rosterArea.innerHTML = '<div class="empty-state">Loading...</div>';
  try {
    const individuals = await apiFetch("/api/individuals", { admin: true });
    renderRoster(individuals);
  } catch (err) {
    rosterArea.innerHTML = `<div class="empty-state">Failed to load roster: ${escapeHtml(err.message)}</div>`;
  }
}

function renderRoster(individuals) {
  if (individuals.length === 0) {
    rosterArea.innerHTML = '<div class="empty-state">No individuals registered yet.</div>';
    return;
  }
  const rows = individuals
    .map(
      (ind) => `
    <tr>
      <td>${escapeHtml(ind.full_name)}</td>
      <td>${escapeHtml(ind.role_or_title || "—")}</td>
      <td>${escapeHtml(ind.email || "—")}</td>
      <td><span class="pill">${ind.sample_count} sample${ind.sample_count === 1 ? "" : "s"}</span></td>
      <td><button class="danger" data-id="${ind.id}" data-name="${escapeHtml(ind.full_name)}">Remove</button></td>
    </tr>`
    )
    .join("");

  rosterArea.innerHTML = `
    <table class="roster">
      <thead>
        <tr><th>Name</th><th>Role</th><th>Email</th><th>Face data</th><th></th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;

  rosterArea.querySelectorAll("button.danger").forEach((btn) => {
    btn.addEventListener("click", () => removeIndividual(btn.dataset.id, btn.dataset.name));
  });
}

async function removeIndividual(id, name) {
  if (!confirm(`Remove ${name} from the roster? This deletes their face data too.`)) return;
  try {
    await apiFetch(`/api/individuals/${id}`, { method: "DELETE", admin: true });
    loadRoster();
  } catch (err) {
    alert("Failed to remove: " + err.message);
  }
}

if (getAdminToken()) loadRoster();

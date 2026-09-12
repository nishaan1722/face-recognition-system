const video = document.getElementById("video");
const canvas = document.getElementById("capture-canvas");
const camStatus = document.getElementById("cam-status");
const resultArea = document.getElementById("result-area");

const btnStartCam = document.getElementById("btn-start-cam");
const btnStopCam = document.getElementById("btn-stop-cam");

let stream = null;
let pollTimer = null;
let inFlight = false;
const POLL_INTERVAL_MS = 1500;

btnStartCam.addEventListener("click", async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    video.srcObject = stream;
    btnStartCam.disabled = true;
    btnStopCam.disabled = false;
    setStatus("Camera active - scanning...", "ok");
    pollTimer = setInterval(captureAndIdentify, POLL_INTERVAL_MS);
  } catch (err) {
    setStatus("Could not access camera: " + err.message, "err");
  }
});

btnStopCam.addEventListener("click", stopCamera);

function stopCamera() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  btnStartCam.disabled = false;
  btnStopCam.disabled = true;
  setStatus("Camera stopped.", "");
  resultArea.innerHTML = '<div class="empty-state">Start the camera to begin identification.</div>';
}

function setStatus(msg, cls) {
  camStatus.textContent = msg;
  camStatus.className = "status-line" + (cls ? " " + cls : "");
}

async function captureAndIdentify() {
  if (inFlight || !stream) return;
  inFlight = true;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(async (blob) => {
    if (!blob) { inFlight = false; return; }
    const form = new FormData();
    form.append("image", blob, "frame.jpg");
    try {
      const result = await apiFetch("/api/identify", { method: "POST", body: form });
      renderResult(result);
    } catch (err) {
      if (err.status === 429) {
        setStatus("Scanning too fast - backing off briefly.", "warn");
      } else {
        setStatus("Identification error: " + err.message, "err");
      }
    } finally {
      inFlight = false;
    }
  }, "image/jpeg", 0.85);
}

function renderResult(result) {
  if (result.identified && result.individual) {
    const ind = result.individual;
    const initials = ind.full_name
      .split(/\s+/)
      .map((p) => p[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
    resultArea.innerHTML = `
      <div class="result-card match">
        <div class="avatar-ring">${escapeHtml(initials)}</div>
        <div>
          <p class="result-name">${escapeHtml(ind.full_name)}</p>
          <p class="result-meta">${escapeHtml(ind.role_or_title || "")}</p>
          <p class="result-meta">${escapeHtml(ind.email || "")} ${ind.phone ? " · " + escapeHtml(ind.phone) : ""}</p>
          ${ind.notes ? `<p class="result-meta">${escapeHtml(ind.notes)}</p>` : ""}
        </div>
        <div class="result-conf">${result.confidence_pct != null ? result.confidence_pct + "% conf." : ""}</div>
      </div>`;
    setStatus("Identified: " + ind.full_name, "ok");
  } else {
    resultArea.innerHTML = `
      <div class="result-card unknown">
        <div class="avatar-ring">?</div>
        <div>
          <p class="result-name">Not identified</p>
          <p class="result-meta">${escapeHtml(result.message)}</p>
        </div>
      </div>`;
    setStatus("Scanning...", "");
  }
}

window.addEventListener("beforeunload", stopCamera);

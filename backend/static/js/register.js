initTokenField("admin-token");

const video = document.getElementById("video");
const canvas = document.getElementById("capture-canvas");
const thumbs = document.getElementById("thumbs");
const camStatus = document.getElementById("cam-status");
const submitStatus = document.getElementById("submit-status");

const btnStartCam = document.getElementById("btn-start-cam");
const btnCapture = document.getElementById("btn-capture");
const btnSubmit = document.getElementById("btn-submit");

let stream = null;
const capturedBlobs = []; // { blob, url }

btnStartCam.addEventListener("click", async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    video.srcObject = stream;
    btnCapture.disabled = false;
    setStatus(camStatus, "Camera active. Capture a few angles.", "ok");
  } catch (err) {
    setStatus(camStatus, "Could not access camera: " + err.message, "err");
  }
});

btnCapture.addEventListener("click", () => {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    capturedBlobs.push({ blob, url });
    renderThumbs();
    updateSubmitEnabled();
  }, "image/jpeg", 0.9);
});

function renderThumbs() {
  thumbs.innerHTML = "";
  capturedBlobs.forEach((item, idx) => {
    const wrap = document.createElement("div");
    wrap.style.position = "relative";
    const img = document.createElement("img");
    img.src = item.url;
    wrap.appendChild(img);
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "×";
    removeBtn.title = "Remove";
    removeBtn.style.cssText =
      "position:absolute;top:-6px;right:-6px;width:20px;height:20px;padding:0;border-radius:50%;font-size:12px;line-height:1;";
    removeBtn.addEventListener("click", () => {
      capturedBlobs.splice(idx, 1);
      renderThumbs();
      updateSubmitEnabled();
    });
    wrap.appendChild(removeBtn);
    thumbs.appendChild(wrap);
  });
}

function updateSubmitEnabled() {
  const name = document.getElementById("full_name").value.trim();
  btnSubmit.disabled = capturedBlobs.length === 0 || name.length === 0;
}

document.getElementById("full_name").addEventListener("input", updateSubmitEnabled);

function setStatus(el, msg, cls) {
  el.textContent = msg;
  el.className = "status-line" + (cls ? " " + cls : "");
}

btnSubmit.addEventListener("click", async () => {
  const full_name = document.getElementById("full_name").value.trim();
  if (!full_name) {
    setStatus(submitStatus, "Full name is required.", "err");
    return;
  }
  if (capturedBlobs.length === 0) {
    setStatus(submitStatus, "Capture at least one photo first.", "err");
    return;
  }
  if (!getAdminToken()) {
    setStatus(submitStatus, "Enter the admin token above first.", "err");
    return;
  }

  btnSubmit.disabled = true;
  setStatus(submitStatus, "Registering...", "warn");

  const form = new FormData();
  form.append("full_name", full_name);
  form.append("role_or_title", document.getElementById("role_or_title").value.trim());
  form.append("email", document.getElementById("email").value.trim());
  form.append("phone", document.getElementById("phone").value.trim());
  form.append("notes", document.getElementById("notes").value.trim());
  capturedBlobs.forEach((item, idx) => {
    form.append("images", item.blob, `capture_${idx}.jpg`);
  });

  try {
    const result = await apiFetch("/api/individuals", { method: "POST", body: form, admin: true });
    setStatus(submitStatus, result.message, "ok");
    capturedBlobs.length = 0;
    renderThumbs();
    document.getElementById("full_name").value = "";
    document.getElementById("role_or_title").value = "";
    document.getElementById("email").value = "";
    document.getElementById("phone").value = "";
    document.getElementById("notes").value = "";
  } catch (err) {
    setStatus(submitStatus, "Registration failed: " + err.message, "err");
  } finally {
    updateSubmitEnabled();
  }
});

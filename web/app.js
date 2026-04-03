const loginSection = document.getElementById("login-section");
const appSection = document.getElementById("app-section");
const adminSection = document.getElementById("admin-section");
const recordsSection = document.getElementById("records-section");

const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const logoutBtn = document.getElementById("logout-btn");
const welcomeTitle = document.getElementById("welcome-title");
const userMeta = document.getElementById("user-meta");

const sessionDateInput = document.getElementById("session-date");
const batchMessage = document.getElementById("batch-message");
const scanMessage = document.getElementById("scan-message");

const modeFaceBtn = document.getElementById("mode-face-btn");
const modeManualBtn = document.getElementById("mode-manual-btn");
const faceModeSection = document.getElementById("face-mode");
const manualModeSection = document.getElementById("manual-mode");

const startCameraBtn = document.getElementById("start-camera-btn");
const captureBtn = document.getElementById("capture-btn");
const fileInput = document.getElementById("file-input");
const submitFaceBtn = document.getElementById("submit-face-btn");
const submitManualBtn = document.getElementById("submit-manual-btn");

const videoEl = document.getElementById("camera");
const previewImage = document.getElementById("preview-image");
const canvasEl = document.getElementById("capture-canvas");

const facePendingBody = document.getElementById("face-pending-body");
const manualBody = document.getElementById("manual-body");

const refreshRecordsBtn = document.getElementById("refresh-records-btn");
const recordsBody = document.getElementById("records-body");
const exportBtn = document.getElementById("export-btn");
const exportSheetBtn = document.getElementById("export-sheet-btn");

const API = {
  login: "/auth/login",
  me: "/auth/me",
  users: "/auth/users",
  scan: "/attendance/scan",
  submitBatch: "/attendance/submit-batch",
  records: "/attendance/records",
  updateRecord: (id) => `/attendance/records/${id}`,
  exportCsv: "/attendance/export-csv",
  exportSheet: "/attendance/export-sheet",
};

let token = localStorage.getItem("access_token");
let currentUser = null;
let stream = null;
let students = [];
let facePending = [];
let markedUserIds = new Set();

function setLoginError(message) {
  loginError.textContent = message;
  loginError.classList.toggle("hidden", !message);
}

function setAppState(isLoggedIn) {
  loginSection.classList.toggle("hidden", isLoggedIn);
  appSection.classList.toggle("hidden", !isLoggedIn);
}

function setMode(mode) {
  faceModeSection.classList.toggle("hidden", mode !== "face");
  manualModeSection.classList.toggle("hidden", mode !== "manual");
}

function getSessionPayload() {
  const attendance_date = sessionDateInput.value;
  if (!attendance_date) throw new Error("Choose a date");
  return { attendance_date };
}

async function apiRequest(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(url, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const msg = typeof data === "object" && data?.detail ? data.detail : "Request failed";
    throw new Error(msg);
  }
  return data;
}

function renderFacePending() {
  facePendingBody.innerHTML = "";
  if (!facePending.length) {
    facePendingBody.innerHTML = "<tr><td>No recognized faces yet.</td></tr>";
    return;
  }
  facePending.forEach((entry) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${entry.name}</td>`;
    facePendingBody.appendChild(tr);
  });
}

function renderManualList() {
  manualBody.innerHTML = "";
  students.forEach((student) => {
    const checked = markedUserIds.has(student.id) ? "checked" : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="checkbox" data-user-id="${student.id}" ${checked} /></td>
      <td>${student.name}</td>
      <td>${student.email}</td>
    `;
    manualBody.appendChild(tr);
  });
}

function updateDateHighlight(hasRecords) {
  sessionDateInput.classList.toggle("date-marked", hasRecords);
}

async function loadRecords() {
  recordsBody.innerHTML = "";
  markedUserIds = new Set();
  const selectedDate = sessionDateInput.value;
  try {
    const rows = await apiRequest(`${API.records}?start_date=${selectedDate}&end_date=${selectedDate}`);
    rows.sort((a, b) => a.user_name.localeCompare(b.user_name));

    rows.forEach((record) => {
      if (record.status === "present") {
        markedUserIds.add(record.user_id);
      }
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${record.id}</td>
        <td>${record.user_name}</td>
        <td>${record.attendance_date}</td>
        <td>
          <select data-role="status" data-id="${record.id}">
            <option value="present" ${record.status === "present" ? "selected" : ""}>present</option>
            <option value="absent" ${record.status === "absent" ? "selected" : ""}>absent</option>
          </select>
        </td>
        <td><button class="secondary" data-role="save" data-id="${record.id}" type="button">Edit</button></td>
      `;
      recordsBody.appendChild(tr);
    });

    if (!rows.length) {
      recordsBody.innerHTML = "<tr><td colspan='5'>No records for selected date.</td></tr>";
    }

    updateDateHighlight(rows.length > 0);
    renderManualList();
  } catch (error) {
    recordsBody.innerHTML = `<tr><td colspan='5'>Error: ${error.message}</td></tr>`;
    updateDateHighlight(false);
  }
}

async function exportFile(url, filename) {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error("Export failed");
  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(downloadUrl);
}

function playDetectedSound() {
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const oscillator = audioContext.createOscillator();
  const gainNode = audioContext.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = 880;
  gainNode.gain.value = 0.08;
  oscillator.connect(gainNode);
  gainNode.connect(audioContext.destination);
  oscillator.start();
  oscillator.stop(audioContext.currentTime + 0.14);
}

function stopCamera() {
  if (!stream) return;
  stream.getTracks().forEach((track) => track.stop());
  stream = null;
  videoEl.srcObject = null;
  videoEl.classList.add("hidden");
  startCameraBtn.textContent = "Show Camera";
}

async function toggleCamera() {
  if (stream) {
    stopCamera();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    alert("Camera is not supported.");
    return;
  }
  stream = await navigator.mediaDevices.getUserMedia({ video: true });
  videoEl.srcObject = stream;
  videoEl.classList.remove("hidden");
  startCameraBtn.textContent = "Close Camera";
}

async function scanBlob(blob) {
  scanMessage.textContent = "Scanning...";
  const formData = new FormData();
  formData.append("file", blob, "scan.jpg");
  try {
    const result = await apiRequest(API.scan, { method: "POST", body: formData });
    result.recognized.forEach((detected) => {
      if (!markedUserIds.has(detected.user_id) && !facePending.some((item) => item.user_id === detected.user_id)) {
        facePending.push(detected);
      }
    });
    renderFacePending();
    if (result.recognized.length > 0) {
      playDetectedSound();
      stopCamera();
    }
    scanMessage.textContent = result.unknown_faces > 0 ? "Unknown face detected and ignored." : result.message;
  } catch (error) {
    scanMessage.textContent = `Scan error: ${error.message}`;
  }
}

function captureFrame() {
  if (!stream) {
    alert("Start camera first.");
    return;
  }
  const width = videoEl.videoWidth || 640;
  const height = videoEl.videoHeight || 480;
  canvasEl.width = width;
  canvasEl.height = height;
  const ctx = canvasEl.getContext("2d");
  ctx.drawImage(videoEl, 0, 0, width, height);
  canvasEl.toBlob((blob) => {
    previewImage.src = URL.createObjectURL(blob);
    previewImage.classList.remove("hidden");
    scanBlob(blob);
  }, "image/jpeg", 0.9);
}

function onFileSelected(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  previewImage.src = URL.createObjectURL(file);
  previewImage.classList.remove("hidden");
  scanBlob(file);
}

async function submitFaceAttendance() {
  try {
    const payload = getSessionPayload();
    if (!facePending.length) throw new Error("No recognized students to submit");
    const entries = facePending.map((item) => ({ user_id: item.user_id, confidence: item.confidence, status: "present" }));
    const result = await apiRequest(API.submitBatch, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, entries }),
    });
    batchMessage.textContent = `Saved. Created ${result.created_count}, updated ${result.updated_count}.`;
    facePending = [];
    renderFacePending();
    await loadRecords();
  } catch (error) {
    batchMessage.textContent = `Submit error: ${error.message}`;
  }
}

async function submitManualAttendance() {
  try {
    const payload = getSessionPayload();
    const checked = Array.from(manualBody.querySelectorAll("input[type='checkbox']:checked"));
    if (!checked.length) throw new Error("Select at least one student");
    const entries = checked.map((input) => ({ user_id: Number(input.dataset.userId), confidence: 1.0, status: "present" }));
    const result = await apiRequest(API.submitBatch, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, entries }),
    });
    batchMessage.textContent = `Saved. Created ${result.created_count}, updated ${result.updated_count}.`;
    await loadRecords();
  } catch (error) {
    batchMessage.textContent = `Submit error: ${error.message}`;
  }
}

async function renderUser() {
  welcomeTitle.textContent = `Welcome, ${currentUser.name}`;
  userMeta.textContent = `${currentUser.email} | Role: ${currentUser.role}`;
  const isAdmin = currentUser.role === "admin";
  adminSection.classList.toggle("hidden", !isAdmin);
  recordsSection.classList.toggle("hidden", !isAdmin);
  if (isAdmin) {
    const users = await apiRequest(API.users);
    students = users.filter((user) => user.role === "student" && user.is_active).sort((a, b) => a.name.localeCompare(b.name));
    renderManualList();
    await loadRecords();
  }
}

async function bootstrapSession() {
  const now = new Date();
  sessionDateInput.value = now.toISOString().slice(0, 10);
  setMode("face");
  if (!token) {
    setAppState(false);
    return;
  }
  try {
    currentUser = await apiRequest(API.me);
    await renderUser();
    setAppState(true);
  } catch (_) {
    token = null;
    localStorage.removeItem("access_token");
    setAppState(false);
  }
}

recordsBody.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.dataset.role !== "save") return;
  const id = Number(target.dataset.id);
  const statusSelect = recordsBody.querySelector(`select[data-role='status'][data-id='${id}']`);
  if (!(statusSelect instanceof HTMLSelectElement)) return;
  try {
    await apiRequest(API.updateRecord(id), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: statusSelect.value }),
    });
    batchMessage.textContent = "Record updated.";
    await loadRecords();
  } catch (error) {
    batchMessage.textContent = `Edit error: ${error.message}`;
  }
});

sessionDateInput.addEventListener("change", async () => {
  facePending = [];
  renderFacePending();
  await loadRecords();
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoginError("");
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  try {
    const result = await apiRequest(API.login, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    token = result.access_token;
    localStorage.setItem("access_token", token);
    currentUser = await apiRequest(API.me);
    await renderUser();
    setAppState(true);
  } catch (error) {
    setLoginError(error.message || "Login failed");
  }
});

logoutBtn.addEventListener("click", () => {
  stopCamera();
  token = null;
  currentUser = null;
  localStorage.removeItem("access_token");
  setAppState(false);
});

modeFaceBtn.addEventListener("click", () => setMode("face"));
modeManualBtn.addEventListener("click", () => setMode("manual"));

startCameraBtn.addEventListener("click", toggleCamera);
captureBtn.addEventListener("click", captureFrame);
fileInput.addEventListener("change", onFileSelected);
submitFaceBtn.addEventListener("click", submitFaceAttendance);
submitManualBtn.addEventListener("click", submitManualAttendance);

refreshRecordsBtn.addEventListener("click", loadRecords);
exportBtn.addEventListener("click", async () => {
  try {
    await exportFile(API.exportCsv, "attendance.csv");
  } catch (error) {
    alert(error.message);
  }
});
exportSheetBtn.addEventListener("click", async () => {
  try {
    await exportFile(API.exportSheet, "attendance_sheet.xls");
  } catch (error) {
    alert(error.message);
  }
});

bootstrapSession();

/* =====================================================================
   ECRM Extractor — web page logic.
   Talks to /api/ecrm/* (webapp/ecrm_routes.py) and streams job logs over
   the shared /ws/logs/{job_id} WebSocket.
   ===================================================================== */

const state = {
  meta: null,               // { fields, presets, modes, deps_ok }
  selectedFields: new Set(),
  mode: "ORDER",
  jobId: null,
  socket: null,
  outputFile: "",
  maxWorkers: Number(localStorage.getItem("ecrm_max_workers") || 5),
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

async function api(path, options) {
  const res = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { detail = (await res.json()).detail || detail; } catch (_) { }
    throw new Error(detail);
  }
  return res.json();
}

/* ----------------------------- toasts ----------------------------- */
function toast(message, type = "info", duration = 3400) {
  const host = $("#toastHost");
  if (!host) {
    console[type === "error" ? "error" : "log"](message);
    return;
  }
  const node = el("div", `toast ${type}`, message);
  host.appendChild(node);
  setTimeout(() => {
    node.style.opacity = "0";
    setTimeout(() => node.remove(), 200);
  }, duration);
}

/* ----------------------------- credentials ----------------------------- */
async function loadCredentials() {
  const res = await fetch("/api/ecrm/credentials", { cache: "no-store" });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }

  const creds = await res.json();
  const username = String(creds.username || creds.windows_user || "").trim();
  const savedPassword = String(creds.password || "");

  console.info("ECRM Windows username:", username, "saved password:", !!savedPassword);

  const userInput = $("#username");
  const passInput = $("#password");

  if (userInput) {
    userInput.value = username;
    userInput.readOnly = true;
    userInput.setAttribute("readonly", "readonly");
    userInput.setAttribute("aria-readonly", "true");
    userInput.tabIndex = -1;
  }

  if (passInput && savedPassword) {
    passInput.value = savedPassword;
  }

  if (passInput) {
    passInput.readOnly = false;
    passInput.removeAttribute("readonly");
  }

  const side = $("#sideUserName");
  const greeting = $("#greetingUser");
  const top = $("#topUserName");
  if (side) side.textContent = username || "Not signed in";
  if (greeting) greeting.textContent = username || "ECRM User";
  if (top) top.textContent = username || "ECRM User";

  // Also keep the Credentials dialog synchronized.
  const dialogUser = $("#credentialsUsername");
  const dialogPass = $("#credentialsPassword");
  if (dialogUser) {
    dialogUser.value = username;
    dialogUser.readOnly = true;
    dialogUser.setAttribute("readonly", "readonly");
    dialogUser.tabIndex = -1;
  }
  if (dialogPass && savedPassword) {
    dialogPass.value = savedPassword;
  }

  return creds;
}

/* ----------------------------- theme ----------------------------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = $(".theme-icon");
  const label = $(".theme-label");
  if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
  if (label) label.textContent = theme === "dark" ? "Light" : "Dark";
  try { localStorage.setItem("we-theme", theme); } catch (_) { }
}

function initTheme() {
  let theme = "light";
  try { theme = localStorage.getItem("we-theme") || "light"; } catch (_) { }
  applyTheme(theme);
  $("#themeToggle").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });
}

/* ----------------------------- sidebar nav ----------------------------- */
function initNav() {
  $$(".side-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const which = btn.dataset.nav;
      if (which === "history") { openHistory(); return; }
      if (which === "presets") { openPresets(); return; }
      if (which === "settings") { openSettings(); return; }
      $$(".side-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
}

/* ----------------------------- status helpers ----------------------------- */
function setSideStatus(title, sub, color) {
  const titleEl = $("#sideStatusText");
  const subEl = $("#sideStatusSub");
  const dotEl = $("#sideDot");

  if (titleEl) titleEl.textContent = title ?? "";
  if (subEl) subEl.textContent = sub ?? "";
  if (dotEl) dotEl.style.background = color || "var(--success)";
}

function setRunStatus(text, cls) {
  const pill = $("#runStatus");
  if (!pill) return;
  pill.textContent = text ?? "";
  pill.className = `pill ${cls || ""}`;
}

/* ----------------------------- meta & fields ----------------------------- */
async function loadMeta() {
  try {
    const meta = await api("/api/ecrm/meta");
    state.meta = meta;

    if (!meta.deps_ok.ok) {
      toast(`Missing ECRM packages: ${meta.deps_ok.missing.join(", ")}`, "error", 6000);
    }

    renderFields();
  } catch (err) {
    toast(`Failed to load fields: ${err.message}`, "error");
    $("#fieldsGrid").innerHTML = "";
    $("#fieldsEmpty").classList.remove("hidden");
    $("#fieldsEmpty").innerHTML = "<p>❌ Could not load ECRM field list.</p>";
  }
}

function renderFields() {
  const grid = $("#fieldsGrid");
  const term = ($("#fieldSearch").value || "").trim().toLowerCase();
  grid.innerHTML = "";

  let visible = 0;
  (state.meta.fields || []).forEach((name) => {
    if (term && !name.toLowerCase().includes(term)) return;
    visible += 1;

    const checked = state.selectedFields.has(name);
    const cell = el("label", `field-cell${checked ? " checked" : ""}`);

    const box = el("input");
    box.type = "checkbox";
    box.checked = checked;
    box.addEventListener("change", () => {
      if (box.checked) state.selectedFields.add(name);
      else state.selectedFields.delete(name);
      cell.classList.toggle("checked", box.checked);
      updateFieldCount();
    });

    cell.appendChild(box);
    cell.appendChild(el("span", null, name));
    grid.appendChild(cell);
  });

  $("#fieldsEmpty").classList.toggle("hidden", visible > 0);
  updateFieldCount();
}

function updateFieldCount() {
  $("#fieldsCount").textContent = `${state.selectedFields.size} selected`;
}

/* ----------------------------- mode tabs ----------------------------- */
function initModeTabs() {
  $$(".mode-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".mode-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.mode = tab.dataset.mode;
      updateDirectPlaceholder();
    });
  });
}

function directLabel() {
  return { ORDER: "orders", CID: "CIDs", SO: "SO numbers", ORD: "ORD numbers" }[state.mode] || "values";
}

function updateDirectPlaceholder() {
  $("#directValues").placeholder =
    `Paste or drag ${directLabel()} here, one per line or separated by comma/space`;
}

function parseDirectValues() {
  const text = ($("#directValues").value || "").trim();
  if (!text) return [];
  const headers = new Set(["ORDER", "ORDERID", "ORDERS", "CID", "SO", "ORD"]);
  const seen = new Set();
  const values = [];
  text.split(/[\s,;]+/).forEach((tok) => {
    const v = tok.trim().replace(/^["']|["']$/g, "");
    if (!v || headers.has(v.toUpperCase())) return;
    if (!seen.has(v)) { seen.add(v); values.push(v); }
  });
  return values;
}

function updateDirectCount() {
  $("#directCount").textContent = `${parseDirectValues().length} added`;
}

/* ----------------------------- file upload ----------------------------- */
function initFileInput() {
  $("#fileInput").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/ecrm/upload", { method: "POST", body: form });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      $("#filePath").value = data.name;
      $("#filePath").dataset.backendPath = data.path;
      toast(`File ready: ${data.name}`, "success");
    } catch (err) {
      toast(`Upload failed: ${err.message}`, "error");
    }
  });
}

/* ----------------------------- logging ----------------------------- */
function showLogPanel() { $("#logPanel").classList.remove("hidden"); }

function isDebugEnabled() {
  return !!$("#debugMode")?.checked;
}

function shouldShowCompactLog(entry) {
  if (isDebugEnabled()) return true;

  const message = String(entry?.message || "").trim();
  const level = String(entry?.level || "info").toLowerCase();

  // Always keep warnings/errors visible.
  if (level === "error" || level === "warning") return true;

  // Job start summary.
  if (/^Job accepted:/i.test(message)) return true;

  // Main processing lifecycle.
  if (/^Processing \d+ item\(s\)…?$/i.test(message)) return true;
  if (/^Processing\.\.\.$/i.test(message)) return true;

  // Per-item progress only.
  if (/^Processed\s+\d+\s*\/\s*\d+\s*-/i.test(message)) return true;

  // Completion.
  if (/^DONE$/i.test(message)) return true;
  if (/^Completed:\s*Saved successfully to:/i.test(message)) return true;
  if (/^✅\s*Extraction finished/i.test(message)) return true;
  if (/^✓\s*Item\s+\d+\/\d+\s+completed/i.test(message)) return false;

  return false;
}

function appendLog(entry) {
  if (!shouldShowCompactLog(entry)) return;

  const out = $("#logOutput");
  if (!out) return;

  const line = el("span", `log-line ${entry?.level || "info"}`);
  line.appendChild(el("span", "ts", `[${entry?.timestamp || new Date().toLocaleTimeString()}]`));
  line.appendChild(document.createTextNode(String(entry?.message || "").replace(/\\r?\\n/g, " ")));
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
}

function setJobStatus(status, outputFile) {
  const map = {
    running: ["Running", "pill pill-info"],
    done: ["Done", "pill pill-success"],
    error: ["Error", "pill pill-error"],
    stopped: ["Stopped", "pill pill-warning"],
  };

  const [label, cls] = map[status] || ["Unknown", "pill pill-info"];

  const jobStatusEl = $("#logJobStatus");
  if (jobStatusEl) {
    jobStatusEl.textContent = label;
    jobStatusEl.className = cls;
  }

  if (status === "running") {
    setRunStatus("● PROCESSING", "pill-warning");
    setSideStatus("PROCESSING", "Extraction in progress…", "var(--warning)");

    const startBtn = $("#startBtn");
    const cancelBtn = $("#cancelBtn");
    if (startBtn) startBtn.disabled = true;
    if (cancelBtn) cancelBtn.disabled = false;
    return;
  }

  const ok = status === "done";
  setRunStatus(
    ok ? "● COMPLETED" : `● ${label.toUpperCase()}`,
    ok ? "pill-success" : "pill-warning"
  );

  setSideStatus(
    ok ? "READY" : label.toUpperCase(),
    ok ? "System is ready to extract data" : "Last run did not complete cleanly",
    ok ? "var(--success)" : "var(--warning)"
  );

  const startBtn = $("#startBtn");
  const cancelBtn = $("#cancelBtn");
  if (startBtn) startBtn.disabled = false;
  if (cancelBtn) cancelBtn.disabled = true;

  if (outputFile) {
    state.outputFile = outputFile;
    const downloadBtn = $("#downloadBtn");
    if (downloadBtn) downloadBtn.classList.remove("hidden");
    showCompactCompletion(outputFile);
  }

  toast(
    `ECRM extraction: ${label}`,
    status === "error" ? "error" : "success",
    5000
  );
}

function showCompactCompletion(outputFile) {
  const out = $("#logOutput");
  if (!out) return;

  // Prevent duplicate completion summary.
  if (out.dataset.compactDone === "1") return;
  out.dataset.compactDone = "1";

  const existing = out.innerText || "";
  const name = outputFile ? String(outputFile).split(/[\\/]/).pop() : "";

  if (name && !existing.includes(name)) {
    const line = el("span", "log-line success");
    line.appendChild(el("span", "ts", `[${new Date().toLocaleTimeString()}]`));
    line.appendChild(document.createTextNode(`📄 ${name}`));
    out.appendChild(line);
  }

  out.scrollTop = out.scrollHeight;
}

function connectLogs(jobId) {
  if (state.socket) { try { state.socket.close(); } catch (_) { } }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${proto}://${location.host}/ws/logs/${jobId}`);
  state.socket = socket;
  let seen = new Set();

  function applyJob(job, replay=false) {
    if (!job) return;
    if (replay && Array.isArray(job.lines)) {
      job.lines.forEach((entry, idx) => {
        const key = `${entry.timestamp}|${entry.level}|${entry.message}`;
        if (!seen.has(key)) { seen.add(key); appendLog(entry); }
      });
    }
    if (typeof job.progress === "number") {
      $("#progress").style.width = `${job.progress}%`;
      $("#progressText").textContent = `${Math.round(job.progress)}%`;
    }
    if (job.phase) {
      try { setSideStatus(job.status === "running" ? "PROCESSING" : job.phase, job.phase, job.status === "running" ? "var(--warning)" : "var(--success)"); } catch (_) {}
    }
    if (job.status && job.status !== "running") setJobStatus(job.status, job.output_file);
  }

  // Immediately replay logs already produced before the WebSocket connected.
  api(`/api/ecrm/jobs/${jobId}?_=${Date.now()}`, { cache: "no-store" })
    .then(job => applyJob(job, true))
    .catch(err => appendLog({timestamp:new Date().toLocaleTimeString(), level:"error", message:`Status check failed: ${err.message}`}));

  socket.addEventListener("message", (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (_) { return; }

    if (data.type === "heartbeat") {
      setSideStatus("PROCESSING", `${data.phase || "Processing"} • ${data.idle_seconds || 0}s`, "var(--warning)");
      return;
    } else if (data.type === "log") {
      const key = `${data.timestamp}|${data.level}|${data.message}`;
      if (!seen.has(key)) { seen.add(key); appendLog(data); }
      const m = /Processed\s+(\d+)\s*\/\s*(\d+)/i.exec(data.message || "");
      if (m) {
        const pct = Math.round((Number(m[1]) / Number(m[2])) * 100);
        $("#progress").style.width = `${pct}%`;
        $("#progressText").textContent = `${pct}%`;
      }
    } else if (data.type === "progress") {
      $("#progress").style.width = `${data.value}%`;
      $("#progressText").textContent = `${Math.round(data.value)}%`;
      if (data.status) setSideStatus("PROCESSING", data.status, "var(--warning)");
    } else if (data.type === "phase") {
      setSideStatus("PROCESSING", data.phase || "Processing", "var(--warning)");
    } else if (data.type === "status") {
      setJobStatus(data.status, data.output_file);
    }
  });

  // Fallback polling guarantees the UI cannot remain stuck on PROCESSING
  // just because a browser/WebSocket connection missed an event.
  if (state.jobPoll) clearInterval(state.jobPoll);
  state.jobPoll = setInterval(async () => {
    try {
      const job = await api(`/api/ecrm/jobs/${jobId}?_=${Date.now()}`, { cache: "no-store" });
      applyJob(job, true);
      if (job.status && job.status !== "running") {
        clearInterval(state.jobPoll);
        state.jobPoll = null;
      }
    } catch (err) {
      // Keep the extraction running, but make transport problems visible.
      if (!state._lastPollError || state._lastPollError !== err.message) {
        state._lastPollError = err.message;
        appendLog({timestamp:new Date().toLocaleTimeString(), level:"warning", message:`Status polling: ${err.message}`});
      }
    }
  }, 1000);
}

/* ----------------------------- start / cancel ----------------------------- */
async function startExtraction() {
  try {
    const directValues = parseDirectValues();
    const fileField = $("#filePath");
    const filePath = fileField?.dataset?.backendPath || "";
    // Username is auto-detected from Windows and is not user-editable.
    const username = ($("#username")?.value || "").trim();
    // Password is entered in the Credentials dialog and mirrored to #password.
    const password =
      $("#password")?.value ||
      $("#credentialsPassword")?.value ||
      "";

    if (!username) {
      toast("Detecting your Windows/ECRM username. Please open Credentials once.", "warning");
      return;
    }

    if (!password) {
      toast("ECRM password is not saved yet. Enter it once in Credentials.", "warning");
      openCredentials();
      return;
    }

    if (!directValues.length && !filePath) {
      toast("Choose an Excel file or paste values", "error");
      return;
    }

    if (!state.selectedFields.size) {
      toast("Select at least one field", "warning");
      return;
    }

    const logOutput = $("#logOutput");
    const downloadBtn = $("#downloadBtn");
    const progress = $("#progress");
    const progressText = $("#progressText");

    if (logOutput) {
      logOutput.innerHTML = "";
      delete logOutput.dataset.compactDone;
    }
    if (downloadBtn) downloadBtn.classList.add("hidden");
    if (progress) progress.style.width = "4%";
    if (progressText) progressText.textContent = "Starting…";

    showLogPanel();

    // UI updates are intentionally defensive. A missing dashboard element
    // must never prevent the actual backend request.
    try {
      setJobStatus("running", "");
    } catch (uiErr) {
      console.warn("Initial job-status UI update failed:", uiErr);
    }

    try {
      setSideStatus(
        "PROCESSING",
        "Extraction in progress…",
        "var(--warning)"
      );
    } catch (uiErr) {
      console.warn("Initial side-status UI update failed:", uiErr);
    }

    const payload = {
      username,
      password,
      mode: state.mode,
      selected_fields: [...state.selectedFields],
      direct_values: directValues,
      file_path: filePath,
      debug_mode: !!$("#debugMode")?.checked,
      max_workers: Math.max(1, Math.min(Number(state.maxWorkers) || 5, 12)),
    };

    console.info("Starting ECRM extraction:", {
      mode: payload.mode,
      values: payload.direct_values.length,
      fields: payload.selected_fields.length,
      workers: payload.max_workers,
      hasFile: !!payload.file_path,
    });

    const result = await api("/api/ecrm/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!result || !result.job_id) {
      throw new Error("Backend did not return a job_id.");
    }

    state.jobId = result.job_id;
    connectLogs(result.job_id);
    toast("Extraction started", "info");

  } catch (err) {
    console.error("ECRM extraction launch failed:", err);

    try {
      appendLog({
        timestamp: new Date().toLocaleTimeString(),
        level: "error",
        message: `Launch failed: ${err.message || err}`,
      });
    } catch (_) {}

    try {
      setJobStatus("error", "");
    } catch (_) {}

    toast(`Launch failed: ${err.message || err}`, "error");
  }
}

async function cancelExtraction() {
  if (!state.jobId) return;
  try {
    await api(`/api/ecrm/jobs/${state.jobId}/stop`, { method: "POST" });
    toast("Cancellation requested", "warning");
  } catch (err) {
    toast(`Cancel failed: ${err.message}`, "error");
  }
}

/* ----------------------------- modal ----------------------------- */
function openModal(title) {
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = "";
  $("#modal").classList.remove("hidden");
}
function closeModal() { $("#modal").classList.add("hidden"); }

function initModal() {
  $("#modalClose").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
}

async function openHistory() {
  openModal("🕐 Extraction History");
  const body = $("#modalBody");
  body.appendChild(el("p", "history-meta", "Loading…"));
  try {
    const files = await api("/api/ecrm/history");
    body.innerHTML = "";
    if (!files.length) {
      body.appendChild(el("p", "history-meta", "No extraction history found yet."));
      return;
    }
    const list = el("div", "history-list");
    files.forEach((f) => {
      const row = el("div", "history-item");
      const info = el("div");
      info.appendChild(el("div", "history-name", f.name));
      info.appendChild(el("div", "history-meta", `${(f.size / 1024).toFixed(1)} KB · ${f.modified}`));
      row.appendChild(info);

      const dl = el("a", "btn btn-primary btn-sm", "⬇ Download");
      dl.href = `/api/ecrm/history/${encodeURIComponent(f.name)}`;
      dl.setAttribute("download", f.name);
      row.appendChild(dl);
      list.appendChild(row);
    });
    body.appendChild(list);
  } catch (err) {
    body.innerHTML = "";
    body.appendChild(el("p", "history-meta", `Failed to load history: ${err.message}`));
  }
}

function openPresets() {
  openModal("⭐ Field Presets");
  const body = $("#modalBody");
  if (!state.meta || !state.meta.presets) { body.textContent = "No presets available."; return; }

  const list = el("div", "preset-list");
  Object.entries(state.meta.presets).forEach(([name, fields]) => {
    const row = el("div", "preset-item");
    const info = el("div");
    info.appendChild(el("strong", null, name));
    info.appendChild(el("div", "history-meta", `${fields.length} fields`));
    row.appendChild(info);

    const apply = el("button", "btn btn-primary btn-sm", "Apply");
    apply.addEventListener("click", () => {
      state.selectedFields = new Set(fields);
      renderFields();
      closeModal();
      toast(`Applied preset: ${name}`, "success");
    });
    row.appendChild(apply);
    list.appendChild(row);
  });
  body.appendChild(list);
}

function openSettings() {
  openModal("⚙️ Settings");
  const body = $("#modalBody");
  const wrap = el("div", "preset-list");

  const themeRow = el("div", "preset-item");
  themeRow.appendChild(el("strong", null, "Appearance"));
  const themeBtn = el("button", "btn btn-ghost btn-sm", "Toggle Light / Dark");
  themeBtn.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });
  themeRow.appendChild(themeBtn);
  wrap.appendChild(themeRow);

  const baseRow = el("div", "preset-item");
  baseRow.appendChild(el("strong", null, "Output folder"));
  baseRow.appendChild(el("span", "history-meta", "ECRM/output"));
  wrap.appendChild(baseRow);

  const workerRow = el("div", "preset-item");
  const workerInfo = el("div");
  workerInfo.appendChild(el("strong", null, "Parallel Workers"));
  workerInfo.appendChild(el("div", "history-meta", "Network/API concurrency per extraction"));
  workerRow.appendChild(workerInfo);
  const workerSelect = document.createElement("select");
  workerSelect.className = "field-select";
  for (let i = 1; i <= 12; i++) {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = `${i} worker${i === 1 ? "" : "s"}`;
    workerSelect.appendChild(option);
  }
  const safeWorkers = Math.max(1, Math.min(Number(state.maxWorkers) || 5, 12));
  workerSelect.value = String(safeWorkers);
  state.maxWorkers = safeWorkers;
  workerSelect.addEventListener("change", () => {
    state.maxWorkers = Math.max(1, Math.min(Number(workerSelect.value) || 5, 12));
    localStorage.setItem("ecrm_max_workers", String(state.maxWorkers));
    toast(`Parallel workers set to ${state.maxWorkers}`, "success");
  });
  workerRow.appendChild(workerSelect);
  wrap.appendChild(workerRow);

  const workerNote = el("div", "history-meta", "Recommended: 4–6. Increase gradually if ECRM/network can handle the extra concurrent requests.");
  workerNote.style.padding = "0 16px 12px";
  wrap.appendChild(workerNote);

  body.appendChild(wrap);
}



/* ----------------------------- credentials dialog ----------------------------- */
function openCredentials() {
  const m = $("#credentialsModal");
  if (!m) return;

  const user = $("#username")?.value || "";
  const pass = $("#password")?.value || "";

  $("#credentialsUsername").value = user;
  $("#credentialsUsername").readOnly = true;
  $("#credentialsUsername").setAttribute("readonly", "readonly");

  $("#credentialsPassword").value = pass;
  $("#credentialsPassword").readOnly = false;
  $("#credentialsPassword").removeAttribute("readonly");

  $("#credentialsDebug").checked = !!$("#debugMode")?.checked;
  m.classList.remove("hidden");
  setTimeout(() => {
    if (pass) {
      $("#credentialsPassword")?.blur();
    } else {
      $("#credentialsPassword")?.focus();
    }
  }, 50);
}

function closeCredentials() {
  $("#credentialsModal")?.classList.add("hidden");
}

async function saveCredentialsFromDialog() {
  const password = String($("#credentialsPassword")?.value || "");

  if (!password) {
    toast("Enter the ECRM password once.", "warning");
    $("#credentialsPassword")?.focus();
    return;
  }

  try {
    await loadCredentials();

    // loadCredentials may return the saved password; restore the newly typed
    // password because the user may be changing it.
    const mainPassword = $("#password");
    if (mainPassword) {
      mainPassword.value = password;
      mainPassword.readOnly = false;
      mainPassword.removeAttribute("readonly");
    }

    const mainUsername = $("#username");
    if (mainUsername) {
      mainUsername.readOnly = true;
      mainUsername.setAttribute("readonly", "readonly");
    }

    // Persist immediately through the backend by asking it to remember the
    // password for the current Windows user.
    const res = await fetch("/api/ecrm/remember-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("#username")?.value || "",
        password: password
      })
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(body || `HTTP ${res.status}`);
    }

    closeCredentials();
    toast("Password saved securely. You won't need to enter it again.", "success");
  } catch (err) {
    toast(`Could not save password: ${err.message || err}`, "error");
  }
}

function initCredentialsDialog() {
  $("#credentialsBtn")?.addEventListener("click", openCredentials);
  $("#credentialsClose")?.addEventListener("click", closeCredentials);
  $("#credentialsCancel")?.addEventListener("click", closeCredentials);
  $("#credentialsSave")?.addEventListener("click", saveCredentialsFromDialog);
  $("#togglePassword")?.addEventListener("click", () => {
    const p = $("#credentialsPassword");
    if (!p) return;
    const show = p.type === "password";
    p.type = show ? "text" : "password";
    $("#togglePassword").textContent = show ? "Hide" : "Show";
  });
  $("#credentialsModal")?.addEventListener("click", e => {
    if (e.target.id === "credentialsModal") closeCredentials();
  });
}

/* ----------------------------- professional dashboard ----------------------------- */
async function loadDashboardStats() {
  try {
    const d = await api("/api/dashboard");
    const rows = (d.recent || []).filter(r => String(r.tool_id || "") === "ecrm" || String(r.tool || "").toLowerCase().includes("ecrm"));
    const total = rows.length;
    const done = rows.filter(r => r.status === "done").length;
    const failed = rows.filter(r => r.status === "error").length;
    const files = rows.filter(r => r.output_file).length;
    const records = rows.reduce((n,r)=>n + Number(r.records || 0),0);
    const durations = rows.map(r => {
      if(!r.started_at || !r.finished_at) return 0;
      return Math.max(0,(new Date(r.finished_at)-new Date(r.started_at))/1000);
    }).filter(Boolean);
    const avg = durations.length ? durations.reduce((a,b)=>a+b,0)/durations.length : 0;
    $("#statJobs").textContent = total;
    $("#statFiles").textContent = files;
    $("#statSuccess").textContent = done;
    $("#statFailed").textContent = failed;
    $("#statRecords").textContent = records.toLocaleString();
    $("#statAvg").textContent = avg ? (avg < 60 ? `${avg.toFixed(1)}s` : `${Math.floor(avg/60)}m ${Math.round(avg%60)}s`) : "—";

    const recent = $("#recentJobs");
    if(!recent) return;
    recent.innerHTML = "";
    if(!rows.length){ recent.innerHTML = '<div class="empty-row">No ECRM jobs recorded yet</div>'; return; }
    rows.slice(0,5).forEach((f)=>{
      const row=el("div","recent-row");
      row.innerHTML=`<span>${String(f.started_at||"").replace("T"," ").slice(0,16)}</span><span>${String(f.mode||"—")}</span><span>${Number(f.records||0).toLocaleString()}</span><span class="${f.status==='done'?'ok':f.status==='error'?'bad':'warn'}">● ${String(f.status||"running").toUpperCase()}</span><span>${f.output_file?'📄':'—'}</span>`;
      recent.appendChild(row);
    });
  } catch (_) {}
}

function initProfessionalDashboard() {
  const username = ($("#username")?.value || "").trim() || "ECRM User";
  $("#greetingUser").textContent = username;
  $("#topUserName").textContent = username;
  $("#topAvatar").textContent = username.split(/[.\s_-]+/).filter(Boolean).slice(0,2).map(x=>x[0]).join("").toUpperCase() || "MA";

  $("#settingsTopBtn")?.addEventListener("click", openSettings);
  $("#sideCredentialsBtn")?.addEventListener("click", openCredentials);

  document.querySelectorAll(".preset-tile").forEach(btn => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.preset;
      if (!state.meta?.presets) return;
      const match = Object.entries(state.meta.presets).find(([k]) => k.toLowerCase() === name.toLowerCase());
      if (match) {
        state.selectedFields = new Set(match[1]);
        renderFields();
        toast(`Applied preset: ${match[0]}`, "success");
      } else {
        openPresets();
      }
    });
  });

  document.querySelectorAll(".suggestions button").forEach(btn => {
    btn.addEventListener("click", () => {
      $("#copilotInput").value = btn.textContent;
      $("#copilotInput").focus();
    });
  });

  $("#copilotSend")?.addEventListener("click", () => {
    const v = $("#copilotInput").value.trim();
    if (!v) return;
    toast(`AI Copilot request queued: ${v}`, "info");
  });

  const globalSearch = $("#globalSearch");
  globalSearch?.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      $("#fieldSearch").value = globalSearch.value;
      renderFields();
      $("#fieldSearch").scrollIntoView({behavior:"smooth", block:"center"});
    }
  });

  loadDashboardStats();
  setInterval(() => {
    const d = new Date();
    $("#clock").textContent = d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  }, 1000);
}

/* ----------------------------- wiring ----------------------------- */
function initControls() {
  $("#startBtn").addEventListener("click", startExtraction);
  $("#cancelBtn").addEventListener("click", cancelExtraction);

  $("#selectAllBtn").addEventListener("click", () => {
    (state.meta?.fields || []).forEach((f) => state.selectedFields.add(f));
    renderFields();
  });

  $("#clearFieldsBtn").addEventListener("click", () => {
    state.selectedFields.clear();
    renderFields();
  });

  $("#clearAllBtn")?.addEventListener("click", () => {
    state.selectedFields.clear();
    renderFields();
    $("#directValues").value = "";
    updateDirectCount();
    $("#filePath").value = "";
    delete $("#filePath").dataset.backendPath;
    toast("Selections cleared", "info");
  });

  $("#fieldSearch").addEventListener("input", renderFields);
  $("#directValues").addEventListener("input", updateDirectCount);
  $("#clearDirect").addEventListener("click", () => {
    $("#directValues").value = "";
    updateDirectCount();
  });

  $("#hideLogBtn").addEventListener("click", () => $("#logPanel").classList.add("hidden"));
  $("#clearLogBtn").addEventListener("click", () => { $("#logOutput").innerHTML = ""; });
  $("#downloadBtn").addEventListener("click", () => {
    if (state.jobId) window.location.href = `/api/ecrm/jobs/${state.jobId}/download`;
  });
  $("#historyBtn").addEventListener("click", openHistory);

  $("#username").setAttribute("autocomplete", "off");
  $("#password").setAttribute("autocomplete", "new-password");

  // Username is server-authoritative; block any browser/script edits.
  $("#username").readOnly = true;
  $("#username").setAttribute("readonly", "readonly");
  $("#username").setAttribute("aria-readonly", "true");

  // Warn if the user navigates away mid-run.
  window.addEventListener("beforeunload", (e) => {
    if ($("#cancelBtn").disabled === false) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initCredentialsDialog();
  initTheme();
  initNav();
  initModeTabs();
  initFileInput();
  initModal();
  initControls();
  updateDirectPlaceholder();
  loadCredentials().then(() => {
    // Refresh dashboard labels after Windows username detection.
    initProfessionalDashboard();
  }).catch(() => {
    initProfessionalDashboard();
  });
  loadMeta();
});


// Credential button safety net: delegated handler works regardless of initializer order.
document.addEventListener("click", (event) => {
  const btn = event.target.closest && event.target.closest("#credentialsBtn");
  if (btn) openCredentials();
});

// Enterprise V10 UI helpers
(function(){
  const sidebar=document.getElementById('sidebar');
  document.getElementById('sidebarToggle')?.addEventListener('click',()=>sidebar?.classList.toggle('collapsed'));
  document.getElementById('quickNewExtraction')?.addEventListener('click',()=>document.querySelector('.extraction-card')?.scrollIntoView({behavior:'smooth',block:'start'}));
  document.getElementById('quickUpload')?.addEventListener('click',()=>document.getElementById('fileInput')?.click());
  document.getElementById('quickPreset')?.addEventListener('click',()=>openPresets());
  document.getElementById('quickHistory')?.addEventListener('click',()=>openHistory());
  document.querySelector('.apply-ai')?.addEventListener('click',()=>{
    const wanted=['Order','Old Circuit ID','New Circuit ID','Old ORD','New ORD','Infra Status','ESPT Status'];
    if(typeof state !== 'undefined' && state.meta?.fields){ wanted.forEach(x=>{ const f=state.meta.fields.find(v=>v.toLowerCase()===x.toLowerCase()); if(f) state.selectedFields.add(f); }); renderFields(); toast('Migration fields applied','success'); }
  });
  function updateDate(){const d=new Date(); const dl=document.getElementById('dateLabel'); if(dl) dl.textContent=d.toLocaleDateString(undefined,{weekday:'long',day:'2-digit',month:'long',year:'numeric'});}
  updateDate();
})();

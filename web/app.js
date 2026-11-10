// AgriAgent Field Service web page. Plain JavaScript, no build step.
// Server data is always written with textContent (never innerHTML): file names come from
// users, so treating them as HTML would allow script injection.
"use strict";

const $ = (id) => document.getElementById(id);
const PAGE_SIZE = 10;

const state = {
  health: null,
  file: null,        // the File to upload (from the picker or the sample button)
  page: 0,
  cropFilter: "",
  pendingDelete: null, // run id whose Delete button is waiting for a second click
};

// ---------- helpers ----------

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (res.status === 204) return null;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = body && body.error ? body.error.message : `HTTP ${res.status}`;
    const err = new Error(message);
    err.status = res.status;
    err.code = body && body.error ? body.error.code : "http_error";
    throw err;
  }
  return body;
}

const pct = (n) => `${Number(n).toFixed(2)}%`;
const ms = (n) => (n >= 1000 ? `${(n / 1000).toFixed(2)} s` : `${Number(n).toFixed(1)} ms`);
const when = (iso) => new Date(iso).toLocaleString();

function cell(row, text, cls) {
  const td = document.createElement("td");
  td.textContent = text;
  if (cls) td.className = cls;
  row.appendChild(td);
  return td;
}

function badgeClass(action) {
  if (action === "ACCEPT") return "badge accept";
  if (action && action.startsWith("SUPPRESS")) return "badge suppress";
  return "badge other";
}

function showError(message) {
  const box = $("form-error");
  box.textContent = message;
  box.hidden = !message;
}

// ---------- tabs (hash routing, so #history opens History directly) ----------

function showView() {
  const name = (location.hash || "#analyze").slice(1);
  const view = ["analyze", "history", "stats"].includes(name) ? name : "analyze";
  for (const v of ["analyze", "history", "stats"]) {
    $(`view-${v}`).hidden = v !== view;
  }
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === view);
    t.setAttribute("aria-selected", String(t.dataset.tab === view));
  });
  if (view === "history") loadHistory();
  if (view === "stats") loadStats();
}

// ---------- health ----------

async function loadHealth() {
  const pill = $("health");
  try {
    const h = await api("/api/health");
    state.health = h;
    pill.textContent = h.status === "ok" ? "Service online" : `Service ${h.status}`;
    pill.className = `pill ${h.status === "ok" ? "ok" : "bad"}`;
    $("version").textContent = `v${h.version}`;

    for (const select of [$("crop-select"), $("history-crop-filter")]) {
      for (const crop of h.crops) {
        const opt = document.createElement("option");
        opt.value = crop;
        opt.textContent = crop.replace(/\b\w/g, (c) => c.toUpperCase());
        select.appendChild(opt);
      }
    }
    const real = $("mode-select").querySelector('option[value="real"]');
    real.disabled = !h.modes.real;
    if (!h.modes.real) real.textContent += " (off on this server)";
  } catch (err) {
    pill.textContent = "Service offline";
    pill.className = "pill bad";
  }
}

// ---------- analyze ----------

function setFile(file) {
  state.file = file;
  $("file-name").textContent = file ? `${file.name} (${(file.size / 1024).toFixed(0)} KiB)` : "No file chosen";
  const preview = $("preview");
  if (file && /^image\/(png|jpeg)$/.test(file.type)) {
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  } else {
    preview.hidden = true;
  }
  showError("");
}

async function useSample() {
  const res = await fetch("/api/sample-image");
  const blob = await res.blob();
  $("image-input").value = "";
  setFile(new File([blob], "sample-field.png", { type: "image/png" }));
}

function validateForm() {
  if (!state.file) return "Choose a field photo or use the sample image first.";
  const raw = $("confidence-input").value.trim();
  if (raw === "") return null; // server default (0.70)
  const n = Number(raw);
  if (!Number.isFinite(n)) return "Min confidence must be a number.";
  const [lo, hi] = state.health ? state.health.limits.min_confidence : [0.7, 1.0];
  if (n < lo || n > hi) return `Min confidence must be between ${lo.toFixed(2)} and ${hi.toFixed(2)}.`;
  return null;
}

async function submitAnalysis(event) {
  event.preventDefault();
  const problem = validateForm();
  if (problem) {
    showError(problem);
    return;
  }
  showError("");
  const form = new FormData();
  form.append("image", state.file, state.file.name);
  form.append("crop", $("crop-select").value);
  form.append("mode", $("mode-select").value);
  const conf = $("confidence-input").value.trim();
  if (conf !== "") form.append("min_confidence", conf);

  $("analyze-button").disabled = true;
  $("analyzing").hidden = false;
  $("result").hidden = true;
  try {
    const run = await api("/api/analyze", { method: "POST", body: form });
    renderResult(run);
  } catch (err) {
    showError(err.message);
  } finally {
    $("analyze-button").disabled = false;
    $("analyzing").hidden = true;
  }
}

function renderResult(run) {
  $("result-run-id").textContent = `#${run.id}`;
  const badge = $("result-safety-action");
  badge.textContent = run.safety_action;
  badge.className = badgeClass(run.safety_action);
  $("result-status").textContent = run.status;
  $("kpi-weeds").textContent = String(run.weed_count);
  $("kpi-withheld").textContent = String(run.withheld_count);
  $("kpi-infestation").textContent = pct(run.infestation_pct);
  $("kpi-savings").textContent = pct(run.savings_pct);
  $("kpi-duration").textContent = ms(run.duration_ms);
  $("result-overlay").src = run.links.overlay;
  $("download-geojson").href = run.links.geojson;
  $("result").hidden = false;
}

// ---------- history ----------

async function loadHistory() {
  const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.page * PAGE_SIZE });
  if (state.cropFilter) params.set("crop", state.cropFilter);
  let data;
  try {
    data = await api(`/api/runs?${params}`);
  } catch (err) {
    $("history-total").textContent = `(error: ${err.message})`;
    return;
  }
  // A delete can empty the last page; step back one page and reload.
  if (data.items.length === 0 && state.page > 0) {
    state.page -= 1;
    return loadHistory();
  }
  const body = $("runs-body");
  body.replaceChildren();
  for (const run of data.items) body.appendChild(historyRow(run));

  $("history-total").textContent = `(${data.total} run${data.total === 1 ? "" : "s"})`;
  $("history-empty").hidden = data.total !== 0;
  $("runs-table").hidden = data.total === 0;
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  $("page-label").textContent = `Page ${state.page + 1} of ${pages}`;
  $("page-prev").disabled = state.page === 0;
  $("page-next").disabled = state.page + 1 >= pages;
}

function historyRow(run) {
  const tr = document.createElement("tr");
  tr.setAttribute("data-testid", "run-row");
  tr.dataset.runId = String(run.id);
  cell(tr, `#${run.id}`, "num");
  cell(tr, when(run.created_at));
  cell(tr, run.filename);
  cell(tr, run.crop);
  cell(tr, run.mode);
  const gate = cell(tr, "");
  const badge = document.createElement("span");
  badge.className = badgeClass(run.safety_action);
  badge.textContent = run.safety_action;
  gate.appendChild(badge);
  cell(tr, String(run.weed_count), "num");
  cell(tr, pct(run.infestation_pct), "num");
  cell(tr, pct(run.savings_pct), "num");

  const actions = cell(tr, "");
  const view = document.createElement("button");
  view.className = "btn small ghost";
  view.textContent = "View";
  view.setAttribute("data-testid", "view-run");
  view.addEventListener("click", () => showDetail(run.id));

  const del = document.createElement("button");
  del.className = "btn small danger";
  del.textContent = "Delete";
  del.setAttribute("data-testid", "delete-run");
  del.addEventListener("click", () => deleteRun(run.id, del));
  actions.append(view, " ", del);
  return tr;
}

async function deleteRun(id, button) {
  // Two clicks: the first arms the button, the second deletes. No browser confirm() dialog.
  if (state.pendingDelete !== id) {
    state.pendingDelete = id;
    button.textContent = "Confirm delete";
    return;
  }
  state.pendingDelete = null;
  try {
    await api(`/api/runs/${id}`, { method: "DELETE" });
    if ($("detail-run-id").textContent === `#${id}`) $("run-detail").hidden = true;
  } catch (err) {
    if (err.status !== 404) alertInline(err.message);
  }
  loadHistory();
}

function alertInline(message) {
  $("history-total").textContent = `(error: ${message})`;
}

async function showDetail(id) {
  let run;
  try {
    run = await api(`/api/runs/${id}`);
  } catch (err) {
    alertInline(err.message);
    return;
  }
  $("detail-run-id").textContent = `#${run.id}`;
  const dl = $("detail-fields");
  dl.replaceChildren();
  const rows = [
    ["When", when(run.created_at)],
    ["File", run.filename],
    ["Image", `${run.width} × ${run.height}`],
    ["Crop", run.crop],
    ["Mode", run.mode],
    ["Min confidence", Number(run.min_confidence).toFixed(2)],
    ["Safety gate", run.safety_action],
    ["Status", run.status],
    ["Weeds approved", String(run.weed_count)],
    ["Withheld", String(run.withheld_count)],
    ["Infestation", pct(run.infestation_pct)],
    ["Chemical saved", pct(run.savings_pct)],
    ["Time", ms(run.duration_ms)],
    ["SHA-256", run.image_sha256],
  ];
  for (const [k, v] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.textContent = v;
    dl.append(dt, dd);
  }
  $("detail-overlay").src = run.links.overlay;
  $("run-detail").hidden = false;
}

// ---------- stats ----------

async function loadStats() {
  let s;
  try {
    s = await api("/api/stats");
  } catch (err) {
    $("stat-total-runs").textContent = "—";
    return;
  }
  $("stat-total-runs").textContent = String(s.total_runs);
  $("stat-total-weeds").textContent = String(s.total_weeds);
  $("stat-avg-infestation").textContent = pct(s.avg_infestation_pct);
  $("stat-avg-savings").textContent = pct(s.avg_savings_pct);
  $("stat-suppressed").textContent = String(s.suppressed_runs);
  const body = $("stats-crop-body");
  body.replaceChildren();
  for (const row of s.by_crop) {
    const tr = document.createElement("tr");
    tr.setAttribute("data-testid", "stats-crop-row");
    cell(tr, row.crop);
    cell(tr, String(row.runs), "num");
    cell(tr, String(row.weeds), "num");
    cell(tr, pct(row.avg_infestation_pct), "num");
    body.appendChild(tr);
  }
}

// ---------- wiring ----------

$("image-input").addEventListener("change", (e) => setFile(e.target.files[0] || null));
$("use-sample").addEventListener("click", useSample);
$("analyze-form").addEventListener("submit", submitAnalysis);
$("history-crop-filter").addEventListener("change", (e) => {
  state.cropFilter = e.target.value;
  state.page = 0;
  loadHistory();
});
$("page-prev").addEventListener("click", () => { state.page = Math.max(0, state.page - 1); loadHistory(); });
$("page-next").addEventListener("click", () => { state.page += 1; loadHistory(); });
$("detail-close").addEventListener("click", () => { $("run-detail").hidden = true; });
window.addEventListener("hashchange", showView);

loadHealth().then(showView);

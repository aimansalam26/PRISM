"use strict";

const $ = (id) => document.getElementById(id);
const state = { run: null, notes: {}, selected: null, filter: "all", scenario: "all", search: "", mode: "prism", view: "workspace", busy: false, dirty: false, label: "Development corpus" };
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const modes = ["prism", "local", "untyped"];
const modeNames = { prism: "PRISM", local: "Local pairwise", untyped: "Untyped traversal" };
const statusNames = { Yes: "Needs review", No: "Not selected", Defer: "Deferred" };
const countryNames = { NL: "Netherlands", BE: "Belgium", FR: "France", UK: "United Kingdom", GB: "United Kingdom", US: "United States", CA: "Canada", MX: "Mexico", IE: "Ireland", DE: "Germany", ES: "Spain", IT: "Italy", AT: "Austria", SG: "Singapore", MY: "Malaysia", TH: "Thailand" };
const reasons = { supported_dependency: "A dependency on the changed property survives the applicability checks.", empty_scope_or_inactive_interval: "The path has no overlapping applicability or valid time interval.", independent_replacement_of_changed_value: "This population uses an independent replacement for the changed value.", unrelated_changed_field: "This relationship is only topical or concerns a different property.", structural_reachability: "The candidate is structurally reachable; this method ignores field, relation and scope semantics.", inactive_interval: "The known time intervals do not overlap.", upstream_uncertainty: "An earlier relationship on this path remains unresolved." };
const actions = { continue: "Continue propagation", review_stop: "Review, then stop this path", exclude: "Exclude this path", defer: "Defer for clarification" };
const downloads = [
  ["xlsx", "XLSX", "Excel review report", "Candidates, scopes, paths, decisions and working notes."],
  ["session", "JSON", "Save review session", "Keep the corpus and notes together. Upload it to resume."],
  ["csv", "CSV", "Candidate comparison", "A flat table of all three predictions and stakeholder notes."],
  ["markdown", "MD", "Readable evidence packet", "Source changes, candidate decisions and supporting paths."],
  ["results", "JSON", "Complete engine results", "Full traces, exclusions and computational reference checks."],
  ["corpus", "JSON", "Active source corpus", "The exact structured input used for this run."],
];

function badge(status) { return `<span class="badge ${esc(status.toLowerCase())}" title="Engine status: ${esc(status)}">${esc(statusNames[status] || status)}</span>`; }
function human(value) { return String(value ?? "").replaceAll("_", " "); }
function values(items, country = false) { return items.map((x) => x === "*" ? "Unrestricted" : country ? (countryNames[x] || x) : human(x)).join(", "); }
function dateLabel(value) { return value === "9999-12-31" ? "No upper bound specified" : value === "0001-01-01" ? "Start not specified" : value; }
function notify(message, error = false) { $("message").textContent = message; $("message").className = "message" + (error ? " error" : ""); $("message").hidden = false; $("message").setAttribute("role", error ? "alert" : "status"); }
function dirty(value) { state.dirty = value; $("unsaved-indicator").hidden = !value; }

function setBusy(value, text = "Analysing the corpus…") {
  state.busy = value; $("loading").hidden = !value; $("loading-text").textContent = text;
  document.querySelectorAll("button, input, select, textarea").forEach((e) => { e.disabled = value; });
  if (!value) {
    ["export-main", "download-session", "rerun", "upload-gold"].forEach((id) => { $(id).disabled = !state.run; });
    document.querySelectorAll("[data-export]").forEach((e) => { e.disabled = !state.run; });
  }
}

async function api(path, data) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-PRISM-Client": "local-ui" }, body: JSON.stringify(data) });
  if (!response.ok) {
    let message = "The local request could not be completed.";
    try { message = (await response.json()).error || message; } catch (_) { /* no JSON response */ }
    throw new Error(message);
  }
  return response;
}

function allCandidates() {
  if (!state.run) return [];
  return state.run.suite.scenarios.flatMap((scenario) => {
    const result = state.run.payload.results[scenario.id];
    return result.prism.items.map((item) => ({ item, scenario, node: scenario.nodes.find((n) => n.id === item.ko_id), result }));
  });
}

function filteredCandidates() {
  return allCandidates().filter(({ item, scenario, node }) =>
    (state.scenario === "all" || scenario.id === state.scenario) &&
    (state.filter === "all" || state.filter === "queue" && ["Yes", "Defer"].includes(item.status) || item.status === state.filter) &&
    `${item.ko_id} ${item.title} ${node.text} ${scenario.title}`.toLowerCase().includes(state.search.toLowerCase()));
}

async function runData(data, label, depth = 3) {
  setBusy(true); $("message").hidden = true;
  try {
    const result = await (await api("/api/run", { data, max_hops: depth })).json();
    state.run = result; state.notes = result.notes || {}; state.label = label; state.filter = "all"; state.scenario = "all"; state.search = ""; state.mode = "prism";
    const rows = allCandidates(); state.selected = (rows.find((r) => r.item.status === "Yes") || rows[0])?.item.ko_id || null;
    $("search").value = ""; $("max-hops").value = String(result.payload.max_hops); dirty(false);
    renderAll();
    if ($("upload-dialog").open) $("upload-dialog").close();
    notify(`${result.suite.scenarios.length} change events analysed. Computational reference checks agree. Human-label accuracy is a separate evaluation.`);
  } catch (error) {
    if ($("upload-dialog").open) $("upload-dialog").close();
    notify(error.message + (state.run ? " Your previous workspace is unchanged." : ""), true);
  } finally { setBusy(false); }
}

async function loadSample() {
  if (!confirmReplace()) return;
  setBusy(true, "Loading the development corpus…");
  try {
    const response = await fetch("/api/sample");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    await runData(data, "Development corpus", 3);
  } catch (error) { notify(error.message, true); setBusy(false); }
}

function confirmReplace() {
  return !state.dirty || window.confirm("You have notes that are not saved in a review-session download. Loading another corpus will replace this workspace. Continue?");
}

async function uploadCorpus(file) {
  if (!file) return;
  if (!confirmReplace()) { $("corpus-file").value = ""; return; }
  try {
    if (file.size > 5 * 1024 * 1024) throw new Error("Choose a JSON file smaller than 5 MB.");
    if (!file.name.toLowerCase().endsWith(".json")) throw new Error("Choose a .json corpus or review session. PDFs and Word files need a separate curation step.");
    const data = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
    await runData(data, file.name, Number($("max-hops").value));
  } catch (error) {
    if ($("upload-dialog").open) $("upload-dialog").close();
    notify(error instanceof SyntaxError ? "This file is not valid JSON. Check commas, brackets and quoted field names. Your previous workspace is unchanged." : error.message, true);
  } finally { $("corpus-file").value = ""; }
}

function renderAll() {
  const rows = allCandidates(), count = (s) => rows.filter((r) => r.item.status === s).length;
  $("corpus-name").textContent = state.label;
  $("corpus-meta").textContent = `${state.run.suite.scenarios.length} change events · Engine ${state.run.payload.prototype_version} · development predictions`;
  $("depth-badge").textContent = `Up to ${state.run.payload.max_hops} impact steps`;
  $("count-all").textContent = rows.length; $("count-queue").textContent = count("Yes") + count("Defer");
  $("count-defer").textContent = count("Defer"); $("count-no").textContent = count("No");
  $("event-count").textContent = `Across ${state.run.suite.scenarios.length} change events`;
  $("queue-breakdown").textContent = `${count("Yes")} supported + ${count("Defer")} deferred`;
  $("scenario-filter").innerHTML = '<option value="all">All change events</option>' + state.run.suite.scenarios.map((s) => `<option value="${esc(s.id)}">${esc(s.title)}</option>`).join("");
  $("scenario-filter").value = state.scenario;
  renderCandidates(); renderComparison(); renderDownloads(); renderProvenance(); renderEvaluation();
}

function renderCandidates() {
  const rows = filteredCandidates();
  if (!rows.some((r) => r.item.ko_id === state.selected)) state.selected = rows[0]?.item.ko_id || null;
  $("visible-count").textContent = rows.length; $("table-total").textContent = `${rows.length} of ${allCandidates().length} candidates`;
  document.querySelectorAll("[data-filter]").forEach((button) => { button.classList.toggle("selected", button.dataset.filter === state.filter); button.setAttribute("aria-pressed", String(button.dataset.filter === state.filter)); });
  $("candidate-rows").innerHTML = rows.map(({ item, scenario }) => `<tr class="${item.ko_id === state.selected ? "active-row" : ""}"><td><button class="candidate-link" data-candidate="${esc(item.ko_id)}" aria-pressed="${item.ko_id === state.selected}"><strong>${esc(item.title)}</strong><small>${esc(item.ko_id)} · ${esc(scenario.title.replace(/^Scenario \d+: /, ""))}</small></button></td><td>${badge(item.status)}</td><td>${esc(item.directness === "none" ? "—" : human(item.directness))}</td></tr>`).join("");
  $("no-candidates").hidden = rows.length !== 0;
  renderEvidence();
}

function scopeMarkup(scope, number) {
  return `<div class="scope-card"><h4>Applicability cell ${number} · keep this combination together</h4><dl class="scope-grid"><div><dt>Employee role</dt><dd>${esc(values(scope.roles))}</dd></div><div><dt>Jurisdiction</dt><dd>${esc(values(scope.jurisdictions, true))}</dd></div><div><dt>Organisation</dt><dd>${esc(values(scope.organisations))}</dd></div><div><dt>Effective period</dt><dd>${esc(dateLabel(scope.start))} → ${esc(dateLabel(scope.end))}</dd></div></dl></div>`;
}

function traceMarkup(path, scenario, index, excluded = false) {
  const nodes = path.node_path.map((id) => scenario.nodes.find((n) => n.id === id));
  const edges = path.edge_path.map((id) => scenario.relationships.find((e) => e.id === id));
  const scopeText = path.scope ? `${values(path.scope.roles)} · ${values(path.scope.jurisdictions, true)} · ${values(path.scope.organisations)} · ${dateLabel(path.scope.start)} → ${dateLabel(path.scope.end)}` : "No definite affected scope asserted on this path.";
  return `<details class="trace ${excluded ? "excluded" : ""}" ${!excluded && index === 0 ? "open" : ""}><summary>${esc(excluded ? "Excluded path" : "Supporting path " + (index + 1))} · ${path.edge_path.length} step${path.edge_path.length === 1 ? "" : "s"} · ${esc(actions[path.action] || path.action)}</summary><div class="trace-content"><div>${nodes.map((n, i) => `<div class="path-node"><b>${i}</b><div>${esc(n?.title || path.node_path[i])}<small>${esc(path.node_path[i])}${i ? " · " + esc(edges[i - 1]?.type || "relationship") : " · changed source"}</small></div></div>`).join("")}</div><p class="trace-reason">${esc(reasons[path.reason] || human(path.reason))}</p>${excluded ? "" : `<p class="trace-cell">${esc(scopeText)}</p>`}<details><summary>Source evidence for each step</summary>${edges.map((e) => `<div class="trace-evidence"><strong>${esc(e?.id)}</strong> · ${esc(e?.field || "topic")}<br>${esc(e?.evidence)}<br><small>Source: ${esc(e?.source)}</small>${e?.uncertainty_reason ? `<br><small>Curated uncertainty: ${esc(e.uncertainty_reason)}</small>` : ""}${e?.mapping ? `<br><small>Explicit adoption mapping: ${esc(JSON.stringify(e.mapping))}</small>` : ""}</div>`).join("")}</details></div></details>`;
}

function renderEvidence() {
  const row = allCandidates().find((r) => r.item.ko_id === state.selected);
  if (!row) { $("evidence-panel").innerHTML = '<div class="empty">Select a candidate from the list to view its evidence.</div>'; $("change-panel").hidden = true; return; }
  const { scenario, node, result } = row;
  const item = result[state.mode].items.find((i) => i.ko_id === state.selected);
  const excluded = result[state.mode].decisions.filter((d) => d.node_path.at(-1) === item.ko_id && d.action === "exclude");
  const note = state.notes[item.ko_id] || { state: "pending", text: "" };
  const uncertainty = item.has_uncertainty ? '<p class="scope-unknown">This candidate also has unresolved evidence. Uncertainty was recorded by the curator; it was not inferred automatically from the text.</p>' : "";
  const scope = item.affected_scopes.length ? item.affected_scopes.map((s, i) => scopeMarkup(s, i + 1)).join("") : `<p class="scope-unknown">${state.mode === "untyped" ? "Untyped traversal does not predict an affected scope." : item.status === "Defer" ? "Affected scope is unresolved. Human clarification is needed before asserting a population." : "No supported affected scope was found within this model and traversal boundary."}</p>`;
  $("evidence-panel").innerHTML = `<div class="evidence-head"><div class="evidence-topline"><p class="eyebrow">EVIDENCE INSPECTOR</p>${badge(item.status)}</div><h3>${esc(item.title)}</h3><span class="subtle-text">${esc(item.ko_id)} · ${esc(scenario.title)} · ${esc(item.directness === "none" ? "no supported impact" : item.directness + " impact")}</span></div><div class="evidence-mode"><label for="evidence-method">Inspect method</label><select id="evidence-method">${modes.map((m) => `<option value="${m}" ${m === state.mode ? "selected" : ""}>${modeNames[m]}</option>`).join("")}</select></div><div class="evidence-content"><p class="detail-label">POLICY PROVISION</p><p class="policy-copy">${esc(node.text)}</p><p class="detail-label">AFFECTED APPLICABILITY</p>${scope}${uncertainty}<p class="fine">Intervals include the start and exclude the end. Each cell is a separate combination.</p><p class="detail-label">DEPENDENCY EVIDENCE</p>${item.paths.map((p, i) => traceMarkup(p, scenario, i)).join("")}${excluded.map((p, i) => traceMarkup(p, scenario, i, true)).join("")}${!item.paths.length && !excluded.length ? '<p class="scope-unknown">No supported path reached this candidate within the configured boundary. Inspect the source relationships before interpreting this as evidence of no real-world impact.</p>' : ""}<p class="fine">Source: ${esc(node.source)}<br>Changed properties: ${esc(scenario.event.changed_fields.map(human).join(", "))}</p></div><div class="review-note"><div class="note-heading"><h4>Stakeholder observations</h4><button class="text-button" data-export="session">Save session ↓</button></div><label for="note-status">Review progress</label><select id="note-status"><option value="pending">Not reviewed</option><option value="reviewed">Evidence reviewed</option><option value="question">Question this recommendation</option><option value="clarification">Needs clarification</option></select><label for="note-text">Note or question</label><textarea id="note-text" maxlength="5000" placeholder="Record what should be checked, and why…">${esc(note.text)}</textarea><p class="fine">Working notes only. Download a review session to keep them. They do not change predictions, gold labels or policy state.</p></div>`;
  $("note-status").value = note.state;
  $("evidence-method").addEventListener("change", (e) => { state.mode = e.target.value; renderEvidence(); });
  const saveNote = () => { state.notes[item.ko_id] = { state: $("note-status").value, text: $("note-text").value }; dirty(true); };
  $("note-status").addEventListener("change", saveNote); $("note-text").addEventListener("input", saveNote);
  const event = scenario.event;
  $("change-panel").hidden = false;
  $("change-panel").innerHTML = `<details><summary>View the source change · ${esc(scenario.title)}</summary><div class="change-grid"><div><h4>Previous provision · ${esc(event.before.version_id)}</h4><p>${esc(event.before.text || "Previous wording was not supplied.")}</p></div><div class="revised"><h4>Revised provision · ${esc(event.after.version_id)}</h4><p>${esc(event.after.text)}</p></div></div><p class="fine">Analysis basis: ${esc(human(event.analysis_basis || "specified change"))}. Previous evidence is retained for inspection; this engine does not traverse a pre-change graph for withdrawn applicability.</p></details>`;
}

function renderComparison() {
  const rows = allCandidates();
  const descriptions = { prism: "Retains accumulated applicability along each typed dependency path.", local: "Uses the same curated information, with local checks that forget earlier scope restrictions.", untyped: "Follows declared connections without interpreting their type, field or scope." };
  $("comparison-cards").innerHTML = modes.map((mode) => {
    const items = rows.map((r) => r.result[mode].items.find((i) => i.ko_id === r.item.ko_id));
    const yes = items.filter((i) => i.status === "Yes").length, defer = items.filter((i) => i.status === "Defer").length, no = items.length - yes - defer;
    const denom = Math.max(items.length, 1), a = 100 * yes / denom, b = 100 * defer / denom;
    return `<article class="comparison-card ${mode === "prism" ? "featured" : ""}"><p class="eyebrow">${mode === "prism" ? "ACCUMULATED PATH STATE" : mode === "local" ? "LOCAL CHECKS" : "STRUCTURAL REACHABILITY"}</p><h3>${modeNames[mode]}</h3><p>${descriptions[mode]}</p><div class="method-total">${yes + defer}<small>candidates in the review queue</small></div><svg class="stack-bar" viewBox="0 0 100 7" preserveAspectRatio="none" aria-label="${yes} supported, ${defer} deferred, ${no} not selected"><rect width="100" height="7" fill="#dfeae5"/><rect width="${a}" height="7" fill="#9782d9"/><rect x="${a}" width="${b}" height="7" fill="#dfbd79"/></svg><div class="method-breakdown"><span>${yes} supported</span><span>${defer} deferred</span><span>${no} not selected</span></div></article>`;
  }).join("");
  const differences = rows.filter((r) => new Set(modes.map((m) => r.result[m].items.find((i) => i.ko_id === r.item.ko_id).status)).size > 1);
  $("difference-count").textContent = differences.length;
  $("comparison-rows").innerHTML = differences.length ? differences.map((r) => `<tr><td><strong>${esc(r.item.title)}</strong><br><span class="subtle-text">${esc(r.item.ko_id)}</span></td>${modes.map((m) => `<td>${badge(r.result[m].items.find((i) => i.ko_id === r.item.ko_id).status)}</td>`).join("")}<td><button class="text-button" data-inspect="${esc(r.item.ko_id)}">Inspect →</button></td></tr>`).join("") : '<tr><td colspan="5">No candidate-label differences in this run. Check scope and path evidence separately.</td></tr>';
}

function renderEvaluation() {
  const evaluation = state.run?.evaluation;
  if (!evaluation) { $("evaluation-body").innerHTML = '<p>Accuracy has not been scored. Upload a completed <code>3_Label_Matrix.xlsx</code> with two initial coder labels and reasons, adjudicated gold, source evidence and the gold freeze date. The corpus fingerprint must match this run.</p><p>Stakeholder notes are not gold labels. Scope and propagation correctness require independent assessment.</p>'; return; }
  const pct = (value) => value == null ? "Undefined" : (100 * value).toFixed(1) + "%";
  $("evaluation-body").innerHTML = `<div class="table-scroll"><table class="evaluation-table"><thead><tr><th>Method</th><th>Precision</th><th>Recall</th><th>F1</th><th>Review capture</th></tr></thead><tbody>${modes.map((m) => { const s = evaluation.metrics[m]; return `<tr><td>${modeNames[m]}</td><td>${pct(s.precision)}</td><td>${pct(s.recall)}</td><td>${pct(s.f1)}</td><td>${pct(s.review_capture_recall)}</td></tr>`; }).join("")}</tbody></table></div><p class="fine">Pooled candidate measures. Deferred gold-positive cases count as missed definite discoveries; review capture also counts Defer. Ambiguous gold is excluded from binary scoring. ${esc(evaluation.interpretation)}</p><button class="text-button" data-export="evaluation">Download full evaluation, including macro measures ↓</button>`;
}

function renderDownloads() {
  $("download-grid").innerHTML = downloads.map(([kind, ext, title, description]) => `<button class="download-card" data-export="${kind}" ${state.run ? "" : "disabled"}><span class="file-type">${ext}</span><span class="download-arrow" aria-hidden="true">↓</span><strong>${title}</strong><p>${description}</p></button>`).join("");
}

function renderProvenance() {
  if (!state.run) return;
  $("provenance").innerHTML = `<h3>Run provenance</h3><p>Created ${esc(new Date(state.run.created_at).toLocaleString())} · engine ${esc(state.run.payload.prototype_version)} · ${state.run.payload.max_hops} impact steps · ${Object.keys(state.run.payload.reference_checks).length} computational reference checks agree.</p><p>Source corpus SHA256</p><code>${esc(state.run.payload.suite_sha256)}</code><p>The reference checks the computation against separately written rules. It does not verify the policy interpretation. Withdrawals, scope contraction and deleted relationships are not supported by this engine.</p>`;
}

function changeView(view) {
  state.view = view;
  document.querySelectorAll(".view").forEach((el) => { el.hidden = el.id !== "view-" + view; });
  document.querySelectorAll("[data-view]").forEach((button) => { button.classList.toggle("active", button.dataset.view === view); button.setAttribute("aria-pressed", String(button.dataset.view === view)); });
}

async function download(kind) {
  if (!state.run || state.busy) return;
  setBusy(true, "Preparing your download…");
  try {
    const response = await api("/api/export", { run_id: state.run.run_id, notes: state.notes, kind });
    const blob = await response.blob(), url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] || "PRISM_download";
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
    if (kind === "session") dirty(false);
    notify("Download prepared for the whole active corpus. " + (kind === "session" ? "Keep the review-session file to resume your notes later." : "On-screen filters do not restrict this export."));
  } catch (error) { notify(error.message, true); } finally { setBusy(false); }
}

async function uploadGold(file) {
  if (!file || !state.run) return;
  setBusy(true, "Checking frozen labels and scoring predictions…");
  try {
    if (!file.name.toLowerCase().endsWith(".xlsx") || file.size > 5 * 1024 * 1024) throw new Error("Choose a completed .xlsx label workbook smaller than 5 MB.");
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary = "";
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    const result = await (await api("/api/evaluate", { run_id: state.run.run_id, workbook: btoa(binary) })).json();
    state.run.evaluation = result; renderEvaluation();
    notify("Label completeness, freeze-date presence and corpus matching passed. Scores are descriptive; independent annotation remains your research responsibility.");
  } catch (error) { notify("Evaluation not run: " + error.message, true); }
  finally { $("gold-file").value = ""; setBusy(false); }
}

document.addEventListener("click", (event) => {
  const view = event.target.closest("[data-view]"); if (view) changeView(view.dataset.view);
  const filter = event.target.closest("[data-filter]"); if (filter) { state.filter = filter.dataset.filter; renderCandidates(); }
  const candidate = event.target.closest("[data-candidate]"); if (candidate) { state.selected = candidate.dataset.candidate; state.mode = "prism"; renderCandidates(); }
  const inspect = event.target.closest("[data-inspect]"); if (inspect) { state.selected = inspect.dataset.inspect; state.filter = "all"; state.scenario = "all"; state.search = ""; $("search").value = ""; $("scenario-filter").value = "all"; changeView("workspace"); renderCandidates(); $("evidence-panel").scrollIntoView({ behavior: "smooth", block: "start" }); }
  const exp = event.target.closest("[data-export]"); if (exp) download(exp.dataset.export);
});
$("search").addEventListener("input", (e) => { state.search = e.target.value; renderCandidates(); });
$("scenario-filter").addEventListener("change", (e) => { state.scenario = e.target.value; renderCandidates(); });
$("reset-filters").addEventListener("click", () => { state.search = ""; state.filter = "all"; state.scenario = "all"; $("search").value = ""; $("scenario-filter").value = "all"; renderCandidates(); });
$("open-upload").addEventListener("click", () => $("upload-dialog").showModal());
$("close-upload").addEventListener("click", () => $("upload-dialog").close());
["file-zone", "upload-corpus-data", "restore-session"].forEach((id) => $(id).addEventListener("click", () => $("corpus-file").click()));
$("corpus-file").addEventListener("change", (e) => uploadCorpus(e.target.files[0]));
$("gold-file").addEventListener("change", (e) => uploadGold(e.target.files[0]));
$("upload-gold").addEventListener("click", () => $("gold-file").click());
["load-sample", "sample-dialog"].forEach((id) => $(id).addEventListener("click", loadSample));
$("export-main").addEventListener("click", () => download("xlsx"));
$("download-session").addEventListener("click", () => download("session"));
$("rerun").addEventListener("click", async () => {
  if (!state.run) return;
  const wasDirty = state.dirty;
  const depthChanged = Number($("max-hops").value) !== state.run.payload.max_hops;
  await runData({ format: "prism-review-session/v1", suite: state.run.suite, notes: state.notes, max_hops: Number($("max-hops").value) }, state.label);
  if (wasDirty || depthChanged) dirty(true);
});
const zone = $("file-zone");
["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (e) => { e.preventDefault(); zone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (e) => { e.preventDefault(); zone.classList.remove("dragging"); }));
zone.addEventListener("drop", (e) => uploadCorpus(e.dataTransfer.files[0]));
window.addEventListener("beforeunload", (e) => { if (state.dirty) { e.preventDefault(); e.returnValue = ""; } });
renderDownloads(); loadSample();

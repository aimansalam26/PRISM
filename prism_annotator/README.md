# PRISM v0.13 — annotation to traversal

For this combined release, follow `../PRISM_ENGINE_UPDATE.md`. It supersedes the historical installation instructions below: this release intentionally updates the root engine, reference checker and traversal UI as well as the annotator. Existing projects are retained.

New: CLI [9] / `prism build-scenario`, connection certainty, explicit terminal trigger fields and editable connection applicability. Final verification includes this metadata. Unknown scope stays unknown and yields possible impact (Defer) in traversal.

---

## Historical v0.12 notes

# PRISM v0.12 — candidate scope editing and workspace navigation

## Install
Stop the annotation server, back up annotation project folders and their shared prism_graph.sqlite, and merge this ZIP's `prism_annotator` folder into your PRISM root. Do not replace your root traversal app.py, engine.py, reference.py or data. Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\prism_annotator\install.ps1
prism
```

Refresh browser tabs after upgrading. Existing annotation projects are retained.

## Candidate review
Under either KO, click **Edit applicability**. This works across sibling projects. Edit ordinary tuple fields, select exact supporting context, and choose Save draft or Save and approve KO. Separate alternatives with `|`; retain separate correlated tuples. Both temporal endpoints may remain unknown. Citation aliases are repaired on save. The original source and earlier decisions remain in the audit. Editing a KO invalidates existing connection/final-review fingerprints; inspect those connections again.

For Netherlands policy rules, select the relevant `GitLab BV (Netherlands) Benefits` heading or explicit Netherlands sentence, then enter NL. The heading establishes the proposed context; it still requires your judgment that the specific rule inherits it. Do not apply NL to every object solely from the filename: local exceptions, cross-country comparisons or quoted global guidance can differ. GitLab BV is the employing entity; NL is the jurisdiction. Do not infer effective dates from Git timestamps.

## Switching workspaces
- CLI **[8] Open traversal workspace**, or `prism traversal`.
- Browser **Open traversal** starts/reuses your existing root application on localhost:8766 in a separate tab.
- Its new **Annotation** link returns to the annotation server (normally localhost:8765); the annotation server must still be running.
- The wrapper adds navigation and a favicon without editing your traversal source files. Existing traversal UI design/assets otherwise remain unchanged.
- Your root needs `app.py`, `engine.py`, `reference.py`, `ui_exports.py`, and the original `ui/index.html`, `ui/styles.css`, `ui/app.js`. Evaluation also uses evaluate.py and run_suite.py. The uploaded Python files did not include those UI assets or the scenario/workbook data, so they are not recreated or fabricated in this patch.
- A different application on port 8766 is never killed or mistaken for this workspace. Startup logs are in `%LOCALAPPDATA%\PRISM\logs\traversal.log`. Background traversal remains running for reuse; download review sessions before terminating its Python process or restarting Windows. Closing a browser tab does not stop it.

## UI changes
Neutral slate/blue palette, simpler cards and headings, fewer banners, collapsed retrieval/model details, and a P favicon. Model provenance and source evidence remain available in details and exports; presentation cleanup does not remove the audit trail. Coverage status retains its meaning.

## Additional fixes
- ADOPTS_VALUE cannot rewrite temporal windows or unknown/wildcard populations.
- Imported records with unsupported scope do not automatically retain a prior approved status.
- Candidate edits use current fingerprints to block stale overwrites and update the correct source project's database.

## What reading your traversal files established
| File | Responsibility |
|---|---|
| engine.py | Schema 0.3 validation, scope intersection, bounded FIFO traversal, local/untyped baselines |
| reference.py | Separate bounded-path implementation for computational comparison |
| run_suite.py / run_demo.py | Execute scenario corpora and write predictions/review packets |
| evaluate.py | Read frozen workbook labels and score predictions |
| app.py | Local traversal dashboard, uploads, sessions and evaluation routes |
| ui_exports.py | CSV, Excel, JSON/session and Markdown downloads |
| test_engine.py / test_ui.py | Engine, evaluation and dashboard regression checks |

**The annotation schema is not yet your engine's scenario schema.** The new Traversal compatibility dialog reports requirements; it does not invent a runnable scenario. Specific differences found:
1. Engine uses roles, jurisdictions, organisations, start and end. Annotator separates employment_types from org_roles. Combining them into a list would incorrectly change AND into OR. A reviewed mapping or engine schema change is required.
2. Engine needs real ISO date bounds with an exclusive end; annotation unknown dates must not become arbitrary dates or `*`.
3. Engine TYPES omits CALCULATES_VALUE. The unchanged field in its queue also does not implement source_field -> target_field renaming.
4. Engine needs scope cells and certainty on relationships, plus a field even for REVIEW_ONLY/OVERRIDES. Current annotation edges have field mappings and scope notes, not a complete engine relationship scope. Independent override semantics must be separately evidenced.
5. A scenario needs a specific before/after change event, changed fields and root version. A curated graph alone does not supply them.
6. Engine supports 1–3 hops and rejects scope withdrawal and relationship-change events. Requirement-group Boolean evaluation is not implemented.

Two engine behaviours were reproduced with its own synthetic fixture: a population value `unknown` passes validation and can be reported as definite affected scope; an uncertain REVIEW_ONLY edge propagates Defer to downstream nodes. These are **reported, not changed**, because this release updates the annotation system and wraps your existing traversal app without silently changing your experimental algorithms or reference baseline. Also, evaluate.py filters workbook identifiers by an S prefix; empirical KO_ identifiers need that evaluation rule revised. Resolve these before admitting new handbook scenarios. Exports remain explicitly not engine-ready.

## Validation
79 annotator tests passed. Live HTTP checks cover candidate edits, NL normalisation, approval, compatibility reporting, traversal startup/reuse, favicon and return navigation with your uploaded server code and placeholder UI assets. A DOM interaction check covers candidate scope editing and context selection. 22 self-contained uploaded engine/evaluation tests passed. The two data/workbook-dependent engine tests and uploaded UI suite could not be run without the scenario JSON, workbook and actual UI assets. No live Ollama/GPU or Windows startup benchmark is claimed.

---
Prior release documentation follows; v0.12 notes above take precedence.

# PRISM v0.11 — scope edits and local startup

## Upgrade without losing annotation projects
1. Stop PRISM with Ctrl+C. Keep a backup of your annotation project folders and shared prism_graph.sqlite.
2. Extract this ZIP into your PRISM root, merging/replacing the `prism_annotator` code folder only. Do not delete your annotation projects or the shared graph database.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\prism_annotator\install.ps1`, then `prism`.
4. Choose **2 Open / resume**, then manual review to repair existing KOs without model calls. Refresh the browser after upgrading.

## What changed
- The inspector has ordinary scope fields; JSON remains available for advanced edits and additional correlated tuples. Use `|` to separate alternatives within one dimension. Dates can stay `unknown`.
- On Save or Approve, recognised aliases and existing citations are reconciled automatically. `Netherlands`/`netherlands` becomes jurisdiction `NL`; a citation is attached only from the exact rule quote or explicitly selected context. No external facts or automatic entity inheritance.
- A country cannot pass the entity check merely because its name appears in the quote. Generic “team members” cannot pass as a specific organisational role. Select appropriate source context or explicitly use unknown.
- Unsupported claims remain editable and saveable as Proposed. Approval gives the exact tuple, dimension and reason. The explicit clearing button asks for confirmation, sets unsupported values to unknown, preserves supported ones, records the prior version in the audit, and returns the KO to Proposed.
- Unknown scope can be curated and finally verified as an honest annotation. Approval is NOT engine admission. Exports are explicitly `engine_ready: false`; final packets and project exports expose unresolved scope. This package does not contain the PRISM traversal engine. Its importer must implement this contract; metadata alone cannot enforce it in an external engine.
- Final verification still requires checking the evidence. Existing evidence, stale-version and endpoint checks remain. Reviewer names are audit labels, not authenticated identities.
- Offline mode checks the local service and starts `ollama serve` in the background only after a refused loopback connection. An already-running server is reused. Startup has a bounded wait; errors point to `%LOCALAPPDATA%\PRISM\logs\ollama-server.log`. It does not install/download models or stop your existing server. The started server remains running for reuse.
- Retains non-thinking mode, temperature zero, 16K context and 4096 output-token budget. Adds a 10-minute warm-model period and generation-speed reporting when Ollama returns timing data. Calls remain sequential. These settings do not guarantee reproducibility or semantic correctness.

## Repair the Medical Allowance example
Open the KO. Keep employment type `full_time` and jurisdiction `NL`. Set generic org_role `team_members` to `unknown`. For entity, select the exact relevant GitLab BV heading as context and set `GitLab BV` only if the policy context establishes that entity; otherwise set `unknown`. Leave both temporal endpoints unknown unless actual effective dates are stated. Save/Approve; no scope citation JSON editing is needed. The model's substantive summary still needs human review.

Git author/commit dates remain provenance, never substituted for policy effective dates. Unknown is neither an empty set nor universal applicability. An engine should defer uncertain intersections (or return separately labelled possible impacts under a documented uncertainty policy), not report definite impact or definite pruning from unknown data.

## Your laptop: Ryzen 7, 16 GB RAM, RTX 5060 Laptop 8 GB VRAM
Keep `qwen3:4b` as a speed baseline. Try `ollama pull qwen3:8b` as the accuracy candidate (official default Q4_K_M download ~5.2 GB; runtime memory is higher). Select it in PRISM. GPU fit and speed depend on context and other GPU users; 16K context is retained to avoid shrinking source evidence. During extraction, use `ollama ps`: PROCESSOR should ideally show 100% GPU. If split CPU/GPU, try 4b, close GPU-heavy applications, and check current NVIDIA drivers/Ollama. Do not interpret shared graphics memory as extra dedicated VRAM. No training required.

Compare the same 10–20 source units in separate projects using 4b vs 8b. Count missed independent rules, invented rules, wrong scope values, exact-evidence failures and elapsed time; choose based on reviewed results. A larger model is not guaranteed more accurate for this extraction task. Do not mix the benchmark projects into your production shared graph. Existing checkpoints skip completed units: use separate projects or explicit rerun, not a resume that skips everything.

Official references: https://docs.ollama.com/gpu ; https://docs.ollama.com/faq ; https://ollama.com/library/qwen3:8b

## Validation
72 Python automated tests, including alias/citation repair, wrong dimensions, preservation of unknown dates/tuple correlations, and mocked Ollama startup. Live HTTP smoke test covers approval, final verification, invalid-entity blocking, explicit clearing and export safety metadata. A DOM interaction test also covers the ordinary scope fields and approval submission. Windows process creation and real GPU inference must be checked on your laptop; no measured GPU speedup or accuracy gain is claimed.

---
Earlier feature documentation follows (v0.11 changes above take precedence).

# PRISM v0.10 — Light curation and final verification

GitLab Handbook Markdown → structural sections → atomic KO proposals → source
coverage and human review → candidate pairs → model-assisted edge proposals →
human-reviewed directed graph. Python 3.11+. Windows PowerShell launcher included.
No Docker, Hugo, Neo4j, CDN, model training or cloud account is needed for manual
review. Ollama is local; Gemini is optional and sends selected evidence to Google.


## What changed in v0.10

The workbench is a supporting dataset-curation tool for PRISM's scope traversal
research. Models draft; the researcher curates a small grounded set; a second
reviewer verifies that set with minimal typing. The older source, graph, import,
coverage and rerun tools remain available.

### Researcher: shortest useful workflow

1. Open/new project. Choose Ollama or Gemini. At section selection type
   `topic:Medical Allowance` (or a different topic) instead of selecting many numbers.
2. Extract drafts. You can choose to draft candidate edges with the same model
   immediately afterwards, or use terminal [6] later. Both are optional model calls.
3. Inspect source and scope. Click **Approve draft**, **Needs fixing**, or
   **Not a useful rule** on KO cards. Routine decisions need no typed justification.
4. In Candidate review, inspect the model's rationale and evidence. **Approve for
   final verification** creates a curated edge if both endpoint KOs are approved.
   **Accept as saved proposal** keeps an edge at proposed status. Manual edge creation
   still needs a causal rationale; model-proposed rationales are prefilled.
5. Give the verifier `prism verify` (menu [7]) or open **Final verification**.

Source coverage is available for curation; completing every source-unit checklist
is NOT a prerequisite for final verification of your selected pilot. Do not infer
that a verified subset establishes complete extraction of the whole document.

### Verifier: no essays or JSON

Choose the saved project, enter your name once, then read the selected rule or
connection, original quotes and scope table. Tick the evidence-check confirmation
and click **Agree · verified**. If something is wrong, choose a reason and click
**Needs fixing** or **Reject**. Comments are optional. The next item appears.
Only researcher-approved KOs/edges enter this view. Edge acceptance requires both
endpoint KOs to be currently verified. Decisions record the person's name, action,
reason code, timestamp and content fingerprint. They are separate from curation
approval and become stale after relevant content changes. Final feedback is visible
on researcher KO cards. These views are workflow conveniences, not user accounts or
an authentication boundary; a self-entered name does not prove independence.

### Applicability is evidence-backed, never filled for convenience

The model is prompted to act as a cautious compliance-policy analyst, not to invent
missing policy facts. Every claimed scope value must include a `scope_support`
citation: tuple index, dimension, value, section ID and an exact source quote. Parent
or heading evidence must also be selected in `context_evidence`. Literal matches in the rule quote or explicitly selected context can supply missing
citation drafts for values the model already proposed; this does not invent new
scope values. Unsupported new extraction values become **unknown**. Tuple combinations are retained; no flattening
or cross product is performed. No default full-time role, legal entity, country,
start date or 9999 end date is assumed. Unknown never means all/everyone.

The deterministic gate checks text presence and a conservative explicit alias map,
including Netherlands→NL and full-time→full_time. Unknown country names/codes and
nonliteral date forms may stay unknown until curated; the map is not exhaustive.
Text presence cannot establish that a scope actually governs the rule, or resolve
negation, exclusion or correlated conditions. Humans must check that interpretation.
A country heading alone does not prove employment type or effective dates.

Older projects are not silently rewritten. In a KO inspector, **Ground existing
scope / clear unsupported values** drafts citations from that rule's quote and
already selected context, then replaces unsupported claims with unknown and resets
curation approval. Previous content remains in the audit. Alternatively re-extract;
changed drafts enter Rerun comparisons. Unsupported legacy scope values block final
acceptance rather than being passed off as verified. Preserve relevant context
quotes before grounding if the source really provides those values.

### Less typing, without fabricated reasoning

Free-text comments are optional for routine KO decisions, coverage, group choices,
rerun resolution, candidate decisions and accepting/rejecting model suggestions.
When absent, the audit records the selected action and explicitly says no free-text
explanation was supplied. It does not pretend the reviewer wrote the model's rationale.
Existing review notes and advanced controls remain. Group logic still defaults to
UNCERTAIN; selecting AND/OR is an explicit researcher judgment, not a model inference.

### Validation for this revision

62 automated tests pass. Live local HTTP + jsdom checks passed for source-grounded
NL/full-time evidence, one-click curation without notes, verifier-only startup, two
KO decisions and one connection decision without typed comments, and final export.
No live Ollama/Gemini quality evaluation or rendered-browser visual test was run for
this revision. The role prompt is not training and does not guarantee expert accuracy.
This remains an annotation workbench, not the scope traversal engine.

## Upgrade in small steps

1. Stop PRISM with Ctrl+C, then exit its menu. Keep a backup of annotation_projects.
2. Copy this prism_annotator folder over your existing CODE folder. Keep all your
   annotation_projects, SQLite files and handbook files. Do not replace those with
   a new empty workspace. Include the new .py, .html, .js and .css files.
3. From your PRISM root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\prism_annotator\install.ps1
$env:Path = "$env:LOCALAPPDATA\PRISM\bin;" + $env:Path
prism
```

Setup uses a dedicated workbench .venv and installs a per-user prism command; no
administrator access is required. The execution-policy option applies to that
setup process. Rerun setup after moving the code folder. Existing projects load;
new SQLite tables are created alongside old tables without deleting annotations.

4. Check Settings points to your existing annotation_projects directory.
5. Open/resume the Netherlands project. Choose manual review to inspect existing
   KOs, or Ollama/Gemini to re-extract a small Medical Allowance section first.
6. Browser: http://127.0.0.1:8765. Keep the terminal running.

## Terminal options

- [1] Start a new annotation project: choose a GitLab .md file.
- [2] Open/resume: choose a saved project. Original source hash must match.
- [3] Settings: handbook and shared annotation_projects folder.
- [4] Help.
- [5] Generate deterministic candidate pairs; writes edge_candidates.json.
- [6] Propose edge types with Ollama/Gemini. Choose a model and maximum pair calls.
- [7] Final verification: no extraction/model prompts.
- [0] Exit.

Shortcuts: `prism new`, `prism open`, `prism settings`, `prism candidates`,
`prism propose-edges`, `prism verify`. Model keys are prompted privately in the terminal, not saved.
For Ollama, its local service must be running and a local text model installed.
There is no automatic cloud fallback. Model generation is initiated from the CLI (or offered directly after KO extraction);
the browser reviews its checkpointed results. Stop the browser server with Ctrl+C
to return to the menu, run [6], then reopen your project in manual mode to review.

## 01 Source review and KO inspector

The screen pairs source units with their linked KOs. Heading paths and disclosure
titles preserve the benefit context. Rendered Markdown is a simplified preview,
not a complete Hugo build. Exact quotes and saved source bytes remain authoritative.

Colours:
- Orange: no active KO linked to the source unit, or no quote overlap for a clause hint.
- Purple: linked KOs or quote overlap exist; completeness still needs human checking.
- Green: a current human source-coverage decision exists.

Click Review clauses. Heuristic fragments split on semicolons, "and" and "but";
these are inspection aids, NOT an automatic rule count. A phrase can be one rule,
and a long quote can cover multiple clauses without its KO expressing them all.
Enter the number of independently changeable rules YOU identified and a note.
Complete coverage requires at least that many valid linked KOs. It does not prove
semantic completeness; that remains the human annotation judgment. Example:
"Unused days carry over but expire July 1st" can require separate carry-over and
expiry KOs. A not-a-rule decision requires a rule count of zero. Source or KO edits
make the unit decision stale. Older section-level coverage reviews remain in the
legacy coverage page/export; they are not converted into per-unit approval.

Click a KO to open the inspector. It separates:
- Automated saved-record quote/schema checks.
- Human approval of meaning, scope, atomicity and context.

Select exact heading/parent-sentence evidence with purpose subject/scope/condition/
group. Document YAML titles are preserved in a context-only record without changing old
policy section IDs or extracting metadata as rules. Each context quote must exist
in its referenced section. A valid citation
proves text presence, not justified inheritance. Unsupported applicability stays
unknown; extraction never invents dates from snapshot timestamps. Old KOs need
manual context evidence selection or re-extraction if those references are absent.
Curation approval requires valid source/context quotations and supported claimed scope values; comments are optional. Unknown scope
may be approved explicitly as unknown; it is not thereby traversal-ready.

Add missing KOs manually. Edits reset the UI's decision to proposed. Stale saves
from another tab are blocked. Delete uses confirmation plus typed KO ID and moves
the node to recoverable trash; the shared graph provides Restore. Related edges
become stale. This is two-step confirmation, not authentication/2FA.

## Eligibility requirement groups

New extraction under an Eligibility heading gives the units a shared proposed
requirement_group_id. It starts with logical_operator UNCERTAIN. Do not infer AND
or OR merely from bullet formatting. Inspect the group, explain the source basis,
and choose AND, OR or UNCERTAIN. Apply updates every active member, resets their KO
approval to proposed, and audits the change. Source interpretation must be reviewed
again. A manual group ID can also be assigned to existing KOs in the inspector.
To add members to an already-confirmed group, first reset its operator to UNCERTAIN
in the group editor, save the new memberships, then review the operator together.

Groups are qualification metadata, not automatically generated causal edges. This
release records flat groups within a project. Nested AND/OR trees and executable
eligibility evaluation are not implemented; record unresolved expressions as
UNCERTAIN rather than flattening them into a false assertion.

## Rerun comparisons

Rerun mode Pending retries old-prompt checkpoints; Uncovered retries sections
without current legacy section-coverage review; All reruns selected units.
New extraction uses prompt version handbook-3. Each bullet/paragraph/table unit has
an explicit rule/non-rule/uncertain response. All responses and failures checkpoint.

Changed proposals for a source unit that already has KOs are staged in Rerun
comparisons. They do not automatically add duplicate graph nodes. Identical records
are reused. The comparison shows old and new summaries, quotes, fields, scopes and
context evidence. Choose:
- Keep existing: dismiss the new proposal.
- Add as distinct: insert a separate proposed rule.
- Replace checked KOs: reject selected old records with superseded_by and insert
  the new proposed KO. Old records and audit history remain; old edges become stale.

Rerun comments are optional. Replacing or adding from a comparison is blocked
if the compared existing KOs changed since the proposal. Keep existing and rerun
in that case. Invalid new proposals must be corrected manually or re-extracted;
they cannot be accepted through the comparison action. Entirely new source units
still create proposed KOs normally. No result is automatically human-approved.

## 02 Candidate review and optional model proposals

Python nominates UNORDERED pairs through same full topic paths within a source,
shared watched fields, two-token lexical overlap with a small explicit alias set,
and links to loaded handbook documents. These are retrieval signals, not proof.
Aliases such as bicycle/bike and limit/cap expand recall; they do not declare field
equivalence and must not be used as automatic causal mappings.

For URL fragments, the generator matches explicit HTML IDs or a unique heading
path and its subsection KOs. Unresolved or ambiguous fragments produce notices;
there is no silent whole-document fallback. Standard heading slugs are supported,
not every Hugo shortcode/generated/duplicate anchor convention. Canonical paths
containing /handbook/ must be available. Relative links other than same-page
fragments and aliases/permalinks are not fully resolved. Unloaded target documents
are reported. Whole-page links still nominate at document level. Missing or unknown
scope does not silently prune retrieval; implicit relationships can still be missed.

Run terminal [6] for model suggestions. One call per nominated pair, with both KOs
and source sections. Pydantic validates outcome, direction, type, field mappings,
dimension rewriting and exact evidence quotes. Matching text is not causal proof.
The model can return relationship, no_dependency or uncertain. Failed calls are
checkpointed and retried next run; current successful proposals and human decisions
are skipped. Sources over the input limit fail visibly rather than being truncated.

The UI offers Accept, Edit in graph, and Reject. Comments are optional; selected decisions are audited. Accept as saved proposal creates a SAVED PROPOSAL. Approve for final verification is a separate explicit curation action. In Graph
review, after approving valid endpoint KOs, the reviewer can explicitly approve the
relationship. Accept no_dependency/uncertain records the corresponding human pair
decision without creating any edge. A pair may support multiple relationships;
creating one edge does not auto-close all interpretation of that pair.
Endpoint or retrieval-signal changes invalidate stale suggestions and pair reviews.

## 03 Shared graph review

Projects directly under the same annotation_projects folder share prism_graph.sqlite.
Node IDs are namespaced by project folder name. Keep folder names stable after
connecting nodes; renaming a folder changes its graph identity.

- Violet dotted arrows: current AI suggestions, not saved graph edges.
- Blue dashed arrows: saved proposed edges.
- Green solid arrows: human-approved annotations.
- Red arrows: stale endpoints; review again.

Drag nodes, pan, zoom, fit, relax/pause layout and save positions. Inspector exposes
quotes, source sections, context evidence, scopes and requirement-group metadata.
Manual connection type starts at "Choose relationship type…". Source → target
means upstream rule/value → dependent rule (general → exception for OVERRIDES).
Types: DEPENDS_ON, CALCULATES_VALUE, ADOPTS_VALUE, REVIEW_ONLY, OVERRIDES, RELATED_TO.
Propagative types require valid endpoint field mappings; adoption requires explicit
dimension rewrites. Similar values do not prove a dependency. No scope-intersection
or impact-traversal engine is executed by this annotation app.

## Imports, persistence and export

Import legacy verified or native KO JSON from the Import KOs page. Preview before
applying. Source hashes and exact quotes are checked; mismatches/conflicts block.
Preserving an imported approval is an explicit option, never inferred from a quote
match alone. All changes stay in SQLite; export snapshots to retain portable JSON.
Project export includes KOs, coverage decisions, comparisons and audit history.
Graph export includes model edge proposals, reviewed edges and shared audit history.

## Validation and practical limits

62 automated tests pass (including original regressions and new coverage, group,
context, rerun and edge-proposal safeguards). A live local HTTP server plus jsdom
interaction checks passed for KO saves, collective grouping, clause review, rerun
resolution, neutral relationship defaults, AI arrow styling and human acceptance.
Chromium launch was blocked by this environment, so a rendered-browser visual test
was NOT completed. Live Ollama/Gemini quality was NOT measured; model tests use
controlled replies. Review a small reference benefit before expanding extraction.
The generator still enumerates combinations in topic/field buckets and the SVG
simulation is pairwise: use pilot-sized workspaces, not the entire handbook graph
at once. Research claims about extraction recall, edge accuracy and annotation time
require separate measured evaluation; this release does not claim those results.

Run local tests from the repository root:

```powershell
.\prism_annotator\.venv\Scripts\python.exe -m unittest discover -s .\prism_annotator -p "test_*.py"
```

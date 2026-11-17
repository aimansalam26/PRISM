# PRISM stakeholder interface setup and walkthrough

This add-on puts a local browser interface around the corrected PRISM 0.2.0 prototype. It uses your existing traversal engine and computational reference. It adds a candidate workspace, evidence inspection, method comparisons, JSON uploads, working review notes and downloadable reports.

The interface is for demonstrating and inspecting predictions. Review observations do not alter gold labels, approve policy changes or update a policy knowledge base. Python 3.10 or newer is sufficient. No pip packages, API keys, database server or cloud account are needed.

## 1 Add the files

Open the existing PRISM folder: the folder that already contains `engine.py`, `reference.py`, `evaluate.py` and `data/scenarios.json`.

Download the individual files and place them as follows. Do not rename `app.js` to `app.py`, and check that Windows has not added `.txt` to any filename.

| Download | Destination relative to your PRISM folder | Purpose |
|---|---|---|
| `app.py` | `app.py` | Starts the local server, validates uploads, calls the engine and handles downloads. |
| `ui_exports.py` | `ui_exports.py` | Produces Excel, CSV, Markdown and JSON exports. |
| `index.html` | `ui/index.html` | Page layout and the PRISM glass-and-spectrum illustration. |
| `styles.css` | `ui/styles.css` | Colours, typography, responsive layout and interaction styles. |
| `app.js` | `ui/app.js` | Connects upload, filters, evidence inspection, notes and downloads to Python. |
| `test_ui.py` | `test_ui.py` | Optional software checks for the add-on. |
| `UI_SETUP.md` | `UI_SETUP.md` | These instructions. |

Create the `ui` folder yourself if it does not exist. The first five files are needed to run the interface. The test and guide are supporting files.

No edits to `engine.py`, `reference.py`, `run_suite.py`, `evaluate.py`, the JSON corpus or the label workbook are required. The existing command-line prototype continues to work. Use the corrected 0.2.0 package, not the earlier starter engine: the API and input schema are different.

## 2 Start the interface on Windows

1. Open the PRISM folder in File Explorer.
2. Click the address bar, type `powershell` and press Enter. This opens a terminal in that folder.
3. Check Python:

```powershell
py --version
```

4. Start the interface:

```powershell
py app.py
```

5. Keep that terminal open. Open your browser and enter:

```text
http://127.0.0.1:8765
```

The page automatically loads and analyses `data/scenarios.json`. With the supplied seven-case development corpus, expect 21 candidates, a 15-item human review queue, 3 deferred cases and 6 not-selected cases. The queue contains 12 supported candidates plus the 3 deferred candidates.

These numbers are model predictions. Accuracy is not shown until an independently completed and frozen label workbook is accepted.

On a computer that uses `python` rather than `py`, substitute `python app.py`. On macOS/Linux the command may be `python3 app.py`.

Do not double-click `index.html` to run the application. It needs the local Python server to analyse data and produce exports.

## 3 A five-minute stakeholder walkthrough

### Review workspace

The four summary cards describe the entire active corpus. Filters below them affect the candidate list only.

1. Select the home-office stipend event from the event dropdown.
2. Select the country stipend rules. Inspect the Netherlands/Belgium applicability cell and supporting source clause.
3. Select the France claims guide. PRISM reports no supported affected scope for this amount change.
4. Use **Inspect method** to switch that candidate to **Local pairwise**. Compare its prediction and path.
5. Expand **View the source change** below the workspace to see the previous and revised provisions.
6. Select the **Deferred** filter. Inspect a case whose relationship was manually marked uncertain and read the uncertainty reason.

The evidence inspector displays the selected method. The candidate list, status filters and summary cards continue to use PRISM predictions. This keeps the primary review queue stable while you compare an individual method.

Each applicability card is a separate correlated scope cell. For example, French managers and German engineers must remain two combinations; do not read them as every country-role combination. Dates use an inclusive start and exclusive end. The very early and far-future dates in the JSON are implementation sentinels, displayed as unspecified bounds in the interface.

### Method comparison

This view shows the review-queue size for PRISM, local pairwise checking and untyped traversal. It lists candidates whose Yes/No/Defer labels differ and provides an Inspect link.

The local comparison uses the same curated metadata but forgets earlier scope restrictions at later steps. The untyped comparison ignores field, relationship and applicability semantics. Smaller queue size does not by itself establish higher accuracy. Identical candidate labels do not establish identical scopes or paths.

### Stakeholder observations

For a selected candidate you can record a progress status and a note. Statuses are:

- Not reviewed.
- Evidence reviewed.
- Question this recommendation.
- Needs clarification.

These are working observations, not approvals and not independent benchmark annotations. They do not change engine predictions or the annotation workbook. A person who has seen these predictions is no longer blind to the system when judging these same cases.

Notes are held in the browser tab. Click **Save review session** before closing or reloading. The downloaded session JSON contains the source corpus, hop limit and notes. The interface warns before replacing a workspace with unsaved notes, but downloads are the persistence mechanism.

## 4 Upload a corpus or restore a session

Use **Upload** in the top bar, or **Data & exports**. You can choose a file or drag a JSON file into the upload dialog.

Supported inputs:

| Input | What happens |
|---|---|
| `data/scenarios.json` | All included scenarios are validated and analysed. |
| `data/policies.json` | The single stipend scenario is validated and analysed. |
| Another schema 0.3 scenario/corpus | The same validation, engine and reference checks run on it. |
| `PRISM_review_session.json` | The corpus and notes are restored; predictions are recomputed, not trusted from uploaded output. |

Raw PDFs, Word policy documents, `results.json` and an ordinary spreadsheet are not corpus inputs. PRISM still requires curated KOs, changed fields, relationships and applicability metadata. This UI does not add automatic text interpretation or relation extraction.

Source files are not overwritten by an upload. Invalid uploads leave the current workspace intact and show an error. The interface accepts a maximum 5 MB file. The local adapter supports up to 64 scenarios, 100 nodes and 200 edges per scenario, four changed fields, four scope cells per record and a conservative total path-expansion budget. Complex inputs may be rejected before traversal to keep the demonstration responsive.

In **Data & exports**, change **Maximum impact steps** to 1, 2 or 3 and click **Re-run corpus**. The same bound applies to all three methods. Notes remain associated with their candidate IDs; any previous evaluation is cleared because the predictions have changed. Export a new session after changing the depth if you want to retain that setting.

Withdrawals, scope contraction and relationship removal remain unsupported by the underlying engine. Do not disguise those changes as ordinary value changes to make an upload pass.

## 5 Download reports

The top-right **Export Excel** button produces a real `.xlsx` workbook. Other formats are in **Data & exports**.

| Download | Contents |
|---|---|
| Excel review report | Overview, Candidates, Policy changes, Affected scopes, Supporting paths and Traversal decisions worksheets. Includes working stakeholder notes. Adds an Evaluation sheet when frozen labels have been scored. |
| Review session JSON | Source corpus, notes and impact-step limit; upload this to resume a review. |
| Candidate CSV | One row per candidate with all three predictions, source text, scope cells and working notes. |
| Readable Markdown packet | Previous/revised evidence, predictions, paths, exclusions and notes. |
| Engine results JSON | The full engine output and computational reference checks, in the existing results structure. |
| Source corpus JSON | The exact structured corpus analysed in the current run. |
| Evaluation JSON | Appears after successful gold-workbook scoring; includes pooled and macro measures. |

Every export covers the **whole active corpus**, not only rows visible under a filter. If you need a report for one event, upload that event as a single-scenario corpus first.

The Excel report is an inspection report, not a replacement for `3_Label_Matrix.xlsx`. It is not accepted as the annotation workbook. Excel cells exceeding 32,000 characters are explicitly marked as truncated; use JSON for complete long evidence. Formula-like text is treated as text in Excel, and escaped in CSV.

## 6 Optional evaluation with the annotation workbook

After independent annotation and adjudication, open **Method comparison** and click **Upload labels .xlsx**.

Use the existing `3_Label_Matrix.xlsx` with:

- Both original coder labels and reasons completed.
- Adjudicated gold labels and supporting evidence completed.
- The gold freeze date in `Legend!B20`.
- A matching corpus fingerprint in `Legend!B22`.
- Human directness labels where direct/indirect recall is to be reported.

The server reuses `evaluate.py`'s gold checks and scoring. A blank workbook is intentionally rejected. Passing these software checks establishes that required fields are present and versions match; it cannot establish that volunteers actually worked independently.

The displayed scores are pooled candidate precision, recall, F1 and review-capture recall. The evaluation download additionally includes event-level macro means and their denominators. Deferred gold-positive cases count as missed definite discoveries. Review-capture recall also counts cases sent to humans as Defer. Ambiguous gold is excluded from binary scoring. Undefined denominators remain undefined.

These are descriptive pilot results. Scope and propagation-decision correctness still need independent assessment. No statistical non-inferiority claim or production validation is added by the UI. The label workbook is read through a temporary local copy and is not changed. Restoring a review session does not restore a previously uploaded gold workbook or evaluation; upload the matching workbook again if needed.

## 7 How the added files connect

The browser loads `index.html`, `styles.css` and `app.js`. When you run a corpus, JavaScript sends JSON to `app.py` on your own computer. Python validates it, calls `engine.discover()` for the three modes, and compares PRISM with `reference.compare()`. The browser receives results and renders the candidate list and evidence inspector.

Downloads call `ui_exports.py`. Optional label scoring calls the existing functions in `evaluate.py`. No policy data is sent to an external model or analytics service; the page uses local assets and system fonts.

The server binds only to `127.0.0.1`. A stakeholder can inspect it on your laptop or through a screen share, or run their own copy. Sending someone the localhost URL alone will not give them access from another computer. Multi-user hosting, authentication and shared persistence are a separate deployment milestone.

## 8 Check the installation

Run these from the PRISM folder:

```powershell
py -m unittest test_engine test_ui -v
py app.py
```

The add-on was checked with 36 passing Python tests: the existing 24 engine/evaluation tests and 12 new adapter/export tests. The checks include an HTTP run and Excel download, session restoration, invalid-input rejection, formula-safe exports and refusal to score blank gold. JavaScript syntax and source-level DOM tests also checked counts, filters, method switching, note retention, empty states and HTML escaping. A temporary software-only completed-workbook fixture exercised the scoring path; no fixture labels are included in the deliverables.

A browser preview could not be completed in the authoring environment because the browser connection timed out. The visual layout and browser interaction need the short acceptance check below on your computer; desktop Excel rendering was not exercised here.

1. Confirm the four summary values for the bundled corpus: **21, 15, 3, 6**.
2. Search `S5-C1`, select it and compare PRISM with Local pairwise.
3. Enter a short test note, save a session, reload the page and restore the session. Confirm the note returns.
4. Export Excel and open it; check that the Candidates sheet has 21 candidate rows and the scope/path sheets contain evidence.
5. Upload the blank annotation workbook. Confirm that it refuses evaluation rather than showing accuracy scores.
6. Resize the browser or use a smaller device window; confirm the candidate list and evidence inspector remain usable.

## 9 Troubleshooting

| What you see | What to do |
|---|---|
| `py` is not recognised | Try `python --version`; use that command if it finds Python 3.10+. |
| Missing engine, reference or export module | Place the Python add-on files beside the corrected core files, not inside `ui`. |
| Missing `ui/index.html` or styles | Confirm the three browser files are inside the `ui` folder with their exact names. |
| Browser cannot connect | Keep the terminal running; open `http://127.0.0.1:8765`, not an HTML file or an HTTPS address. |
| Port is already in use | Run `py app.py --port 8766`, then open `http://127.0.0.1:8766`. |
| Corpus missing | Check `data/scenarios.json`, or upload a valid schema 0.3 corpus. |
| Unsupported scope/relationship change | The engine cannot analyse that event yet. Retain the case for the planned dual-version implementation. |
| Gold fingerprint differs | Use the workbook for this exact corpus version. Do not simply replace the hash to silence the check. |
| Working run expired | Re-run or restore the saved session. The local server retains up to eight recent runs and clears them when stopped. |
| Notes disappeared after reload | Restore a downloaded review session. Notes are not automatically saved to disk or the annotation workbook. |

Press Ctrl+C in the terminal to stop the app after saving any review session you need.

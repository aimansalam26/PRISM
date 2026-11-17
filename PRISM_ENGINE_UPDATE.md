# PRISM engine 0.3.0 + annotation workbench 0.13

This update connects final-verified handbook annotations to the traversal engine. It includes the complete annotator, updated engine/reference checker, a scenario converter, and a replacement local impact-review UI. Existing projects do not need re-extraction.

## Install on Windows

1. Stop both PRISM servers. Download any open traversal review session first; those notes are held in memory.
2. Extract this ZIP into a **separate folder**, for example `C:\Users\LOQ\Downloads\PRISM_engine_update`. Do not extract over the repository before running the backup installer.
3. In PowerShell, run (adjust the extracted folder):

```powershell
cd C:\Users\LOQ\Downloads\PRISM_engine_update
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_update.ps1 -ProjectRoot "C:\4thYear\FYP\10-17-fyp\PRISM\PRISM"
cd C:\4thYear\FYP\10-17-fyp\PRISM\PRISM
powershell -NoProfile -ExecutionPolicy Bypass -File .\prism_annotator\install.ps1
prism
```

The update installer backs up each existing file it replaces under `backups\engine-update-TIMESTAMP`. It does not replace data, annotation project folders, SQLite databases, settings, or virtual environments. Newly added file paths are recorded in the backup's `new-files.json`. For rollback, stop servers and restore backed-up files; remove only recorded new files you no longer need. UI assets are replaced and backed up too.

## Start with one real change

1. **[2] Open / resume** your existing small pilot. Review the KOs; do not rerun extraction merely to install this update.
2. Create a few directed edges in Graph review, or use **[5] candidate pairs → [6] model proposals**, then inspect each proposal. Arrows mean upstream rule → dependent rule.
3. For each edge, check type, field mapping, certainty and applicability. `REVIEW_ONLY` / `OVERRIDES` need source trigger fields. An independent override must explicitly select that behaviour. Known edge scope needs a source explanation. Blank scope remains unknown; it is never filled as universal. ADOPTS_VALUE scope is the target-side scope after its explicit mapping.
4. **[7] Final verification:** accept the current KOs and connections you want in the pilot; download the **verification packet**. This is different from the raw graph export. Editing a KO/edge invalidates its previous final verification.
5. **[9] Build traversal scenario** (or `prism build-scenario`). Select the packet, root KO and changed field. Supply an actual previous Markdown snapshot and exact previous rule quote. A commit ID identifies the source version, not its applicability date. If old scope is unknown, the wizard requires explicit revised-clause-only analysis. It does not prove the old and new populations are identical.
6. **[8] Open traversal workspace.** Upload `data\handbook_scenario.json`, run analysis, inspect paths and download the review session/results. Default ports: annotation 8765, traversal 8766. Refresh old browser tabs.

The wizard writes to `data/handbook_scenario.json` relative to the project root when launched through `prism`; give distinct output paths in the command below to keep multiple scenarios. Use one event first, then add cross-file dependencies. No factual handbook nodes, edges or before snapshots are fabricated by this update.

### Command-line alternative

```powershell
.\.venv\Scripts\python.exe build_handbook_scenario.py --annotations "path\verification_packet.json" --event "path\change_event.json" --output data\handbook_scenario.json
.\.venv\Scripts\python.exe run_suite.py --data data\handbook_scenario.json --out output\handbook_pilot --max-hops 3
.\.venv\Scripts\python.exe verify_update.py
```

`examples/change_event.template.json` contains placeholders, not runnable policy data. JSON event mode relies on you supplying genuine before evidence. The interactive wizard checks the previous quote against the local Markdown file. With known end dates, explicitly declare inclusive/exclusive semantics; the engine uses exclusive end bounds. For mixed source conventions use `end_date_convention` keyed by original KO key/edge ID in the event JSON. Never infer a policy effective date from a commit.

## What changed

- CALCULATES_VALUE propagates like a dependency; it does not perform arithmetic.
- Field mappings carry the changed attribute into the target and onward, including different source/target names.
- Employment type and organisational role stay separate. Entity and jurisdiction remain separate. Correlated applicability cases are not flattened.
- Unknown dimensions/dates remain unresolved. A possible path reports **Defer**, with possible bounds where available; it never asserts a definite affected scope. If all policy dates are unknown, expect possible impacts rather than definite Yes results. This is useful for an uncertainty-aware pilot, but is not validation of known temporal overlap.
- Confirmed edges can still prune known contradictions (e.g. NL versus UK) even if another dimension is unknown. Uncertain relationships use conservative temporal-only handling and defer; they do not justify population pruning.
- REVIEW_ONLY stops on all paths, including uncertain ones. Confirmed independent OVERRIDES blocks. RELATED_TO is dropped. Cycles stop and the supported horizon remains 1–3 hops.
- The converter imports only current accepted final-verification records, validates fingerprints and quotes, and explicitly lists omitted records. Missing graph links remain a coverage limitation: traversal does not discover dependencies outside the reviewed graph.
- Reference checking, exports and empirical KO IDs in evaluation are updated. Browser and CLI single-scenario normalisation is consistent. Review notes can be saved in a downloadable session.

## Boundaries and validation

Supported event kinds remain value_change and rule_change. Population/scope changes, deleted relationships, withdrawn rules, full version-lifecycle analysis and automatic Git change detection are **not** implemented by this patch. Use explicit before/after events. Review the exact semantics in `ENGINE_0_3_SPEC.md`.

Legacy schema 0.3 remains supported, with stricter rejection of literal unknown strings. Handbook schema 0.4 uses explicit nulls. Rerun old experiments after upgrading; do not mix metrics from engine versions.

128 self-contained automated tests passed (22 legacy engine/evaluation, 24 handbook engine/converter/API, 82 annotator). A real SQLite→final verification→converter→traversal smoke check passed. Live HTTP and DOM checks covered traversal run/details/notes/session export/assets/shutdown; a graph-editor DOM check covered certainty, trigger fields and scope saving. Test fixtures are synthetic and are not gold policy annotations.

The two original data/workbook-dependent engine tests and the original UI suite were not run without your original scenario/workbook assets. No real handbook accuracy score, Windows installer execution or GPU performance benchmark is claimed. Run `verify_update.py` locally, then test a few hand-reviewed real paths before scaling.

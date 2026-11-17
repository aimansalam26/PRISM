# Validation record

Checked on 6 October 2026 with Python 3.12 on Linux.

| Check | Observed result |
|---|---|
| `python -m unittest -v` | 24 tests passed. |
| Bounded independent reference | Matched PRISM on all seven pilot scenarios. |
| Small-graph differential exercise | 40 seeded variations passed inside the test suite. |
| `python run_demo.py` | Generated the stipend example and its three-method comparison. |
| `python run_suite.py` | Generated results for seven events and 21 candidate pairs. |
| Blank-workbook evaluation | Correctly refused to score before gold was frozen. |
| Completed software-only workbook probe | End-to-end XLSX reading and evaluation succeeded; probe labels were not included in the deliverable. |
| Workbook formula probes | Deferred positive, missing prediction, review volume, review-capture recall and blank-gold behaviour checked. |
| Exported workbook | Re-opened; annotation/prediction inputs blank; expected validation lists present; corpus hash matches JSON. |
| Volunteer packet source check | All 28 node texts in the seven scenarios retained in the packet. |
| Word layout | All 17 packet pages and both guideline pages rendered and visually checked. |

Workbook formulas were exercised in the artifact calculation engine. Microsoft Excel desktop and Windows execution were not exercised. The Python runtime code uses only standard-library features available in Python 3.10 and newer.

The bundled outputs show PRISM returning 12 Yes, 6 No and 3 Defer; local comparison returns 14 Yes, 4 No and 3 Defer; untyped traversal returns 21 Yes. These are development predictions under curated metadata, not precision/recall results. No independently adjudicated volunteer gold labels are present.

The scope, reference-evaluator and annotation limitations are specified in `SPECIFICATION.md`. The implementation has no production deployment, legal-compliance determination, automatic relationship extraction, semantic-retrieval baseline or withdrawal handling.

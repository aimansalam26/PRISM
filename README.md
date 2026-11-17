# PRISM development prototype 0.2.0

This release is ready for a supervised demonstration and a volunteer annotation pilot. It corrects the supplied code and materials while keeping the task small: identify policy provisions that deserve human review after an explicit change, and show the supporting scope and path.

It is **not the completed proposal evaluation**. These seven synthetic scenarios have been used during development. Independent volunteer answers are still required. A later held-out evaluation needs new policy families.

## Start here

Install Python 3.10 or newer. The prototype uses only the Python standard library. There are no API keys, model downloads or pip dependencies.

Unzip this package. Open a terminal in the `PRISM` folder and run:

```bash
python -m unittest -v
python run_demo.py
python run_suite.py
```

On macOS/Linux your command may be `python3`. On Windows you can use `py`.

1. Open `output/demo/review_packet.md` first. It shows the three-candidate stipend chain.
2. Open `output/predictions.csv` for all 21 candidate decisions.
3. Open `output/review_packet.md` for the supporting explanations.
4. `output/results.json` contains complete paths, scopes, rejected transitions, version hashes and reference checks.

The demo selects Scenario 5. The full suite covers all seven scenarios. Output files are regenerated on each run; save a run folder with `python run_suite.py --out output/run_01` when you need to preserve it.

## Meaning of the outputs

| Output | Meaning |
|---|---|
| Yes | At least one supported path justifies review under the implemented rules. |
| No | No supported review path was found within this curated model and the three-hop boundary. |
| Defer | The representation explicitly records an unresolved interpretation. A human must inspect it. No affected scope is asserted from that uncertain path. |

A KO can have a definite path and an uncertain alternative. Its status remains Yes, and `has_uncertainty` records the unresolved evidence. It is counted once in review volume.

PRISM recommends review. It does not rewrite, approve, archive or interpret real employment law.

## Send volunteers only these files

- `1_Annotation_Packet.docx`
- `2_Annotation_Guidelines.docx`

Keep `3_Label_Matrix.xlsx`, the code, predictions and the `internal` folder with the researcher. The workbook contains a clearly named author-intent sheet preserved from the original. It must not be sent as a blinded annotation form.

Use the Word packet independently for each reviewer. Prefer two reviewers able to interpret policy language. If the second coder is you, record your developer role and report the limitation. Keep initial answers before adjudication. Reviewers may disagree with both the design expectations and PRISM.

## Record and score the pilot

1. Enter original Reviewer A and Reviewer B labels/reasons in `Labels` F:I. Use pseudonymous IDs and record relevant experience in `Legend`.
2. Enter scope judgements in `Scope`. Keep correlated combinations on separate rows. An independent annotator should justify the connection from the policy text before inspecting graph predictions.
3. Discuss disagreements using source evidence. Enter adjudicated labels in K and reasons/quotes in L. Record human directness in P and supporting paths/decisions in `Path Review` when justified.
4. Enter the freeze date in `Legend` B20. Do not silently revise frozen labels to match an output. Log any later correction, retain the previous version and rerun all methods.
5. Run the suite. For the workbook view, compare item IDs in `output/prediction_matrix.csv` with `Labels` A2:A22. Paste only its three prediction columns into M2:O22. If you sorted the workbook, match by item ID; do not paste by assumed row order.
6. Generate the checked report:

```bash
python evaluate.py
```

`evaluate.py` reads `3_Label_Matrix.xlsx` directly and writes `output/evaluation.json`. It refuses incomplete labels, missing initial coders, duplicate/missing IDs, unfrozen labels and a data-version mismatch. It does not rely on Excel's cached formulas. The blank workbook intentionally cannot produce an accuracy report.

The workbook shows pooled item measures; the JSON report additionally gives event-level macro means and their denominators. Deferred gold-positive cases count as missed definite discoveries. A separate review-capture recall counts Yes plus Defer. Ambiguous gold is counted separately. Review volume includes every Yes and Defer, including ambiguous-gold cases. Empty denominators produce blank/undefined rates, not invented zero accuracy.

Scope comparisons and propagation decisions have structured recording spaces. Their independent semantic correctness is **not automatically scored by this release**. The reference evaluator checks computation, not human policy interpretation.

## What changed

Read `CHANGES_AND_NEXT_STEPS.md` for the case-by-case corrections. Read `BEGINNER_GUIDE.md` while running the stipend example. `SPECIFICATION.md` defines the implemented rules and boundaries.

The corrected development run returns 12 Yes, 6 No and 3 Defer for PRISM, given the supplied curated interpretations. These are system outputs, **not accuracy results**. In particular, the uncertainty flags were manually curated during development; the engine does not discover ambiguous language automatically.

## Implemented and remaining work

| Component | Status |
|---|---|
| PRISM accumulated path state | Implemented with separate scope cells and recorded paths. |
| Local pairwise typed comparison | Implemented using the same graph and transition vocabulary, without retained earlier scope restrictions. |
| Three-hop untyped comparison | Implemented over the same declared edge set. It ignores types, fields and scope and returns no affected-scope prediction. |
| Small-graph exhaustive path reference | Implemented separately, without importing engine transition code. |
| Volunteer packet and researcher workbook | Updated; human answers remain blank. |
| Semantic retrieval and diff-led lexical retrieval | Planned for the next milestone; not included or claimed as completed. |
| Scope contraction, withdrawal and deleted relationships | Unsupported and rejected when declared/detected. Need pre-change and post-change graph contexts. |
| Arbitrary exception reasoning or LegalRuleML | Outside this small release. Only the documented relation vocabulary is supported. |
| Final statistical evaluation | Pending a larger independent corpus and a frozen protocol. |

The proposal can keep its broader objectives, but progress reports should describe this as the first implementation milestone. Do not claim full RQ1 coverage, non-inferiority, production scalability or superiority over named literature systems from this pilot.


 powershell -NoProfile -ExecutionPolicy Bypass -File .\prism_annotator\install.ps1
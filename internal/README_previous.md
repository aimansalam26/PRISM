# PRISM Starter — version 0.1

Start here. This is a small, executable learning prototype for your HR-policy ReviewImpact project.
It includes synthetic policy text, a Python traversal engine, two comparison configurations,
a readable review packet and 10 behavior checks. It uses Python's standard library only.

**Tested here with Python 3.12.14.** Use Python 3.12 or newer; a current stable release is
available from [python.org](https://www.python.org/downloads/).

## 1. Run the example

Extract `PRISM_Starter.zip`. Open a terminal inside its `prism_starter` folder,
where `run_demo.py` is located.

On Windows:

```powershell
py --version
py run_demo.py
py -m unittest -v
```

If Windows recognises `python` instead of `py`, substitute `python` in those commands.
On macOS/Linux:

```bash
python3 --version
python3 run_demo.py
python3 -m unittest -v
```

No API key, database service, package installation or paid account is needed.
If Python is not found, install it from the official link above, reopen your terminal,
and check the version again. If the script is not found, check that your terminal
is inside the extracted folder containing `run_demo.py`.

Expected demo output:

```text
prism   : B-v1, C-v1 (2 candidates)
local   : B-v1, C-v1, D-v1 (3 candidates)
untyped : B-v1, C-v1, D-v1, J-v1, O-v1, S-v1 (6 candidates)
```

Open `output/review_packet.md` in a text or Markdown viewer. Open
`output/prism_results.json` to inspect individual path steps and scope changes.
These sample outputs are also included, so you can read them before running Python.
The demo replaces these four generated output files when rerun; it does not edit policy data.

## 2. Understand the example

The base equipment allowance changes from 500 to 600 budget units.
The affected population includes HQ engineers and managers in the UK and France
for September–December 2026. All documents and relationships here are synthetic.

| KO | Meaning | Expected behavior under the teaching rules |
| --- | --- | --- |
| A-v2 | Changed allowance rule | Starting point, excluded from the other-KO review set |
| B-v1 | UK manager procedure depending on A | Direct review candidate: UK managers |
| C-v1 | UK/France regional guidance depending on B for its UK content | Indirect review candidate: its inherited impact remains UK managers |
| D-v1 | France manager checklist depending on C's France content | No impact through the UK-only A–B–C–D path |
| J-v1 | Japan guidance connected to A | Pruned because the changed rule covers UK/France |
| O-v1 | Prior-period guidance connected to A | Pruned because its 2025 interval does not overlap this change |
| S-v1 | Subsidiary guidance connected to A | Pruned because the changed rule applies to HQ |

The local configuration forgets B's restriction once it examines C–D.
It sees that C and D both mention France and incorrectly includes D for this event.
The accumulated configuration remembers that this particular path only carries UK impact.
An independent valid path to D could still justify D's inclusion; one blocked path never
proves a KO is unaffected through every other path.

The date example deliberately has no retrospective review requirement. The final method must
handle historical evidence and withdrawals explicitly; this toy exclusion rule cannot settle those cases.

## 3. Read the files in this order

| File | Purpose |
| --- | --- |
| `BEGINNER_GUIDE.md` | Concepts, worked explanations and the route to the complete project |
| `data/policies.json` | The event, KOs, scopes and curated dependency links |
| `output/review_packet.md` | Human-readable result |
| `run_demo.py` | Reads data, calls the engine, writes outputs |
| `engine.py` | Scope intersection and graph traversal |
| `test_engine.py` | Behavioral examples that catch meaningful implementation mistakes |

## 4. Exact boundaries of version 0.1

- One curated graph snapshot; previous and revised root content is retained as evidence.
- One allowance-value change with unchanged scope and no relationship edits.
- Only ordinary `DEPENDS_ON` relationships explicitly referring to that allowance amount.
- Exact role, jurisdiction and organisation identifiers; no aliases or hierarchy inference.
- One scope cell per input object: combinations within that cell are intentionally permitted.
- Dates are half-open intervals: start included, end excluded. No timezone or time-of-day reasoning.
- Multiple path arrivals are kept separately. Their populations are not merged into a new cross-product.
- The default depth is three dependency steps. Cycles terminate at the cap.
- A KO is classified direct if any supporting path has one step; otherwise indirect.
  This is the starter's explicit rule, to be confirmed in the final methodology.
- Results are stable for the same inputs, rules and depth; no runtime timestamps enter the result.
- Input scope changes, exceptions, overrides and unknown scopes are rejected, not silently interpreted.

Semantic retrieval, diff-led lexical retrieval, withdrawal/removal handling, exception semantics,
deferral, scope unions, state subsumption, an independent computational evaluator,
independent annotations and research statistics are **not implemented yet**.
The `untyped` configuration currently only removes scope/time filtering: all supplied edges
are ordinary dependencies. It cannot yet test the contribution of a richer relation vocabulary.

The local configuration returns edge-local scope, not a claimed valid accumulated scope.
Untyped traversal does not output an affected scope. Do not score their missing scope outputs
as if they were incorrect scope predictions.

## 5. Your first change

1. Keep a copy of `data/policies.json` as `data/my_first_case.json`.
2. In the copy, find D-v1's `jurisdictions` list and change `["FR"]` to `["UK"]`.
3. Update D-v1's title and text to describe UK managers too. Metadata and source meaning must agree.
4. Predict the new review set on paper: B-v1, C-v1 and D-v1.
5. Run `py run_demo.py --data data/my_first_case.json` (or use `python3`).
6. Confirm that D-v1 has a three-step path with UK-manager scope.
7. Run the default demo again to restore the supplied sample outputs.

The unit tests load the original example, so edit the copy for experiments.

Your first milestone is complete when you can explain why the original France checklist is
excluded and why the UK version is included, then locate that reasoning in the JSON trace.

## 6. How this becomes the final project

Follow the milestones in `BEGINNER_GUIDE.md`. The next implementation task is to write
small expected-result examples for changes in scope and relationships, then define their
version contexts before extending the traversal. This executable prototype is a foundation;
the complete proposal remains the target.

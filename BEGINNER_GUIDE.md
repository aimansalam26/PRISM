# Learn PRISM by running one change

Start with the home-office stipend example. You do not need to remember every paper to follow this release.

## 1 Read the four provisions

The group stipend rises from 30 to 45 units for full-time employees. Country guidance uses the group amount for the Netherlands and Belgium. France keeps an independent fixed amount of 25. A payroll procedure uses those country amounts. A French claims guide points to that payroll procedure.

The question is which other provisions deserve review **because of this amount change**. It is not whether every provision could be improved or whether the policy is lawful.

Run:

```bash
python run_demo.py
```

Open `output/demo/review_packet.md`. PRISM selects the country guidance and payroll procedure for the Netherlands/Belgium scope. It does not propagate this group-amount change into the French claims guide. France's independent amount did not change.

## 2 Find the representation

Open `data/policies.json`. This is the same Scenario 5 used in the full suite, copied as a small demo input.

- `event` says which version and field changed.
- `nodes` contain the source text of each policy unit.
- `relationships` contain the declared connections and their source evidence.
- `scope` says which roles, countries, organisations and dates a connection covers.

An edge is an explicit claim about dependence. The program does not read the English and invent that claim. A person must curate it correctly. This is why expert review remains necessary even when the tests pass.

## 3 Carry the scope through the chain

The initial changed scope is all full-time employees in the group. The first inheritance step narrows the scope to the Netherlands and Belgium. The payroll step keeps those two countries. The France-only endpoint has no overlap with that accumulated country set.

The local comparison forgets the earlier restriction when it reaches the broad payroll node. Its last pair of nodes looks compatible, so it includes France. Open `output/demo/prediction_matrix.csv` to see the difference. This is the purpose of the local comparison: the methods have the same curated metadata, but one retains the earlier path restrictions.

## 4 Keep an exception separate from a dependency

“France pays a fixed 25 instead of the group amount” is an independent replacement of the amount. “France pays the group amount plus 10” would still depend on the group amount. The latter must continue to downstream guidance.

Do not make every exception a stop sign. Identify which property changes and which properties the exception still inherits. This prototype represents only the explicitly supported cases in `SPECIFICATION.md`.

## 5 Understand the Ireland case

Run the full suite with `python run_suite.py`. Ireland explicitly uses the number of parental-leave weeks given by the UK provision. Simply intersecting UK with Ireland would wrongly discard that connection.

An `ADOPTS_VALUE` relationship first checks the source scope, then maps the adopted value to the receiving scope. It is like a labelled bridge. The curator must justify the bridge and what it carries. This example carries the number of weeks, not an automatic assumption that Ireland also inherits UK eligibility conditions.

## 6 Understand uncertainty

The Sales case refers to unspecified portal rules while the revised clause excludes Sales. The supplied text does not settle the reference. A human curator marks that relationship uncertain. PRISM returns Defer and records why.

Defer means that someone must inspect the case. It does not mean “the algorithm correctly predicted a positive”. The workbook counts it in the human review queue but keeps it separate when scoring definite discoveries.

## 7 Read the code in this order

1. `run_demo.py`: loads a small case and invokes the runner.
2. `engine.py`, `validate`: refuses malformed or unsupported inputs.
3. `intersection`: keeps only overlapping scope.
4. `transfer`: implements ordinary inheritance and explicit adoption.
5. `discover`: carries states through the graph, recording selections and reasons.
6. `test_engine.py`: illustrates the behaviours that must keep working.
7. `reference.py`: provides a separately written computation for comparison.

When you change a rule, first write down a tiny example that distinguishes the intended behaviour from a wrong one. Add a behavioural test, make the change and rerun all tests. Do not edit only a scenario's expected answer until the test passes.

## 8 Your next working session

Run the demo and explain aloud why France is excluded. Then inspect the two uncertain references in the flight and audit cases. Check whether the packet gives a reviewer enough information to make an independent judgement. Ask one or two volunteers to pilot the instructions before sending the full set more widely.

After their answers arrive, enter and adjudicate them without forcing agreement with the graph. Classify disagreements as a wording/annotation issue, a representation issue, an unsupported semantic case or an implementation error. A real false negative is a justified gold-positive missed by PRISM; a disagreement with your own design expectation is not yet an independent result.

The next implementation milestone is dual-version change handling on a few carefully written withdrawal/scope-contraction cases. Then add the promised retrieval baselines and a larger corpus with new policy families. Keep this development set separate from the final test set.

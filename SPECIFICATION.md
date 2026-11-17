# Implemented semantics

Version 0.2.0 uses schema 0.3. The input is a curated graph, not raw text awaiting semantic extraction. `event.changed_fields` identifies what changed. Each transmitting relationship names the field it depends on and quotes source evidence.

## Direction and initial state

Edges are stored from **prerequisite to dependent** so discovery follows the direction of possible change impact. A statement that B depends on A is stored A → B. This convention is deliberate even when the edge label is `DEPENDS_ON`.

The initial state contains the revised root, one changed field, the intersection of `change_scope` with the revised root scope, and an empty path. Before-version evidence is preserved for inspection. It is not traversed by this release. Known differences in old/new population, a withdrawal event, or declared relationship changes are rejected. Do not hide an unsupported change by setting its flags to false.

The flight scenario has no supplied previous text. Its `revised_clause_only` basis is explicit. It cannot establish whether the Sales exemption was newly introduced or discover lost old applicability.

## Scope cells

A cell contains sets of role, jurisdiction and organisation identifiers plus a half-open interval `[start, end)`. A change effective on the day an edge stops being valid has no temporal overlap with that edge. Dates use ISO `YYYY-MM-DD`.

`["*"]` means explicitly unrestricted in that dimension. It does not mean unknown. `0001-01-01` and `9999-12-31` are finite implementation sentinels for an unspecified lower/upper bound; they are not historical dates asserted by the source. The terminal sentinel itself is excluded by half-open semantics.

Node and edge records accept either `scope` or a nonempty `scope_cells` list. Cells form a disjunction. Within each cell, dimensions form a conjunction. “French managers OR German engineers” is two cells. Combining their role sets and country sets into one cell would invent French engineers and German managers and is prohibited.

Identifiers are normalized by the curator. There is no automatic hierarchy, role synonym expansion, employee eligibility calculation, or organisation taxonomy. The `eligible_employees` identifier in the parental-leave scenario stands for the supplied qualification. Human scope notes must retain its six-month-service meaning. An administrator is not automatically a member of the affected employee population.

## Relationship transitions

| Type | Selection and continuation |
|---|---|
| DEPENDS_ON | For a matching changed field, intersect incoming, edge and target scope. Select and continue only for nonempty cells. An offset such as “parent amount plus 100” remains a dependency. |
| RELATED_TO | A topic association. Does not select or propagate in typed modes. |
| ADOPTS_VALUE | Check the explicit source-population guard, replace only the mapped dimensions, then intersect with destination edge and KO scope. Preserve dates and unmapped constraints. Limited to value changes. |
| OVERRIDES with independent_value | A confirmed independent replacement of the named value. It does not transmit this value change or select its replacement-only scope under this pilot convention. Other inherited conditions require their own field-specific relationship. |
| REVIEW_ONLY | A supported nonempty scope selects the target for review, then stops that path. This capability is exercised by a behavioural test rather than a scored pilot case. |

There is no rule that every exception stops propagation. An unsupported override mode or unknown relation type raises an error. A confirmed dependency and independent replacement between the same endpoints for the same field must have disjoint scopes; overlapping declarations are rejected instead of being assigned an invented priority.

Ireland's adoption maps the UK source population to the Irish destination for the **number of weeks**. The source eligibility dimension is explicitly replaced by the destination population rather than silently imported. That is a curated interpretation of the wording, subject to representation review, not an inferred legal rule.

## Uncertainty

`certainty: "uncertain"` needs an explanation. For a potentially relevant changed field, the typed methods return Defer when temporal overlap remains. Uncertainty can concern the reference itself and therefore the applicability constraint; spatial incompatibility alone is not used to prove exclusion on that uncertain link.

The possible path continues up to the hop limit with unknown scope, producing deferred downstream candidates. Field/topic exclusions and known temporal disjointness still stop it. This is deliberately conservative. It may increase review volume. A confirmed alternative path yields Yes and retains the additional uncertainty flag.

The engine does not infer uncertainty from natural language. Three relationships in this pilot were manually marked unclear because of source wording. These marks are inputs to both typed methods. They must not be presented as an algorithmic ambiguity-detection result or as gold labels.

Missing/malformed scope, an unknown relation type and missing provenance are input errors, not silent No predictions.

## Comparisons

PRISM retains each accumulated cell through every hop. The local comparison uses the same types, changed fields, mappings, uncertainty handling and fixed-replacement rules. At the second and later steps it resets the scope to the current node's declared cells within the event's time window, then checks the current edge and target. Earlier restrictions are forgotten. This definition makes the comparison repeatable and isolates retained path information in supported cases.

Untyped traversal follows every declared relationship, including topic associations and replacements, up to the same depth. It does not predict applicability. Beating it can demonstrate the combined value of curated metadata and semantics; it does not alone demonstrate the value of accumulated scope. Local comparison addresses that narrower question. All comparisons operate on the same root and maintained candidate universe.

The input associations must be evidence-based; do not insert arbitrary edges to make untyped traversal look poor. A later evaluation can add a dependency-only untyped sensitivity analysis.

## Paths and stopping

The maximum supported depth is three impact edges. The root is not a candidate. All other supplied KOs receive a status, including unreachable objects. Distinct supporting paths and cells are retained. A KO is direct if any definite path has one step; otherwise a definite multi-step arrival is indirect. The full paths preserve cases that also have an indirect route.

Cycles terminate because depth is bounded. This implementation enumerates states; it makes no scalability claim. It performs no dimension-wise scope union, dominance pruning or general fixed-point computation.

`reference.py` enumerates structural paths up to the same bound and evaluates them afresh using separately written scope operations. It imports no engine transitions. Its agreement checks positive/deferred path status, field, scope and continuation/stop action. It does not establish that the graph represents the policy correctly and is not an independent human annotation process. Hand-authored behavioural tests supply additional checks on expected outcomes.

## Evaluation boundaries

Gold refers to a separately adjudicated need for review from source text. Researcher design intent, graph validity, reference agreement and PRISM predictions are four different things. The independent reference must never populate gold.

The workbook retains two original coder labels, adjudicated gold, reasons, separate scope cells and path decisions. Kappa concerns the original coder answers, not engine correctness. `evaluate.py` scores candidate discovery only, with explicit ambiguous/deferred counts, pooled and macro measures, and no-impact denominator conventions. Scope and propagation assessments are recorded for manual review until a separately specified scope-scoring implementation is added.

These seven synthetic development scenarios are not independent policy families for a final inferential study. No non-inferiority interval, statistical significance or complete transitive recall claim is produced here.

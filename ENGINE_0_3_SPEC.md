# PRISM engine 0.3.0 — operational contract

## Inputs and compatibility
Schema 0.3 retains roles/jurisdictions/organisations with known ISO dates. Schema 0.4 uses employment_types/org_roles/entities/jurisdictions plus start/end. The two role dimensions are separate AND constraints; alternatives inside one list are OR. Multiple scope cells are separate correlated cases and never merged dimension by dimension. Schema 0.4 null denotes unknown. Literal unknown/unspecified population identifiers are rejected in both schemas. An explicit `['*']` is universal and must be justified by the caller; annotation conversion does not admit inferred wildcards.

Start is inclusive and end exclusive. Missing dates stay null. A commit date is provenance, never a policy effective date. The annotation converter requires declared inclusive/exclusive end semantics when known end dates occur. Inclusive dates are deterministically converted by adding one day and the declaration/original annotation scopes are retained. Per-record end conventions can be specified in the event JSON using a map from original node/edge ID to inclusive or exclusive.

Only value_change/rule_change events are supported. Scope withdrawals and relationship changes require a different, dual-snapshot algorithm and are rejected. Unknown prior scope requires explicit revised_clause_only analysis; that is not a claim to cover effects on withdrawn populations. A multi-cell revised root is supported; the converter requires selecting the change case when more than one exists.

## Traversal
FIFO entries carry node, current field, possible scope bounds, edge/node history, scope uncertainty and relationship uncertainty. A path never revisits a node. Depth is bounded to 1–3 hops. No text search occurs during traversal. Missing edges therefore remain a graph-recall limitation.

| Relation | Known confirmed path | Unresolved path |
|---|---|---|
| DEPENDS_ON / CALCULATES_VALUE | Intersect scope, flag, transfer mapped field(s), enqueue | Defer and enqueue possible path |
| ADOPTS_VALUE | Apply explicit from/to mapping to population dimensions, intersect target-side edge/target scopes, transfer field(s) | Retain uncertainty; no definite scope assertion |
| REVIEW_ONLY | Flag target, never enqueue | Defer target, never enqueue |
| OVERRIDES | Confirmed independent_value blocks transmission | Uncertain override is deferred for review, never propagated |
| RELATED_TO | Exclude | Exclude |

Only explicitly matching source trigger fields are considered. Propagative mappings can rename a field and branch to several output fields; each is its own queue entry. Terminal/blocked relations have trigger_fields but no output field. Legacy single `field` relationships retain identity transfer. CALCULATES_VALUE denotes dependency on a calculation input; the engine does not execute arithmetic.

For a confirmed relation with unknown applicability, intersection computes possible bounds. Any known categorical contradiction or known non-overlapping time bounds can prune the path. Otherwise the path is Defer, even if other constraints narrow the possible bounds to known-looking values. An unknown input must not become definite merely by meeting a known target. `possible_scope` is diagnostic only and is not part of `affected_scopes`.

An uncertain relationship can undermine population-based pruning; its path uses temporal possibility, remains Defer and carries relationship uncertainty forward. Confirmed independent-value overrides still block, and REVIEW_ONLY is terminal regardless of uncertainty. No false-positive-free or complete-recall claim follows from these choices.

ADOPTS_VALUE is an explicit dimension transformation. Unmapped dimensions and time do not widen; the mapped population changes by the declared relation. This is not ordinary set-subset monotonicity across jurisdictions.

## Outputs and evaluation
Yes requires at least one supported definite path. Defer means only possible paths exist. No means no supported path within this graph and hop bound, not a universal no-impact assertion. A definite path can coexist with deferred alternatives. All paths retain field transfer and source evidence. Untyped reachability intentionally ignores relationship/scope semantics; local baseline resets scope at intermediate nodes as before.

The independent reference enumerates bounded simple paths without importing the engine's transfer/intersection code. Agreement checks computation, not policy truth. Existing frozen gold labels must be scored against newly recomputed results; old result hashes/metrics are not reused. Researcher/final annotation approvals are not change-impact gold labels. Requirement groups are preserved as metadata; the engine is not an employee eligibility evaluator.

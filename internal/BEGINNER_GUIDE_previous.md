# PRISM: a beginner's guide from first example to finished project

## 1. Start with the decision

A policy has changed. PRISM helps answer: **which other policy units need a person to review
them, for whom, during which period, and why?**

Imagine an HR officer receives a new equipment-allowance rule. They also maintain purchasing
procedures, local guidance and checklists. Some depend on that allowance; some only look
similar. PRISM prepares a review list with evidence. The HR officer makes the eventual decision.

The working direction from Chapters 1 and 2 is sufficient to begin a learning prototype.
Keep a short decision log for details discovered during implementation. The finished method,
experiments and claims must eventually agree with Chapter 3 and with the revised literature review.
Beginning the code does not establish that every novelty or methodology question is resolved.

## 2. The building blocks

| Concept | Plain explanation | PRISM example |
| --- | --- | --- |
| Policy | A maintained rule or guidance document | Equipment allowance policy |
| Corpus / knowledge base | The collection being studied or maintained | Rules, guides and checklists |
| KO | One version of a policy unit that can be reviewed meaningfully | A clause stating the allowance and its qualifications |
| Stable identity and version | The same maintained unit across different saved states | A is the unit; A-v1 and A-v2 are versions |
| Metadata | Structured facts describing a KO or relationship | Role, country, department, dates, source |
| Change event | A record of what changed, before and after | A-v1 says 500; A-v2 says 600 |
| Dependency | A reason one unit relies on another | Purchasing procedure B uses allowance rule A |
| Graph | Objects connected by relationships | A, B and C with dependency links |
| Node | An object in the graph | KO B-v1 |
| Edge | One relationship between objects | B depends on A |
| Typed edge | A relationship with an explicit meaning | Dependency versus exception versus version lineage |
| Path / hop | A sequence of links / one step along it | A → B → C is two hops |
| Traversal | Following links to examine possible consequences | Start at A and visit dependent B, then C |
| Candidate universe | All objects eligible to be considered in an experiment | The six non-seed KOs in the starter |
| Predicted review set | The candidates the method selects | B-v1 and C-v1 in the default example |

Dependency direction is easy to confuse. The statement **B DEPENDS_ON A** points from B to
A if stored literally. To investigate a change in A, traversal must find B, the dependent.
The starter uses explicit `prerequisite` and `dependent` fields so the direction is visible.

A graph database is a storage choice. A Python list of nodes and links is enough to learn
the algorithm. Keep the conceptual schema stable when adding a database later.

## 3. ReviewImpact and OutcomeImpact

**ReviewImpact:** there is a justified reason to examine B after A changes.
**OutcomeImpact:** after examining the evidence, a reviewer decides that B actually needs a
content or lifecycle change.

The review might conclude that B remains valid. That does not automatically mean that asking
for review was wrong. Evaluation must use the agreed definition of justified review.

“Direct” means supported by one eligible dependency step. “Indirect” means supported by
multiple steps. When both kinds of path exist, apply a stated classification rule. Version
lineage is useful evidence but does not automatically count as an impact-propagating step.

## 4. Applicability: who, where, which organisation and when?

A scope answers four questions:

- Role: which categories of employee?
- Jurisdiction: which country or other defined jurisdiction?
- Organisation: which organisational units?
- Time: which effective period?

For the toy example, scopes use exact identifiers such as `manager`, `UK` and `HQ`.
The code does not infer that one role or organisational unit contains another. That requires
an explicitly defined hierarchy or normalisation procedure later.

An intersection keeps what two scopes have in common. UK-or-France intersected with UK
leaves UK. UK intersected with France is empty. All four dimensions must be compatible.
Sharing a country cannot compensate for incompatible roles or non-overlapping dates.

The starter represents time as `[start, end)`: start included, end excluded.
`2026-09-01` to `2027-01-01` covers September–December 2026. It does not include 1 January 2027.
Two intervals that only touch at an endpoint do not overlap under this convention.

## 5. Why the whole path matters

| Step | What the next KO covers | Scope still carried from the change |
| --- | --- | --- |
| A, the changed rule | UK and France, engineers and managers | UK and France, engineers and managers |
| B, the purchasing procedure | UK managers | UK managers |
| C, the regional guide | UK and France | Still UK managers |
| D, the France checklist | France managers | Empty along this path |

A **local check** looks at the current link. When it examines C–D, both mention France.
An **accumulated check** also remembers the restriction encountered at B. France was already
lost on this path, so C's wider scope cannot reintroduce it.

The information carried with one arrival is called its **state**: current KO, accumulated
scope and supporting path. Applying a relationship's rules to that state is a **transition**.
The idea of propagating and transforming information through a graph is related to established
dataflow analysis. The research contribution must concern the specified HR task and evaluation,
not claim that graph propagation itself is new.

**Pruning** stops investigating a path when its known constraints make it inapplicable.
**Termination** may also follow a supported relation rule or the declared hop boundary.
**Deferral** means the available information is insufficient for a reliable decision and needs
human examination. Unknown does not mean unaffected. The starter rejects unknown input;
later versions must implement and evaluate explicit deferral.

## 6. Several paths can reach the same KO

One path to C might carry UK managers. Another might carry France engineers. Both can be
valid. Keep both scope combinations. Combining countries and roles independently would
invent UK engineers and France managers, which neither path established.

Do not mark a node permanently visited merely because one path reached it. Another path
may carry different applicability. A future optimisation may merge equivalent or subsumed
states, but only after defining when doing so preserves results and required evidence.
Version 0.1 simply keeps separate arrivals. This is understandable but can be expensive as
the graph grows. Its hop cap also makes cyclic graphs terminate.

## 7. Exceptions and overrides need meaning, not just labels

Suppose the base allowance is 500:

- A local rule saying “base allowance plus 100” still depends on that amount. Changing the
  base can affect a downstream local checklist.
- A local rule saying “fixed allowance of 700, independent of the base amount” behaves
  differently for this particular amount change. Its eligibility conditions may still rely
  on the parent rule, however.

Selection for review and permission to continue propagation are separate decisions.
Do not turn every `EXCEPTION_TO` or `OVERRIDES` edge into an unconditional stop sign.
Define supported cases using the changed field or clause, remaining scope and what the
local rule inherits or replaces. Version 0.1 deliberately does not implement these relations.

## 8. Previous evidence remains relevant after a change

If an old rule covered France and Germany and its replacement covers Germany only, a France
handbook might need review because it loses coverage. Starting only from the new German scope
could hide the very effect being investigated.

Similarly, removing a dependency does not prove there is nothing left to review. Existing
guidance can still rely on the old arrangement. Preserve relevant previous and revised scopes,
relationships and source versions. Identify whether a finding follows a pre-change or
post-change context. Do not combine edges from different snapshots into a path that never existed.

The affected scope of a change therefore need not equal the applicability of the revised policy.
Version 0.1 retains previous text but does not yet compute across historical graph snapshots.

## 9. Evidence and human authority

A useful review packet should eventually contain the event, candidate KO, source/version
references, directness, supporting paths, affected scope, scope transitions and continuation,
termination or deferral reasons. State what is known and what remains unresolved.

**Provenance** is the record of where the evidence came from and how the recommendation was
produced. **Reproducibility** means fixed inputs and rules produce the same recorded result.
Neither guarantees that the original policy interpretation or curated relationship was right.

A reviewer must be able to reject a candidate, question its scope or ask for further work.
Policy revision, supersession and archival require authorised decisions outside this prototype.

## 10. RAG and the comparison methods

RAG retrieves outside information and supplies it to a language model generating an answer.
It explains why maintaining reliable evidence matters, but generating answers is outside this
project's principal task. PRISM's first engine does not need an LLM.

| Method or concept | What it does | What the comparison can tell us |
| --- | --- | --- |
| Semantic retrieval / embeddings | Represents meaning as numerical vectors and retrieves similar text | Whether dependency-based discovery helps relative to meaning-based association |
| Document differencing | Identifies changed wording between versions | Supplies change terms; alone it does not find other affected KOs |
| Diff-led lexical retrieval | Searches other KOs using wording extracted from differences | Whether changed wording is enough for this review-discovery task |
| Untyped traversal | Follows graph links without applicability reasoning | The consequence of selecting reachable objects broadly |
| Local-scope configuration | Uses the same metadata but checks links locally | Whether accumulated path state adds value beyond having metadata |
| Ablation | Removes one specified component while retaining others | The effect of that component under the experiment's conditions |
| Independent exhaustive evaluator | Separately computes small-graph results from the formal rules | Whether the main implementation computes those rules correctly |

Beating a text-only method does not isolate the benefit of accumulated path state when PRISM
also receives curated metadata. That is why the local comparison is essential. The starter
implements accumulated, local and untyped configurations only.

The independent evaluator must be implemented separately; running the same traversal function
under another name is not an independent computational check. It receives graph inputs and
specified semantics, not PRISM predictions or gold labels as reasoning inputs. The experimental
evaluator compares its outputs with PRISM's outputs.

## 11. What counts as evidence that the project works?

Three different questions need separate checks:

1. **Domain:** do the policies justify reviewing this KO for this scope?
2. **Representation:** does the curated graph correctly describe those policies?
3. **Computation:** does the engine correctly follow the specified graph rules?

Independent annotation addresses the first question. Graph verification addresses the second.
Behavior tests and an independent computational reference address the third. The 10 supplied
tests are teaching and regression checks, not an independently annotated benchmark.

| Measure | Beginner explanation |
| --- | --- |
| True positive | A selected KO that independently merits review |
| False positive | A selected KO that does not merit review under the annotation rules |
| False negative | A KO meriting review that the method missed |
| Precision | Correct selections divided by all selections |
| Recall | Correct selections divided by all gold affected KOs |
| F1 | Harmonic mean of precision and recall: 2PR/(P+R) when defined |
| Direct / indirect recall | Recovery of immediate dependencies versus consequences further away |
| Scope accuracy and coverage | Whether the returned populations and periods are correct and complete |
| Propagation decision correctness | Whether continuation or termination is justified at the relevant boundary |
| Trace validity and completeness | Whether supplied evidence is valid and meets the stated evidence-coverage definition |
| Review volume | Unique KOs a human must inspect, including deferred candidates; deduplicate overlap |
| Runtime / visited states | Execution time and the amount of graph exploration |

Returning the right handbook with the wrong affected population can still receive KO-level
credit, so KO F1 is insufficient. Score scope and boundary decisions separately.
Trace completeness must have an explicit definition; do not require every redundant raw path
if the specification only promises representative evidence covering each distinct scope.

No-impact events and ambiguous cases need scoring rules fixed before testing. Retrieval must
be allowed to return no candidates using a justified threshold. Missing structured outputs
from text retrieval should not be scored as invented incorrect scope predictions.

When untyped traversal enumerates the same reachable universe under the same seeds, direction
and depth, a filtering method normally trades some reachability for greater selectivity. The
planned claim is fewer unnecessary candidates with acceptable recall preservation.
**Non-inferiority** asks whether the uncertainty around the recall difference supports that
the loss is within a justified, pre-specified margin. A small observed loss alone is insufficient.

## 12. Build the corpus carefully

Begin with clearly documented synthetic examples. Then add permitted public policies for
realistic language. Keep the two source types distinguishable. Existing QA, conflict and
formalisation labels are not automatically ReviewImpact labels.

For the research corpus, annotate policy meaning independently of PRISM predictions. Record
disagreement and ambiguity. Include unaffected objects, no-impact events, contractions, removed
links, alternate paths and difficult exceptions. Record data sources and reuse permissions;
the planned corpus excludes employee records and confidential personal information.

Keep all versions and related change events from one policy family in the same split.
Training/development material is used to construct or tune choices; held-out test material
assesses the frozen method. Even without model training, thresholds and rule refinements can
overfit examples. Forty events from eight families are not forty independent policy families.
Report family, version, event, KO and event–candidate counts separately and account for family
dependence when estimating uncertainty.

The proposed minimum of eight families and 40 events is a planning target, not a guarantee
of sufficient statistical power. Reassess the claim if diversity or uncertainty is inadequate.

## 13. The small amount of Python needed first

| Python concept | Plain meaning | Where you see it |
| --- | --- | --- |
| Variable | A name for a value | `root` stores the changed KO identifier |
| List | An ordered collection | `nodes` and `relationships` in JSON |
| Dictionary | Named fields and their values | A node's `id`, `text` and `scope` |
| Set | A collection supporting overlap operations | Shared countries or roles |
| Condition | Run something when a rule is true | Stop when an intersection is empty |
| Loop | Repeat an operation | Examine each outgoing dependency |
| Function | A named reusable operation | `discover` or `intersect` |
| Queue | Work waiting to be processed | Breadth-first traversal starts with nearby KOs |
| Dataclass | A compact definition of a structured value | `Scope` groups the applicability fields |
| JSON | A text format for structured data | The input file and result packets |
| Test | A check of expected behavior | A France-only continuation after a UK-only path must fail |

Read the toy data first. Then read `run_demo.py`, `Scope.intersect`, and finally `discover`.
Trace one path on paper before trying to understand every line. The official
[Python tutorial](https://docs.python.org/3/tutorial/) is useful reference material once you
have these programming basics; it assumes some general programming understanding.
The checks use Python's built-in [unittest](https://docs.python.org/3/library/unittest.html).

## 14. Milestones from here to completion

| Stage | Build / decide | Evidence needed before moving on |
| --- | --- | --- |
| 1. Learn the core — supplied now | Load toy KOs; traverse dependencies; intersect all four scope dimensions; output a packet; compare local and untyped modes | Explain the two-versus-three-versus-six result and pass the starter checks |
| 2. Specify the full semantics | Written examples for old/new context, withdrawals, removed links, partial inheritance, correlated cells and unknowns; settle directness and depth rules | For each example, a justified expected review set, scope and propagation decision |
| 3. Implement the supported semantics | Snapshot-aware inputs, relation-specific transitions, separate inclusion/continuation, deferrals and correct multipath handling | Each agreed example works; unsupported interpretations are explicit |
| 4. Check computation independently | Separate small-graph exhaustive evaluator; compare objects, scope and decisions | Agreement on a diverse set of small graphs, with mismatches investigated |
| 5. Prepare the research corpus | Source register, independent annotation, graph verification, family splits and ambiguity rules | Auditable labels and provenance; development/test separation before tuning |
| 6. Complete comparisons | Semantic and diff-led lexical retrieval; richer untyped traversal; local comparison and other precise ablations | Same event information/candidate units and declared input differences; development-only tuning |
| 7. Run the frozen evaluation | KO, scope, propagation, trace and execution measures; family-aware uncertainty; justified recall-margin decision | Reproducible results, limitations, errors and positive/negative/mixed findings |
| 8. Finish the review prototype and dissertation | Inspectable packet interface, setup instructions, versioned release, result tables, discussion and demonstration | Another person can reproduce an experiment and follow one recommendation back to evidence |

Storage and interface work can be added after the core data contract stabilises. If the
proposal commits to a property-graph database, introduce it as a storage adapter while keeping
the traversal behavior testable. A graphical interface should present evidence clearly and
preserve human authority; it is not evidence of discovery accuracy by itself.

Use version control before substantial extensions and keep a brief decision log. Commit a
working milestone before changing semantics. Keep the tutorial dataset as a development
fixture; never present its deliberately constructed results as held-out research findings.

The project is complete when the implementation, bounded claims, independent checks,
dataset documentation, evaluation and dissertation tell the same reproducible story.
Better-looking demo results alone are not a completion criterion.

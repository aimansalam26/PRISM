# Changes and next steps

This package corrects the supplied seven-scenario archive. The original scenario data and author expectations are retained in `internal` for comparison. No volunteer labels were supplied or invented.

## Engine corrections

| Original problem | Correction | Why it matters |
|---|---|---|
| Declared relationship types and fields were not used | Typed modes check relation semantics and the changed field | Similar subject matter no longer automatically creates impact. |
| UK/Ireland intersection removed explicit adoption | A guarded source-to-destination mapping handles value adoption | Cross-country dependence can survive without pretending the countries overlap. |
| Fixed replacements propagated like ordinary inheritance | Explicit independent-value replacement stops that value | Italy/France/Thailand replacement amounts do not inherit a changed parent amount. |
| Unclear references could be returned as definite Yes or No | Curated uncertain links produce Defer with no invented scope | Ambiguity reaches the human queue visibly. This is manual metadata, not automatic language understanding. |
| Administrator metadata could be mistaken for the affected population | Group Finance and German managers are recorded separately as administrators where appropriate | Scope describes the people whose guidance needs review. |
| Legacy wildcards and malformed values could silently alter scope | Strict schema and identifier checks | Invalid inputs fail explicitly. |
| Only printed sets were available | JSON traces, a review packet, prediction CSVs and an independent path reference | A reviewer can inspect the evidence and reproduce the run. |

The proposed changes to the uncertainty annotations concern S2-C2, S4-C1 and S6-C1. Their explanations are in the JSON. Review them as representation judgements. They were not established by independent volunteers.

The prior source's before-version scopes began on the revised effective date and stayed open. Their stored intervals now end at the revised effective date. The unknown historical start uses a documented sentinel. Scenario 2 still has no supplied old text; it remains a revised-clause-only example rather than an invented old policy.

All candidate policy wording in the latest archive is retained. Previous provisions are now visible beside revised provisions in the volunteer packet. The parental case explicitly says the stated change concerns weeks, without asserting a change to eligibility. Practice remains unscored.

## Workbook corrections

- Initial coder labels, adjudicated gold and model predictions remain separate and blank.
- The three prediction columns accept Yes, No and Defer.
- Recall no longer silently drops deferred positives. Review-capture recall is reported separately.
- Review volume counts Yes plus Defer, including ambiguous cases requiring inspection.
- Missing labels/predictions prevent comparison scores rather than shrinking the denominator unnoticed.
- Scenario design groups are no longer described as gold direct/indirect impact classes.
- Human directness, correlated scope cells, qualifications, end dates and path decisions have explicit places.
- Historical developer discrepancies are marked as development findings; their gold column is blank.
- A corpus hash ties the workbook to the scenario version. The CLI refuses mismatched versions.

The author-intent sheet is preserved for provenance. It is a reason to keep this workbook with the researcher. It is not an answer key for volunteers.

## What the checks establish

Behavioural tests exercise known outcomes for field filtering, adoption, fixed replacement, dependent offsets, review-only stops, uncertainty, correlated cells, alternate paths, temporal boundaries and invalid input. The full pilot is compared with a separately implemented bounded path evaluator. Formula probes check that deferred positives and blank predictions change the spreadsheet scores correctly. These checks support implementation correctness under the written rules.

They do not establish that the rules or curated edges are correct interpretations of HR policy. They also do not turn the pilot into a held-out experiment. Strong agreement with the developer's intended cases is expected after debugging and must not be advertised as research accuracy.

## Next moves

1. **Demonstrate this release.** Run the tests, the three-candidate demo and the full suite. Explain one confirmed path, one excluded path and one deferred case.
2. **Pilot the annotation instructions.** Give one or two volunteers only the Word files. Ask which words or references prevented a decision. Record their original answers and relevant experience.
3. **Review disagreements.** Keep source interpretation, graph representation and code behaviour as separate questions. Fix only the layer justified by evidence. Version any corrected label or source text.
4. **Add dual-version semantics.** Before implementing withdrawals or scope contraction, define the event and old/new graph contexts with a small example. This version explicitly does not support them.
5. **Complete the comparison plan.** Add semantic and diff-led lexical retrieval over the same KO universe, and independently specified scope/decision metrics. Keep thresholds fixed before testing.
6. **Build fresh evaluation families.** Use policy families not involved in debugging, include no-impact and difficult negative events, independently annotate, and freeze the split and scoring protocol.

You can hand in this release as a development prototype with its demonstration and limitations. Describing it as the finished dissertation evaluation would overstate what has been completed.

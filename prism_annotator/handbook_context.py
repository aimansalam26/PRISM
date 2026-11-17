"""Heading hints are context, never rules or proof of applicability."""
import re

def context_for(section):
    path=section.get('heading_path',[])
    title=section.get('disclosure_title') or (path[-1] if path else '')
    t=title.casefold()
    category='mixed'
    for pattern,label in [(r'eligib|qualif','eligibility'),(r'how to|enroll|apply|claim|access','procedure'),(r'important dates|deadline','deadline'),(r'entitlement','entitlement'),(r'coverage|features','benefit_rules'),(r'exception|exclusion','exception')]:
        if re.search(pattern,t):category=label;break
    return {'topic_path':path,'disclosure_title':section.get('disclosure_title'),'heading_hint':category,'notice':'Hint only. Classify the actual clause. Headings do not establish universal scope.'}

GUIDANCE='''GitLab handbook guidance: use the topic heading AND disclosure title to interpret each target. For example Medical Allowance / Eligibility Requirements / Full-time employment status means eligibility for that allowance requires full-time employment, not that all GitLab benefits require it. Write a standalone summary naming the benefit/topic and preserving every condition, negation, amount, unit and timing. Keep the source_quote verbatim; never prepend a heading to it. Eligibility bullets are separate requirements; preserve AND/OR, nested-list parent conditions and alternatives, and do not invent their connective when ambiguous. An eligibility requirement is itself a rule, not merely disposable metadata. Set rule_kind to eligibility, entitlement, calculation, deadline, procedure, obligation, exception, or other according to the clause (the heading_hint is not authoritative). A procedure can be a rule when it mandates an action; a mere contact/link is not. A cap and frequency may remain together if they define one value; separate independently changeable obligations/deadlines. Context may resolve the subject but any inherited applicability needs exact contextual evidence in scope_evidence and human review. Missing dates remain unknown. Never assume a sibling eligibility condition governs unrelated benefits. Do not manufacture dependency edges from common wording or equal numbers.'''

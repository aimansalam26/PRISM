"""Apply four reviewed edits; validate exact quotes. Python 3.9+, no packages.
Default input/output directory: data_pipeline/artifacts relative to this script.
All other audit decisions remain open. Output is NOT a verified/gold dataset.
"""
import argparse
import copy
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'artifacts')
    args = parser.parse_args()
    folder = args.artifacts
    kos = json.loads((folder / 'kos_proposed.json').read_text(encoding='utf-8-sig'))
    sections = json.loads((folder / 'parsed_sections.json').read_text(encoding='utf-8-sig'))
    require(isinstance(kos, list) and len(kos) == 103, 'Expected exactly 103 KOs.')
    require(isinstance(sections, list), 'Sections must be a JSON list.')
    original = copy.deepcopy(kos)
    by_id = {k['ko_id']: k for k in kos}
    by_section = {s['section_id']: s for s in sections}
    require(len(by_id) == len(kos), 'Duplicate KO IDs.')
    require(len(by_section) == len(sections), 'Duplicate section IDs.')
    changes = []

    def replace(kid, container, field, old, new):
        require(container[field] in (old, new), f'{kid}: unexpected {field}; review manually.')
        if container[field] != new:
            changes.append({'ko_id': kid, 'field': field, 'before': old, 'after': new})
            container[field] = new

    for number, label in [(1, 'Company-Wide Benefits'), (2, 'Entity-Specific Benefits')]:
        kid = f'KO_GLOBAL_BASELINE_{number:02}'
        ko = by_id[kid]
        source = by_section[ko['provenance']['section_id']]['raw_text']
        # Retrieve the actual source sentence; do not reconstruct or normalize it.
        matches = [line for line in source.splitlines() if line.startswith(f'**{label}** ')]
        require(len(matches) == 1, f'{kid}: expected exactly one source sentence.')
        exact = matches[0]
        old = exact.replace(f'**{label}**', label, 1)
        replace(kid, ko['evidence'], 'source_quote', old, exact)

    kid = 'KO_NL_MEDICAL_02'
    scopes = by_id[kid]['applicability_tuples']
    require(len(scopes) == 1, f'{kid}: expected one applicability tuple.')
    replace(kid, scopes[0], 'employment_types', ['unspecified'], ['full_time'])
    kid = 'KO_NL_SICK_VACATION_20'
    replace(kid, by_id[kid]['semantics'], 'watched_fields',
            ['vacation_days_pro_rata_on_termination'], ['vacation_days_proration_partial_year'])

    failures = []
    for ko in kos:
        kid, provenance = ko['ko_id'], ko['provenance']
        source = by_section.get(provenance['section_id'])
        if source is None:
            failures.append(f'{kid}: missing cited section')
            continue
        quote = ko['evidence']['source_quote']
        # Strict Unicode substring check: no stripping, casefolding, fuzzy matching,
        # Unicode normalization, or Markdown cleanup.
        if not isinstance(quote, str) or not quote or quote not in source['raw_text']:
            failures.append(f'{kid}: source_quote is not an exact nonempty substring')
        for field in ('source_file', 'source_sha256', 'line_start', 'line_end',
                      'heading_path', 'disclosure_title'):
            if provenance[field] != source[field]:
                failures.append(f'{kid}: provenance mismatch in {field}')
        if provenance['section_outgoing_links'] != source['outgoing_links']:
            failures.append(f'{kid}: section links mismatch')
    require(not failures, 'Validation failed; no output written:\n' + '\n'.join(failures))
    changed_ids = [a['ko_id'] for a, b in zip(original, kos) if a != b]
    output = folder / 'kos_corrected.json'
    output.write_text(json.dumps(kos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = {'exact_quote_matches': 103, 'total_kos': 103, 'pass_percentage': 100,
              'provenance_checks_passed': True, 'changed_ko_ids': changed_ids,
              'changes': changes, 'annotation_status': 'Unchanged; still proposed',
              'limitation': 'Exact quote matching does not establish semantic correctness.'}
    (folder / 'ko_fix_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PASS: 103/103 quotes match their cited sections character-for-character (100%).')
    print(f'Changed {len(changed_ids)} KOs. Original input unchanged. Output: {output}')
    print('Other audit findings remain open; this is not kos_verified.json.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(f'ERROR: {error}')

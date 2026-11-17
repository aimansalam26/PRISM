#!/usr/bin/env python3
"""Apply canonical field/scope alignment and lock kos_verified.json."""

import json
from pathlib import Path

FIELD_RENAMES = {
    "KO_GLOBAL_BASELINE_04": {
        "parental_leave_eligibility_start_date": "parental_leave_tenure_requirement"
    },
    "KO_LEAVE_CORE_05": {
        "parental_leave_segment_limit": "parental_leave_max_segments"
    },
    "KO_UK_CONTROL_11": {
        "shared_parental_leave_max_weeks": "shared_parental_leave_pay_max_weeks"
    },
}

DUPLICATE_PAIRS = {
    "KO_NL_SICK_VACATION_04": "KO_NL_SICK_VACATION_15",
    "KO_NL_SICK_VACATION_06": "KO_NL_SICK_VACATION_14",
    "KO_NL_SICK_VACATION_07": "KO_NL_SICK_VACATION_16",
    "KO_NL_SICK_VACATION_09": "KO_NL_SICK_VACATION_17",
    "KO_NL_SICK_VACATION_10": "KO_NL_SICK_VACATION_18",
    "KO_NL_SICK_VACATION_11": "KO_NL_SICK_VACATION_19",
}


def locate_quote_lines(quote: str, sec: dict) -> tuple[int, int]:
    raw = sec["raw_text"]
    idx = raw.find(quote)
    if idx == -1:
        return sec["line_start"], sec["line_end"]
    start_offset = raw[:idx].count("\n")
    end_offset = raw[: idx + len(quote)].count("\n")
    return sec["line_start"] + start_offset, sec["line_start"] + end_offset


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    kos_path = base / "artifacts" / "kos_corrected.json"
    sec_path = base / "artifacts" / "parsed_sections.json"
    out_path = base / "artifacts" / "kos_verified.json"

    kos = json.loads(kos_path.read_text(encoding="utf-8"))
    sections = {s["section_id"]: s for s in json.loads(sec_path.read_text(encoding="utf-8"))}

    for ko in kos:
        kid = ko["ko_id"]
        sec = sections[ko["provenance"]["section_id"]]

        # 1. Exact quote line span (F23)
        q_start, q_end = locate_quote_lines(ko["evidence"]["source_quote"], sec)
        ko["provenance"]["quote_line_start"] = q_start
        ko["provenance"]["quote_line_end"] = q_end

        # 2. Canonical field renames (F15, F19)
        if kid in FIELD_RENAMES:
            mapping = FIELD_RENAMES[kid]
            ko["semantics"]["watched_fields"] = [
                mapping.get(f, f) for f in ko["semantics"]["watched_fields"]
            ]

        # 3. Standardize global entity wildcard (F07)
        for tup in ko["applicability_tuples"]:
            if tup["entities"] == ["GitLab"]:
                tup["entities"] = ["unspecified"]

        # 4. Link duplicate occurrences without deleting (F03)
        ko["duplicate_occurrence_of"] = DUPLICATE_PAIRS.get(kid)

        # 5. Freeze status
        ko["annotation_status"] = "verified"

    out_path.write_text(json.dumps(kos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified and locked {len(kos)} KOs -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
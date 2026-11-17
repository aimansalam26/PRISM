#!/usr/bin/env python3
"""Extract atomic Knowledge Objects (KOs) from curated pilot sections using Gemini + Pydantic."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. Curated high-signal topic bundles from parsed_sections.json (28 sections -> ~35-45 KOs)
PILOT_TOPIC_GROUPS = [
    {
        "group_id": "NL_BIKE",
        "topic_name": "Netherlands Bike to Work Scheme",
        "section_ids": ["SEC_NL_38", "SEC_NL_39", "SEC_NL_40", "SEC_NL_41"],
    },
    {
        "group_id": "NL_MEDICAL",
        "topic_name": "Netherlands Medical Allowance",
        "section_ids": ["SEC_NL_05", "SEC_NL_06", "SEC_NL_07", "SEC_NL_08"],
    },
    {
        "group_id": "NL_SICK_VACATION",
        "topic_name": "Netherlands Statutory Sick & Vacation Leave",
        "section_ids": ["SEC_NL_20", "SEC_NL_21", "SEC_NL_66", "SEC_NL_69"],
    },
    {
        "group_id": "NL_PARENTAL",
        "topic_name": "Netherlands Statutory Maternity, Partner & Adoption Leave",
        "section_ids": ["SEC_NL_45", "SEC_NL_46", "SEC_NL_48", "SEC_NL_50", "SEC_NL_53"],
    },
    {
        "group_id": "GLOBAL_BASELINE",
        "topic_name": "Company-Wide Benefits, Global Parental Leave, Life Insurance & Contractors",
        "section_ids": [
            "SEC_GLOBAL_01",
            "SEC_GLOBAL_12",
            "SEC_GLOBAL_13",
            "SEC_GLOBAL_20",
            "SEC_GLOBAL_21",
            "SEC_GLOBAL_47",
        ],
    },
    {
        "group_id": "LEAVE_CORE",
        "topic_name": "Core Parental Leave, Wage Top-Up, Sick Leave Threshold & Equity Vesting",
        "section_ids": [
            "SEC_LEAVE_01",
            "SEC_LEAVE_02",
            "SEC_LEAVE_05",
            "SEC_LEAVE_17",
            "SEC_LEAVE_19",
        ],
    },
    {
        "group_id": "UK_CONTROL",
        "topic_name": "UK Negative Controls (Bike Scheme, Maternity, Paternity & Sick Pay)",
        "section_ids": ["SEC_UK_38", "SEC_UK_39", "SEC_UK_43", "SEC_UK_46", "SEC_UK_73"],
    },
]


# 2. Pydantic Blueprint (Strict Schema Contract)
class ScopeTuple(BaseModel):
    employment_types: List[str] = Field(
        description="e.g., ['full_time'], ['contractor'], ['intern'], or ['unspecified']"
    )
    org_roles: List[str] = Field(
        description="e.g., ['manager'], ['individual_contributor'], or ['unspecified']"
    )
    entities: List[str] = Field(
        description="e.g., ['GitLab BV'], ['GitLab LTD'], ['GitLab IT BV'], or ['unspecified']"
    )
    jurisdictions: List[str] = Field(
        description="ISO country codes e.g., ['NL'], ['UK'], ['US'], ['CA'], or ['global'] / ['unspecified']"
    )
    temporal_window: List[str] = Field(
        description="Exactly 2 strings: [start_date, end_date] in YYYY-MM-DD format. Use 'unknown' if not explicitly stated in text."
    )


class ExtractedKO(BaseModel):
    ko_id: str = Field(
        description="Unique snake/upper ID prefixed with group_id, e.g., KO_NL_BIKE_01"
    )
    source_section_id: str = Field(
        description="Exact section_id from the provided input bundle where source_quote appears"
    )
    source_quote: str = Field(
        description="Exact verbatim substring copied character-for-character from that section's raw_text"
    )
    rule_classification: Literal[
        "entitlement",
        "calculation",
        "eligibility",
        "exception",
        "procedure",
        "definition",
    ]
    summary: str = Field(description="One clear, factual sentence summarizing the atomic rule")
    watched_fields: List[str] = Field(
        description="Explicit snake_case policy attributes controlled or referenced, e.g., ['bike_purchase_cap_eur']"
    )
    applicability_tuples: List[ScopeTuple] = Field(
        description="Union of correlated scope tuples. Never cross-multiply unrelated entities and jurisdictions."
    )
    additional_conditions: List[str] = Field(
        description="Eligibility/operational constraints outside the 4 scope dimensions (e.g., '26 weeks continuous service', 'child under age 8')"
    )
    scope_evidence: str = Field(
        description="Brief explanation of where each scope restriction was derived from (e.g., heading_path vs body text)"
    )


class TopicExtractionResult(BaseModel):
    kos: List[ExtractedKO]


SYSTEM_PROMPT = """You are a precision policy-atomization engine building a ground-truth dataset for PRISM, a policy impact-traversal system.

Extract atomic, independently reviewable Knowledge Objects (KOs) from the provided GitLab Handbook section bundle.

STRICT EXTRACTION RULES:
1. BOUNDARY RULE: Create a separate KO ONLY when a provision has an independently changeable entitlement, calculation/formula, eligibility condition, exception/override, or core procedural requirement. Do NOT split every bullet into a KO if they are steps of a single procedure, and do NOT merge distinct rules (e.g., split Bike Purchase Cap, Net-Salary Excess Deduction, Tax Benefit Ceiling, and 2-Year Interval into separate KOs).
2. VERBATIM EVIDENCE: `source_quote` MUST be an exact, unmodified substring of `raw_text` inside `source_section_id`. Do not fix typos, alter punctuation, or paraphrase.
3. UNKNOWN IS NOT UNIVERSAL: If a start/end date is not explicitly written in the text, set `temporal_window` to `["unknown", "unknown"]`. Never invent dates like "2023-01-01". If employment type or org role is not stated, use `["unspecified"]`.
4. CORRELATED SCOPES: Keep `entities` and `jurisdictions` paired in `applicability_tuples`. If a rule applies to GitLab BV in NL, output one tuple with `entities: ["GitLab BV"]` and `jurisdictions: ["NL"]`.
5. CONSISTENT FIELD NAMES: Use clear, reusable snake_case names in `watched_fields` (e.g., `parental_leave_weeks`, `sick_pay_continuation_pct`, `bike_purchase_cap_eur`) so cross-document dependencies can be matched later.
6. SKIP PURE FLUFF: Do not create KOs for marketing intros ("We've Got You Covered") or generic contact emails unless they define a mandatory policy rule.
"""


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verify_ko(ko: ExtractedKO, section_map: Dict[str, dict]) -> List[str]:
    """Run deterministic audit checks on each LLM-proposed KO."""
    issues = []
    sec = section_map.get(ko.source_section_id)
    if not sec:
        issues.append(f"{ko.ko_id}: unknown source_section_id '{ko.source_section_id}'")
        return issues

    raw = sec["raw_text"]
    if ko.source_quote not in raw:
        if normalize_ws(ko.source_quote) not in normalize_ws(raw):
            issues.append(
                f"{ko.ko_id}: source_quote not found verbatim in {ko.source_section_id}"
            )
        else:
            issues.append(
                f"{ko.ko_id}: source_quote matched only after whitespace normalization in {ko.source_section_id}"
            )

    for tup in ko.applicability_tuples:
        if len(tup.temporal_window) != 2:
            issues.append(f"{ko.ko_id}: temporal_window must have exactly 2 items")
        for dt in tup.temporal_window:
            if dt != "unknown" and dt not in raw:
                issues.append(
                    f"{ko.ko_id}: date '{dt}' in temporal_window not explicitly present in {ko.source_section_id}"
                )
    return issues


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sections",
        type=Path,
        default=base / "artifacts" / "parsed_sections.json",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=base / "artifacts" / "kos_proposed.json",
    )
    ap.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model supporting structured outputs (e.g., gemini-2.5-flash or gemini-2.5-pro)",
    )
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    if not args.sections.is_file():
        print(f"ERROR: Sections file not found: {args.sections}", file=sys.stderr)
        return 1

    sections = json.loads(args.sections.read_text(encoding="utf-8"))
    section_map = {s["section_id"]: s for s in sections}

    client = genai.Client()
    proposed_records = []
    all_warnings = []
    seen_ids = set()

    for group in PILOT_TOPIC_GROUPS:
        bundle = []
        for sid in group["section_ids"]:
            if sid not in section_map:
                print(f"ERROR: Missing section {sid} in {args.sections}", file=sys.stderr)
                return 1
            sec = section_map[sid]
            bundle.append(
                {
                    "section_id": sec["section_id"],
                    "source_file": sec["source_file"],
                    "heading_path": sec["heading_path"],
                    "disclosure_title": sec["disclosure_title"],
                    "line_start": sec["line_start"],
                    "line_end": sec["line_end"],
                    "raw_text": sec["raw_text"],
                    "outgoing_links": sec["outgoing_links"],
                }
            )

        user_prompt = (
            f"Topic Group ID: {group['group_id']}\n"
            f"Topic Name: {group['topic_name']}\n"
            f"Prefix all ko_id values with 'KO_{group['group_id']}_' (e.g., KO_{group['group_id']}_01).\n\n"
            f"Section Bundle JSON:\n{json.dumps(bundle, ensure_ascii=False, indent=2)}"
        )

        print(f"Extracting {group['group_id']} ({len(bundle)} sections)...")
        response = client.models.generate_content(
            model=args.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=TopicExtractionResult,
                temperature=0.0,
            ),
        )

        extracted: TopicExtractionResult = response.parsed
        for ko in extracted.kos:
            if ko.ko_id in seen_ids:
                all_warnings.append(f"Duplicate ko_id generated: {ko.ko_id}")
            seen_ids.add(ko.ko_id)

            all_warnings.extend(verify_ko(ko, section_map))
            sec = section_map[ko.source_section_id]

            proposed_records.append(
                {
                    "ko_id": ko.ko_id,
                    "version_id": "v1.0",
                    "annotation_status": "proposed",
                    "topic_group": group["group_id"],
                    "provenance": {
                        "section_id": sec["section_id"],
                        "source_file": sec["source_file"],
                        "source_sha256": sec["source_sha256"],
                        "line_start": sec["line_start"],
                        "line_end": sec["line_end"],
                        "heading_path": sec["heading_path"],
                        "disclosure_title": sec["disclosure_title"],
                        "section_outgoing_links": sec["outgoing_links"],
                    },
                    "evidence": {
                        "source_quote": ko.source_quote,
                    },
                    "semantics": {
                        "rule_classification": ko.rule_classification,
                        "summary": ko.summary,
                        "watched_fields": ko.watched_fields,
                    },
                    "applicability_tuples": [t.model_dump() for t in ko.applicability_tuples],
                    "additional_conditions": ko.additional_conditions,
                    "scope_evidence": ko.scope_evidence,
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proposed_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nDone! Extracted {len(proposed_records)} proposed KOs -> {args.output}")
    if all_warnings:
        print(f"\nAudit Warnings ({len(all_warnings)}):", file=sys.stderr)
        for w in all_warnings:
            print(f"  - {w}", file=sys.stderr)
    else:
        print("All quotes and dates passed strict provenance assertions.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
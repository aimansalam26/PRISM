#!/usr/bin/env python3
"""Deterministically nominate candidate KO pairs for PRISM edge classification.

Reads kos_verified.json and parsed_sections.json.
Does NOT infer causal direction—only nominates pairs with explicit retrieval reasons,
reference hints, and explicit statuses for unresolved or out-of-slice links.
"""

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple

SLUG_TO_FILE = {
    "/handbook/total-rewards/benefits/general-and-entity-benefits/bv-benefits-netherlands/": "bv-benefits-netherlands.md",
    "/handbook/total-rewards/benefits/general-and-entity-benefits/": "general-and-entity-benefits__index.md",
    "/handbook/people-group/time-off-and-absence/leave-types/": "leave-types.md",
    "/handbook/total-rewards/benefits/general-and-entity-benefits/ltd-benefits-uk/": "ltd-benefits-uk.md",
}

DEPENDENCY_CUES = re.compile(
    r"\b(calculat\w*|difference|concurrent\w*|subject to|unless|supersed\w*|overrid\w*|prorat\w*|supplement\w*|top\w*\s+up|combin\w*|applies to|first eur|over eur|first \d+|not applicable|in accordance with)\b",
    re.I,
)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "are", "will",
    "have", "has", "can", "may", "not", "all", "any", "per", "under", "into",
    "within", "during", "when", "where", "which", "who", "their", "they", "you",
    "team", "member", "members", "gitlab", "policy", "leave", "benefit", "benefits",
}


def tokenize(text: str) -> List[str]:
    clean = re.sub(r"https?://\S+|/handbook/\S+", " ", text.lower())
    tokens = re.findall(r"[a-z]{3,}", clean)
    return [t for t in tokens if t not in STOPWORDS]


def normalize_heading_slug(heading: str) -> str:
    s = heading.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s)


def resolve_link(url: str, source_file: str, sections: List[dict]) -> dict:
    """Resolve an outgoing handbook link against the 4-file pilot corpus."""
    if url.startswith("mailto:"):
        return {"status": "external_non_handbook", "target_url": url, "matched_section_ids": []}

    if url.startswith("http://") or url.startswith("https://"):
        if url.startswith("https://handbook.gitlab.com/handbook/"):
            path_part = url[len("https://handbook.gitlab.com") :]
        elif url.startswith("http://handbook.gitlab.com/handbook/"):
            path_part = url[len("http://handbook.gitlab.com") :]
        elif "internal.gitlab.com/handbook/" in url:
            return {
                "status": "unresolved_internal_handbook",
                "target_url": url,
                "matched_section_ids": [],
            }
        else:
            return {"status": "external_non_handbook", "target_url": url, "matched_section_ids": []}
    else:
        path_part = url

    base_path, _, anchor = path_part.partition("#")
    if not base_path:
        target_file = source_file
    else:
        if not base_path.endswith("/"):
            base_path += "/"
        target_file = SLUG_TO_FILE.get(base_path)

    if not target_file:
        return {
            "status": "unresolved_external_to_pilot",
            "target_url": url,
            "matched_section_ids": [],
        }

    file_secs = [s for s in sections if s["source_file"] == target_file]
    if anchor:
        matched = [
            s["section_id"]
            for s in file_secs
            if any(normalize_heading_slug(h) == anchor.lower() for h in s["heading_path"])
        ]
        if matched:
            return {
                "status": "resolved_anchor",
                "target_url": url,
                "target_file": target_file,
                "matched_section_ids": matched,
            }
        return {
            "status": "unresolved_anchor",
            "target_url": url,
            "target_file": target_file,
            "anchor": anchor,
            "matched_section_ids": [],
        }

    return {
        "status": "resolved_page",
        "target_url": url,
        "target_file": target_file,
        "matched_section_ids": [s["section_id"] for s in file_secs],
    }


def extract_quote_links(quote: str, section_links: List[dict]) -> List[dict]:
    """Match exact inline Markdown links present inside the specific KO quote."""
    return [
        link
        for link in section_links
        if f"[{link['anchor_text']}]({link['target_url']})" in quote
    ]


def build_tfidf_vectors(kos: List[dict]) -> Dict[str, Dict[str, float]]:
    """Fit TF-IDF across the full verified KO corpus so scores stay invariant to slice filtering."""
    docs = {}
    df = Counter()
    for ko in kos:
        text = (
            ko["evidence"]["source_quote"]
            + " "
            + " ".join(ko["provenance"]["heading_path"][-2:])
            + " "
            + " ".join(ko["semantics"]["watched_fields"]).replace("_", " ")
        )
        toks = tokenize(text)
        counts = Counter(toks)
        docs[ko["ko_id"]] = counts
        for t in counts:
            df[t] += 1

    n_docs = max(len(kos), 1)
    vecs = {}
    for kid, counts in docs.items():
        vec = {}
        norm = 0.0
        for t, tf in counts.items():
            idf = math.log((n_docs + 1) / (df[t] + 1)) + 1.0
            w = tf * idf
            vec[t] = w
            norm += w * w
        norm = math.sqrt(norm) or 1.0
        vecs[kid] = {t: w / norm for t, w in vec.items()}
    return vecs


def cosine_sim(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(w * v2.get(t, 0.0) for t, w in v1.items())


def field_tokens(fields: List[str]) -> Set[str]:
    ignore = {"leave", "gitlab", "policy", "rule", "status", "type", "rate", "max", "min"}
    toks = set()
    for f in fields:
        for part in f.split("_"):
            if len(part) >= 3 and part not in ignore:
                toks.add(part)
    return toks


def all_jurisdictions(ko: dict) -> Set[str]:
    jurs = set()
    for tup in ko.get("applicability_tuples", []):
        jurs.update(tup.get("jurisdictions", []))
    return jurs


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kos", type=Path, default=base / "artifacts" / "kos_verified.json")
    ap.add_argument("--sections", type=Path, default=base / "artifacts" / "parsed_sections.json")
    ap.add_argument(
        "--output", type=Path, default=base / "artifacts" / "edge_candidates.json"
    )
    ap.add_argument(
        "--groups",
        nargs="*",
        default=["NL_BIKE", "NL_MEDICAL"],
        help="Topic groups to include (default: NL_BIKE NL_MEDICAL). Pass --all for all 103 KOs.",
    )
    ap.add_argument("--all", action="store_true", help="Include all topic groups in kos_verified.json")
    ap.add_argument("--sim-threshold", type=float, default=0.35)
    args = ap.parse_args()

    all_kos = json.loads(args.kos.read_text(encoding="utf-8"))
    sections = json.loads(args.sections.read_text(encoding="utf-8"))

    # Fit TF-IDF on full corpus before slicing
    tfidf = build_tfidf_vectors(all_kos)

    all_ko_by_section: Dict[str, List[str]] = {}
    for k in all_kos:
        all_ko_by_section.setdefault(k["provenance"]["section_id"], []).append(k["ko_id"])

    if args.all:
        kos = all_kos
    else:
        allowed = set(args.groups)
        kos = [k for k in all_kos if k["topic_group"] in allowed]

    selected_ko_by_section: Dict[str, List[str]] = {}
    for k in kos:
        selected_ko_by_section.setdefault(k["provenance"]["section_id"], []).append(k["ko_id"])

    link_audit_by_ko: Dict[str, List[dict]] = {}
    resolved_link_targets: Dict[str, List[Tuple[str, str]]] = {}

    for k in kos:
        kid = k["ko_id"]
        q_links = extract_quote_links(
            k["evidence"]["source_quote"], k["provenance"]["section_outgoing_links"]
        )
        for lnk in q_links:
            res = resolve_link(lnk["target_url"], k["provenance"]["source_file"], sections)
            if res["status"].startswith("resolved"):
                selected_targets = []
                all_corpus_targets = []
                for target_sec in res["matched_section_ids"]:
                    selected_targets.extend(
                        [t for t in selected_ko_by_section.get(target_sec, []) if t != kid]
                    )
                    all_corpus_targets.extend(
                        [t for t in all_ko_by_section.get(target_sec, []) if t != kid]
                    )

                if selected_targets:
                    for target_kid in selected_targets:
                        resolved_link_targets.setdefault(kid, []).append(
                            (target_kid, f"explicit_link:{res['status']}:{lnk['target_url']}")
                        )
                elif all_corpus_targets:
                    link_audit_by_ko.setdefault(kid, []).append(
                        {
                            "status": "target_outside_selected_slice",
                            "target_url": lnk["target_url"],
                            "excluded_ko_ids": sorted(set(all_corpus_targets)),
                        }
                    )
                else:
                    link_audit_by_ko.setdefault(kid, []).append(
                        {
                            "status": "target_section_without_ko",
                            "target_url": lnk["target_url"],
                            "matched_section_ids": res["matched_section_ids"],
                        }
                    )
            else:
                link_audit_by_ko.setdefault(kid, []).append(res)

    candidates_map: Dict[Tuple[str, str], dict] = {}
    ko_map = {k["ko_id"]: k for k in kos}

    def add_signal(
        ko_a: dict,
        ko_b: dict,
        signal: str,
        ref_link: Tuple[str, str] | None = None,
    ):
        a_id, b_id = ko_a["ko_id"], ko_b["ko_id"]
        if a_id == b_id:
            return
        pair_key = tuple(sorted([a_id, b_id]))
        jurs_a = all_jurisdictions(ko_map[pair_key[0]])
        jurs_b = all_jurisdictions(ko_map[pair_key[1]])
        entry = candidates_map.setdefault(
            pair_key,
            {
                "ko_a_id": pair_key[0],
                "ko_b_id": pair_key[1],
                "retrieval_reasons": [],
                "reference_hints": [],
                "jurisdiction_comparison": {
                    "ko_a_jurisdictions": sorted(jurs_a),
                    "ko_b_jurisdictions": sorted(jurs_b),
                    "exact_set_match": jurs_a == jurs_b,
                },
            },
        )
        if signal not in entry["retrieval_reasons"]:
            entry["retrieval_reasons"].append(signal)
        if ref_link:
            hint_obj = {"from_ko_id": ref_link[0], "to_ko_id": ref_link[1]}
            if hint_obj not in entry["reference_hints"]:
                entry["reference_hints"].append(hint_obj)

    # Signal 2: Explicit resolved links (stored as reference_hints, NOT causal direction)
    for src_id, targets in resolved_link_targets.items():
        for tgt_id, reason in targets:
            add_signal(ko_map[src_id], ko_map[tgt_id], reason, ref_link=(src_id, tgt_id))

    # Signals 1, 3, 4, 5 across pairs
    for i in range(len(kos)):
        for j in range(i + 1, len(kos)):
            a, b = kos[i], kos[j]
            same_full_heading = (
                a["provenance"]["source_file"] == b["provenance"]["source_file"]
                and a["provenance"]["heading_path"] == b["provenance"]["heading_path"]
            )

            # Signal 1: Full heading path match within same file
            if same_full_heading:
                leaf = a["provenance"]["heading_path"][-1]
                add_signal(a, b, f"same_benefit_heading:{leaf}")

            # Signal 3: Exact shared watched_fields OR overlapping domain parameter tokens
            f_a = set(a["semantics"]["watched_fields"])
            f_b = set(b["semantics"]["watched_fields"])
            exact_shared = f_a & f_b
            if exact_shared:
                add_signal(a, b, f"shared_exact_field:{sorted(exact_shared)}")
            else:
                tok_overlap = field_tokens(list(f_a)) & field_tokens(list(f_b))
                if len(tok_overlap) >= 2:
                    add_signal(a, b, f"related_field_tokens:{sorted(tok_overlap)}")

            # Signal 4: Dependency language cues (no causal direction inferred)
            cue_a = DEPENDENCY_CUES.findall(a["evidence"]["source_quote"])
            cue_b = DEPENDENCY_CUES.findall(b["evidence"]["source_quote"])
            if same_full_heading and (cue_a or cue_b):
                if cue_a:
                    add_signal(
                        a,
                        b,
                        f"dependency_cue_in_{a['ko_id']}:{sorted(set(c.lower() for c in cue_a))}",
                    )
                if cue_b:
                    add_signal(
                        a,
                        b,
                        f"dependency_cue_in_{b['ko_id']}:{sorted(set(c.lower() for c in cue_b))}",
                    )

            # Signal 5: Lexical TF-IDF cosine similarity (fitted on full 103-KO corpus)
            sim = cosine_sim(tfidf[a["ko_id"]], tfidf[b["ko_id"]])
            if sim >= args.sim_threshold:
                add_signal(a, b, f"lexical_tfidf_cosine:{sim:.3f}")

    candidates_list = [
        {"candidate_id": f"CAND_{idx:03d}", **item}
        for idx, (_, item) in enumerate(sorted(candidates_map.items()), start=1)
    ]

    output_payload = {
        "scope_filter": "ALL" if args.all else args.groups,
        "tfidf_fitted_corpus_size": len(all_kos),
        "selected_ko_count": len(kos),
        "candidate_count": len(candidates_list),
        "link_resolution_audit": link_audit_by_ko,
        "candidates": candidates_list,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated {len(candidates_list)} candidate pairs across {len(kos)} KOs -> {args.output}"
    )
    if link_audit_by_ko:
        print(f"Logged {len(link_audit_by_ko)} KOs with unresolved or out-of-slice links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
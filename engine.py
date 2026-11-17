"""PRISM 0.2.0: bounded review discovery over curated metadata.

No text interpretation or gold labels are used. See SPECIFICATION.md.
Each queue entry carries one field, scope cell and path. Distinct scope cells
are never merged dimension-by-dimension.
"""
from collections import defaultdict, deque
from copy import deepcopy
from datetime import date
import hashlib
import json

VERSION = "0.2.0"
DIMENSIONS = ("roles", "jurisdictions", "organisations")
TYPES = {"DEPENDS_ON", "RELATED_TO", "ADOPTS_VALUE", "OVERRIDES", "REVIEW_ONLY"}
MODES = ("prism", "local", "untyped")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check_scope(scope):
    if not isinstance(scope, dict):
        raise ValueError("Scope must be an object. Unknown metadata needs explicit handling.")
    for dim in DIMENSIONS:
        values = scope.get(dim)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f"Scope {dim} must contain nonempty strings.")
        if len(set(values)) != len(values) or ("*" in values and len(values) != 1):
            raise ValueError(f"Scope {dim}: use either ['*'] or unique identifiers.")
        if {"GLOBAL", "all_dimensions", "all_roles"} & set(values):
            raise ValueError("Legacy wildcard detected. Use '*' explicitly.")
    try:
        for key in ('start','end'):
            if date.fromisoformat(scope[key]).isoformat() != scope[key]:
                raise ValueError('Use canonical YYYY-MM-DD dates.')
        if date.fromisoformat(scope["start"]) >= date.fromisoformat(scope["end"]):
            raise ValueError("Scope interval must have start < end.")
    except (KeyError, TypeError):
        raise ValueError("Scope requires ISO start and end dates.") from None


def cells(record):
    return record.get("scope_cells", [record.get("scope")])


def intersection(*scopes):
    result = deepcopy(scopes[0])
    for other in scopes[1:]:
        for dim in DIMENSIONS:
            a, b = set(result[dim]), set(other[dim])
            value = b if "*" in a else a if "*" in b else a & b
            if not value:
                return None
            result[dim] = sorted(value)
        result["start"] = max(result["start"], other["start"])
        result["end"] = min(result["end"], other["end"])
        if result["start"] >= result["end"]:
            return None
    return result


def time_window(scope):
    return {**{d: ["*"] for d in DIMENSIONS}, "start": scope["start"], "end": scope["end"]}


def validate(snapshot):
    if snapshot.get("schema_version") != "0.3":
        raise ValueError("Expected schema_version 0.3. Use the migrated data supplied with this release.")
    event = snapshot.get("event", {})
    if event.get("kind") not in {"value_change", "rule_change"}:
        raise ValueError("Only value_change and rule_change are supported.")
    if event.get("scope_change") or event.get("relationship_changes"):
        raise ValueError("Withdrawal/scope or relationship changes require dual snapshots; unsupported in 0.2.0.")
    fields = event.get("changed_fields")
    if not isinstance(fields, list) or not fields or any(not isinstance(x, str) or not x for x in fields) or len(set(fields)) != len(fields):
        raise ValueError("changed_fields must be unique nonempty identifiers.")
    check_scope(event.get("change_scope"))
    after, before = event.get("after", {}), event.get("before", {})
    check_scope(after.get("scope"))
    check_scope(before.get("scope"))
    if before.get("scope_known", True):
        if any(set(before["scope"][d]) != set(after["scope"][d]) for d in DIMENSIONS):
            raise ValueError("Old/new population differs: scope-change discovery is unsupported.")
    elif event.get("analysis_basis") != "revised_clause_only":
        raise ValueError("Unknown prior scope requires explicit revised_clause_only analysis.")
    if before.get("version_id") == after.get("version_id"):
        raise ValueError("Before and after must have different version IDs.")
    nodes = snapshot.get("nodes", [])
    ids = [n.get("id") for n in nodes]
    if not ids or any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Node IDs must be unique and nonempty.")
    root = event.get("root_ko")
    if root not in ids or root != after.get("version_id"):
        raise ValueError("root_ko must be the revised version present in nodes.")
    for n in nodes:
        if not n.get("text") or not n.get("source"):
            raise ValueError(f"Missing text/provenance on {n['id']}.")
        if "scope" in n and "scope_cells" in n:
            raise ValueError("Use scope OR scope_cells.")
        if not cells(n):
            raise ValueError("At least one scope cell is required.")
        for c in cells(n):
            check_scope(c)
    node_map = {n["id"]: n for n in nodes}
    if node_map[root]["text"] != after.get("text") or cells(node_map[root]) != [after["scope"]]:
        raise ValueError("Root text/scope must match revised evidence.")
    if not intersection(after["scope"], event["change_scope"]):
        raise ValueError("Change scope does not overlap the revised root.")
    edge_ids = set()
    for e in snapshot.get("relationships", []):
        if not e.get("id") or e["id"] in edge_ids:
            raise ValueError("Relationship IDs must be unique and nonempty.")
        edge_ids.add(e["id"])
        if e.get("prerequisite") not in ids or e.get("dependent") not in ids:
            raise ValueError(f"Unknown endpoint on {e['id']}.")
        if e.get("type") not in TYPES or not e.get("source") or not e.get("evidence"):
            raise ValueError(f"Unsupported type or missing source/evidence on {e['id']}.")
        if e["type"] != "RELATED_TO" and (not isinstance(e.get("field"), str) or not e["field"]):
            raise ValueError(f"Transmitting relationships need a field on {e['id']}.")
        if e.get("certainty") not in {"confirmed", "uncertain"}:
            raise ValueError(f"Declare confirmed or uncertain certainty on {e['id']}.")
        if e["certainty"] == "uncertain" and not e.get("uncertainty_reason"):
            raise ValueError("Uncertain relationships need a reason.")
        if e["type"] == "OVERRIDES" and e.get("override_mode") != "independent_value":
            raise ValueError("Only explicitly independent fixed-value overrides are supported.")
        if e["type"] in {"OVERRIDES", "ADOPTS_VALUE"} and event["kind"] != "value_change":
            raise ValueError("Value adoption/replacement is limited to value_change events in this release.")
        if e["type"] == "ADOPTS_VALUE":
            mapping = e.get("mapping", {})
            if not mapping.get("from") or set(mapping.get("from", {})) != set(mapping.get("to", {})):
                raise ValueError("Adoption requires matching source/target mapped dimensions.")
            for side in ("from", "to"):
                for d, v in mapping[side].items():
                    if d not in DIMENSIONS:
                        raise ValueError("Adoption maps population dimensions, never dates.")
                    check_scope({**time_window(event["change_scope"]), d: v})
        if "scope" in e and "scope_cells" in e:
            raise ValueError("Use scope OR scope_cells on relationships.")
        if not cells(e):
            raise ValueError("Relationship scope cells cannot be empty.")
        for c in cells(e):
            check_scope(c)
    # Priority resolution is deliberately outside this prototype. A confirmed
    # independent replacement and inheritance must have disjoint scopes.
    for override in snapshot.get("relationships", []):
        if override['type'] != 'OVERRIDES' or override['certainty'] != 'confirmed':
            continue
        for edge in snapshot['relationships']:
            if edge['type'] not in {'DEPENDS_ON','REVIEW_ONLY'} or edge['certainty'] != 'confirmed':
                continue
            if all(edge[k] == override[k] for k in ('prerequisite','dependent','field')):
                if any(intersection(a,b) for a in cells(edge) for b in cells(override)):
                    raise ValueError('Overlapping inheritance and independent replacement: curate disjoint scopes or mark uncertainty.')
    return node_map


def transfer(scope, edge, target, window):
    """Known-scope transition. Keep distinct cells separate."""
    source = deepcopy(scope)
    if edge["type"] == "ADOPTS_VALUE":
        mapping = edge["mapping"]
        source = intersection(source, {**time_window(window), **mapping["from"]})
        if source is None:
            return []
        source.update(deepcopy(mapping["to"]))
    out = []
    for ec in cells(edge):
        for nc in cells(target):
            x = intersection(source, ec, nc)
            if x is not None and x not in out:
                out.append(x)
    return out


def discover(snapshot, mode="prism", max_hops=3):
    nodes = validate(snapshot)
    if mode not in MODES or type(max_hops) is not int or not 1 <= max_hops <= 3:
        raise ValueError("Use prism/local/untyped and integer max_hops from 1 to 3.")
    event, root = snapshot["event"], snapshot["event"]["root_ko"]
    adjacency = defaultdict(list)
    for e in sorted(snapshot["relationships"], key=lambda x: x["id"]):
        adjacency[e["prerequisite"]].append(e)
    initial = intersection(event["change_scope"], event["after"]["scope"])
    queue = deque((root, initial, f, [], [root], False) for f in sorted(event["changed_fields"]))
    paths, decisions, visited = defaultdict(list), [], 0
    while queue:
        current, accumulated, field, edge_path, node_path, uncertain = queue.popleft()
        visited += 1
        if len(edge_path) >= max_hops:
            continue
        for e in adjacency[current]:
            target = e["dependent"]
            next_edges, next_nodes = edge_path + [e["id"]], node_path + [target]
            decision = {"edge_path": next_edges, "node_path": next_nodes, "field": field,
                        "edge_id": e["id"], "source": e["source"], "evidence": e["evidence"]}
            output_scopes = []
            if mode == "untyped":
                action, reason, output_scopes = "continue", "structural_reachability", [None]
            elif e["type"] == "RELATED_TO" or e["field"] != field:
                action, reason = "exclude", "unrelated_changed_field"
            elif e["certainty"] == "uncertain" or uncertain:
                # An unresolved link can invalidate the constraint used to prune
                # it. Preserve a possible path without asserting affected scope.
                overlaps = any(intersection(time_window(event["change_scope"]), time_window(ec), time_window(nc))
                               for ec in cells(e) for nc in cells(nodes[target]))
                action, reason = ("defer", e.get("uncertainty_reason", "upstream_uncertainty")) if overlaps else ("exclude", "inactive_interval")
                output_scopes = [None] if overlaps else []
            elif e["type"] == "OVERRIDES":
                action, reason = "exclude", "independent_replacement_of_changed_value"
            else:
                bases = [accumulated] if mode == "prism" or not edge_path else [intersection(c, time_window(event["change_scope"])) for c in cells(nodes[current])]
                for base in bases:
                    if base:
                        output_scopes.extend(transfer(base, e, nodes[target], event["change_scope"]))
                action = ("review_stop" if e["type"] == "REVIEW_ONLY" else "continue") if output_scopes else "exclude"
                reason = "supported_dependency" if output_scopes else "empty_scope_or_inactive_interval"
            decision.update(action=action, reason=reason, surviving_scopes=[s for s in output_scopes if s])
            decisions.append(decision)
            for scope in output_scopes:
                status = "Defer" if action == "defer" else "Yes"
                trace = {**deepcopy(decision), "scope": scope, "status": status, "hops": len(next_edges)}
                if target != root and trace not in paths[target]:
                    paths[target].append(trace)
                if action != "review_stop":
                    queue.append((target, scope, field, next_edges, next_nodes, status == "Defer"))
    items = []
    for ident in sorted(set(nodes) - {root}):
        traces = paths[ident]
        definite = [p for p in traces if p["status"] == "Yes"]
        status = "Yes" if definite else "Defer" if traces else "No"
        scopes = []
        for p in definite:
            if p["scope"] is not None and p["scope"] not in scopes:
                scopes.append(p["scope"])
        items.append({"ko_id": ident, "title": nodes[ident]["title"], "status": status,
                      "directness": ("direct" if any(p["hops"] == 1 for p in definite) else "indirect") if definite else "unresolved" if traces else "none",
                      "affected_scopes": scopes, "has_uncertainty": any(p["status"] == "Defer" for p in traces), "paths": traces})
    return {"prototype_version": VERSION, "snapshot_id": snapshot.get("snapshot_id", snapshot.get("id")),
            "input_sha256": fingerprint(snapshot), "mode": mode, "max_hops": max_hops,
            "scope_supported": mode != "untyped", "items": items, "decisions": decisions,
            "visited_states": visited, "review_volume": sum(i["status"] in {"Yes", "Defer"} for i in items)}

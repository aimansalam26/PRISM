"""Download serializers for the local app. Pure standard-library OOXML export.

Every Excel string is an inline string, never a formula. CSV formula-like strings
are escaped. Full untruncated evidence remains available in JSON downloads.
"""
import csv
import io
import json
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MODES = ("prism", "local", "untyped")


def candidate_rows(run, notes):
    rows = [["KO ID", "Scenario", "Title", "PRISM", "Local", "Untyped", "Directness", "Additional uncertainty", "Affected scopes (separate cells)", "Policy text", "Source", "Stakeholder review status", "Stakeholder note"]]
    for scenario in run["suite"]["scenarios"]:
        modes = run["payload"]["results"][scenario["id"]]
        nodes = {n["id"]: n for n in scenario["nodes"]}
        lookups = {m: {i["ko_id"]: i for i in modes[m]["items"]} for m in MODES}
        for item in modes["prism"]["items"]:
            ident = item["ko_id"]
            note = notes.get(ident, {})
            rows.append([ident, scenario["title"], item["title"], *[lookups[m][ident]["status"] for m in MODES],
                         item["directness"], str(item["has_uncertainty"]), json.dumps(item["affected_scopes"], ensure_ascii=False),
                         nodes[ident]["text"], nodes[ident]["source"], note.get("state", "pending"), note.get("text", "")])
    return rows


def report_sheets(run, notes):
    payload = run["payload"]
    overview = [["PRISM stakeholder report", "Value"], ["Created at (UTC)", run["created_at"]],
                ["Engine version", payload["prototype_version"]], ["Maximum impact steps", payload["max_hops"]],
                ["Corpus SHA256", payload["suite_sha256"]], ["Scenario count", len(run["suite"]["scenarios"])],
                ["Interpretation", "Predictions from curated metadata. Stakeholder notes are not gold labels or authorised lifecycle decisions."],
                ["Scope semantics", "Each scope row is a separate correlated applicability cell; do not union dimensions independently."],
                ["Date semantics", "Start inclusive, end exclusive. Year 0001/9999 values are implementation sentinels."],
                ["Reference check", "Computational agreement with a separate implementation; not domain accuracy."],
                ["Export scope", "Whole active corpus; on-screen filters do not restrict this report."],
                ["Long text", "Excel cells over 32,000 characters are marked as truncated. JSON contains the complete evidence."]]
    for mode in MODES:
        items = [i for s in payload["results"].values() for i in s[mode]["items"]]
        for label in ("Yes", "No", "Defer"):
            overview.append([mode + " — " + label, sum(i["status"] == label for i in items)])
        overview.append([mode + " — review queue (Yes + Defer)", sum(i["status"] in {"Yes", "Defer"} for i in items)])
    scopes = [["KO ID", "Cell", "Roles", "Jurisdictions", "Organisations", "Start inclusive", "End exclusive"]]
    paths = [["Scenario", "Mode", "KO ID", "Status", "Field", "Node path", "Edge path", "Hops", "Action", "Reason", "Scope cell", "Source evidence"]]
    decisions = [["Scenario", "Mode", "Node path", "Field", "Action", "Reason", "Surviving cells", "Evidence", "Source"]]
    changes = [["Scenario", "Kind", "Changed fields", "Previous version", "Previous text", "Revised version", "Revised text", "Change scope", "Analysis basis"]]
    for scenario in run["suite"]["scenarios"]:
        event = scenario["event"]
        changes.append([scenario["title"], event["kind"], ", ".join(event["changed_fields"]), event["before"]["version_id"], event["before"].get("text", "Not supplied"), event["after"]["version_id"], event["after"]["text"], json.dumps(event["change_scope"]), event.get("analysis_basis", "")])
        for mode in MODES:
            result = payload["results"][scenario["id"]][mode]
            for item in result["items"]:
                if mode == "prism":
                    for n, scope in enumerate(item["affected_scopes"], 1):
                        scopes.append([item["ko_id"], n, ", ".join(scope["roles"]), ", ".join(scope["jurisdictions"]), ", ".join(scope["organisations"]), scope["start"], scope["end"]])
                for p in item["paths"]:
                    paths.append([scenario["id"], mode, item["ko_id"], p["status"], p["field"], " → ".join(p["node_path"]), " → ".join(p["edge_path"]), p["hops"], p["action"], p["reason"], json.dumps(p["scope"]), p["evidence"]])
            for d in result["decisions"]:
                decisions.append([scenario["id"], mode, " → ".join(d["node_path"]), d["field"], d["action"], d["reason"], json.dumps(d["surviving_scopes"]), d["evidence"], d["source"]])
    sheets = {"Overview": overview, "Candidates": candidate_rows(run, notes), "Policy changes": changes,
              "Affected scopes": scopes, "Supporting paths": paths, "Traversal decisions": decisions}
    if run.get("evaluation"):
        metrics = [["Mode", "Measure", "Value"], ["All", "Interpretation", run["evaluation"]["interpretation"]], ["All", "Gold SHA256", run["evaluation"]["gold_sha256"]]]
        for mode, data in run["evaluation"]["metrics"].items():
            for key, value in data.items():
                metrics.append([mode, key, json.dumps(value) if isinstance(value, dict) else "Undefined" if value is None else value])
        sheets["Evaluation"] = metrics
    return sheets


def excel_bytes(sheets):
    """Write a small standards-based .xlsx, with no installed Excel dependency."""
    def col(n):
        result = ""
        while n:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    def text(value):
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))
        if len(value) > 32000:
            value = value[:31940] + " [TRUNCATED — complete text in JSON export]"
        return escape(value)

    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as z:
        parts = ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1))
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + parts + '</Types>')
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        names = ''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheets, 1))
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + names + '</sheets></workbook>')
        rels = ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels + f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/><color rgb="FF202738"/></font><font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF242544"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i, rows in enumerate(sheets.values(), 1):
            content = []
            width = max(len(r) for r in rows)
            for r, values in enumerate(rows, 1):
                entries = []
                for c, value in enumerate(values, 1):
                    attr = f'r="{col(c)}{r}" s="{1 if r == 1 else 0}"'
                    if type(value) in (int, float):
                        entries.append(f'<c {attr}><v>{value}</v></c>')
                    else:
                        entries.append(f'<c {attr} t="inlineStr"><is><t xml:space="preserve">{text(value)}</t></is></c>')
                content.append(f'<row r="{r}">' + ''.join(entries) + '</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="25" customWidth="1"/><col min="2" max="'+str(max(2,width))+'" width="34" customWidth="1"/></cols><sheetData>' + ''.join(content) + f'</sheetData><autoFilter ref="A1:{col(width)}{len(rows)}"/></worksheet>')
    return buffer.getvalue()


def csv_bytes(rows):
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerows([[safe(v) for v in row] for row in rows])
    return out.getvalue().encode("utf-8-sig")


def markdown_report(run, notes):
    lines = ["# PRISM stakeholder review packet", "", "Predictions support human review. Notes are observations, not gold labels or policy approvals.", "", "Corpus: " + run["payload"]["suite_sha256"], "Maximum impact steps: " + str(run["payload"]["max_hops"]), ""]
    for s in run["suite"]["scenarios"]:
        lines += ["## " + s["title"], "", "Previous: " + s["event"]["before"].get("text", "Not supplied"), "", "Revised: " + s["event"]["after"]["text"], ""]
        nodes = {n["id"]: n for n in s["nodes"]}
        result = run["payload"]["results"][s["id"]]["prism"]
        for item in result["items"]:
            ident = item["ko_id"]
            lines += ["### " + ident + " — " + item["title"], "", nodes[ident]["text"], "", f"Prediction: {item['status']}. Directness: {item['directness']}.", ""]
            for scope in item["affected_scopes"]:
                lines += ["Affected cell: " + json.dumps(scope, ensure_ascii=False), ""]
            for p in item["paths"]:
                lines.append("- " + " → ".join(p["node_path"]) + ": " + p["action"] + "; " + p["reason"])
            for d in result["decisions"]:
                if d["node_path"][-1] == ident and d["action"] == "exclude":
                    lines.append("- Excluded: " + " → ".join(d["node_path"]) + "; " + d["reason"])
            note = notes.get(ident, {})
            if note:
                lines += ["", "Stakeholder status: " + note.get("state", "pending"), "Stakeholder note: " + note.get("text", "")]
            lines += [""]
    return '\n'.join(lines).encode()


def export_report(run, notes, kind):
    if kind == "xlsx":
        return excel_bytes(report_sheets(run, notes)), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "PRISM_review_report.xlsx"
    if kind == "csv":
        return csv_bytes(candidate_rows(run, notes)), "text/csv; charset=utf-8", "PRISM_candidates.csv"
    if kind == "markdown":
        return markdown_report(run, notes), "text/markdown; charset=utf-8", "PRISM_review_packet.md"
    values = {"results": (run["payload"], "PRISM_results.json"), "corpus": (run["suite"], "PRISM_corpus.json"),
              "session": ({"format": "prism-review-session/v1", "suite": run["suite"], "notes": notes, "max_hops": run["payload"]["max_hops"], "saved_from_run": run["run_id"]}, "PRISM_review_session.json")}
    if kind == "evaluation" and run.get("evaluation"):
        values[kind] = (run["evaluation"], "PRISM_evaluation.json")
    if kind not in values:
        raise ValueError("Unsupported export, or evaluation has not been run.")
    value, name = values[kind]
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode(), "application/json; charset=utf-8", name

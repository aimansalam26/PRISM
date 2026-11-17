"""Local stakeholder interface for PRISM 0.2.0. Run: python app.py

Place beside engine.py, reference.py and evaluate.py. No third-party packages.
Uploaded data and working runs stay in memory; downloads are saved by the browser.
"""
import argparse
import base64
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.parse import urlsplit
import zipfile

try:
    from engine import VERSION, MODES, discover, fingerprint, validate, cells
    from reference import compare
    from ui_exports import export_report
except ImportError as exc:
    raise SystemExit("Place app.py and ui_exports.py beside the corrected engine.py and reference.py. " + str(exc))

BASE = Path(__file__).resolve().parent
MAX_BYTES = 8 * 1024 * 1024
RUNS = OrderedDict()
LOCK = threading.Lock()
REVIEW_STATES = {"pending", "reviewed", "question", "clarification"}


def normalise_input(data, max_hops=3):
    """Accept a suite, a single scenario, or a downloaded review session."""
    notes = {}
    if not isinstance(data, dict):
        raise ValueError("Upload a JSON object containing a scenario or a scenarios list.")
    if data.get("format") == "prism-review-session/v1":
        max_hops, notes, data = data.get("max_hops", 3), data.get("notes", {}), data.get("suite")
        if not isinstance(data, dict):
            raise ValueError("This session does not contain its source corpus.")
    if type(max_hops) is not int or max_hops not in (1, 2, 3):
        raise ValueError("Maximum depth must be 1, 2 or 3 impact steps.")
    if "event" in data and "nodes" in data:
        data = {"schema_version": data.get("schema_version"), "snapshot_id": data.get("snapshot_id",data.get("id","single-scenario")), "scenarios": [data]}
    if data.get("schema_version") not in {"0.3","0.4"}:
        raise ValueError("Expected schema 0.3 or 0.4. Upload data/scenarios.json, data/policies.json or a saved UI session; raw PDFs and results-only JSON are not corpus inputs.")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 64:
        raise ValueError("A corpus must contain between 1 and 64 scenarios.")
    ids, node_ids, budget = set(), set(), 0
    for s in scenarios:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not s["id"]:
            raise ValueError("Every scenario needs a nonempty id.")
        if s["id"] in ids:
            raise ValueError("Duplicate scenario id: " + s["id"])
        ids.add(s["id"])
        if not isinstance(s.get("title"), str) or not s["title"].strip():
            raise ValueError(s["id"] + ": a title is required.")
        nodes, edges = s.get("nodes"), s.get("relationships")
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100 or not isinstance(edges, list) or len(edges) > 200:
            raise ValueError(s["id"] + ": use at most 100 nodes and 200 relationships per scenario.")
        for record in nodes + edges:
            if not isinstance(record, dict):
                raise ValueError(s["id"] + ": node and relationship records must be objects.")
            if len(cells(record)) > 4:
                raise ValueError("The local UI supports at most four applicability cells per record.")
        for n in nodes:
            if not isinstance(n.get("id"), str) or n["id"] in node_ids:
                raise ValueError("KO identifiers must be unique across the whole corpus.")
            if not isinstance(n.get("title"), str) or not n["title"].strip():
                raise ValueError("Each KO needs a nonempty title.")
            node_ids.add(n["id"])
        try:
            mapped = validate(s)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            raise ValueError(s["id"] + ": " + str(exc)) from None
        if len(s["event"]["changed_fields"]) > 4:
            raise ValueError("Use at most four changed fields per scenario in this local UI.")
        # Bound the worst-case state expansion, including local-scope cell resets.
        frontier = {s["event"]["root_ko"]: len(s["event"]["changed_fields"])}
        for _ in range(max_hops):
            following = Counter()
            for e in edges:
                count = frontier.get(e["prerequisite"], 0)
                following[e["dependent"]] += count * len(cells(e)) * len(cells(mapped[e["dependent"]])) * len(cells(mapped[e["prerequisite"]]))
            budget += sum(following.values())
            if budget > 50000:
                raise ValueError("This graph exceeds the local UI's bounded path budget. Use a smaller corpus or fewer impact steps.")
            frontier = following
    return data, max_hops, clean_notes(notes, data)


def clean_notes(notes, suite):
    if not isinstance(notes, dict):
        raise ValueError("Review notes must be an object keyed by KO id.")
    allowed = {n["id"] for s in suite["scenarios"] for n in s["nodes"] if n["id"] != s["event"]["root_ko"]}
    clean = {}
    for key, value in notes.items():
        if key not in allowed or not isinstance(value, dict):
            raise ValueError("Review note refers to an unknown candidate.")
        state, text = value.get("state", "pending"), value.get("text", "")
        if state not in REVIEW_STATES or not isinstance(text, str) or len(text) > 5000:
            raise ValueError("Invalid review note. Use a supported status and at most 5,000 characters.")
        clean[key] = {"state": state, "text": text}
    return clean


def analyse(data, max_hops=3):
    suite, depth, notes = normalise_input(data, max_hops)
    results, checks = {}, {}
    for s in suite["scenarios"]:
        results[s["id"]] = {mode: discover(s, mode, depth) for mode in MODES}
        checks[s["id"]] = compare(s, results[s["id"]]["prism"])
        if not checks[s["id"]]["matches"]:
            raise ValueError("Computational reference disagreement in " + s["id"] + ". Review this input before presenting the run.")
    return {"suite": suite, "notes": notes, "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": secrets.token_hex(16), "payload": {"prototype_version": VERSION,
            "suite_sha256": fingerprint(suite), "max_hops": depth,
            "evaluation_status": "not_scored_without_independent_gold", "reference_checks": checks, "results": results}}


def evaluate_workbook(run, encoded):
    """Reuse the existing gold safeguards; never derive labels from predictions."""
    from evaluate import read_gold, score
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ValueError("The workbook upload is not valid base64.") from None
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist()) > 1000 or sum(i.file_size for i in z.infolist()) > 25 * 1024 * 1024:
            raise ValueError("Workbook expands beyond the supported size.")
    with tempfile.TemporaryDirectory(prefix="prism_gold_") as directory:
        path = Path(directory) / "labels.xlsx"
        path.write_bytes(raw)
        gold = read_gold(path, run["suite"])
    metrics = {}
    for mode in MODES:
        predictions = {i["ko_id"]: i["status"] for s in run["payload"]["results"].values() for i in s[mode]["items"]}
        metrics[mode] = score(gold, predictions)
        events = []
        for s in run["payload"]["results"].values():
            part = {i["ko_id"]: i["status"] for i in s[mode]["items"]}
            events.append(score({k: gold[k] for k in part}, part))
        metrics[mode]["macro"] = {}
        metrics[mode]["macro_event_denominators"] = {}
        for key in ("precision", "recall", "f1"):
            values = [e[key] for e in events if e[key] is not None]
            metrics[mode]["macro"][key] = sum(values) / len(values) if values else None
            metrics[mode]["macro_event_denominators"][key] = len(values)
    return {"gold_sha256": fingerprint(gold), "metrics": metrics,
            "interpretation": "Descriptive development results only. Scope and propagation correctness require independent assessment; this is not a non-inferiority test."}


class Handler(BaseHTTPRequestHandler):
    server_version = "PRISM-Local/1.0"

    def log_message(self, *args):
        pass  # Never log uploaded policy content, workbook data or notes.

    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        return self.headers.get("Host") in hosts and self.headers.get("Origin", f"http://127.0.0.1:{port}") in {f"http://{h}" for h in hosts}

    def send(self, status, data, mime="application/json; charset=utf-8", filename=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.local_request():
            return self.send(403, {"error": "Open this local app through localhost or 127.0.0.1."})
        path = urlsplit(self.path).path
        if path == "/api/sample":
            try:
                return self.send(200, json.loads(next(p for p in [BASE / "data/scenarios.json", BASE / "data/data.json"] if p.is_file()).read_text(encoding="utf-8")))
            except (OSError, ValueError, StopIteration):
                return self.send(404, {"error": "Bundled corpus missing. Place the UI beside data/scenarios.json, or upload a schema 0.3 / 0.4 scenario or corpus."})
        assets = {"/favicon.svg": ("favicon.svg", "image/svg+xml"), "/": ("index.html", "text/html; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if path not in assets:
            return self.send(404, {"error": "Not found."})
        name, mime = assets[path]
        try:
            self.send(200, (BASE / "ui" / name).read_bytes(), mime)
        except OSError:
            self.send(404, {"error": "Missing ui/" + name + ". See PRISM_ENGINE_UPDATE.md."})

    def do_POST(self):
        if not self.local_request() or self.headers.get("X-PRISM-Client") != "local-ui":
            return self.send(403, {"error": "This endpoint accepts requests from the local PRISM interface."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BYTES:
                raise ValueError("Upload limit is 8 MB per request.")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Send JSON through the dashboard upload controls.")
            data = json.loads(self.rfile.read(length), parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON value: " + x)))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
            route = urlsplit(self.path).path
            if route == "/api/shutdown":
                self.send(200,{"stopped":True})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if route == "/api/run":
                run = analyse(data.get("data"), data.get("max_hops", 3))
                with LOCK:
                    RUNS[run["run_id"]] = run
                    while len(RUNS) > 8:
                        RUNS.popitem(last=False)
                return self.send(200, run)
            with LOCK:
                run = RUNS.get(data.get("run_id"))
            if run is None:
                raise ValueError("This working run expired or the server restarted. Run the corpus again.")
            if route == "/api/evaluate":
                evaluation = evaluate_workbook(run, data.get("workbook"))
                with LOCK:
                    run["evaluation"] = evaluation
                return self.send(200, evaluation)
            if route == "/api/export":
                notes = clean_notes(data.get("notes", {}), run["suite"])
                content, mime, filename = export_report(run, notes, data.get("kind"))
                return self.send(200, content, mime, filename)
            self.send(404, {"error": "Not found."})
        except (ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError, zipfile.BadZipFile, ImportError, OSError) as exc:
            self.send(400, {"error": str(exc) or "The uploaded file could not be read."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        raise SystemExit(f"Could not start: {exc}. Try python app.py --port 8767") from None
    print(f"PRISM stakeholder workspace: http://127.0.0.1:{server.server_port}")
    print("Keep this terminal open. Press Ctrl+C to stop. Download a review session to retain notes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPRISM stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

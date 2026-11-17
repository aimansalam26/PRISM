"""Behaviour checks for the UI adapter. Run from PRISM: python -m unittest test_ui -v"""
import base64
from copy import deepcopy
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import app
from ui_exports import candidate_rows, csv_bytes, excel_bytes, export_report, report_sheets

BASE = Path(__file__).resolve().parent


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads((BASE / "data/scenarios.json").read_text(encoding="utf-8"))
        cls.bundle = app.analyse(cls.suite)

    def test_same_predictions_and_reference_as_engine(self):
        self.assertEqual(len(self.bundle["payload"]["reference_checks"]), 7)
        items = [i for s in self.bundle["payload"]["results"].values() for i in s["prism"]["items"]]
        self.assertEqual({v: sum(i["status"] == v for i in items) for v in ("Yes", "No", "Defer")}, {"Yes": 12, "No": 6, "Defer": 3})
        self.assertEqual(sum(i["status"] in {"Yes", "Defer"} for i in items), 15)

    def test_session_recomputes_and_restores_notes(self):
        notes = {"S5-C1": {"state": "question", "text": "Check the France exception."}}
        content, _, name = export_report(self.bundle, notes, "session")
        self.assertTrue(name.endswith(".json"))
        session = json.loads(content)
        session["results"] = {"invented": "must be ignored"}
        restored = app.analyse(session)
        self.assertEqual(restored["notes"], notes)
        self.assertEqual(restored["payload"], self.bundle["payload"])

    def test_single_scenario_upload(self):
        demo = json.loads((BASE / "data/policies.json").read_text(encoding="utf-8"))
        result = app.analyse(demo)
        self.assertEqual(len(result["suite"]["scenarios"]), 1)

    def test_unsupported_scope_change_is_rejected(self):
        bad = deepcopy(self.suite)
        bad["scenarios"][0]["event"]["scope_change"] = True
        with self.assertRaisesRegex(ValueError, "unsupported"):
            app.analyse(bad)

    def test_result_file_cannot_masquerade_as_corpus(self):
        with self.assertRaisesRegex(ValueError, "schema 0.3"):
            app.analyse(self.bundle["payload"])

    def test_duplicate_ids_are_rejected(self):
        bad = deepcopy(self.suite)
        bad["scenarios"].append(deepcopy(bad["scenarios"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate scenario"):
            app.analyse(bad)

    def test_invalid_note_does_not_change_gold_or_predictions(self):
        with self.assertRaisesRegex(ValueError, "unknown candidate"):
            app.clean_notes({"invented": {"state": "reviewed", "text": ""}}, self.suite)
        with self.assertRaisesRegex(ValueError, "Invalid review note"):
            app.clean_notes({"S1-C1": {"state": "approved", "text": ""}}, self.suite)

    def test_export_has_all_candidates_and_separate_scopes(self):
        rows = candidate_rows(self.bundle, {})
        self.assertEqual(len(rows), 22)
        sheets = report_sheets(self.bundle, {"S1-C2": {"state": "reviewed", "text": "Evidence inspected."}})
        self.assertIn("Affected scopes", sheets)
        self.assertIn("Traversal decisions", sheets)
        self.assertNotIn("Evaluation", sheets)
        self.assertTrue(any("Evidence inspected." in row for row in sheets["Candidates"]))

    def test_xlsx_is_valid_xml_and_text_is_not_formula(self):
        data = excel_bytes({"Example": [["Text", "Number"], ["=1+1", 7], ["<source> & evidence", 3]]})
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith((".xml", ".rels")):
                    ET.fromstring(z.read(name))
            root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            self.assertEqual(root.find('.//s:c[@r="A2"]', ns).attrib["t"], "inlineStr")
            self.assertEqual(len(root.findall(".//s:f", ns)), 0)

    def test_csv_formula_prefix_is_escaped(self):
        text = csv_bytes([["=1+1", "  @SUM(A1)", "ordinary"]]).decode("utf-8-sig")
        self.assertIn("'=1+1", text)
        self.assertIn("'  @SUM", text)

    def test_blank_gold_is_refused(self):
        encoded = base64.b64encode((BASE / "3_Label_Matrix.xlsx").read_bytes()).decode()
        with self.assertRaisesRegex(ValueError, "freeze date"):
            app.evaluate_workbook(self.bundle, encoded)

    def test_http_run_export_and_file_boundaries(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/") as response:
                self.assertIn(b"Review workspace", response.read())
            with self.assertRaises(HTTPError) as denied:
                urlopen(base + "/engine.py")
            self.assertEqual(denied.exception.code, 404)
            request = Request(base + "/api/run", json.dumps({"data": self.suite}).encode(), {"Content-Type": "application/json", "X-PRISM-Client": "local-ui"})
            with urlopen(request) as response:
                run = json.load(response)
            request = Request(base + "/api/export", json.dumps({"run_id": run["run_id"], "kind": "xlsx", "notes": {}}).encode(), {"Content-Type": "application/json", "X-PRISM-Client": "local-ui"})
            with urlopen(request) as response:
                self.assertEqual(response.read(2), b"PK")
            request = Request(base + "/api/run", b"{}", {"Content-Type": "application/json", "X-PRISM-Client": "local-ui", "Origin": "https://unrelated.example"})
            with self.assertRaises(HTTPError) as blocked:
                urlopen(request)
            self.assertEqual(blocked.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == "__main__":
    unittest.main()

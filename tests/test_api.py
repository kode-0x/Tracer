"""
Integration tests for Tracer Backend HTTP Server (backend/server.py).
Starts server on an ephemeral local port and tests REST endpoints.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from backend.server import TraceAPIHandler


class TestServerAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Bind to port 0 to get an OS-assigned available ephemeral port
        cls.server = HTTPServer(("127.0.0.1", 0), TraceAPIHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def _post(self, path, payload):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def test_health_endpoint(self):
        status, data = self._get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "healthy")

    def test_scenarios_list_endpoint(self):
        status, data = self._get("/api/scenarios")
        self.assertEqual(status, 200)
        self.assertIn("scenarios", data)
        self.assertGreaterEqual(len(data["scenarios"]), 4)

    def test_single_scenario_endpoint(self):
        status, data = self._get("/api/scenarios/INC-001")
        self.assertEqual(status, 200)
        self.assertEqual(data["incident_id"], "INC-001")

    def test_frontend_static_serving(self):
        url = f"http://127.0.0.1:{self.port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
            self.assertIn("Tracer", data)

    def test_investigate_post_endpoint(self):
        status, data = self._post("/api/investigate", {"scenario_id": "INC-002"})
        self.assertEqual(status, 200)
        self.assertEqual(data["incident_id"], "INC-002")
        self.assertEqual(data["leading_hypothesis"]["id"], "H2")
        self.assertGreaterEqual(len(data["investigation_steps"]), 1)
        self.assertIn("completed_checks_count", data)
        self.assertIn("total_checks_available", data)
        self.assertEqual(data["total_checks_available"], 3)
        self.assertNotIn("ground_truth", data)


    def test_scenario_api_never_exposes_ground_truth(self):
        """Regression test: verify public scenario endpoints never expose ground_truth field."""
        # Single scenario endpoint
        status, data = self._get("/api/scenarios/INC-001")
        self.assertEqual(status, 200)
        self.assertNotIn("ground_truth", data)

        # Scenarios list endpoint
        status, data = self._get("/api/scenarios")
        self.assertEqual(status, 200)
        for sc in data.get("scenarios", []):
            self.assertNotIn("ground_truth", sc)

    def test_get_unknown_scenario_returns_404(self):
        """Verify GET /api/scenarios/UNKNOWN_ID returns HTTP 404."""
        url = f"http://127.0.0.1:{self.port}/api/scenarios/UNKNOWN_ID_DOES_NOT_EXIST"
        req = urllib.request.Request(url)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 404)
        error_data = json.loads(ctx.exception.read().decode("utf-8"))
        ctx.exception.close()
        self.assertIn("error", error_data)

    def test_post_investigate_malformed_json_returns_400(self):
        """Verify malformed JSON payload sent to /api/investigate returns HTTP 400."""
        url = f"http://127.0.0.1:{self.port}/api/investigate"
        malformed_body = b"this is not valid json {{{{"
        req = urllib.request.Request(
            url,
            data=malformed_body,
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        error_data = json.loads(ctx.exception.read().decode("utf-8"))
        ctx.exception.close()
        self.assertIn("error", error_data)


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for Tracer Diagnostic Executor (backend/diagnostics.py).
"""

import unittest
from backend.diagnostics import run_check


class TestDiagnosticsExecutor(unittest.TestCase):

    def setUp(self):
        self.sample_check = {
            "id": "T1",
            "name": "Validate payment configuration",
            "required_evidence": ["payment_config"],
            "possible_results": ["valid", "invalid"]
        }

    def test_run_check_successful(self):
        evidence = {"payment_config": "invalid"}
        result = run_check(self.sample_check, evidence)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"], "invalid")
        self.assertEqual(result["evidence_type"], "simulated")
        self.assertEqual(result["evidence_source"], "payment_config")

    def test_run_check_missing_evidence(self):
        evidence = {"other_key": "some_value"}
        result = run_check(self.sample_check, evidence)

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("Missing evidence", result["reason"])

    def test_run_check_unexpected_result(self):
        evidence = {"payment_config": "corrupted_payload"}
        result = run_check(self.sample_check, evidence)

        self.assertEqual(result["status"], "invalid_result")
        self.assertIn("Unexpected result", result["reason"])

    def test_run_check_malformed_definition(self):
        result = run_check({}, {"payment_config": "valid"})
        self.assertEqual(result["status"], "invalid_check_definition")

        result2 = run_check(None, {})
        self.assertEqual(result2["status"], "invalid_check_definition")


if __name__ == "__main__":
    unittest.main()

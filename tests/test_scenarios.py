"""
End-to-End tests for all Tracer Incident Scenarios.
Verifies each scenario produces expected hypothesis classifications.
"""

import unittest
from pathlib import Path
from backend.investigator import (
    PROJECT_ROOT,
    load_json,
    run_investigation,
    resolve_scenario_path
)


class TestScenariosE2E(unittest.TestCase):

    def setUp(self):
        self.checks_data = load_json(PROJECT_ROOT / "data" / "diagnostic_checks.json")

    def test_scenario_001_checkout_config(self):
        scenario_file = resolve_scenario_path("INC-001")
        incident = load_json(scenario_file)
        result = run_investigation(incident, self.checks_data)

        self.assertIsNotNone(result["leading_hypothesis"])
        self.assertEqual(result["leading_hypothesis"]["id"], "H1")
        self.assertTrue(result["leading_hypothesis"]["is_decisive"], "INC-001 is genuinely decisive")
        self.assertIn("CONFIRMED ROOT CAUSE: H1 - Incorrect payment endpoint", result["report"])
        self.assertIn("All alternative hypotheses contradicted by diagnostic telemetry", result["report"])
        self.assertIn("invalid", result["report"])
        self.assertIn("payment endpoint in version 1.8", result["report"])

    def test_scenario_002_provider_outage(self):
        scenario_file = resolve_scenario_path("INC-002")
        incident = load_json(scenario_file)
        result = run_investigation(incident, self.checks_data)

        self.assertIsNotNone(result["leading_hypothesis"])
        self.assertEqual(result["leading_hypothesis"]["id"], "H2")
        # Must be cautious because H3 was ruled out only by initial log observation E3, not by probe T3
        self.assertFalse(result["leading_hypothesis"]["is_decisive"], "INC-002 must not claim decisive root cause")
        self.assertIn("H3", result["leading_hypothesis"]["unresolved_alternatives"])
        self.assertIn("PROBABLE ROOT CAUSE (INCOMPLETE TRIAGE): H2 - Payment provider outage", result["report"])
        self.assertNotIn("All alternative hypotheses contradicted by diagnostic telemetry", result["report"])
        self.assertIn("ruled out only by preliminary observations without an executed diagnostic probe", result["report"])
        self.assertIn("circuit breaker failover", result["report"])

    def test_scenario_003_database_pool(self):
        scenario_file = resolve_scenario_path("INC-003")
        incident = load_json(scenario_file)

        # 1. Verify weak initial observations do not prematurely contradict H1 or H2
        initial_obs = incident.get("evidence", [])
        obs_effects = {o["id"]: o.get("effects", {}) for o in initial_obs}
        self.assertEqual(obs_effects["E2"], {}, "E2 (no recent deployments) must be neutral context")
        self.assertEqual(obs_effects["E3"], {}, "E3 (45ms ping) must be neutral context")

        # 2. Run investigation
        result = run_investigation(incident, self.checks_data)

        # 3. Verify all relevant diagnostic probes executed to test unresolved hypotheses
        self.assertEqual(result["completed_checks_count"], 3)
        self.assertEqual(result["total_checks_available"], 3)
        executed_check_ids = [step["check_id"] for step in result["investigation_steps"]]
        self.assertIn("T1", executed_check_ids, "T1 (payment config) must run")
        self.assertIn("T2", executed_check_ids, "T2 (payment provider) must run")
        self.assertIn("T3", executed_check_ids, "T3 (database health) must run")

        # 4. Verify evidence-based evaluations: H1/H2 contradicted by probes, H3 supported
        final_eval_map = {e["id"]: e for e in result["final_evaluations"]}
        self.assertEqual(final_eval_map["H1"]["status"], "contradicted")
        self.assertTrue(any("Validate payment configuration" in c for c in final_eval_map["H1"]["contradicting_evidence"]))

        self.assertEqual(final_eval_map["H2"]["status"], "contradicted")
        self.assertTrue(any("Check payment provider" in c for c in final_eval_map["H2"]["contradicting_evidence"]))

        self.assertEqual(final_eval_map["H3"]["status"], "supported")
        self.assertTrue(any("Check database health" in s for s in final_eval_map["H3"]["supporting_evidence"]))

        # 5. Verify final conclusion matches the evidence actually collected
        self.assertIsNotNone(result["leading_hypothesis"])
        self.assertEqual(result["leading_hypothesis"]["id"], "H3")
        self.assertTrue(result["leading_hypothesis"]["is_decisive"])
        self.assertEqual(result["leading_hypothesis"]["unresolved_alternatives"], [])
        self.assertIn("CONFIRMED ROOT CAUSE: H3 - Database failure", result["report"])
        self.assertIn("All alternative hypotheses contradicted by diagnostic telemetry", result["report"])
        self.assertIn("terminate long-running blocked database queries", result["report"])
        self.assertIn("connection pool", result["report"])

    def test_scenario_004_intermittent_ambiguous(self):
        scenario_file = resolve_scenario_path("INC-004")
        incident = load_json(scenario_file)
        result = run_investigation(incident, self.checks_data)

        # Inconclusive scenario should not have a false positive leading hypothesis
        self.assertIsNone(result["leading_hypothesis"])
        self.assertIn("Inconclusive", result["report"])


if __name__ == "__main__":
    unittest.main()

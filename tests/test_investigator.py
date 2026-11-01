"""
Unit tests for Tracer Investigation Core (backend/investigator.py).
Tests check selection heuristic, hypothesis evaluation, stopping condition,
and strictly verifies runtime independence from ground_truth.
"""

import unittest
from backend.investigator import (
    choose_next_check,
    evaluate_hypotheses,
    has_decisive_result,
    run_investigation,
    build_report
)


class TestInvestigatorCore(unittest.TestCase):

    def setUp(self):
        self.hypotheses = [
            {"id": "H1", "name": "Config Error", "recommended_action": "Fix config URL."},
            {"id": "H2", "name": "Provider Outage", "recommended_action": "Contact vendor."},
            {"id": "H3", "name": "Database Failure", "recommended_action": "Restart DB pool."}
        ]
        self.checks = [
            {
                "id": "T1",
                "name": "Check Config",
                "required_evidence": ["config_val"],
                "possible_results": ["valid", "invalid"],
                "helps_distinguish": ["H1", "H2"],
                "result_effects": {
                    "valid": {"H1": "contradicts"},
                    "invalid": {"H1": "supports"}
                }
            },
            {
                "id": "T2",
                "name": "Check Provider",
                "required_evidence": ["provider_val"],
                "possible_results": ["healthy", "unhealthy"],
                "helps_distinguish": ["H1", "H2"],
                "result_effects": {
                    "healthy": {"H2": "contradicts"},
                    "unhealthy": {"H2": "supports"}
                }
            }
        ]

    def test_evaluate_hypotheses_with_initial_observations(self):
        initial_obs = [
            {
                "id": "E1",
                "source": "deployment_log",
                "observation": "Recent deployment detected.",
                "effects": {"H1": "supports"}
            },
            {
                "id": "E2",
                "source": "db_metrics",
                "observation": "DB latency normal.",
                "effects": {"H3": "contradicts"}
            }
        ]
        evals = evaluate_hypotheses(self.hypotheses, {}, self.checks, initial_observations=initial_obs)

        eval_map = {e["id"]: e for e in evals}
        self.assertEqual(eval_map["H1"]["status"], "supported")
        self.assertEqual(eval_map["H2"]["status"], "unresolved")
        self.assertEqual(eval_map["H3"]["status"], "contradicted")
        self.assertTrue(any("INITIAL OBSERVATION" in s for s in eval_map["H1"]["supporting_evidence"]))

    def test_choose_next_check_scoring(self):
        evaluations = [
            {"id": "H1", "status": "supported"},
            {"id": "H2", "status": "unresolved"},
            {"id": "H3", "status": "unresolved"}
        ]
        available_sources = {"config_val", "provider_val"}
        completed = set()

        check, reason = choose_next_check(self.checks, available_sources, completed, evaluations)
        self.assertIsNotNone(check)
        self.assertIn(check["id"], ["T1", "T2"])
        self.assertIn("Heuristic Relevance Score", reason)

    def test_has_decisive_result_positive(self):
        evaluations = [
            {"id": "H1", "name": "Config Error", "status": "supported"},
            {
                "id": "H2",
                "name": "Provider Outage",
                "status": "contradicted",
                "contradicting_evidence": ["[SIMULATED PROBE (Check Provider)] returned 'healthy'."]
            },
            {
                "id": "H3",
                "name": "Database Failure",
                "status": "contradicted",
                "contradicting_evidence": ["[SIMULATED PROBE (Check DB)] returned 'healthy'."]
            }
        ]
        # Completed all distinguishing checks
        completed = {"T1", "T2"}
        is_decisive, reason = has_decisive_result(evaluations, self.checks, completed)
        self.assertTrue(is_decisive)
        self.assertIn("Decisive outcome", reason)

    def test_ground_truth_never_used_at_runtime(self):
        """
        Verify that tampering with or removing ground_truth in incident data
        has zero effect on the runtime investigation outcome.
        """
        incident_a = {
            "incident_id": "TEST-1",
            "title": "Test Incident",
            "ground_truth": "H1",  # Matches simulated evidence
            "hypotheses": self.hypotheses,
            "evidence": [],
            "diagnostic_results": {
                "config_val": "invalid",
                "provider_val": "healthy"
            }
        }

        incident_b = {
            "incident_id": "TEST-1",
            "title": "Test Incident",
            "ground_truth": "H3_FAKE_ANSWER",  # Conflicting / misleading ground truth tag
            "hypotheses": self.hypotheses,
            "evidence": [],
            "diagnostic_results": {
                "config_val": "invalid",
                "provider_val": "healthy"
            }
        }

        incident_c = {
            "incident_id": "TEST-1",
            "title": "Test Incident",
            # No ground_truth field at all
            "hypotheses": self.hypotheses,
            "evidence": [],
            "diagnostic_results": {
                "config_val": "invalid",
                "provider_val": "healthy"
            }
        }

        diagnostic_data = {"checks": self.checks}

        res_a = run_investigation(incident_a, diagnostic_data)
        res_b = run_investigation(incident_b, diagnostic_data)
        res_c = run_investigation(incident_c, diagnostic_data)

        # All three must produce identical leading hypotheses despite ground_truth changes
        self.assertEqual(res_a["leading_hypothesis"]["id"], "H1")
        self.assertEqual(res_b["leading_hypothesis"]["id"], "H1")
        self.assertEqual(res_c["leading_hypothesis"]["id"], "H1")

        # Steps and evaluations must be identical
        self.assertEqual(res_a["investigation_steps"], res_b["investigation_steps"])
        self.assertEqual(res_a["investigation_steps"], res_c["investigation_steps"])


    def test_hypothesis_mixed_when_supporting_and_contradicting(self):
        """Verify that a hypothesis with both supporting and contradicting evidence becomes 'mixed'."""
        initial_obs = [
            {
                "id": "E1",
                "source": "deployment_log",
                "observation": "Recent deployment detected.",
                "effects": {"H1": "supports"}
            }
        ]
        # T1 with valid config contradicts H1
        evidence_findings = {"config_val": "valid"}
        evals = evaluate_hypotheses(self.hypotheses, evidence_findings, self.checks, initial_observations=initial_obs)

        eval_map = {e["id"]: e for e in evals}
        self.assertEqual(eval_map["H1"]["status"], "mixed")
        self.assertTrue(len(eval_map["H1"]["supporting_evidence"]) > 0)
        self.assertTrue(len(eval_map["H1"]["contradicting_evidence"]) > 0)

    def test_multiple_supported_hypotheses_handled_safely(self):
        """Verify that multiple supported hypotheses are treated as ambiguous without false certainty."""
        incident = {
            "incident_id": "TEST-MULTI",
            "title": "Multi-Supported Test",
            "hypotheses": self.hypotheses,
            "evidence": [],
            "diagnostic_results": {
                "config_val": "invalid",    # Supports H1
                "provider_val": "unhealthy"  # Supports H2
            }
        }
        res = run_investigation(incident, {"checks": self.checks})

        self.assertIsNone(res["leading_hypothesis"])
        self.assertIn("Ambiguous", res["report"])
        self.assertIn("Ambiguous outcome", res["stopping_reason"])

    def test_exhausted_checks_with_unresolved_alternatives_does_not_claim_all_contradicted(self):
        """
        Verify that when checks are exhausted, the engine does NOT claim all alternatives
        are contradicted if any competing hypothesis remains unresolved.
        """
        # Checks only test config_val (H1/H2). H3 has no check and remains unresolved.
        incident = {
            "incident_id": "TEST-EXHAUST",
            "title": "Exhausted Checks Test",
            "hypotheses": self.hypotheses,
            "evidence": [],
            "diagnostic_results": {
                "config_val": "invalid",   # Supports H1, contradicts nothing for H3
                "provider_val": "healthy"  # Contradicts H2, leaves H3 unresolved
            }
        }
        res = run_investigation(incident, {"checks": self.checks})

        self.assertIsNotNone(res["leading_hypothesis"])
        self.assertEqual(res["leading_hypothesis"]["id"], "H1")
        # Must flag that triage is incomplete
        self.assertFalse(res["leading_hypothesis"]["is_decisive"])
        self.assertIn("H3", res["leading_hypothesis"]["unresolved_alternatives"])
        self.assertNotIn("all alternatives contradicted", res["stopping_reason"])
        self.assertIn("Incomplete triage", res["stopping_reason"])
        self.assertIn("PROBABLE ROOT CAUSE (INCOMPLETE TRIAGE)", res["report"])

    def test_empty_hypotheses_and_empty_checks_handled_safely(self):
        """Verify engine gracefully handles incidents with empty hypotheses or empty check sets."""
        incident_empty_h = {
            "incident_id": "TEST-EMPTY-H",
            "title": "Empty Hypotheses",
            "hypotheses": [],
            "evidence": [],
            "diagnostic_results": {"config_val": "invalid"}
        }
        res_empty_h = run_investigation(incident_empty_h, {"checks": self.checks})
        self.assertIsNone(res_empty_h["leading_hypothesis"])
        self.assertEqual(res_empty_h["final_evaluations"], [])

        incident_empty_c = {
            "incident_id": "TEST-EMPTY-C",
            "title": "Empty Checks",
            "hypotheses": self.hypotheses,
            "evidence": [],
            "diagnostic_results": {"config_val": "invalid"}
        }
        res_empty_c = run_investigation(incident_empty_c, {"checks": []})
        self.assertIsNone(res_empty_c["leading_hypothesis"])
        self.assertIn("Inconclusive", res_empty_c["report"])


if __name__ == "__main__":
    unittest.main()

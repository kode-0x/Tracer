"""
Tracer - Autonomous Incident Investigation and Root Cause Analysis Engine
Autonomously investigates system incidents by selecting and executing
diagnostic checks to test and evaluate competing hypotheses.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path for direct or module execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.diagnostics import run_check


def load_json(relative_or_abs_path):
    """Load JSON from a path relative to PROJECT_ROOT or absolute."""
    path = Path(relative_or_abs_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def list_available_scenarios():
    """List all available incident scenarios in data/ and data/scenarios/."""
    scenarios = []
    seen_ids = set()

    search_dirs = [PROJECT_ROOT / "data" / "scenarios", PROJECT_ROOT / "data"]
    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for file_path in sorted(s_dir.glob("*.json")):
            if file_path.name == "diagnostic_checks.json":
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                inc_id = data.get("incident_id")
                if inc_id and inc_id not in seen_ids:
                    seen_ids.add(inc_id)
                    scenarios.append({
                        "file_path": str(file_path.relative_to(PROJECT_ROOT)),
                        "incident_id": inc_id,
                        "title": data.get("title", file_path.stem),
                        "service": data.get("service", "unknown-service"),
                        "severity": data.get("severity", "MEDIUM"),
                        "description": data.get("description", "")
                    })
            except Exception:
                continue

    return scenarios


def resolve_scenario_path(scenario_identifier):
    """Resolve a scenario identifier (path, filename, or incident_id) to a Path."""
    if not scenario_identifier:
        return PROJECT_ROOT / "data" / "incident.json"

    direct_path = Path(scenario_identifier)
    if direct_path.exists():
        return direct_path

    rel_path = PROJECT_ROOT / scenario_identifier
    if rel_path.exists():
        return rel_path

    # Check scenarios folder
    in_scenarios = PROJECT_ROOT / "data" / "scenarios" / scenario_identifier
    if in_scenarios.exists():
        return in_scenarios
    if in_scenarios.with_suffix(".json").exists():
        return in_scenarios.with_suffix(".json")

    # Match by incident_id
    for item in list_available_scenarios():
        if item["incident_id"].lower() == scenario_identifier.lower():
            return PROJECT_ROOT / item["file_path"]

    raise FileNotFoundError(f"Could not locate scenario matching: {scenario_identifier}")


def evaluate_hypotheses(hypotheses, evidence_findings, checks, initial_observations=None):
    """
    Evaluate hypothesis statuses based on gathered diagnostic evidence
    and initial incident observations.
    
    Status values:
    - 'supported': Only supporting evidence collected.
    - 'contradicted': Only contradicting evidence collected.
    - 'mixed': Both supporting and contradicting evidence collected.
    - 'unresolved': No conclusive supporting or contradicting evidence.
    """
    results = []

    # Map effects for each hypothesis
    effects_by_hypothesis = {
        h["id"]: {
            "supporting": [],
            "contradicting": []
        }
        for h in hypotheses
    }

    # 1. Incorporate initial observations using explicit explainable rules
    if initial_observations:
        for obs in initial_observations:
            obs_effects = obs.get("effects", {})
            obs_text = obs.get("observation", "")
            source = obs.get("source", "initial_evidence")

            for h_id, effect in obs_effects.items():
                if h_id not in effects_by_hypothesis:
                    continue
                tag = f"[INITIAL OBSERVATION ({source})] {obs_text}"
                if effect == "supports":
                    effects_by_hypothesis[h_id]["supporting"].append(tag)
                elif effect == "contradicts":
                    effects_by_hypothesis[h_id]["contradicting"].append(tag)

    # 2. Evaluate simulated diagnostic check results
    for check in checks:
        required_keys = check.get("required_evidence", [])
        if not required_keys:
            continue
        primary_key = required_keys[0]

        # Ignore checks whose results haven't been collected yet
        if primary_key not in evidence_findings:
            continue

        result_val = evidence_findings[primary_key]
        effects = check.get("result_effects", {}).get(result_val, {})

        for h_id, effect in effects.items():
            if h_id not in effects_by_hypothesis:
                continue

            tag = f"[SIMULATED PROBE ({check['name']})] returned '{result_val}'."
            if effect == "supports":
                effects_by_hypothesis[h_id]["supporting"].append(tag)
            elif effect == "contradicts":
                effects_by_hypothesis[h_id]["contradicting"].append(tag)

    # 3. Compile hypothesis status summaries
    for hypothesis in hypotheses:
        h_id = hypothesis["id"]
        supporting = effects_by_hypothesis[h_id]["supporting"]
        contradicting = effects_by_hypothesis[h_id]["contradicting"]

        if supporting and contradicting:
            status = "mixed"
        elif supporting:
            status = "supported"
        elif contradicting:
            status = "contradicted"
        else:
            status = "unresolved"

        results.append({
            "id": h_id,
            "name": hypothesis["name"],
            "description": hypothesis.get("description", ""),
            "recommended_action": hypothesis.get("recommended_action", ""),
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "status": status
        })

    return results


def choose_next_check(checks, available_sources, completed_checks, evaluations):
    """
    Select the next best diagnostic check using a transparent heuristic scoring algorithm.
    Prioritizes checks that can disambiguate unresolved or competing supported hypotheses.
    
    Score = (Unresolved Hypotheses Distinguished * 2) + (Supported Hypotheses Distinguished * 1)
    """
    unresolved_ids = {
        item["id"]
        for item in evaluations
        if item["status"] in ("unresolved", "mixed")
    }

    supported_ids = {
        item["id"]
        for item in evaluations
        if item["status"] == "supported"
    }

    candidates = []

    for check in checks:
        if check["id"] in completed_checks:
            continue

        required = check.get("required_evidence", [])
        if not required or not all(item in available_sources for item in required):
            continue

        relevant_ids = set(check.get("helps_distinguish", []))
        unresolved_coverage = len(relevant_ids & unresolved_ids)
        supported_coverage = len(relevant_ids & supported_ids)

        if unresolved_coverage == 0 and supported_coverage == 0:
            continue

        score = unresolved_coverage * 2 + supported_coverage
        reason = (
            f"Heuristic Relevance Score {score}: Helps distinguish "
            f"{unresolved_coverage} unresolved and {supported_coverage} supported hypotheses "
            f"({', '.join(sorted(relevant_ids))})."
        )
        candidates.append((check, score, reason))

    if not candidates:
        return None, None

    # Sort descending by score, tie-break by check id
    candidates.sort(key=lambda item: (item[1], item[0]["id"]), reverse=True)
    selected_check, _, selected_reason = candidates[0]

    return selected_check, selected_reason


def classify_action_safety(action_text):
    """
    Classify whether a remediation action is safe read-only verification
    or requires explicit operator review due to potential operational disruption.
    
    Actions involving query termination, service restarts, gateway failovers,
    or connection-pool resets are classified as OPERATOR_REVIEW_REQUIRED.
    """
    if not action_text:
        return {
            "tier": "SAFE_READ_ONLY",
            "badge": "READ-ONLY VERIFICATION",
            "warning": "Safe read-only verification step. No system state modification expected."
        }

    lower = action_text.lower()
    disruptive_terms = [
        "kill", "terminate", "restart", "failover", "cycle",
        "drop", "flush", "revert", "purge", "connection pool", "connection-pool"
    ]

    matched_terms = [term for term in disruptive_terms if term in lower]

    if matched_terms:
        return {
            "tier": "OPERATOR_REVIEW_REQUIRED",
            "badge": "OPERATOR REVIEW REQUIRED",
            "disruptive_aspects": matched_terms,
            "warning": (
                "Potentially disruptive operational action (involves connection termination, "
                "service restart, or state change). Manual human verification required; "
                "automatic execution disabled."
            )
        }

    return {
        "tier": "SAFE_READ_ONLY",
        "badge": "READ-ONLY VERIFICATION",
        "disruptive_aspects": [],
        "warning": "Safe read-only verification step. No system state modification expected."
    }


def has_decisive_result(evaluations, checks, completed_checks):
    """
    Determine whether the investigation has reached a conclusive termination point.
    Returns (is_decisive, stopping_reason).
    """
    supported = [item for item in evaluations if item["status"] == "supported"]
    unresolved = [item for item in evaluations if item["status"] in ("unresolved", "mixed")]

    # Check if any remaining checks could differentiate hypotheses
    remaining_checks = [
        c for c in checks
        if c["id"] not in completed_checks
    ]

    # Decisive Case 1: Exactly 1 hypothesis is supported and all alternatives are contradicted
    if len(supported) == 1 and len(unresolved) == 0:
        leading = supported[0]
        # Check if any non-leading hypothesis was only contradicted by initial observations without probe telemetry
        non_leading = [item for item in evaluations if item["id"] != leading["id"]]
        obs_only_contradicted = [
            item["id"] for item in non_leading
            if not any("[SIMULATED PROBE" in ev for ev in item.get("contradicting_evidence", []))
        ]

        # Ensure no remaining check targets this hypothesis
        further_checks = [
            c for c in remaining_checks
            if leading["id"] in c.get("helps_distinguish", [])
        ]
        if not further_checks:
            if not obs_only_contradicted:
                return True, (
                    f"Decisive outcome: Leading hypothesis '{leading['id']} - {leading['name']}' "
                    "is confirmed with all alternatives contradicted by diagnostic telemetry."
                )
            else:
                return True, (
                    f"Incomplete triage: Leading candidate '{leading['id']} - {leading['name']}' "
                    f"is supported, but alternative(s) {', '.join(obs_only_contradicted)} were ruled out only by initial observations without an executed diagnostic probe."
                )

    # Decisive Case 2: No more eligible checks can be performed
    if not remaining_checks:
        if len(supported) == 1:
            non_leading = [item for item in evaluations if item["id"] != supported[0]["id"]]
            obs_only_contradicted = [
                item["id"] for item in non_leading
                if not any("[SIMULATED PROBE" in ev for ev in item.get("contradicting_evidence", []))
            ]
            if len(unresolved) == 0 and not obs_only_contradicted:
                return True, (
                    f"Decisive outcome: Leading hypothesis '{supported[0]['id']} - {supported[0]['name']}' "
                    "is confirmed with all diagnostic checks completed and all alternatives contradicted by diagnostic telemetry."
                )
            elif len(unresolved) == 0 and obs_only_contradicted:
                return True, (
                    f"Incomplete triage: Leading candidate '{supported[0]['id']} - {supported[0]['name']}' "
                    f"is supported, but alternative(s) {', '.join(obs_only_contradicted)} were ruled out only by initial observations without an executed diagnostic probe."
                )
            else:
                unresolved_names = [f"{u['id']} ({u['status']})" for u in unresolved]
                return True, (
                    f"Incomplete triage: Leading candidate '{supported[0]['id']} - {supported[0]['name']}' "
                    f"is supported, but competing alternatives remain unresolved or mixed: {', '.join(unresolved_names)}."
                )
        elif len(supported) > 1:
            supported_names = [f"{s['id']} - {s['name']}" for s in supported]
            return True, f"Ambiguous outcome: Multiple competing hypotheses supported ({', '.join(supported_names)}); no further checks available."
        else:
            return True, "Inconclusive outcome: No hypotheses supported by diagnostic checks; telemetry appears healthy or ambiguous."

    return False, "Investigation continuing: Diagnostic checks remain."


def build_report(incident, evaluations, history, stopping_reason=None):
    """
    Construct a formatted, comprehensive investigation report.
    Presents findings, confidence notes, and hypothesis-specific remediation steps.
    """
    report = []
    separator = "=" * 50

    report.append("\n" + separator)
    report.append("TRACER INCIDENT INVESTIGATION REPORT")
    report.append(separator)
    report.append(f"Incident ID : {incident.get('incident_id', 'UNKNOWN')}")
    report.append(f"Title       : {incident.get('title', 'Untitled')}")
    report.append(f"Service     : {incident.get('service', 'N/A')}")
    report.append(f"Severity    : {incident.get('severity', 'UNKNOWN')}")
    report.append(f"Description : {incident.get('description', '')}")

    supported = [item for item in evaluations if item["status"] == "supported"]
    unresolved = [item for item in evaluations if item["status"] in ("unresolved", "mixed")]
    mixed = [item for item in evaluations if item["status"] == "mixed"]

    if len(supported) == 1:
        leading = supported[0]
        action = leading.get("recommended_action") or f"Investigate root cause related to {leading['name']}."
        safety = classify_action_safety(action)

        if len(unresolved) == 0:
            non_leading = [item for item in evaluations if item["id"] != leading["id"]]
            probe_contradicted = []
            obs_only_contradicted = []
            for item in non_leading:
                has_probe_contradiction = any("[SIMULATED PROBE" in ev for ev in item.get("contradicting_evidence", []))
                if has_probe_contradiction:
                    probe_contradicted.append(item["id"])
                else:
                    obs_only_contradicted.append(item["id"])

            if not obs_only_contradicted:
                report.append(f"\n[+] CONFIRMED ROOT CAUSE: {leading['id']} - {leading['name']}")
                report.append("    Confidence Note: Decisive. All alternative hypotheses contradicted by diagnostic telemetry.")
            else:
                report.append(f"\n[!] PROBABLE ROOT CAUSE (INCOMPLETE TRIAGE): {leading['id']} - {leading['name']}")
                report.append(
                    f"    Confidence Note: Leading candidate is supported by diagnostic telemetry, "
                    f"but alternative(s) ({', '.join(obs_only_contradicted)}) were ruled out only by preliminary observations without an executed diagnostic probe. "
                    "Further probe verification recommended before concluding definitively."
                )
        else:
            unresolved_summary = ", ".join([f"{u['id']} ({u['status']})" for u in unresolved])
            report.append(f"\n[!] PROBABLE ROOT CAUSE (INCOMPLETE TRIAGE): {leading['id']} - {leading['name']}")
            report.append(f"    Confidence Note: Leading candidate is supported, but competing alternatives were NOT ruled out ({unresolved_summary}). Further targeted checks required.")

        report.append(f"\n[+] RECOMMENDED NEXT ACTION [{safety['badge']}]:")
        report.append(f"    Action: {action}")
        report.append(f"    Safety Tier: {safety['tier']}")
        report.append(f"    Safety Note: {safety['warning']}")

    elif len(supported) > 1:
        report.append("\n[?] LEADING ROOT CAUSE: Ambiguous / Multiple Competing Causes")
        report.append(f"    Competing Hypotheses: {', '.join([h['id'] + ': ' + h['name'] for h in supported])}")
        report.append("    Confidence Note: Multiple hypotheses have supporting evidence. Further manual triage required.")
        report.append("\n[?] RECOMMENDED NEXT ACTION [OPERATOR REVIEW REQUIRED]:")
        report.append("    Action: Review application traces and isolate components to differentiate causes.")
        report.append("    Safety Note: Requires manual review before executing failover or remediation.")
    elif mixed:
        report.append("\n[?] LEADING ROOT CAUSE: Mixed Telemetry Signals")
        report.append("    Confidence Note: Evidence shows contradictory signals across probes.")
        report.append("\n[?] RECOMMENDED NEXT ACTION [OPERATOR REVIEW REQUIRED]:")
        report.append("    Action: Audit logging pipelines and retry diagnostics under controlled load.")
        report.append("    Safety Note: Telemetry inconclusive; avoid unverified production interventions.")
    else:
        report.append("\n[?] LEADING ROOT CAUSE: Inconclusive / Transient Event")
        report.append("    Confidence Note: All executed diagnostic probes returned healthy or non-discriminating results.")
        report.append("\n[?] RECOMMENDED NEXT ACTION [READ-ONLY VERIFICATION]:")
        report.append("    Action: Capture fine-grained distributed traces and monitor for recurrence.")
        report.append("    Safety Note: Safe read-only telemetry monitoring; no operational disruption warranted.")

    if stopping_reason:
        report.append(f"\nInvestigation Termination Rationale:\n- {stopping_reason}")

    report.append("\nDiagnostic Checks Executed:")
    if history:
        for idx, item in enumerate(history, 1):
            report.append(
                f"  {idx}. {item['check']} (ID: {item.get('check_id', 'N/A')}): '{item['result']}' "
                f"[{item.get('evidence_type', 'simulated').upper()} EVIDENCE]"
            )
    else:
        report.append("  - No checks completed.")

    report.append("\nHypothesis Evaluation Summary:")
    for item in evaluations:
        report.append(f"\n  - {item['id']}: {item['name']}")
        report.append(f"    Status: {item['status'].upper()}")

        if item["supporting_evidence"]:
            report.append("    Supporting:")
            for ev in item["supporting_evidence"]:
                report.append(f"      * {ev}")

        if item["contradicting_evidence"]:
            report.append("    Contradicting:")
            for ev in item["contradicting_evidence"]:
                report.append(f"      * {ev}")

        if not item["supporting_evidence"] and not item["contradicting_evidence"]:
            report.append("    Evidence: No direct signals observed.")

    report.append("\n" + "-" * 50)
    report.append(
        "Notice: This investigation evaluated simulated telemetry fixtures.\n"
        "Ground truth is never consulted by Tracer runtime investigation logic."
    )
    report.append(separator + "\n")

    return "\n".join(report)


def run_investigation(incident_data, diagnostic_data):
    """
    Execute a full investigation programmatically and return a structured dictionary
    containing the complete chronological trace, hypothesis evaluations, and final report.
    
    This function is strictly ground-truth blind and safe for API and CLI consumption.
    """
    hypotheses = incident_data.get("hypotheses", [])
    initial_observations = incident_data.get("evidence", [])
    simulated_telemetry = incident_data.get("diagnostic_results", {})
    checks = diagnostic_data.get("checks", [])

    available_sources = set(simulated_telemetry.keys())
    completed_checks = set()
    history = []
    investigation_steps = []

    # Initial baseline hypothesis evaluation
    evaluations = evaluate_hypotheses(
        hypotheses=hypotheses,
        evidence_findings={},
        checks=checks,
        initial_observations=initial_observations
    )

    stopping_reason = None
    step_num = 1

    while True:
        # Check termination condition before picking next check
        is_decisive, reason = has_decisive_result(evaluations, checks, completed_checks)
        if is_decisive:
            stopping_reason = reason
            break

        # Select next diagnostic check
        check, selection_reason = choose_next_check(
            checks=checks,
            available_sources=available_sources,
            completed_checks=completed_checks,
            evaluations=evaluations
        )

        if check is None:
            stopping_reason = "No more eligible diagnostic checks match available evidence sources."
            break

        check_id = check["id"]
        result = run_check(check, simulated_telemetry)
        completed_checks.add(check_id)

        step_record = {
            "step": step_num,
            "check_id": check_id,
            "check_name": check["name"],
            "description": check.get("description", ""),
            "selection_reason": selection_reason,
            "status": result["status"],
            "result": result.get("result"),
            "evidence_type": result.get("evidence_type", "simulated"),
            "evidence_source": result.get("evidence_source", "")
        }

        if result["status"] == "completed":
            primary_key = check["required_evidence"][0]
            # Record in history
            history.append({
                "check_id": check_id,
                "check": check["name"],
                "result": result["result"],
                "evidence_type": result.get("evidence_type", "simulated")
            })

            # Re-evaluate hypotheses with new evidence
            findings_so_far = {item["evidence_source"]: item["result"] for item in investigation_steps if item["status"] == "completed"}
            findings_so_far[primary_key] = result["result"]

            evaluations = evaluate_hypotheses(
                hypotheses=hypotheses,
                evidence_findings=findings_so_far,
                checks=checks,
                initial_observations=initial_observations
            )

        step_record["evaluations_after_step"] = [dict(e) for e in evaluations]
        investigation_steps.append(step_record)
        step_num += 1

    # Final report
    report_text = build_report(incident_data, evaluations, history, stopping_reason)

    leading_hyp = None
    supported = [item for item in evaluations if item["status"] == "supported"]
    unresolved = [item for item in evaluations if item["status"] in ("unresolved", "mixed")]

    if len(supported) == 1:
        leading_hyp = dict(supported[0])
        non_leading = [item for item in evaluations if item["id"] != supported[0]["id"]]
        obs_only_contradicted = [
            item["id"] for item in non_leading
            if not any("[SIMULATED PROBE" in ev for ev in item.get("contradicting_evidence", []))
        ]
        is_decisive = (len(unresolved) == 0 and len(obs_only_contradicted) == 0)
        leading_hyp["is_decisive"] = is_decisive
        leading_hyp["unresolved_alternatives"] = [u["id"] for u in unresolved] + obs_only_contradicted
        leading_hyp["remediation_safety"] = classify_action_safety(leading_hyp.get("recommended_action", ""))

    return {
        "incident_id": incident_data.get("incident_id"),
        "title": incident_data.get("title"),
        "service": incident_data.get("service", "unknown"),
        "severity": incident_data.get("severity", "MEDIUM"),
        "description": incident_data.get("description"),
        "initial_observations": initial_observations,
        "investigation_steps": investigation_steps,
        "final_evaluations": evaluations,
        "leading_hypothesis": leading_hyp,
        "stopping_reason": stopping_reason,
        "report": report_text,
        "completed_checks_count": len(completed_checks),
        "total_checks_available": len(checks)
    }


def inspect_incident(scenario_path=None, checks_path=None):
    """CLI runner for incident investigation."""
    scenario_file = resolve_scenario_path(scenario_path) if scenario_path else PROJECT_ROOT / "data" / "incident.json"
    checks_file = Path(checks_path) if checks_path else PROJECT_ROOT / "data" / "diagnostic_checks.json"

    incident = load_json(scenario_file)
    diagnostic_data = load_json(checks_file)

    print(f"\n==================================================")
    print(f"Tracer - Autonomous Incident Investigation")
    print(f"==================================================")
    print(f"Target Scenario : {incident.get('incident_id', 'INC-???')} - {incident.get('title')}")
    print(f"Service / Sev   : {incident.get('service', 'N/A')} [{incident.get('severity', 'UNKNOWN')}]")
    print(f"Description     : {incident.get('description')}")
    print(f"\nInitial Observations Loaded: {len(incident.get('evidence', []))}")
    for obs in incident.get("evidence", []):
        print(f"  * [{obs.get('source')}]: {obs.get('observation')}")

    print("\nInitiating diagnostic probe triage loop...")

    result = run_investigation(incident, diagnostic_data)

    for step in result["investigation_steps"]:
        print(f"\n--- [Step {step['step']}] Selecting Check ---")
        print(f"Selected Check : {step['check_name']} ({step['check_id']})")
        print(f"Why this check : {step['selection_reason']}")
        print(f"Probe Execution: status={step['status']}, result='{step['result']}' [SIMULATED]")

    print(result["report"])
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Tracer Autonomous Incident Investigation and Root Cause Analysis"
    )
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        default=None,
        help="Path or identifier of the incident scenario (e.g. INC-001, INC-002, or path to json)"
    )
    parser.add_argument(
        "--checks", "-c",
        type=str,
        default=None,
        help="Path to diagnostic checks file (default: data/diagnostic_checks.json)"
    )
    parser.add_argument(
        "--list-scenarios", "-l",
        action="store_true",
        help="List all available incident scenarios and exit"
    )

    args = parser.parse_args()

    if args.list_scenarios:
        scenarios = list_available_scenarios()
        print("\nAvailable Tracer Incident Scenarios:")
        print("------------------------------------------------------------------")
        for sc in scenarios:
            print(f"ID: {sc['incident_id']:<8} | Sev: {sc['severity']:<8} | Title: {sc['title']}")
            print(f"   Path: {sc['file_path']}")
        print("------------------------------------------------------------------\n")
        return

    inspect_incident(args.scenario, args.checks)


if __name__ == "__main__":
    main()

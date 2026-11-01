"""
Tracer Diagnostic Check Executor
Executes diagnostic checks against available telemetry/evidence sources.
Distinguishes simulated fixture evidence from live diagnostic probe results.
"""


def run_check(check, available_evidence, live_probe_runner=None):
    """
    Run a diagnostic check against available evidence.
    
    Args:
        check: Dictionary containing check definition (id, required_evidence, possible_results, etc.)
        available_evidence: Dictionary mapping evidence keys to observed values.
        live_probe_runner: Optional callable for executing real live probes if available.
        
    Returns:
        Dictionary with execution status, check_id, result, and evidence_type.
    """
    if not check or not isinstance(check, dict) or "id" not in check or "required_evidence" not in check:
        return {
            "check_id": check.get("id", "unknown") if isinstance(check, dict) else "unknown",
            "status": "invalid_check_definition",
            "reason": "Malformed diagnostic check definition."
        }

    required = check.get("required_evidence", [])
    if not isinstance(required, list) or len(required) == 0:
        return {
            "check_id": check["id"],
            "status": "invalid_check_definition",
            "reason": "Check definition missing required_evidence list."
        }

    missing = [
        item for item in required
        if item not in available_evidence
    ]

    # Never run a check without its required evidence.
    if missing:
        return {
            "check_id": check["id"],
            "status": "unavailable",
            "reason": f"Missing evidence: {', '.join(missing)}"
        }

    # Determine result from available evidence
    primary_key = required[0]
    result = available_evidence[primary_key]

    # Accept only results defined by the check.
    possible = check.get("possible_results", [])
    if possible and result not in possible:
        return {
            "check_id": check["id"],
            "status": "invalid_result",
            "reason": f"Unexpected result '{result}'. Expected one of: {', '.join(possible)}"
        }

    return {
        "check_id": check["id"],
        "status": "completed",
        "result": result,
        "evidence_type": "simulated",
        "evidence_source": primary_key
    }

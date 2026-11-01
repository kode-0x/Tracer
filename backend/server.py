"""
Tracer - Backend HTTP API Server
Provides REST endpoints for the React/Vite dashboard to query scenarios
and execute live incident investigations.
Zero external dependencies (uses standard library http.server).
Ensures public API responses strictly protect and never leak ground_truth.
"""

import argparse
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.investigator import (
    list_available_scenarios,
    resolve_scenario_path,
    load_json,
    run_investigation
)

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


class TraceAPIHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for Tracer REST API and static frontend assets."""

    def end_headers(self):
        # Enable CORS for local Vite dev server
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=HTTPStatus.BAD_REQUEST):
        self.send_json({"error": str(message), "status": status.value}, status=status)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Health endpoint
        if path == "/api/health":
            return self.send_json({
                "status": "healthy",
                "engine": "Tracer Autonomous RCA Engine",
                "version": "2.0.0"
            })

        # List scenarios
        if path == "/api/scenarios":
            scenarios = list_available_scenarios()
            # Ensure ground_truth is not in any scenario summary
            cleaned_scenarios = []
            for sc in scenarios:
                c = dict(sc)
                c.pop("ground_truth", None)
                cleaned_scenarios.append(c)
            return self.send_json({"scenarios": cleaned_scenarios})

        # Get specific scenario
        if path.startswith("/api/scenarios/"):
            scenario_id = unquote(path[len("/api/scenarios/"):])
            try:
                scenario_file = resolve_scenario_path(scenario_id)
                data = load_json(scenario_file)
                # Strictly redact ground_truth from public API response
                response_data = dict(data)
                response_data.pop("ground_truth", None)
                return self.send_json(response_data)
            except FileNotFoundError as e:
                return self.send_error_json(f"Scenario not found: {e}", HTTPStatus.NOT_FOUND)
            except Exception as e:
                return self.send_error_json(f"Error loading scenario: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)

        # Get diagnostic checks catalog
        if path == "/api/checks":
            try:
                checks_file = PROJECT_ROOT / "data" / "diagnostic_checks.json"
                checks_data = load_json(checks_file)
                return self.send_json(checks_data)
            except Exception as e:
                return self.send_error_json(f"Could not load checks: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)

        # Static assets / frontend fallback
        if FRONTEND_DIST.exists():
            file_path = FRONTEND_DIST / parsed.path.lstrip("/")
            if file_path.is_file():
                return self.serve_file(file_path)
            # SPA fallback to index.html
            index_path = FRONTEND_DIST / "index.html"
            if index_path.is_file():
                return self.serve_file(index_path)

        # Fallback if no frontend build and non-API route
        return self.send_error_json(
            "Tracer API Server running. Frontend not built or route not found. Use /api/scenarios or /api/health.",
            HTTPStatus.NOT_FOUND
        )

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Trigger investigation
        if path == "/api/investigate":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

            try:
                body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                if not isinstance(body, dict):
                    return self.send_error_json("Request body must be a JSON object.", HTTPStatus.BAD_REQUEST)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return self.send_error_json(f"Malformed JSON request: {e}", HTTPStatus.BAD_REQUEST)

            scenario_id = body.get("scenario_id") or body.get("incident_id")
            scenario_path = body.get("scenario_path")

            try:
                if scenario_path:
                    target_file = resolve_scenario_path(scenario_path)
                elif scenario_id:
                    target_file = resolve_scenario_path(scenario_id)
                else:
                    target_file = PROJECT_ROOT / "data" / "incident.json"

                incident_data = load_json(target_file)
                checks_data = load_json(PROJECT_ROOT / "data" / "diagnostic_checks.json")

                # Run autonomous investigation
                result = run_investigation(incident_data, checks_data)
                return self.send_json(result)

            except FileNotFoundError as e:
                return self.send_error_json(f"Scenario file not found: {e}", HTTPStatus.NOT_FOUND)
            except Exception as e:
                return self.send_error_json(f"Investigation execution error: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)

        return self.send_error_json(f"Unknown POST endpoint: {path}", HTTPStatus.NOT_FOUND)

    def serve_file(self, file_path):
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        try:
            content = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_json(f"Error serving file: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server(port=8000, host="0.0.0.0"):
    server_address = (host, port)
    httpd = HTTPServer(server_address, TraceAPIHandler)
    print(f"\n==================================================")
    print(f"Tracer API Server running at http://localhost:{port}/")
    print(f"Health Check : http://localhost:{port}/api/health")
    print(f"Scenarios    : http://localhost:{port}/api/scenarios")
    print(f"==================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Tracer API Server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Tracer API Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default 0.0.0.0)")
    args = parser.parse_args()
    run_server(args.port, args.host)

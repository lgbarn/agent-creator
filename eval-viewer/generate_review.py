#!/usr/bin/env python3
"""Generate and serve an interactive review page for agent eval results.

Reads a workspace directory, discovers test runs with transcripts and
assertion results, embeds all data into a self-contained HTML page, and
serves it via a tiny HTTP server. Feedback auto-saves to feedback.json.

Adapted from skill-creator's eval-viewer for multi-turn agent transcripts.

Usage:
    python eval-viewer/generate_review.py <workspace-path> [--port PORT] [--agent-name NAME]
    python eval-viewer/generate_review.py <workspace-path> --static report.html
    python eval-viewer/generate_review.py <workspace-path> --previous-workspace <prev-iter-path>

No dependencies beyond the Python stdlib.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def find_runs(workspace: Path) -> list[dict]:
    """Find test runs in a workspace directory.

    Looks for directories containing test_results.json or transcript.md.
    Supports multiple layouts:
    - workspace/scenario-name/test_results.json
    - workspace/scenario-name/run-N/test_results.json
    - workspace/train/scenario-name/test_results.json
    - workspace/iteration-N/train/scenario-name/test_results.json
    """
    runs: list[dict] = []
    _find_runs_recursive(workspace, workspace, runs)
    runs.sort(key=lambda r: r.get("id", ""))
    return runs


def _find_runs_recursive(root: Path, current: Path, runs: list[dict]) -> None:
    if not current.is_dir():
        return

    # Check if this directory has test results
    if (current / "test_results.json").exists():
        run = _build_run(root, current)
        if run:
            runs.append(run)
        return

    skip = {"__pycache__", ".git", "logs", "node_modules"}
    for child in sorted(current.iterdir()):
        if child.is_dir() and child.name not in skip:
            _find_runs_recursive(root, child, runs)


def _build_run(root: Path, run_dir: Path) -> dict | None:
    """Build a run dict from a directory containing test_results.json."""
    test_results_path = run_dir / "test_results.json"
    if not test_results_path.exists():
        return None

    try:
        with open(test_results_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    run_id = str(run_dir.relative_to(root)).replace("/", "-").replace("\\", "-")

    # Build turns from test_results
    turns = []
    for tr in data.get("turn_results", []):
        turn = {
            "user_message": tr.get("user_message", ""),
            "response": tr.get("response", ""),
            "tool_calls": tr.get("tool_calls", []),
            "assertions": tr.get("assertions", []),
            "error": tr.get("error"),
        }
        turns.append(turn)

    # Load grading if present
    grading = None
    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        try:
            with open(grading_path) as f:
                grading = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "id": run_id,
        "scenario_name": data.get("scenario_name", run_dir.name),
        "agent": data.get("agent", ""),
        "archetype": data.get("archetype", "unknown"),
        "turns": turns,
        "global_assertions": data.get("global_assertions", []),
        "grading": grading,
    }


def load_previous_feedback(workspace: Path) -> dict[str, str]:
    """Load previous iteration's feedback."""
    feedback_path = workspace / "feedback.json"
    if not feedback_path.exists():
        return {}

    try:
        data = json.loads(feedback_path.read_text())
        return {
            r["run_id"]: r["feedback"]
            for r in data.get("reviews", [])
            if r.get("feedback", "").strip()
        }
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def generate_html(
    runs: list[dict],
    agent_name: str,
    previous_feedback: dict[str, str] | None = None,
    benchmark: dict | None = None,
) -> str:
    """Generate the complete standalone HTML page with embedded data."""
    template_path = Path(__file__).parent / "viewer.html"
    template = template_path.read_text()

    embedded = {
        "agent_name": agent_name,
        "runs": runs,
        "previous_feedback": previous_feedback or {},
    }
    if benchmark:
        embedded["benchmark"] = benchmark

    data_json = json.dumps(embedded)
    return template.replace(
        "/*__EMBEDDED_DATA__*/", f"const EMBEDDED_DATA = {data_json};"
    )


def _kill_port(port: int) -> None:
    """Kill any process listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for pid_str in result.stdout.strip().split("\n"):
            if pid_str.strip():
                try:
                    os.kill(int(pid_str.strip()), signal.SIGTERM)
                except (ProcessLookupError, ValueError):
                    pass
        if result.stdout.strip():
            time.sleep(0.5)
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass


class ReviewHandler(BaseHTTPRequestHandler):
    """Serves the review HTML and handles feedback saves.

    Regenerates HTML on each page load so refreshing picks up
    new eval outputs without restarting the server.
    """

    def __init__(
        self,
        workspace: Path,
        agent_name: str,
        feedback_path: Path,
        previous_feedback: dict[str, str],
        benchmark_path: Path | None,
        *args,
        **kwargs,
    ):
        self.workspace = workspace
        self.agent_name = agent_name
        self.feedback_path = feedback_path
        self.previous_feedback = previous_feedback
        self.benchmark_path = benchmark_path
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            runs = find_runs(self.workspace)
            benchmark = None
            if self.benchmark_path and self.benchmark_path.exists():
                try:
                    benchmark = json.loads(self.benchmark_path.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            html = generate_html(
                runs, self.agent_name, self.previous_feedback, benchmark
            )
            content = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/feedback":
            data = b"{}"
            if self.feedback_path.exists():
                data = self.feedback_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/feedback":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                if not isinstance(data, dict) or "reviews" not in data:
                    raise ValueError("Expected JSON with 'reviews' key")
                self.feedback_path.write_text(json.dumps(data, indent=2) + "\n")
                resp = b'{"ok":true}'
                self.send_response(200)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                resp = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress request logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and serve agent eval review viewer"
    )
    parser.add_argument("workspace", type=Path, help="Path to workspace directory")
    parser.add_argument(
        "--port", "-p", type=int, default=3118, help="Server port (default: 3118)"
    )
    parser.add_argument(
        "--agent-name", "-n", type=str, default=None, help="Agent name for header"
    )
    parser.add_argument(
        "--previous-workspace",
        type=Path,
        default=None,
        help="Path to previous iteration's workspace (shows old feedback as context)",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=None,
        help="Path to benchmark.json to show in the Benchmark tab",
    )
    parser.add_argument(
        "--static",
        "-s",
        type=Path,
        default=None,
        help="Write standalone HTML to this path instead of starting a server",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"Error: {workspace} is not a directory", file=sys.stderr)
        sys.exit(1)

    runs = find_runs(workspace)
    if not runs:
        print(f"No runs found in {workspace}", file=sys.stderr)
        sys.exit(1)

    agent_name = args.agent_name or workspace.name.replace("-workspace", "")
    feedback_path = workspace / "feedback.json"

    previous_feedback: dict[str, str] = {}
    if args.previous_workspace:
        previous_feedback = load_previous_feedback(args.previous_workspace.resolve())

    benchmark_path = args.benchmark.resolve() if args.benchmark else None
    benchmark = None
    if benchmark_path and benchmark_path.exists():
        try:
            benchmark = json.loads(benchmark_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if args.static:
        html = generate_html(runs, agent_name, previous_feedback, benchmark)
        args.static.parent.mkdir(parents=True, exist_ok=True)
        args.static.write_text(html)
        print(f"\n  Static viewer written to: {args.static}\n")
        sys.exit(0)

    # Kill any existing process on the target port
    port = args.port
    _kill_port(port)
    handler = partial(
        ReviewHandler,
        workspace,
        agent_name,
        feedback_path,
        previous_feedback,
        benchmark_path,
    )
    try:
        server = HTTPServer(("127.0.0.1", port), handler)
    except OSError:
        server = HTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]

    url = f"http://localhost:{port}"
    print("\n  Agent Eval Viewer")
    print("  -----------------------------------")
    print(f"  URL:       {url}")
    print(f"  Workspace: {workspace}")
    print(f"  Feedback:  {feedback_path}")
    if previous_feedback:
        print(
            f"  Previous:  {args.previous_workspace} ({len(previous_feedback)} reviews)"
        )
    if benchmark_path:
        print(f"  Benchmark: {benchmark_path}")
    print("\n  Press Ctrl+C to stop.\n")

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()

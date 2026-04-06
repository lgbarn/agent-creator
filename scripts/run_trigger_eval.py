#!/usr/bin/env python3
"""Test whether an agent's description causes Claude to delegate to it.

Adapted from skill-creator's run_eval.py for agent descriptions.
Agents trigger via the same mechanism as skills — Claude sees the name +
description in its available list and decides whether to invoke.

Usage:
    python scripts/run_trigger_eval.py --agent <path> --eval-set <path> [--verbose]
"""

import argparse
import json
import os
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import parse_agent_md


def find_project_root() -> Path:
    """Find project root by walking up from cwd looking for .claude/."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def run_single_query(
    query: str,
    agent_name: str,
    agent_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
) -> bool:
    """Run a single query and detect whether Claude delegates to the agent.

    Creates a temporary agent file so it appears in Claude's available
    agents list, then runs `claude -p` with the query. Detects delegation
    via stream events (looking for Agent tool invocation targeting our agent).
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{agent_name}-test-{unique_id}"

    # Create temporary agent file in project's .claude/agents/
    agents_dir = Path(project_root) / ".claude" / "agents"
    agent_file = agents_dir / f"{clean_name}.md"

    try:
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Write a minimal agent file with the description being tested
        agent_content = f"---\nname: {clean_name}\ndescription: |\n"
        for line in agent_description.split("\n"):
            agent_content += f"  {line}\n"
        agent_content += (
            "model: haiku\n"
            "tools: Read\n"
            "maxTurns: 1\n"
            "---\n\n"
            "You are a test agent. Respond briefly.\n"
        )
        agent_file.write_text(agent_content)

        cmd = [
            "claude",
            "-p",
            query,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Allow nested claude invocations
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )

        triggered = False
        start_time = time.time()
        buffer = ""
        pending_tool_name = None
        accumulated_json = ""

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Detect via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name == "Agent":
                                    pending_tool_name = tool_name
                                    accumulated_json = ""

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if clean_name in accumulated_json:
                                    return True

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                return clean_name in accumulated_json
                            if se_type == "message_stop":
                                return False

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Agent" and clean_name in json.dumps(
                                tool_input
                            ):
                                triggered = True
                            return triggered

                    elif event.get("type") == "result":
                        return triggered
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

        return triggered
    finally:
        if agent_file.exists():
            agent_file.unlink()


def run_trigger_eval(
    eval_set: list[dict],
    agent_name: str,
    description: str,
    num_workers: int = 5,
    timeout: int = 30,
    project_root: Path | None = None,
    runs_per_query: int = 3,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full trigger eval set and return results."""
    if project_root is None:
        project_root = find_project_root()

    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info: dict = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    agent_name,
                    description,
                    timeout,
                    str(project_root),
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "trigger_rate": trigger_rate,
                "triggers": sum(triggers),
                "runs": len(triggers),
                "pass": did_pass,
            }
        )

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "agent_name": agent_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test agent description triggering accuracy"
    )
    parser.add_argument("--agent", required=True, help="Path to agent .md file")
    parser.add_argument(
        "--eval-set", required=True, help="Path to trigger eval set JSON"
    )
    parser.add_argument(
        "--description", default=None, help="Override description to test"
    )
    parser.add_argument("--num-workers", type=int, default=5, help="Parallel workers")
    parser.add_argument(
        "--timeout", type=int, default=30, help="Timeout per query in seconds"
    )
    parser.add_argument("--runs-per-query", type=int, default=3, help="Runs per query")
    parser.add_argument(
        "--trigger-threshold",
        type=float,
        default=0.5,
        help="Trigger rate threshold",
    )
    parser.add_argument("--model", default=None, help="Model for claude -p")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    agent_data = parse_agent_md(Path(args.agent))
    description = args.description or agent_data["description"]
    project_root = find_project_root()

    if args.verbose:
        print(f"Agent: {agent_data['name']}", file=sys.stderr)
        print(f"Description: {description[:100]}...", file=sys.stderr)

    output = run_trigger_eval(
        eval_set=json.loads(Path(args.eval_set).read_text()),
        agent_name=agent_data["name"],
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        s = output["summary"]
        print(f"Results: {s['passed']}/{s['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate = f"{r['triggers']}/{r['runs']}"
            print(
                f"  [{status}] rate={rate} expected={r['should_trigger']}: {r['query'][:70]}",
                file=sys.stderr,
            )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

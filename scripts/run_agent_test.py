#!/usr/bin/env python3
"""Run test scenarios against an agent and capture transcripts for grading.

For each turn in a test scenario, invokes the agent via `claude --agent`
and captures the response. After all turns complete, saves the full
transcript and runs programmatic assertions.

Usage:
    python scripts/run_agent_test.py --agent <name-or-path> --scenario <path> --output-dir <dir>
    python scripts/run_agent_test.py --agent go-expert --scenario evals/example-scenario.json --output-dir workspace/run-1/
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import find_agent_file


def load_scenarios(scenario_path: str) -> list[dict]:
    """Load test scenarios from a JSON file."""
    with open(scenario_path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    return data


def run_turn(
    agent: str, prompt: str, timeout: int = 120, model: str | None = None
) -> dict:
    """Run a single turn against an agent via claude CLI.

    Returns dict with:
        response: The agent's text response
        tool_calls: List of tool names used
        duration_ms: Wall clock time
        raw: Raw CLI output
    """
    cmd = ["claude", "--agent", agent, "-p", prompt, "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start) * 1000)
    except subprocess.TimeoutExpired:
        return {
            "response": "",
            "tool_calls": [],
            "duration_ms": int((time.time() - start) * 1000),
            "raw": "",
            "error": f"Timeout after {timeout}s",
        }

    raw_output = result.stdout
    response_text = ""
    tool_calls = []

    # Parse JSON output
    try:
        output = json.loads(raw_output)
        if isinstance(output, dict):
            response_text = output.get("result", output.get("text", raw_output))
            # Extract tool calls from the response if available
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, dict) and msg.get("type") == "tool_use":
                        tool_calls.append(msg.get("name", "unknown"))
    except json.JSONDecodeError:
        response_text = raw_output

    return {
        "response": response_text,
        "tool_calls": tool_calls,
        "duration_ms": duration_ms,
        "raw": raw_output,
        "error": result.stderr if result.returncode != 0 else None,
    }


def check_programmatic_assertions(
    response: str, tool_calls: list[str], assertions: list[dict]
) -> list[dict]:
    """Check programmatic assertions (contains, not_contains, regex, tool_usage).

    Returns list of assertion results with passed/evidence fields added.
    Behavioral and tone assertions are left for the grader agent.
    """
    results = []
    for assertion in assertions:
        atype = assertion["type"]
        value = assertion["value"]
        desc = assertion.get("description", value)

        if atype == "contains":
            found = value.lower() in response.lower()
            results.append(
                {
                    "text": desc,
                    "type": atype,
                    "passed": found,
                    "evidence": f"'{value}' {'found' if found else 'not found'} in response",
                }
            )

        elif atype == "not_contains":
            found = value.lower() in response.lower()
            results.append(
                {
                    "text": desc,
                    "type": atype,
                    "passed": not found,
                    "evidence": f"'{value}' {'found (FAIL)' if found else 'not found (PASS)'} in response",
                }
            )

        elif atype == "regex":
            match = re.search(value, response, re.IGNORECASE)
            results.append(
                {
                    "text": desc,
                    "type": atype,
                    "passed": match is not None,
                    "evidence": f"Pattern '{value}' {'matched' if match else 'did not match'}",
                }
            )

        elif atype == "tool_usage":
            value_lower = value.lower()
            if "should not" in value_lower or "should not" in value_lower:
                # Extract tool name after "should NOT use"
                tool_match = re.search(
                    r"should\s+not\s+use\s+(\w+)", value, re.IGNORECASE
                )
                if tool_match:
                    tool_name = tool_match.group(1)
                    used = any(t.lower() == tool_name.lower() for t in tool_calls)
                    results.append(
                        {
                            "text": desc,
                            "type": atype,
                            "passed": not used,
                            "evidence": f"Tool '{tool_name}' {'was used (FAIL)' if used else 'was not used (PASS)'}",
                        }
                    )
            elif "should use" in value_lower:
                tool_match = re.search(r"should\s+use\s+(\w+)", value, re.IGNORECASE)
                if tool_match:
                    tool_name = tool_match.group(1)
                    used = any(t.lower() == tool_name.lower() for t in tool_calls)
                    results.append(
                        {
                            "text": desc,
                            "type": atype,
                            "passed": used,
                            "evidence": f"Tool '{tool_name}' {'was used (PASS)' if used else 'was not used (FAIL)'}",
                        }
                    )
            else:
                # Defer to grader for complex tool_usage assertions
                results.append(
                    {
                        "text": desc,
                        "type": atype,
                        "passed": None,  # Deferred to grader
                        "evidence": "Deferred to behavior-grader for evaluation",
                    }
                )

        else:
            # behavioral, tone — deferred to grader agent
            results.append(
                {
                    "text": desc,
                    "type": atype,
                    "passed": None,  # Deferred to grader
                    "evidence": "Deferred to behavior-grader for evaluation",
                }
            )

    return results


def build_context_prompt(scenario: dict, turn_idx: int, history: list[dict]) -> str:
    """Build a prompt with conversation history context for multi-turn scenarios.

    For the first turn, returns the user message as-is.
    For subsequent turns, prepends a summary of previous exchanges.
    """
    turn = scenario["turns"][turn_idx]
    user_msg = turn["user"]

    if turn_idx == 0 or not history:
        return user_msg

    # Build context from previous turns
    context_parts = ["[Previous conversation context:]"]
    for prev in history:
        context_parts.append(f"User: {prev['user_message']}")
        # Truncate long responses to keep context manageable
        resp = prev["response"]
        if len(resp) > 500:
            resp = resp[:500] + "..."
        context_parts.append(f"You responded: {resp}")
        context_parts.append("")

    context_parts.append(f"[Current question:]\n{user_msg}")
    return "\n".join(context_parts)


def run_scenario(
    scenario: dict, output_dir: str, timeout: int = 120, model: str | None = None
) -> dict:
    """Run a complete test scenario against an agent.

    Returns the full test result including transcript and assertion results.
    """
    agent = scenario["agent"]
    scenario_name = scenario.get("name", "unnamed")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    history: list[dict] = []
    turn_results: list[dict] = []
    all_tool_calls: list[str] = []
    total_duration_ms = 0

    print(f"Running scenario: {scenario_name}")

    for i, turn in enumerate(scenario["turns"]):
        prompt = build_context_prompt(scenario, i, history)
        print(f"  Turn {i + 1}/{len(scenario['turns'])}: {turn['user'][:60]}...")

        result = run_turn(agent, prompt, timeout=timeout, model=model)

        if result.get("error"):
            print(f"    Error: {result['error']}")

        # Check programmatic assertions
        assertions = turn.get("assertions", [])
        assertion_results = check_programmatic_assertions(
            result["response"], result["tool_calls"], assertions
        )

        turn_result = {
            "turn": i + 1,
            "user_message": turn["user"],
            "prompt_sent": prompt,
            "response": result["response"],
            "tool_calls": result["tool_calls"],
            "duration_ms": result["duration_ms"],
            "assertions": assertion_results,
            "error": result.get("error"),
        }

        turn_results.append(turn_result)
        history.append(turn_result)
        all_tool_calls.extend(result["tool_calls"])
        total_duration_ms += result["duration_ms"]

    # Build transcript markdown
    transcript_lines = [
        f"# Test Transcript: {scenario_name}",
        f"Agent: {agent}",
        f"Archetype: {scenario.get('archetype', 'unknown')}",
        "",
    ]
    for tr in turn_results:
        transcript_lines.append(f"## Turn {tr['turn']}")
        transcript_lines.append(f"**User:** {tr['user_message']}")
        transcript_lines.append("")
        transcript_lines.append("**Agent Response:**")
        transcript_lines.append(tr["response"])
        if tr["tool_calls"]:
            transcript_lines.append(f"\n**Tools Used:** {', '.join(tr['tool_calls'])}")
        if tr.get("error"):
            transcript_lines.append(f"\n**Error:** {tr['error']}")
        transcript_lines.append("")
        transcript_lines.append("---")
        transcript_lines.append("")

    transcript_text = "\n".join(transcript_lines)
    transcript_path = out_path / "transcript.md"
    transcript_path.write_text(transcript_text)

    # Save scenario copy for grader reference
    scenario_path = out_path / "scenario.json"
    with open(scenario_path, "w") as f:
        json.dump(scenario, f, indent=2)

    # Save raw results
    raw_results = {
        "scenario_name": scenario_name,
        "agent": agent,
        "archetype": scenario.get("archetype", "unknown"),
        "turn_results": turn_results,
        "global_assertions": scenario.get("global_assertions", []),
        "timing": {
            "total_duration_ms": total_duration_ms,
            "total_duration_seconds": round(total_duration_ms / 1000, 1),
        },
        "all_tool_calls": all_tool_calls,
    }
    results_path = out_path / "test_results.json"
    with open(results_path, "w") as f:
        json.dump(raw_results, f, indent=2)

    # Save timing data
    timing_path = out_path / "timing.json"
    with open(timing_path, "w") as f:
        json.dump(raw_results["timing"], f, indent=2)

    # Summary
    programmatic_results = [
        a for tr in turn_results for a in tr["assertions"] if a["passed"] is not None
    ]
    passed = sum(1 for a in programmatic_results if a["passed"])
    failed = sum(1 for a in programmatic_results if not a["passed"])
    deferred = sum(
        1 for tr in turn_results for a in tr["assertions"] if a["passed"] is None
    )

    print(f"  Results: {passed} passed, {failed} failed, {deferred} deferred to grader")
    print(f"  Transcript saved: {transcript_path}")

    return raw_results


def run_scenario_multiple(
    scenario: dict,
    output_dir: str,
    runs: int = 1,
    timeout: int = 120,
    model: str | None = None,
) -> list[dict]:
    """Run a scenario multiple times for statistical reliability.

    When runs > 1, results are placed in run-1/, run-2/, etc. subdirectories.
    When runs == 1, results are placed directly in output_dir (backward compatible).

    Returns list of result dicts, one per run.
    """
    if runs <= 1:
        result = run_scenario(
            scenario, output_dir=output_dir, timeout=timeout, model=model
        )
        return [result]

    results = []
    for run_idx in range(1, runs + 1):
        run_dir = os.path.join(output_dir, f"run-{run_idx}")
        print(f"  [Run {run_idx}/{runs}]")
        result = run_scenario(
            scenario, output_dir=run_dir, timeout=timeout, model=model
        )
        results.append(result)

    # Write aggregate summary across runs
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    all_passed = 0
    all_failed = 0
    all_total = 0
    for r in results:
        for tr in r.get("turn_results", []):
            for a in tr.get("assertions", []):
                if a.get("passed") is True:
                    all_passed += 1
                elif a.get("passed") is False:
                    all_failed += 1
        all_total += 1

    total_assertions = all_passed + all_failed
    aggregate = {
        "scenario_name": scenario.get("name", "unnamed"),
        "runs": runs,
        "aggregate": {
            "passed": all_passed,
            "failed": all_failed,
            "total_assertions": total_assertions,
            "pass_rate": all_passed / total_assertions if total_assertions > 0 else 0.0,
            "per_run_pass_rates": [],
        },
    }

    for r in results:
        p = 0
        f = 0
        for tr in r.get("turn_results", []):
            for a in tr.get("assertions", []):
                if a.get("passed") is True:
                    p += 1
                elif a.get("passed") is False:
                    f += 1
        t = p + f
        aggregate["aggregate"]["per_run_pass_rates"].append(p / t if t > 0 else 0.0)

    (out_path / "aggregate.json").write_text(json.dumps(aggregate, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser(description="Run agent test scenarios")
    parser.add_argument("--agent", required=True, help="Agent name or path to .md file")
    parser.add_argument("--scenario", required=True, help="Path to test scenario JSON")
    parser.add_argument(
        "--output-dir", required=True, help="Directory for output files"
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="Per-turn timeout in seconds"
    )
    parser.add_argument("--model", default=None, help="Override model for the agent")
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of times to run each scenario (default: 1, use 3+ for statistical reliability)",
    )
    args = parser.parse_args()

    # Resolve agent
    agent = args.agent
    if not Path(agent).exists() and not agent.endswith(".md"):
        found = find_agent_file(agent)
        if found:
            agent = str(found)

    # Load scenarios
    scenarios = load_scenarios(args.scenario)

    all_results = []
    for i, scenario in enumerate(scenarios):
        scenario_name = scenario.get("name", f"scenario-{i}")
        scenario_dir = os.path.join(args.output_dir, scenario_name)
        results = run_scenario_multiple(
            scenario,
            output_dir=scenario_dir,
            runs=args.runs,
            timeout=args.timeout,
            model=args.model,
        )
        all_results.extend(results)

    # Summary
    total_scenarios = len(scenarios)
    total_runs = len(all_results)
    print(
        f"\nCompleted {total_scenarios} scenario(s) x {args.runs} run(s) = {total_runs} total run(s)"
    )
    print(f"Results in: {args.output_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Iterative test-improve cycle for agents.

Runs test scenarios against an agent, grades the results, uses Claude to
improve the system prompt based on failures, and repeats until passing
or max iterations reached.

Usage:
    python scripts/run_loop.py --agent <path> --scenarios <path> --max-iterations 5 --model sonnet
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import parse_agent_md


def run_loop(
    agent_path: str,
    scenarios_path: str,
    output_dir: str,
    max_iterations: int = 5,
    model: str | None = None,
    timeout: int = 120,
    verbose: bool = False,
    mode: str = "behavior",
) -> dict:
    """Run the iterative test-improve cycle.

    This function orchestrates the loop but delegates to external scripts
    for each step, making it suitable for both direct Python usage and
    CLI invocation where subagents handle grading.

    Returns dict with iteration history and best result.
    """
    from scripts.run_agent_test import load_scenarios, run_scenario

    agent_data = parse_agent_md(Path(agent_path))
    scenarios = load_scenarios(scenarios_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    history: list[dict] = []
    best_iteration: dict | None = None
    best_pass_rate = -1.0

    # Save original agent for reference
    original_path = out / "original_agent.md"
    shutil.copy2(agent_path, original_path)

    current_agent_path = agent_path

    for iteration in range(1, max_iterations + 1):
        iter_dir = out / f"iteration-{iteration}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Iteration {iteration}/{max_iterations}")
            print(f"{'=' * 60}")

        # Step 1: Run all test scenarios
        all_results = []
        for i, scenario in enumerate(scenarios):
            scenario_name = scenario.get("name", f"scenario-{i}")
            scenario_dir = str(iter_dir / scenario_name)

            result = run_scenario(
                scenario,
                output_dir=scenario_dir,
                timeout=timeout,
                model=model,
            )
            all_results.append(result)

        # Step 2: Collect programmatic assertion results
        total_passed = 0
        total_failed = 0
        total_deferred = 0

        for result in all_results:
            for tr in result.get("turn_results", []):
                for a in tr.get("assertions", []):
                    if a["passed"] is True:
                        total_passed += 1
                    elif a["passed"] is False:
                        total_failed += 1
                    else:
                        total_deferred += 1

        total = total_passed + total_failed
        pass_rate = total_passed / total if total > 0 else 0.0

        iter_record = {
            "iteration": iteration,
            "agent_path": current_agent_path,
            "passed": total_passed,
            "failed": total_failed,
            "deferred": total_deferred,
            "total": total,
            "pass_rate": pass_rate,
        }
        history.append(iter_record)

        if verbose:
            print(f"  Programmatic: {total_passed}/{total} passed ({pass_rate:.0%})")
            print(f"  Deferred to grader: {total_deferred}")

        # Track best iteration
        if pass_rate > best_pass_rate:
            best_pass_rate = pass_rate
            best_iteration = iter_record
            # Save best agent version
            shutil.copy2(current_agent_path, out / "best_agent.md")

        # Save iteration summary
        summary_path = iter_dir / "summary.json"
        summary_path.write_text(json.dumps({
            **iter_record,
            "scenarios": [r.get("scenario_name", f"scenario-{i}") for i, r in enumerate(all_results)],
        }, indent=2))

        # Check if all programmatic assertions pass
        if total_failed == 0 and total > 0:
            if verbose:
                print(f"\nAll programmatic assertions pass! Stopping at iteration {iteration}.")
            iter_record["exit_reason"] = "all_passed"
            break

        if iteration == max_iterations:
            if verbose:
                print(f"\nMax iterations reached ({max_iterations}).")
            iter_record["exit_reason"] = "max_iterations"
            break

        # Step 3: Improve the agent
        # Note: Full behavioral grading (via behavior-grader agent) should be
        # done by the caller (SKILL.md workflow or manual invocation).
        # This loop handles programmatic improvements.
        if verbose:
            print(f"\n  Improving agent prompt...")

        try:
            import anthropic
            from scripts.improve_prompt import improve_prompt

            client = anthropic.Anthropic()

            # Build a simplified grading result from programmatic assertions
            grading = {
                "turn_results": [
                    {
                        "turn": tr.get("turn", i + 1),
                        "user_message": tr.get("user_message", ""),
                        "assertions": [
                            a for a in tr.get("assertions", [])
                            if a["passed"] is not None
                        ],
                    }
                    for result in all_results
                    for i, tr in enumerate(result.get("turn_results", []))
                ],
                "global_results": [],
                "behavioral_notes": "",
            }

            agent_data = parse_agent_md(Path(current_agent_path))
            improvement = improve_prompt(
                client=client,
                agent_name=agent_data["name"],
                agent_content=agent_data["raw"],
                grading_results=grading,
                history=history,
                model=model or "claude-sonnet-4-6",
                mode=mode,
                log_dir=iter_dir / "logs",
                iteration=iteration,
            )

            if improvement.get("improved_content"):
                # Write improved agent
                improved_path = iter_dir / "improved_agent.md"
                improved_path.write_text(improvement["improved_content"])
                current_agent_path = str(improved_path)

                if verbose:
                    print(f"  Reasoning: {improvement.get('reasoning', 'N/A')[:200]}")

        except ImportError:
            if verbose:
                print("  Skipping auto-improvement (anthropic package not installed)")
            break
        except Exception as e:
            if verbose:
                print(f"  Improvement failed: {e}")
            break

    # Final summary
    output = {
        "original_agent": str(original_path),
        "best_agent": str(out / "best_agent.md") if best_iteration else str(original_path),
        "best_pass_rate": best_pass_rate,
        "best_iteration": best_iteration,
        "iterations_run": len(history),
        "history": history,
    }

    output_path = out / "loop_results.json"
    output_path.write_text(json.dumps(output, indent=2))

    if verbose:
        print(f"\nBest: iteration {best_iteration['iteration'] if best_iteration else 'N/A'} "
              f"({best_pass_rate:.0%} pass rate)")
        print(f"Results: {output_path}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Iterative agent improvement loop")
    parser.add_argument("--agent", required=True, help="Path to agent .md file")
    parser.add_argument("--scenarios", required=True, help="Path to test scenarios JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for iteration outputs")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max improvement iterations")
    parser.add_argument("--model", default=None, help="Model for agent runs and improvement")
    parser.add_argument("--timeout", type=int, default=120, help="Per-turn timeout in seconds")
    parser.add_argument("--mode", default="behavior", choices=["behavior", "description"],
                       help="What to improve: system prompt or description")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = run_loop(
        agent_path=args.agent,
        scenarios_path=args.scenarios,
        output_dir=args.output_dir,
        max_iterations=args.max_iterations,
        model=args.model,
        timeout=args.timeout,
        verbose=args.verbose,
        mode=args.mode,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

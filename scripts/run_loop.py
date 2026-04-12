#!/usr/bin/env python3
"""Iterative test-improve cycle for agents.

Runs test scenarios against an agent, grades the results, uses Claude to
improve the system prompt based on failures, and repeats until passing
or max iterations reached.

Supports:
- Train/test split to prevent overfitting
- Baseline runs (original agent alongside improved version) for comparison

Usage:
    python scripts/run_loop.py --agent <path> --scenarios <path> --max-iterations 5 --model sonnet
"""

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import parse_agent_md


def split_scenarios(
    scenarios: list[dict], holdout: float, seed: int = 42
) -> tuple[list[dict], list[dict]]:
    """Split scenarios into train and test sets.

    Keeps at least 1 scenario in each set when possible.
    """
    if holdout <= 0 or len(scenarios) < 2:
        return scenarios, []

    rng = random.Random(seed)
    shuffled = list(scenarios)
    rng.shuffle(shuffled)

    n_test = max(1, int(len(shuffled) * holdout))
    test_set = shuffled[:n_test]
    train_set = shuffled[n_test:]

    # Ensure train set is never empty
    if not train_set:
        train_set = [test_set.pop(0)]

    return train_set, test_set


def _collect_assertion_stats(all_results: list[dict]) -> dict:
    """Collect pass/fail/deferred counts from scenario results."""
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
    return {
        "passed": total_passed,
        "failed": total_failed,
        "deferred": total_deferred,
        "total": total,
        "pass_rate": total_passed / total if total > 0 else 0.0,
    }


def _run_scenarios(
    scenarios: list[dict],
    output_dir: Path,
    timeout: int,
    model: str | None,
    runs_per_scenario: int = 1,
) -> list[dict]:
    """Run a list of scenarios and return results.

    When runs_per_scenario > 1, each scenario runs multiple times for
    statistical reliability.
    """
    from scripts.run_agent_test import run_scenario, run_scenario_multiple

    results = []
    for i, scenario in enumerate(scenarios):
        scenario_name = scenario.get("name", f"scenario-{i}")
        scenario_dir = str(output_dir / scenario_name)
        if runs_per_scenario > 1:
            run_results = run_scenario_multiple(
                scenario,
                output_dir=scenario_dir,
                runs=runs_per_scenario,
                timeout=timeout,
                model=model,
            )
            # Use the first run's result for assertion tracking,
            # but store all results for benchmark aggregation
            results.append(run_results[0])
        else:
            result = run_scenario(
                scenario,
                output_dir=scenario_dir,
                timeout=timeout,
                model=model,
            )
            results.append(result)
    return results


def _load_feedback(output_dir: Path) -> list[dict]:
    """Load structured feedback from feedback.json if present."""
    feedback_path = output_dir / "feedback.json"
    if not feedback_path.exists():
        return []

    try:
        data = json.loads(feedback_path.read_text())
        return data.get("reviews", [])
    except (json.JSONDecodeError, OSError):
        return []


def run_loop(
    agent_path: str,
    scenarios_path: str,
    output_dir: str,
    max_iterations: int = 5,
    model: str | None = None,
    timeout: int = 120,
    verbose: bool = False,
    mode: str = "behavior",
    holdout: float = 0.0,
    run_baseline: bool = True,
    runs_per_scenario: int = 1,
) -> dict:
    """Run the iterative test-improve cycle.

    Args:
        holdout: Fraction of scenarios to hold out for testing (0 to disable).
            Prevents overfitting by evaluating improvements on unseen scenarios.
        run_baseline: If True, run the original agent on the same scenarios
            each iteration for comparison.
        runs_per_scenario: Number of times to run each scenario per iteration
            (default 1, use 3+ for statistical reliability).

    Returns dict with iteration history and best result.
    """
    from scripts.run_agent_test import load_scenarios

    agent_data = parse_agent_md(Path(agent_path))
    all_scenarios = load_scenarios(scenarios_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Train/test split
    if holdout > 0:
        train_scenarios, test_scenarios = split_scenarios(all_scenarios, holdout)
        if verbose:
            print(
                f"Split: {len(train_scenarios)} train, {len(test_scenarios)} test "
                f"(holdout={holdout})"
            )
    else:
        train_scenarios = all_scenarios
        test_scenarios = []

    history: list[dict] = []
    best_iteration: dict | None = None
    best_pass_rate = -1.0

    # Save original agent for baseline runs
    original_path = out / "original_agent.md"
    shutil.copy2(agent_path, original_path)

    # Run baseline once if enabled (original agent on train scenarios)
    baseline_stats: dict | None = None
    if run_baseline:
        if verbose:
            print(f"\n{'=' * 60}")
            print("Baseline: running original agent")
            print(f"{'=' * 60}")

        baseline_dir = out / "baseline"
        baseline_results = _run_scenarios(
            train_scenarios, baseline_dir, timeout, model, runs_per_scenario
        )
        baseline_stats = _collect_assertion_stats(baseline_results)

        if verbose:
            bs = baseline_stats
            print(
                f"  Baseline: {bs['passed']}/{bs['total']} passed "
                f"({bs['pass_rate']:.0%})"
            )

        # Save baseline summary
        (baseline_dir / "summary.json").write_text(
            json.dumps({"config": "baseline", **baseline_stats}, indent=2)
        )

    current_agent_path = agent_path

    for iteration in range(1, max_iterations + 1):
        iter_dir = out / f"iteration-{iteration}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Iteration {iteration}/{max_iterations}")
            print(f"{'=' * 60}")

        # Step 1: Run train scenarios with current agent
        train_dir = iter_dir / "train"
        train_results = _run_scenarios(
            train_scenarios, train_dir, timeout, model, runs_per_scenario
        )
        train_stats = _collect_assertion_stats(train_results)

        if verbose:
            ts = train_stats
            print(
                f"  Train: {ts['passed']}/{ts['total']} passed ({ts['pass_rate']:.0%})"
            )

        # Step 2: Run test scenarios (if holdout > 0)
        test_stats: dict | None = None
        if test_scenarios:
            test_dir = iter_dir / "test"
            test_results = _run_scenarios(
                test_scenarios, test_dir, timeout, model, runs_per_scenario
            )
            test_stats = _collect_assertion_stats(test_results)

            if verbose:
                tes = test_stats
                print(
                    f"  Test:  {tes['passed']}/{tes['total']} passed "
                    f"({tes['pass_rate']:.0%})"
                )

        # Step 3: Run baseline comparison (original agent on same train scenarios)
        iter_baseline_stats: dict | None = None
        if run_baseline and iteration > 1:
            # Reuse the initial baseline for train scenarios (deterministic split)
            iter_baseline_stats = baseline_stats

        # Build iteration record
        iter_record: dict = {
            "iteration": iteration,
            "agent_path": current_agent_path,
            "train": train_stats,
            "test": test_stats,
            "baseline": iter_baseline_stats,
            # Convenience fields
            "passed": train_stats["passed"],
            "failed": train_stats["failed"],
            "total": train_stats["total"],
            "pass_rate": train_stats["pass_rate"],
        }

        # Compute delta vs baseline
        if baseline_stats and baseline_stats["total"] > 0:
            delta = train_stats["pass_rate"] - baseline_stats["pass_rate"]
            iter_record["delta_vs_baseline"] = round(delta, 3)
            if verbose:
                sign = "+" if delta >= 0 else ""
                print(f"  Delta vs baseline: {sign}{delta:.0%}")

        history.append(iter_record)

        # Track best by test score if available, else train score
        score = test_stats["pass_rate"] if test_stats else train_stats["pass_rate"]
        if score > best_pass_rate:
            best_pass_rate = score
            best_iteration = iter_record
            shutil.copy2(current_agent_path, out / "best_agent.md")

        # Save iteration summary
        (iter_dir / "summary.json").write_text(json.dumps(iter_record, indent=2))

        # Check if all train assertions pass
        if train_stats["failed"] == 0 and train_stats["total"] > 0:
            if verbose:
                print(
                    f"\nAll train assertions pass! Stopping at iteration {iteration}."
                )
            iter_record["exit_reason"] = "all_passed"
            break

        if iteration == max_iterations:
            if verbose:
                print(f"\nMax iterations reached ({max_iterations}).")
            iter_record["exit_reason"] = "max_iterations"
            break

        # Step 4: Improve the agent
        if verbose:
            print("\n  Improving agent prompt...")

        try:
            import anthropic
            from scripts.improve_prompt import improve_prompt

            client = anthropic.Anthropic()

            # Build grading result from programmatic assertions
            grading = {
                "turn_results": [
                    {
                        "turn": tr.get("turn", i + 1),
                        "user_message": tr.get("user_message", ""),
                        "assertions": [
                            a
                            for a in tr.get("assertions", [])
                            if a["passed"] is not None
                        ],
                    }
                    for result in train_results
                    for i, tr in enumerate(result.get("turn_results", []))
                ],
                "global_results": [],
                "behavioral_notes": "",
            }

            # Load user feedback if available
            feedback = _load_feedback(out)

            agent_data = parse_agent_md(Path(current_agent_path))
            improvement = improve_prompt(
                client=client,
                agent_name=agent_data["name"],
                agent_content=agent_data["raw"],
                grading_results=grading,
                history=[
                    {k: v for k, v in h.items() if not k.startswith("test")}
                    for h in history
                ],
                model=model or "claude-sonnet-4-6",
                mode=mode,
                log_dir=iter_dir / "logs",
                iteration=iteration,
                feedback=feedback,
            )

            if improvement.get("improved_content"):
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
    output: dict = {
        "original_agent": str(original_path),
        "best_agent": (
            str(out / "best_agent.md") if best_iteration else str(original_path)
        ),
        "best_pass_rate": best_pass_rate,
        "best_iteration": best_iteration,
        "iterations_run": len(history),
        "holdout": holdout,
        "train_scenarios": len(train_scenarios),
        "test_scenarios": len(test_scenarios),
        "baseline": baseline_stats,
        "history": history,
    }

    output_path = out / "loop_results.json"
    output_path.write_text(json.dumps(output, indent=2))

    if verbose:
        best_iter_num = best_iteration["iteration"] if best_iteration else "N/A"
        print(f"\nBest: iteration {best_iter_num} ({best_pass_rate:.0%} pass rate)")
        if baseline_stats:
            print(f"Baseline: {baseline_stats['pass_rate']:.0%}")
        print(f"Results: {output_path}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Iterative agent improvement loop")
    parser.add_argument("--agent", required=True, help="Path to agent .md file")
    parser.add_argument(
        "--scenarios", required=True, help="Path to test scenarios JSON"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory for iteration outputs"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=5, help="Max improvement iterations"
    )
    parser.add_argument(
        "--model", default=None, help="Model for agent runs and improvement"
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="Per-turn timeout in seconds"
    )
    parser.add_argument(
        "--mode",
        default="behavior",
        choices=["behavior", "description"],
        help="What to improve: system prompt or description",
    )
    parser.add_argument(
        "--holdout",
        type=float,
        default=0.0,
        help="Fraction of scenarios to hold out for testing (0 to disable)",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip baseline runs (original agent comparison)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of times to run each scenario per iteration (default: 1, use 3+ for statistical reliability)",
    )
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
        holdout=args.holdout,
        run_baseline=not args.no_baseline,
        runs_per_scenario=args.runs,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Aggregate individual run results into benchmark summary statistics.

Reads test_results.json and grading.json files from run directories and
produces benchmark.json with mean±stddev for pass_rate, time, tokens,
and tool_calls across multiple runs.

Supports two directory layouts:

    Agent-creator workspace layout:
    <benchmark_dir>/
    └── iteration-N/
        └── train|test/
            └── <scenario-name>/
                ├── run-1/
                │   ├── test_results.json
                │   ├── grading.json (optional)
                │   └── timing.json
                └── run-2/
                    └── ...

    Flat layout:
    <benchmark_dir>/
    └── <scenario-name>/
        ├── run-1/
        │   ├── test_results.json
        │   └── timing.json
        └── run-2/
            └── ...

Usage:
    python scripts/aggregate_benchmark.py <benchmark_dir>
    python scripts/aggregate_benchmark.py workspace/iteration-1/train/ --agent-name go-expert
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _find_run_dirs(benchmark_dir: Path) -> dict[str, list[Path]]:
    """Find all run directories grouped by configuration.

    Returns dict mapping config name -> list of run directory paths.
    A 'run directory' contains test_results.json or grading.json.
    """
    configs: dict[str, list[Path]] = {}

    # Check for iteration-based layout (iteration-N/train|test/scenario/run-N/)
    iteration_dirs = sorted(benchmark_dir.glob("iteration-*"))
    if iteration_dirs:
        for iter_dir in iteration_dirs:
            for config_dir in sorted(iter_dir.iterdir()):
                if not config_dir.is_dir():
                    continue
                config_name = config_dir.name  # "train" or "test"
                if config_name not in configs:
                    configs[config_name] = []
                # Scenario dirs under config
                for scenario_dir in sorted(config_dir.iterdir()):
                    if not scenario_dir.is_dir():
                        continue
                    # Check for run-N subdirs
                    run_dirs = sorted(scenario_dir.glob("run-*"))
                    if run_dirs:
                        configs[config_name].extend(run_dirs)
                    elif (scenario_dir / "test_results.json").exists():
                        # Single run, no run-N subdirs
                        configs[config_name].append(scenario_dir)
        return configs

    # Check for config-based layout (config-name/scenario/run-N/)
    for config_dir in sorted(benchmark_dir.iterdir()):
        if not config_dir.is_dir():
            continue
        config_name = config_dir.name
        if config_name in ("logs", "__pycache__"):
            continue

        run_dirs = sorted(config_dir.glob("**/run-*"))
        if run_dirs:
            configs[config_name] = list(run_dirs)
            continue

        # Check for direct test_results.json in scenario subdirs
        scenario_dirs = [
            d
            for d in sorted(config_dir.iterdir())
            if d.is_dir() and (d / "test_results.json").exists()
        ]
        if scenario_dirs:
            configs[config_name] = scenario_dirs
            continue

    # Flat layout: scenario dirs directly under benchmark_dir
    if not configs:
        for scenario_dir in sorted(benchmark_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            run_dirs = sorted(scenario_dir.glob("run-*"))
            if run_dirs:
                if "default" not in configs:
                    configs["default"] = []
                configs["default"].extend(run_dirs)
            elif (scenario_dir / "test_results.json").exists():
                if "default" not in configs:
                    configs["default"] = []
                configs["default"].append(scenario_dir)

    return configs


def _load_run_result(run_dir: Path) -> dict | None:
    """Load result data from a single run directory."""
    result: dict = {}

    # Try test_results.json first (agent-creator format)
    test_results_path = run_dir / "test_results.json"
    if test_results_path.exists():
        try:
            with open(test_results_path) as f:
                data = json.load(f)
            # Count assertions
            passed = 0
            failed = 0
            deferred = 0
            for tr in data.get("turn_results", []):
                for a in tr.get("assertions", []):
                    if a.get("passed") is True:
                        passed += 1
                    elif a.get("passed") is False:
                        failed += 1
                    else:
                        deferred += 1
            total = passed + failed
            result = {
                "scenario_name": data.get("scenario_name", run_dir.parent.name),
                "pass_rate": passed / total if total > 0 else 0.0,
                "passed": passed,
                "failed": failed,
                "deferred": deferred,
                "total": total,
                "tool_calls": len(data.get("all_tool_calls", [])),
                "turn_count": len(data.get("turn_results", [])),
            }
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: error reading {test_results_path}: {e}")
            return None

    # Try grading.json (behavior-grader output)
    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        try:
            with open(grading_path) as f:
                grading = json.load(f)
            summary = grading.get("summary", {})
            result["pass_rate"] = summary.get("pass_rate", result.get("pass_rate", 0.0))
            result["passed"] = summary.get("passed", result.get("passed", 0))
            result["failed"] = summary.get("failed", result.get("failed", 0))
            result["total"] = summary.get("total", result.get("total", 0))

            # Extract claims if present
            claims = grading.get("claims", [])
            if claims:
                result["claims_total"] = len(claims)
                result["claims_verified"] = sum(1 for c in claims if c.get("verified"))

            # Extract expectations for detailed view
            result["expectations"] = grading.get(
                "turn_results", grading.get("expectations", [])
            )
        except (json.JSONDecodeError, OSError):
            pass

    if not result:
        return None

    # Load timing data
    timing_path = run_dir / "timing.json"
    if timing_path.exists():
        try:
            with open(timing_path) as f:
                timing = json.load(f)
            result["time_seconds"] = timing.get(
                "total_duration_seconds",
                timing.get("duration_ms", 0) / 1000,
            )
            result["tokens"] = timing.get("total_tokens", 0)
        except (json.JSONDecodeError, OSError):
            pass

    result.setdefault("time_seconds", 0.0)
    result.setdefault("tokens", 0)

    return result


def load_all_results(benchmark_dir: Path) -> dict[str, list[dict]]:
    """Load all run results grouped by configuration."""
    config_dirs = _find_run_dirs(benchmark_dir)
    results: dict[str, list[dict]] = {}

    for config, run_dirs in config_dirs.items():
        results[config] = []
        for run_dir in run_dirs:
            result = _load_run_result(run_dir)
            if result:
                results[config].append(result)

    return results


def aggregate_results(results: dict[str, list[dict]]) -> dict:
    """Aggregate run results into summary statistics."""
    run_summary: dict = {}
    configs = list(results.keys())

    for config in configs:
        runs = results.get(config, [])
        if not runs:
            run_summary[config] = {
                "pass_rate": calculate_stats([]),
                "time_seconds": calculate_stats([]),
                "tokens": calculate_stats([]),
                "tool_calls": calculate_stats([]),
                "run_count": 0,
            }
            continue

        run_summary[config] = {
            "pass_rate": calculate_stats([r["pass_rate"] for r in runs]),
            "time_seconds": calculate_stats([r["time_seconds"] for r in runs]),
            "tokens": calculate_stats([r.get("tokens", 0) for r in runs]),
            "tool_calls": calculate_stats([r.get("tool_calls", 0) for r in runs]),
            "run_count": len(runs),
        }

    # Calculate delta between first two configs
    if len(configs) >= 2:
        primary = run_summary.get(configs[0], {})
        baseline = run_summary.get(configs[1], {})
        delta_pr = primary.get("pass_rate", {}).get("mean", 0) - baseline.get(
            "pass_rate", {}
        ).get("mean", 0)
        delta_time = primary.get("time_seconds", {}).get("mean", 0) - baseline.get(
            "time_seconds", {}
        ).get("mean", 0)
        delta_tokens = primary.get("tokens", {}).get("mean", 0) - baseline.get(
            "tokens", {}
        ).get("mean", 0)
        run_summary["delta"] = {
            "pass_rate": f"{delta_pr:+.2f}",
            "time_seconds": f"{delta_time:+.1f}",
            "tokens": f"{delta_tokens:+.0f}",
        }

    return run_summary


def generate_benchmark(
    benchmark_dir: Path,
    agent_name: str = "",
    agent_path: str = "",
) -> dict:
    """Generate complete benchmark.json from run results."""
    results = load_all_results(benchmark_dir)
    run_summary = aggregate_results(results)

    # Build runs array
    runs = []
    for config in results:
        for i, result in enumerate(results[config]):
            runs.append(
                {
                    "scenario_name": result.get("scenario_name", f"scenario-{i}"),
                    "configuration": config,
                    "run_number": i + 1,
                    "result": {
                        "pass_rate": result["pass_rate"],
                        "passed": result["passed"],
                        "failed": result["failed"],
                        "total": result["total"],
                        "time_seconds": result["time_seconds"],
                        "tokens": result.get("tokens", 0),
                        "tool_calls": result.get("tool_calls", 0),
                    },
                }
            )

    # Determine scenario names
    scenario_names = sorted(
        set(
            r.get("scenario_name", "unknown")
            for config_runs in results.values()
            for r in config_runs
        )
    )

    return {
        "metadata": {
            "agent_name": agent_name or "<agent-name>",
            "agent_path": agent_path or "<path/to/agent>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scenarios": scenario_names,
            "configurations": list(results.keys()),
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": [],  # To be filled by analyzer agent
    }


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    configs = [k for k in run_summary if k != "delta"]
    lines = [
        f"# Agent Benchmark: {metadata['agent_name']}",
        "",
        f"**Date**: {metadata['timestamp']}",
        f"**Scenarios**: {', '.join(metadata.get('scenarios', []))}",
        f"**Configurations**: {', '.join(configs)}",
        "",
        "## Summary",
        "",
    ]

    if len(configs) >= 2:
        label_a = configs[0].replace("_", " ").title()
        label_b = configs[1].replace("_", " ").title()
        delta = run_summary.get("delta", {})

        lines.extend(
            [
                f"| Metric | {label_a} | {label_b} | Delta |",
                "|--------|------------|---------------|-------|",
            ]
        )

        a_s = run_summary.get(configs[0], {})
        b_s = run_summary.get(configs[1], {})

        a_pr = a_s.get("pass_rate", {})
        b_pr = b_s.get("pass_rate", {})
        lines.append(
            f"| Pass Rate | {a_pr.get('mean', 0) * 100:.0f}% "
            f"\u00b1 {a_pr.get('stddev', 0) * 100:.0f}% | "
            f"{b_pr.get('mean', 0) * 100:.0f}% "
            f"\u00b1 {b_pr.get('stddev', 0) * 100:.0f}% | "
            f"{delta.get('pass_rate', '\u2014')} |"
        )

        a_t = a_s.get("time_seconds", {})
        b_t = b_s.get("time_seconds", {})
        lines.append(
            f"| Time | {a_t.get('mean', 0):.1f}s "
            f"\u00b1 {a_t.get('stddev', 0):.1f}s | "
            f"{b_t.get('mean', 0):.1f}s "
            f"\u00b1 {b_t.get('stddev', 0):.1f}s | "
            f"{delta.get('time_seconds', '\u2014')}s |"
        )
    else:
        for config in configs:
            s = run_summary.get(config, {})
            pr = s.get("pass_rate", {})
            t = s.get("time_seconds", {})
            label = config.replace("_", " ").title()
            lines.extend(
                [
                    f"### {label}",
                    f"- **Pass Rate**: {pr.get('mean', 0) * 100:.0f}% "
                    f"\u00b1 {pr.get('stddev', 0) * 100:.0f}%",
                    f"- **Time**: {t.get('mean', 0):.1f}s "
                    f"\u00b1 {t.get('stddev', 0):.1f}s",
                    f"- **Runs**: {s.get('run_count', 0)}",
                    "",
                ]
            )

    if benchmark.get("notes"):
        lines.extend(["", "## Notes", ""])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate agent benchmark run results into summary statistics"
    )
    parser.add_argument(
        "benchmark_dir", type=Path, help="Path to the benchmark directory"
    )
    parser.add_argument(
        "--agent-name", default="", help="Name of the agent being benchmarked"
    )
    parser.add_argument(
        "--agent-path", default="", help="Path to the agent being benchmarked"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output path for benchmark.json (default: <benchmark_dir>/benchmark.json)",
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"Directory not found: {args.benchmark_dir}")
        sys.exit(1)

    benchmark = generate_benchmark(args.benchmark_dir, args.agent_name, args.agent_path)

    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    with open(output_json, "w") as f:
        json.dump(benchmark, f, indent=2)
    print(f"Generated: {output_json}")

    markdown = generate_markdown(benchmark)
    with open(output_md, "w") as f:
        f.write(markdown)
    print(f"Generated: {output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print("\nSummary:")
    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        n = run_summary[config].get("run_count", 0)
        label = config.replace("_", " ").title()
        print(f"  {label}: {pr * 100:.1f}% pass rate ({n} runs)")
    if delta:
        print(f"  Delta: {delta.get('pass_rate', '\u2014')}")


if __name__ == "__main__":
    main()

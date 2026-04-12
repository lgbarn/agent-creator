#!/usr/bin/env python3
"""Generate an HTML report from run_loop.py output.

Takes the JSON output from run_loop.py and generates a visual HTML report
showing each iteration's pass rates, assertions, and improvement deltas.
Supports auto-refresh for live monitoring during active loops.

Usage:
    python scripts/generate_report.py workspace/loop_results.json -o report.html
    python scripts/generate_report.py workspace/loop_results.json --auto-refresh -o report.html
    python scripts/generate_report.py - < loop_results.json  # stdin
"""

import argparse
import html
import json
import sys
from pathlib import Path


def generate_html(data: dict, auto_refresh: bool = False, agent_name: str = "") -> str:
    """Generate HTML report from loop output data."""
    history = data.get("history", [])
    holdout = data.get("holdout", 0)
    baseline = data.get("baseline")
    title_prefix = html.escape(agent_name + " — ") if agent_name else ""

    refresh_tag = (
        '    <meta http-equiv="refresh" content="10">\n' if auto_refresh else ""
    )

    html_parts = [
        """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
"""
        + refresh_tag
        + """    <title>"""
        + title_prefix
        + """Agent Improvement Report</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
            color: #1a1a1a;
        }
        h1 { margin-bottom: 6px; font-size: 1.5rem; }
        .subtitle { color: #888; margin-bottom: 20px; font-size: 0.9rem; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
        .card {
            background: white;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #e5e5e5;
        }
        .card-label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .card-value { font-size: 1.4rem; font-weight: 700; }
        .card-value.good { color: #2d7d46; }
        .card-value.warn { color: #d97706; }
        .card-value.bad { color: #c44; }
        .card-detail { font-size: 0.8rem; color: #888; margin-top: 4px; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #e5e5e5;
            font-size: 0.875rem;
        }
        th {
            background: #1a1a1a;
            color: white;
            padding: 10px 14px;
            text-align: left;
            font-weight: 500;
            font-size: 0.8rem;
        }
        td {
            padding: 10px 14px;
            border-bottom: 1px solid #f0f0f0;
        }
        tr:hover td { background: #fafafa; }
        .best-row td { background: #f0f7f0; }
        .pass-rate {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.8rem;
        }
        .pr-good { background: #e8f5e9; color: #2d7d46; }
        .pr-ok { background: #fff8e1; color: #d97706; }
        .pr-bad { background: #fce4ec; color: #c44; }
        .delta { font-size: 0.8rem; color: #888; }
        .delta.positive { color: #2d7d46; }
        .delta.negative { color: #c44; }
        .exit-reason {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75rem;
            background: #e3f2fd;
            color: #1565c0;
        }
        .bar-container { display: flex; align-items: center; gap: 8px; }
        .bar {
            height: 8px;
            border-radius: 4px;
            background: #e0e0e0;
            flex: 1;
            max-width: 120px;
            overflow: hidden;
        }
        .bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        .bar-fill.good { background: #2d7d46; }
        .bar-fill.ok { background: #d97706; }
        .bar-fill.bad { background: #c44; }
        .section-title { margin: 24px 0 12px; font-size: 1.1rem; font-weight: 600; }
    </style>
</head>
<body>
"""
    ]

    # Header
    html_parts.append(f"    <h1>{title_prefix}Agent Improvement Report</h1>\n")
    html_parts.append(
        f'    <p class="subtitle">Iterations: {len(history)} | '
        f"Holdout: {holdout:.0%} | "
        f"Train scenarios: {data.get('train_scenarios', '?')} | "
        f"Test scenarios: {data.get('test_scenarios', '?')}</p>\n"
    )

    # Summary cards
    best_rate = data.get("best_pass_rate", 0)
    best_iter = (
        data.get("best_iteration", {}).get("iteration", "?")
        if data.get("best_iteration")
        else "?"
    )
    baseline_rate = baseline.get("pass_rate", 0) if baseline else None

    def rate_class(r):
        if r >= 0.8:
            return "good"
        if r >= 0.5:
            return "warn"
        return "bad"

    html_parts.append('    <div class="cards">\n')

    # Best pass rate card
    html_parts.append(
        f'        <div class="card">\n'
        f'            <div class="card-label">Best Pass Rate</div>\n'
        f'            <div class="card-value {rate_class(best_rate)}">{best_rate:.0%}</div>\n'
        f'            <div class="card-detail">Iteration {best_iter}</div>\n'
        f"        </div>\n"
    )

    # Baseline card
    if baseline_rate is not None:
        delta = best_rate - baseline_rate
        delta_str = f"{delta:+.0%}"
        html_parts.append(
            f'        <div class="card">\n'
            f'            <div class="card-label">Baseline</div>\n'
            f'            <div class="card-value">{baseline_rate:.0%}</div>\n'
            f'            <div class="card-detail">Delta: {delta_str}</div>\n'
            f"        </div>\n"
        )

    # Iterations card
    html_parts.append(
        f'        <div class="card">\n'
        f'            <div class="card-label">Iterations Run</div>\n'
        f'            <div class="card-value">{data.get("iterations_run", 0)}</div>\n'
        f'            <div class="card-detail">Max: {len(history)}</div>\n'
        f"        </div>\n"
    )

    # Exit reason
    if history:
        last = history[-1]
        exit_reason = last.get("exit_reason", "in_progress")
        html_parts.append(
            f'        <div class="card">\n'
            f'            <div class="card-label">Exit Reason</div>\n'
            f'            <div class="card-value"><span class="exit-reason">{html.escape(exit_reason)}</span></div>\n'
            f"        </div>\n"
        )

    html_parts.append("    </div>\n")

    # Iteration history table
    html_parts.append('    <div class="section-title">Iteration History</div>\n')
    html_parts.append("""    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Train Pass Rate</th>
                <th>Test Pass Rate</th>
                <th>Delta vs Baseline</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Exit</th>
            </tr>
        </thead>
        <tbody>
""")

    best_iter_num = (
        data.get("best_iteration", {}).get("iteration")
        if data.get("best_iteration")
        else None
    )

    for h in history:
        iteration = h.get("iteration", "?")
        train = h.get("train", {})
        test = h.get("test")
        train_rate = train.get("pass_rate", h.get("pass_rate", 0))
        test_rate = test.get("pass_rate", 0) if test else None
        passed = train.get("passed", h.get("passed", 0))
        failed = train.get("failed", h.get("failed", 0))
        delta_vs_baseline = h.get("delta_vs_baseline")
        exit_reason = h.get("exit_reason", "")

        row_class = "best-row" if iteration == best_iter_num else ""
        train_class = rate_class(train_rate)
        bar_pct = int(train_rate * 100)

        html_parts.append(f'            <tr class="{row_class}">\n')
        html_parts.append(f"                <td>{iteration}</td>\n")

        # Train rate with bar
        html_parts.append(
            f'                <td><div class="bar-container">'
            f'<span class="pass-rate pr-{train_class}">{train_rate:.0%}</span>'
            f'<div class="bar"><div class="bar-fill {train_class}" style="width:{bar_pct}%"></div></div>'
            f"</div></td>\n"
        )

        # Test rate
        if test_rate is not None:
            t_class = rate_class(test_rate)
            html_parts.append(
                f'                <td><span class="pass-rate pr-{t_class}">{test_rate:.0%}</span></td>\n'
            )
        else:
            html_parts.append("                <td>—</td>\n")

        # Delta
        if delta_vs_baseline is not None:
            d_class = "positive" if delta_vs_baseline >= 0 else "negative"
            html_parts.append(
                f'                <td><span class="delta {d_class}">{delta_vs_baseline:+.0%}</span></td>\n'
            )
        else:
            html_parts.append("                <td>—</td>\n")

        html_parts.append(f"                <td>{passed}</td>\n")
        html_parts.append(f"                <td>{failed}</td>\n")

        if exit_reason:
            html_parts.append(
                f'                <td><span class="exit-reason">{html.escape(exit_reason)}</span></td>\n'
            )
        else:
            html_parts.append("                <td></td>\n")

        html_parts.append("            </tr>\n")

    html_parts.append("""        </tbody>
    </table>
""")

    html_parts.append("\n</body>\n</html>\n")
    return "".join(html_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML report from agent improvement loop output"
    )
    parser.add_argument(
        "input", help="Path to JSON output from run_loop.py (or - for stdin)"
    )
    parser.add_argument(
        "-o", "--output", default=None, help="Output HTML file (default: stdout)"
    )
    parser.add_argument("--agent-name", default="", help="Agent name for report title")
    parser.add_argument(
        "--auto-refresh",
        action="store_true",
        help="Add auto-refresh meta tag (for live monitoring during active loops)",
    )
    args = parser.parse_args()

    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(args.input).read_text())

    html_output = generate_html(
        data, auto_refresh=args.auto_refresh, agent_name=args.agent_name
    )

    if args.output:
        Path(args.output).write_text(html_output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(html_output)


if __name__ == "__main__":
    main()

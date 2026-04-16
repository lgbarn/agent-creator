# Scripts Reference

All scripts require Python 3.12+ with `pyyaml` installed (`pip install pyyaml`).

## Validate an agent

Checks frontmatter fields, system prompt structure, and flags common issues.

```bash
python scripts/validate_agent.py path/to/agent.md
```

## Run test scenarios

Runs test scenarios against an agent and captures transcripts.

```bash
python scripts/run_agent_test.py \
  --agent my-agent \
  --scenario evals/scenario.json \
  --output-dir workspace/iteration-1/ \
  --runs 3
```

| Flag | Description |
|------|-------------|
| `--agent` | Agent name (resolved from `~/.claude/agents/` and `.claude/agents/`) or path to `.md` file |
| `--scenario` | Path to scenario JSON file |
| `--output-dir` | Directory to write transcripts and results |
| `--runs` | Number of times to run each scenario (default: 1; use 3+ for benchmarking) |

Results go into `run-1/`, `run-2/`, etc. subdirectories with an `aggregate.json` summary.

## Automated improvement loop

Runs test → identify failures → improve prompt → re-test, up to N iterations.

```bash
python scripts/run_loop.py \
  --agent path/to/agent.md \
  --scenarios evals/scenarios.json \
  --output-dir workspace/ \
  --max-iterations 5 \
  --holdout 0.3 \
  --runs 3 \
  --model sonnet \
  --verbose
```

| Flag | Description |
|------|-------------|
| `--agent` | Path to agent `.md` file |
| `--scenarios` | Path to scenarios JSON file |
| `--output-dir` | Directory for all output (transcripts, loop results, best agent) |
| `--max-iterations` | Maximum improvement cycles (default: 5) |
| `--holdout` | Fraction of scenarios held out as test set, e.g. `0.3` = 30% (prevents overfitting) |
| `--runs` | Runs per scenario per iteration for statistical reliability |
| `--model` | Claude model for prompt improvement (`sonnet`, `opus`) |
| `--no-baseline` | Skip running the original agent as a baseline comparison |
| `--mode description` | Optimize the `description` field instead of the system prompt |
| `--verbose` | Print iteration progress |

If `feedback.json` exists in the output directory (exported from the eval viewer), the loop automatically incorporates it. Human feedback takes priority over automated assertions.

## Eval viewer

Interactive browser-based viewer for reviewing transcripts, writing feedback, and tracking benchmark progress.

```bash
python eval-viewer/generate_review.py workspace/iteration-1/ --agent-name my-agent
```

| Flag | Description |
|------|-------------|
| `--agent-name` | Agent name shown in the viewer |
| `--static report.html` | Write a standalone HTML file instead of opening a browser |

Features:
- Navigate between scenarios with prev/next
- Write feedback per scenario (auto-saved)
- Benchmark tab when aggregate data is available
- Export feedback as `feedback.json` for the improvement loop

## Improve prompt (standalone)

Improve a system prompt using Claude with extended thinking, given grading results.

```bash
python scripts/improve_prompt.py \
  --agent path/to/agent.md \
  --grading path/to/grading.json \
  --model sonnet
```

## Aggregate benchmark statistics

Aggregates results across multiple runs into benchmark statistics.

```bash
python scripts/aggregate_benchmark.py workspace/ --agent-name my-agent
```

Produces `benchmark.json` and `benchmark.md` with mean±stddev for pass rates, timing, and token usage. Feed into the eval viewer's Benchmark tab.

## Generate HTML progress report

Visualizes improvement loop progress across iterations.

```bash
python scripts/generate_report.py workspace/loop_results.json -o report.html
```

Add `--auto-refresh` for live monitoring during an active loop (reloads every 10 seconds).

## Test trigger accuracy

Tests whether Claude correctly delegates to an agent for matching queries and avoids delegating for non-matching ones. Only relevant for agents that use `<example>` blocks in their description for auto-triggering.

```bash
python scripts/run_trigger_eval.py \
  --agent path/to/agent.md \
  --eval-set trigger-queries.json \
  --runs-per-query 3 \
  --verbose
```

The eval set is a JSON array:
```json
[
  {"query": "can you review this auth flow for security issues?", "should_trigger": true},
  {"query": "write a fibonacci function in Python", "should_trigger": false}
]
```

To review and edit trigger queries in the browser before running:
1. Read `assets/eval_review.html`
2. Replace `__AGENT_NAME_PLACEHOLDER__`, `__AGENT_DESCRIPTION_PLACEHOLDER__`, `__EVAL_DATA_PLACEHOLDER__`
3. Open in browser — add/remove queries, toggle `should_trigger`, export `eval_set.json`

## Package for distribution

Packages an agent into a distributable `.agent` archive.

```bash
python scripts/package_agent.py path/to/agent.md output-dir/
```

## Evaluation agents

Located in `agents/` — spawned by the skill during testing:

| Agent | Role | When to use |
|-------|------|-------------|
| `behavior-grader.md` | Grades transcripts against behavioral assertions, extracts claims, critiques test coverage | After running tests |
| `agent-comparator.md` | Blind A/B comparison with task-specific rubrics | When comparing before/after an improvement |
| `agent-analyzer.md` | Post-hoc analysis with prioritized improvement suggestions | After a comparison |

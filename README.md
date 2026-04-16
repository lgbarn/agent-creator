# agent-creator

A Claude Code plugin for building, testing, and iteratively improving custom Claude Code agents.

Agents are markdown files with YAML frontmatter that define a specialized Claude persona — started with `claude --agent name` for a full session, or invoked mid-conversation with `@agent-name`.

## Installation

Add the marketplace and install the plugin:

```bash
claude plugin marketplace add lgbarn/agent-creator
claude plugin install agent-creator@lgbarn/agent-creator
```

Or install from a local clone:

```bash
git clone https://github.com/lgbarn/agent-creator.git
claude plugin marketplace add ./agent-creator
claude plugin install agent-creator@agent-creator
```

## Usage

Start Claude Code and invoke the skill:

```
> /agent-creator
```

Or describe what you want — the skill triggers automatically:

```
> create a Go expert agent
> build me a code review agent
> my security-advisor agent isn't behaving right
```

The guided workflow walks you through:

1. **Design** — Define the agent's role, scope, metadata, and system prompt
2. **Test** — Validate the file, run multi-turn test scenarios, grade behavior
3. **Iterate** — Improve the prompt automatically or manually based on test results

## Agent Archetypes

**Conversational agents** — Domain experts the user talks to. Minimal tools (Read, Grep, Glob). Examples: security advisor, Go expert, recipe helper.

**Task agents** — Automated workers that perform actions. Full tool access. Examples: code reviewer, test generator, deployment helper.

## Project Structure

```
.claude-plugin/        Plugin metadata (plugin.json, marketplace.json)
agents/                Evaluation agents used during testing
  agent-analyzer.md    Post-hoc analysis of why one version performed better
  agent-comparator.md  Blind A/B comparison of two agent versions
  behavior-grader.md   Grade transcripts against behavioral assertions
assets/
  eval_review.html     Template for reviewing trigger eval queries in browser
eval-viewer/           Browser-based transcript viewer with feedback collection
  generate_review.py   Generate interactive HTML review from test results
  viewer.html          HTML template (embedded data, no external deps)
evals/
  example-scenario.json  Example test scenario demonstrating the schema
references/            Documentation for agent authoring
  agent-frontmatter-reference.md   Frontmatter field reference
  agent-templates.md               Common agent templates
  schemas.md                       Test scenario JSON schema
  system-prompt-patterns.md        System prompt writing patterns
scripts/               Automation scripts
  validate_agent.py    Validate agent .md file structure and fields
  run_agent_test.py    Run test scenarios and capture transcripts
  run_loop.py          Iterative test-improve cycle with train/test split
  run_trigger_eval.py  Test agent description triggering accuracy
  improve_prompt.py    Improve system prompt using Claude + extended thinking
  aggregate_benchmark.py  Aggregate results into benchmark stats
  generate_report.py   Generate HTML report of improvement loop progress
  package_agent.py     Package agent into distributable .agent archive
  utils.py             Shared parsing utilities
skills/
  agent-creator/
    SKILL.md           Main skill definition
```

## Scripts

All scripts are in `scripts/` and require Python 3.12+ with `pyyaml`.

### Validate an agent

```bash
python scripts/validate_agent.py path/to/agent.md
```

### Run test scenarios

```bash
python scripts/run_agent_test.py \
  --agent my-agent \
  --scenario evals/example-scenario.json \
  --output-dir workspace/iteration-1/ \
  --runs 3
```

### Iterative improvement loop

```bash
python scripts/run_loop.py \
  --agent path/to/agent.md \
  --scenarios evals/scenarios.json \
  --output-dir workspace/ \
  --max-iterations 5 \
  --holdout 0.3 \
  --runs 3
```

### Review results in browser

```bash
python eval-viewer/generate_review.py workspace/iteration-1/ --agent-name my-agent
```

### Aggregate benchmark statistics

```bash
python scripts/aggregate_benchmark.py workspace/ --agent-name my-agent
```

### Generate HTML progress report

```bash
python scripts/generate_report.py workspace/loop_results.json -o report.html
```

### Test trigger accuracy

```bash
python scripts/run_trigger_eval.py \
  --agent path/to/agent.md \
  --eval-set trigger-queries.json \
  --runs-per-query 3
```

### Package for distribution

```bash
python scripts/package_agent.py path/to/agent.md output-dir/
```

## CI

GitHub Actions runs on push/PR to master — lints with ruff, validates plugin structure, tests imports, runs the validator against sample agents, and tests packaging. See `.github/workflows/ci.yml`.

## License

MIT

# Changelog

## 2.0.0

### Added
- **Eval viewer** — Browser-based interactive transcript viewer with per-scenario feedback collection, benchmark tab, and JSON export (`eval-viewer/`)
- **Benchmark aggregation** — `aggregate_benchmark.py` produces `benchmark.json` and `benchmark.md` with mean/stddev for pass rates, timing, and token usage
- **HTML progress reports** — `generate_report.py` generates visual HTML reports of improvement loop progress with optional auto-refresh for live monitoring
- **Claim extraction and verification** — Behavior grader now extracts factual, process, and quality claims from agent responses and verifies them, catching hallucination that assertions miss
- **Scenario critique** — Behavior grader flags trivially satisfied, non-discriminating, or missing assertions
- **Dynamic rubrics** — Agent comparator generates task-specific evaluation rubrics tailored to the agent's domain instead of using generic criteria
- **Feedback-driven improvement** — Improvement loop integrates human feedback from the eval viewer (`feedback.json`), prioritizing human judgment over automated assertions
- **Trigger eval review UI** — `assets/eval_review.html` template for reviewing and editing trigger eval queries in a browser before running optimization
- **Description optimization mode** — `run_loop.py --mode description` iteratively optimizes the description field for trigger accuracy

### Changed
- Updated behavior grader with claim extraction and scenario critique capabilities
- Updated agent comparator with dynamic rubric generation
- Updated SKILL.md with documentation for all new workflows and scripts
- Bumped plugin version to 2.0.0 in both `plugin.json` and `marketplace.json`

## 1.1.0

### Added
- **Train/test split** — `run_loop.py --holdout` holds out a fraction of scenarios as a test set to prevent overfitting; best version selected by test score
- **Baseline comparison** — Improvement loop runs the original agent first by default (`--no-baseline` to skip), showing improvement deltas
- **Multi-run statistical reliability** — `run_agent_test.py --runs N` runs each scenario multiple times with aggregate statistics
- **Trigger testing** — `run_trigger_eval.py` tests whether Claude correctly delegates to the agent based on its description `<example>` blocks
- **Marketplace metadata** — Added `marketplace.json` for plugin discovery

### Changed
- Updated SKILL.md with documentation for new capabilities
- Added CI import tests for new modules

## 1.0.0

### Added
- **Plugin structure** — `.claude-plugin/plugin.json`, `skills/agent-creator/SKILL.md`
- **Agent creation workflow** — 8-step guided workflow: design (steps 1-6), test (step 7), iterate (step 8)
- **Two agent archetypes** — Conversational (domain experts) and task (automated workers) with archetype-specific defaults
- **Validation** — `validate_agent.py` checks frontmatter fields, system prompt structure, and flags issues
- **Multi-turn test runner** — `run_agent_test.py` runs test scenarios with programmatic and behavioral assertions
- **Behavior grader agent** — Grades transcripts against behavioral assertions (persona, boundaries, style, tools)
- **Agent comparator** — Blind A/B comparison of two agent versions
- **Agent analyzer** — Post-hoc analysis of comparison results with prioritized improvement suggestions
- **Iterative improvement loop** — `run_loop.py` automates test-improve cycles using Claude with extended thinking
- **Prompt improvement** — `improve_prompt.py` rewrites system prompts based on grading results
- **Agent packaging** — `package_agent.py` creates distributable `.agent` archives
- **Reference documentation** — Frontmatter reference, agent templates, schemas, system prompt patterns
- **Example scenario** — `evals/example-scenario.json` demonstrating the test scenario schema
- **CI pipeline** — GitHub Actions with ruff lint/format, structure validation, import tests, validator tests, packaging tests

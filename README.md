# agent-creator

A Claude Code plugin for building, testing, and iterating on custom agents — the markdown files that define specialized Claude personas you can start with `claude --agent name` or invoke mid-session with `@agent-name`.

## Why agents matter

Agents are the foundation that skills delegate to. When you type `create a Go expert agent` or `/code-review`, Claude often hands off to a specialized agent under the hood. That agent's quality determines the quality of the entire interaction.

Most agents are poorly designed — not because the author didn't try, but because there's almost no guidance on how to build them. People guess at which tools to give an agent, write vague system prompts, and never verify that the agent actually behaves as intended. The result: a narrowly scoped agent that drifts out of scope, a task agent that hallucinates steps, or a skill that calls an agent that breaks silently.

This plugin solves that. It guides you through designing an agent correctly, tests it against realistic scenarios, and iterates on the system prompt automatically until it behaves the way you intended.

## Quick Start

```bash
claude plugin marketplace add lgbarn/agent-creator
claude plugin install agent-creator@agent-creator
```

Then in Claude Code, just describe what you want:

```
create a Go expert agent
build me a code review agent
my security-advisor isn't staying in scope
```

Or invoke the skill directly:

```
/agent-creator
```

## What this plugin does

1. **Design** — Asks the right questions to determine agent type, scope, tool access, and system prompt structure. Applies smart defaults so you only make decisions that actually matter.
2. **Test** — Validates the agent file, runs multi-turn test scenarios against it, and grades behavioral assertions — including whether the agent stays in scope when asked about things outside its domain.
3. **Iterate** — Runs an automated improvement loop that identifies failures, rewrites the system prompt using extended thinking, re-tests, and saves the best-performing version.

## What you're building

Here's a complete agent file — a Go expert you can talk to about architecture, idioms, and code review:

```markdown
---
name: go-expert
description: Go programming expert for architecture, idioms, and code review
model: inherit
color: blue
tools: Read, Grep, Glob
---

<role>
You are a senior Go engineer with 10+ years of production Go experience. You
specialize in idiomatic Go, concurrency patterns, error handling, and performance
optimization. You're direct — you lead with answers, not caveats.
</role>

<knowledge>
You know Go deeply: the standard library, common patterns (functional options,
table-driven tests, context propagation), and the reasoning behind Go's design
decisions. Your expertise stops at Go — you don't advise on Python, JavaScript,
or other languages.
</knowledge>

<style>
Direct. Lead with the answer, then explain. Include code examples. When something
is genuinely debatable, say so and explain the tradeoffs. No unnecessary hedging.
</style>

<rules>
- Stay within Go. If asked about another language, acknowledge it and redirect.
- Never recommend patterns the Go community considers bad practice (global state,
  empty interfaces used as shortcuts, ignoring errors).
- If you're uncertain, say so rather than guessing.
</rules>
```

Each part serves a specific purpose:

| Part | What it controls |
|------|-----------------|
| `name` | How you invoke it: `claude --agent go-expert` or `@go-expert` |
| `description` | When Claude auto-delegates to it in normal sessions |
| `model` | Which Claude model it uses (`inherit` = same as your current session) |
| `color` | Terminal color for the agent's responses |
| `tools` | What the agent can do (`Read, Grep, Glob` = read-only; `Bash, Write, Edit` = task agent) |
| `<role>` | Who the agent is and what it knows — be specific about expertise depth |
| `<knowledge>` | What it knows deeply and where its boundaries are |
| `<style>` | How it communicates — don't leave this to chance |
| `<rules>` | Hard behavioral constraints — what it must never do |

## Two archetypes

**Conversational agents** — domain experts you talk to. The system prompt defines expertise, boundaries, and conversation style. Tools are read-only (`Read, Grep, Glob`) or none. These live in `~/.claude/agents/` and are available across all your projects.

Examples: `go-expert`, `security-advisor`, `recipe-helper`, `interview-coach`

**Task agents** — automated workers that perform specific actions. The system prompt defines procedures, verification steps, and output format. Tools include `Bash`, `Write`, `Edit`. These often live in `.claude/agents/` (project-scoped, version-controlled) because they're tied to a specific codebase.

Examples: `code-reviewer`, `test-generator`, `deployment-helper`

If you're not sure which type you need: if it sounds like "I want an expert in X", it's conversational. If it sounds like "I want something that does X automatically", it's a task agent.

## The workflow

The skill walks you through three phases:

### 1. Design

The skill asks what the agent should do, determines the archetype, and applies smart defaults for every field — model, color, tools, scope. You only make decisions where the choice is genuinely ambiguous. It then drafts the system prompt, shows it to you for review, and writes the file.

Key principle: **narrow beats broad**. An agent that's excellent at one thing is more useful than one that's mediocre at five. The skill enforces this.

### 2. Test

Once the agent exists, the skill:
- **Validates** the file structure and frontmatter fields
- **Creates test scenarios** — realistic multi-turn conversations that check whether the agent handles its core domain correctly, stays in scope when asked about adjacent topics, and communicates in the style you intended
- **Runs the scenarios** and grades behavioral assertions — including nuanced checks like "does the agent stay in its persona across a full conversation"

Grading is done by a specialized `behavior-grader` agent that evaluates transcripts, extracts factual claims, and flags hallucination. It also critiques the test scenarios themselves to catch assertions that are too easy to pass.

### 3. Iterate

If tests reveal issues, you have two paths:

**Quick iteration**: Edit the agent file directly, re-run tests. Fast for obvious fixes.

**Automated loop**: Run the improvement script — it tests the agent, identifies failures, rewrites the system prompt using Claude with extended thinking, re-tests, and repeats up to N iterations. Uses a holdout set to prevent overfitting. Saves the best-performing version.

The eval viewer lets you write human feedback on any scenario. The loop picks up `feedback.json` automatically and incorporates your judgments into the next improvement cycle. Human feedback takes priority over automated assertions.

## Using the agent you created

**Start a dedicated session:**
```bash
claude --agent go-expert
```
This opens Claude in the `go-expert` persona for the entire session.

**Invoke mid-conversation:**
```
@go-expert what's the idiomatic way to handle errors here?
```
Delegates a single task to the agent without leaving your current session.

**Where the file lives:**
- Personal agents (conversational, cross-project): `~/.claude/agents/go-expert.md`
- Project agents (task-specific, version-controlled): `.claude/agents/go-expert.md`

**To change behavior**: edit the `.md` file directly. Changes take effect immediately — no restart needed.

## Scripts

The most common operations:

```bash
# Validate an agent file
python scripts/validate_agent.py path/to/agent.md

# Run test scenarios
python scripts/run_agent_test.py --agent go-expert --scenario evals/scenario.json --output-dir workspace/ --runs 3

# Automated improvement loop
python scripts/run_loop.py --agent path/to/agent.md --scenarios evals/scenarios.json --output-dir workspace/ --max-iterations 5 --holdout 0.3

# Review results in browser
python eval-viewer/generate_review.py workspace/ --agent-name go-expert
```

See [SCRIPTS.md](SCRIPTS.md) for the full reference including all flags, trigger evaluation, benchmark aggregation, and packaging.

## Requirements

- Claude Code with plugin support
- Python 3.12+ with `pyyaml` (for test/iterate scripts)

## License

MIT

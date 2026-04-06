---
name: agent-creator
description: >-
  Interactive builder for creating, testing, and iteratively improving custom
  Claude Code agents. Use this skill when the user asks to "create an agent",
  "build me an agent", "make an agent for X", "I want an agent that...",
  "create a domain expert", "make a conversational agent", "agent builder",
  "new agent", or describes any persona they want to converse with or delegate
  tasks to via `claude --agent`. Also use when the user wants to turn a workflow
  into a reusable agent, test an existing agent, improve an agent's behavior,
  or asks about creating agents for specific topics. Even if the user doesn't
  say "agent" explicitly — if they say something like "I want to be able to
  talk to Claude about security anytime" or "can I have a Go expert on demand"
  or "my agent isn't behaving right", this skill applies.
---

# Agent Creator

Build, test, and iteratively improve custom Claude Code agents through a guided workflow. Agents are markdown files with YAML frontmatter that define a specialized Claude persona — started with `claude --agent name` for a full session, or invoked mid-conversation with `@agent-name`.

The plugin root is the parent of this skill's directory. Scripts are at `../../scripts/` relative to this file, agents at `../../agents/`, and references at `../../references/`.

## Two Agent Archetypes

Before starting, understand which type the user needs:

**Conversational Agents** — Domain experts the user talks to. The system prompt defines persona, expertise boundaries, and conversation style. Tools are minimal (often just `Read, Grep, Glob` or none). The user starts a session and has an ongoing dialogue.
- Examples: security advisor, Go expert, recipe helper, writing coach, interview prep partner

**Task Agents** — Automated workers that perform specific actions. The system prompt defines procedures, verification steps, and output formats. Tools include `Bash`, `Write`, `Edit`, etc.
- Examples: code reviewer, test generator, deployment helper, debugging assistant

Most users asking to "create an agent" want a conversational agent. If the request sounds like "I want an expert in X", default to conversational unless they describe specific automated actions.

## Workflow Overview

The full workflow is 8 steps: design (1-6), test (7), iterate (8). Adapt based on how much the user already knows — skip steps when intent is clear.

### Step 1: Understand Intent

Figure out what the agent should do. Ask:
- What domain or expertise should the agent have?
- Is this conversational (you talk to it) or task-oriented (it does work)?
- What would a typical interaction look like?

If the request is already clear (e.g., "make me a Go expert agent"), acknowledge and move on.

### Step 2: Determine Scope and Location

| Location | Path | When to use |
|----------|------|-------------|
| **Personal** | `~/.claude/agents/` | Available across all projects. Default for conversational domain experts. |
| **Project** | `.claude/agents/` | Tied to current repo, version-controlled. Default for task agents specific to a codebase. |

Create the directory if it doesn't exist (`mkdir -p`). Default to personal for conversational, project for task agents.

### Step 3: Configure Metadata

Decide on frontmatter fields. Offer sensible defaults — only ask about a field when the choice is genuinely ambiguous. Read `references/agent-frontmatter-reference.md` for details on any field.

**Smart defaults by archetype:**

| Field | Conversational Default | Task Default |
|-------|----------------------|--------------|
| `name` | Derive from domain: `go-expert`, `security-advisor` | Derive from action: `code-reviewer`, `test-generator` |
| `model` | `inherit` (or `opus` if deep reasoning needed) | `inherit` (or `sonnet` for fast iteration) |
| `color` | Match domain semantics (see below) | Match domain semantics |
| `tools` | `Read, Grep, Glob` (read-only) | Select based on what it does |
| `maxTurns` | Omit (unlimited conversation) | 15-30 based on task complexity |
| `memory` | Consider `user` if the agent should remember across sessions | Omit unless stateful |

**Color semantics:** `blue`/`cyan` — analysis, research. `green` — creation, building. `yellow` — validation, teaching. `red` — security, critical. `magenta` — creative, writing, design.

### Step 4: Craft the System Prompt

The system prompt defines everything about the agent's behavior. Read `references/system-prompt-patterns.md` for detailed patterns.

**For conversational agents**, use this structure:

```xml
<role>
Who the agent is, their expertise, and personality traits.
Be specific: not "you know about security" but "you specialize in
application security, OWASP Top 10, threat modeling, and secure code
review in Python and Go."
</role>

<knowledge>
What the agent knows deeply, and where its boundaries are.
Include when it should say "I don't know" or recommend external resources.
</knowledge>

<style>
How the agent communicates:
- Socratic (asks questions to guide understanding)
- Direct (gives clear answers with rationale)
- Teaching (explains concepts, builds mental models)
- Advisory (weighs tradeoffs, recommends approaches)
</style>

<rules>
Behavioral boundaries:
- What the agent should NOT do
- When to escalate or defer
- Scope limits
</rules>
```

**For task agents**, use:

```xml
<role>
Expertise and function. What this agent does and why it exists.
</role>

<instructions>
Step-by-step procedure the agent follows.
Include verification steps and output format.
</instructions>

<rules>
Hard constraints: MUST / MUST NOT rules, quality standards, when to stop.
</rules>
```

**Key principles:**
- Be specific about expertise — generic prompts produce generic agents
- Include behavioral guardrails — what the agent should NOT do is as important as what it should do
- Define conversation/output style — don't leave this to chance
- Target 300-800 words for conversational agents, 500-1,500 for task agents
- Explain the **why** behind rules so the model can generalize to edge cases

Check `references/agent-templates.md` if the user's request matches a common pattern — adapt a template rather than writing from scratch.

### Step 5: Generate and Save

1. Assemble the complete agent file (frontmatter + system prompt body)
2. Present it to the user for review before writing
3. Ask if they want any changes
4. Write the file to the chosen location

**For the description field**: If the agent will only be used via `claude --agent name`, a simple one-line description is fine. If the user also wants it to auto-trigger when delegated by Claude in normal sessions, write a richer description with `<example>` blocks:

```yaml
description: |
  Use this agent when the user asks about application security,
  threat modeling, or secure coding practices. Examples:
  <example>
  Context: User is reviewing code for security issues.
  user: "Can you check this auth flow for vulnerabilities?"
  assistant: "I'll use the security-advisor agent to review this."
  <commentary>Security review is this agent's core expertise.</commentary>
  </example>
```

### Step 6: Post-Creation Guidance

After saving, tell the user:
1. **How to start it**: `claude --agent agent-name`
2. **How to invoke mid-session**: Type `@agent-name` followed by a task
3. **Where the file lives**: Full path for future editing
4. **How to edit**: Modify the `.md` file directly anytime
5. **Offer to test**: "Want me to validate and test it?"

### Step 7: Validate and Test

This step verifies the agent works as intended. Run the validation script first, then create test scenarios.

**Validate the agent file:**
```bash
python <plugin-root>/scripts/validate_agent.py <path-to-agent.md>
```
This checks frontmatter fields, system prompt structure, and flags issues. Fix any errors before proceeding.

**Create test scenarios:**
Write 2-3 realistic test scenarios — the kind of thing a real user would actually say to this agent. Include:
- A straightforward request in the agent's domain
- An edge case or boundary test (e.g., asking about an out-of-scope topic)
- For task agents: a complete workflow exercise

Save scenarios as JSON following the format in `references/schemas.md`. See `evals/example-scenario.json` for a complete example.

Each scenario has:
- `turns`: multi-turn conversation with per-turn assertions
- `global_assertions`: behavioral checks across the full conversation
- Assertion types: `contains`, `not_contains`, `regex` (programmatic), `behavioral`, `tone` (graded by behavior-grader agent)

**Run the tests:**
```bash
python <plugin-root>/scripts/run_agent_test.py \
  --agent <agent-name-or-path> \
  --scenario <scenario.json> \
  --output-dir <workspace>/iteration-1/
```

Review the transcript and assertion results. For behavioral assertions that need judgment-based grading, spawn the behavior-grader agent:

Read `agents/behavior-grader.md` for the grader's instructions. Spawn it with:
- `transcript_path`: path to the generated transcript.md
- `scenario_path`: path to the test scenario JSON
- `output_path`: where to write grading.json

### Step 8: Iterate and Improve

If tests reveal issues, improve the agent and re-test.

**Quick iteration**: Edit the agent file directly based on test feedback, then re-run Step 7.

**Automated improvement loop** (for more thorough optimization):
```bash
python <plugin-root>/scripts/run_loop.py \
  --agent <path-to-agent.md> \
  --scenarios <scenarios.json> \
  --output-dir <workspace>/ \
  --max-iterations 5 \
  --model sonnet \
  --verbose
```

This runs the test-improve cycle automatically: test → identify failures → use Claude to improve the prompt → re-test → repeat. It saves the best-performing version.

**For deeper analysis**, use the evaluation agents:
- **agent-comparator** (`agents/agent-comparator.md`): Blind A/B comparison of two agent versions on the same scenarios
- **agent-analyzer** (`agents/agent-analyzer.md`): Post-hoc analysis of why one version performed better, with prioritized improvement suggestions

**For description optimization** (improving auto-triggering accuracy): The improvement loop supports `--mode description` to iteratively optimize the description field instead of the system prompt.

Keep iterating until:
- The user is happy with the agent's behavior
- All test assertions pass
- You're not making meaningful progress

## Tips for Better Agents

- **Narrow beats broad**: An agent that's great at one thing is more useful than one that's mediocre at five things
- **Persona matters for conversational agents**: A "grumpy but brilliant security expert" is more engaging than a generic advisor
- **Tool restriction is a feature**: Giving a recipe agent `Write` access means it might try to create files when the user just wants to talk about cooking
- **Memory is powerful**: If the agent should learn preferences over time, enable `memory: user`
- **Explain the why**: Don't just add MUST rules — explain reasoning so the model can generalize to cases you didn't anticipate
- **Start simple, iterate**: Create a minimal agent, test it, then refine based on actual behavior
- **Test behavioral boundaries**: The most valuable tests check what the agent does when asked about things outside its scope

## Scripts Reference

All scripts are in `<plugin-root>/scripts/`:

| Script | Purpose | Usage |
|--------|---------|-------|
| `validate_agent.py` | Validate agent .md file structure and fields | `python scripts/validate_agent.py <agent.md>` |
| `run_agent_test.py` | Run test scenarios and capture transcripts | `python scripts/run_agent_test.py --agent <name> --scenario <file> --output-dir <dir>` |
| `run_loop.py` | Iterative test-improve cycle | `python scripts/run_loop.py --agent <path> --scenarios <file> --output-dir <dir>` |
| `improve_prompt.py` | Improve system prompt using Claude + extended thinking | `python scripts/improve_prompt.py --agent <path> --grading <file> --model <model>` |
| `package_agent.py` | Package agent into distributable .agent archive | `python scripts/package_agent.py <agent.md> [output-dir]` |
| `utils.py` | Shared parsing utilities (imported by other scripts) | — |

## Evaluation Agents

Located in `<plugin-root>/agents/`:

| Agent | Role | When to use |
|-------|------|-------------|
| `behavior-grader.md` | Grade transcripts against behavioral assertions | After running tests — evaluates persona, boundaries, style |
| `agent-comparator.md` | Blind A/B comparison of two agent versions | When comparing before/after an improvement |
| `agent-analyzer.md` | Post-hoc analysis with improvement suggestions | After comparison — extracts actionable changes |

# Agent Frontmatter Reference

Complete reference for all YAML frontmatter fields in Claude Code agent `.md` files.

## Required Fields

### name
Agent identifier used for invocation and namespacing.

- **Format**: Lowercase letters, numbers, hyphens only
- **Length**: 3-50 characters
- **Pattern**: Must start and end with alphanumeric character
- **Examples**: `go-expert`, `security-advisor`, `code-reviewer`, `recipe-helper`
- **Bad**: `helper` (too generic), `-agent-` (starts with hyphen), `my_agent` (underscore)

### description
Defines when Claude should trigger this agent and what it does.

**For `--agent` usage only** (user starts it directly): A simple one-line description is sufficient.
```yaml
description: Go programming expert for architecture, idioms, and code review
```

**For auto-triggering** (Claude delegates to it during normal sessions): Include `<example>` blocks.
```yaml
description: |
  Use this agent when the user asks about Go programming, architecture,
  or idiomatic Go patterns. Examples:
  <example>
  Context: User is writing Go code and asks about patterns.
  user: "What's the idiomatic way to handle errors in Go?"
  assistant: "I'll use the go-expert agent for this."
  <commentary>Go-specific questions are this agent's core domain.</commentary>
  </example>
```

**Length**: 10-5,000 characters. Best: 200-1,000 characters with 2-4 examples.

## Optional Fields

### model
Which Claude model the agent uses.

| Value | When to use |
|-------|-------------|
| `inherit` | Default. Uses whatever model the parent session runs. Best choice most of the time. |
| `opus` | Deep reasoning, complex analysis, nuanced conversation. More expensive. |
| `sonnet` | Balanced capability and speed. Good for task agents that run frequently. |
| `haiku` | Fast and cheap. Good for simple lookup/routing agents. |

You can also use a full model ID string like `claude-sonnet-4-6`.

### color
Visual identifier in the UI. Choose based on domain semantics.

| Color | Semantic | Good for |
|-------|----------|----------|
| `blue` | Analysis, depth | Researchers, architects, analysts |
| `cyan` | Technical, precise | Code reviewers, debuggers |
| `green` | Creation, growth | Builders, generators, helpers |
| `yellow` | Caution, teaching | Validators, tutors, coaches |
| `red` | Critical, security | Security agents, risk assessors |
| `magenta` | Creative, expressive | Writers, designers, brainstormers |

### tools
Restricts which tools the agent can use. If omitted, agent has access to all tools.

**Format**: Comma-separated tool names.
```yaml
tools: Read, Grep, Glob
```

**Available tools**:
- `Read` — Read files
- `Write` — Create/overwrite files
- `Edit` — Modify existing files
- `Bash` — Run shell commands
- `Glob` — Find files by pattern
- `Grep` — Search file contents
- `WebFetch` — Fetch web pages
- `WebSearch` — Search the web
- `Agent(name)` — Spawn specific sub-agents
- `Skill(name)` — Invoke specific skills

**Common tool sets**:
- Read-only analysis: `Read, Grep, Glob`
- Code generation: `Read, Write, Edit, Grep, Glob`
- Full development: `Read, Write, Edit, Bash, Grep, Glob`
- Research: `Read, Grep, Glob, WebFetch, WebSearch`
- Conversational only: omit entirely or `Read, Grep, Glob`

### disallowedTools
Tools to explicitly deny. Applied before `tools` allowlist.
```yaml
disallowedTools: Write, Edit, Bash
```

### maxTurns
Maximum agentic turns before the agent stops.

- Omit for conversational agents (unlimited dialogue)
- 10-15 for simple tasks
- 20-30 for complex multi-step tasks
- 50+ for extensive operations

### permissionMode
How the agent handles permission prompts.

| Value | Behavior |
|-------|----------|
| `default` | Normal permission prompting |
| `acceptEdits` | Auto-approve file edits, prompt for Bash |
| `auto` | Auto-approve most actions |
| `dontAsk` | Skip disallowed tools silently |
| `bypassPermissions` | No permission prompts at all |
| `plan` | Read-only planning mode |

Default: omit (uses `default`). Only suggest `bypassPermissions` if the user explicitly asks for autonomous execution.

### skills
Skills to preload into the agent's context.
```yaml
skills: [api-conventions, error-handling-patterns]
```

The agent will have these skills available without needing to discover them.

### memory
Persistent memory scope. The agent remembers information across sessions.

| Value | Location | Shared |
|-------|----------|--------|
| `user` | `~/.claude/agent-memory/<name>/` | Across all projects |
| `project` | `.claude/agent-memory/<name>/` | Within this project |
| `local` | `.claude/agent-memory-local/<name>/` | This machine only |

Use `user` for conversational agents that should learn preferences over time.

### mcpServers
MCP servers scoped to this agent. Can reference existing servers by name or define inline.
```yaml
mcpServers:
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
  - github  # reference existing server by name
```

### hooks
Lifecycle hooks for validation or side effects.
```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate.sh"
```

### isolation
Set to `worktree` to give the agent an isolated git worktree copy of the repo.
```yaml
isolation: worktree
```

### initialPrompt
Auto-submitted first turn when the agent runs as a session agent via `--agent`.
```yaml
initialPrompt: "Analyze the current project and give me a status overview."
```

### background
Set to `true` to always run this agent as a background task.
```yaml
background: true
```

### effort
Override reasoning effort level.

| Value | When to use |
|-------|-------------|
| `low` | Simple routing or lookup |
| `medium` | Standard tasks |
| `high` | Complex reasoning |
| `max` | Deepest analysis possible |

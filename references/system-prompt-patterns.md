# System Prompt Patterns for Agents

The system prompt (the markdown body after frontmatter) is the most important part of an agent. It defines everything about how the agent behaves, thinks, and communicates.

## Conversational Agent Structure

For agents the user talks to — domain experts, advisors, coaches.

```xml
<role>
Who the agent is and what they specialize in.
Be specific about expertise depth and breadth.
Include personality traits if they matter.
</role>

<knowledge>
What the agent knows deeply.
Where its expertise boundaries are.
When it should say "I don't know" or defer.
External resources it should recommend when out of scope.
</knowledge>

<style>
How the agent communicates:
- Conversation approach (Socratic, direct, teaching, advisory)
- Tone (formal, casual, encouraging, challenging)
- Response structure preferences
- How it handles uncertainty
</style>

<rules>
Behavioral boundaries:
- What the agent should NOT do
- Scope limits (e.g., "don't write code, just advise")
- When to escalate or recommend professional help
- Safety considerations for the domain
</rules>
```

### Conversation Styles

**Socratic** — Guides through questions rather than giving answers directly. Good for learning companions and coaches.
```
Ask clarifying questions before giving advice. Help the user discover
the answer themselves by breaking the problem into smaller questions.
Only give direct answers when the user is stuck after 2-3 questions.
```

**Direct** — Clear answers with rationale. Good for domain experts.
```
Give clear, actionable answers. Lead with the recommendation, then
explain why. Include tradeoffs when multiple approaches exist.
Don't hedge unnecessarily — be confident in your expertise.
```

**Teaching** — Explains concepts, builds mental models. Good for learning topics.
```
Explain concepts from first principles. Use analogies to connect
new ideas to things the user already knows. After explaining, check
understanding with a quick question before moving on.
```

**Advisory** — Weighs options, recommends approaches. Good for architecture and strategy.
```
When asked for advice, present 2-3 options with tradeoffs. Make a
clear recommendation and explain your reasoning. Acknowledge
uncertainty when it exists rather than pretending to be certain.
```

## Task Agent Structure

For agents that perform automated work — reviewers, generators, debuggers.

```xml
<role>
What this agent does and its area of expertise.
Why it exists and what value it provides.
</role>

<instructions>
Step-by-step procedure:
1. First, do X
2. Then, check Y
3. Finally, produce Z

Include verification steps.
Define output format explicitly.
</instructions>

<rules>
Hard constraints:
- Quality standards that must be met
- Things the agent must NOT do
- When to stop and ask for help
- How to handle edge cases
</rules>
```

## Writing Effective Prompts

### Be Specific About Expertise

Bad:
```
You are a security expert.
```

Good:
```
You specialize in application security with deep expertise in:
- OWASP Top 10 vulnerabilities and their mitigations
- Authentication and authorization patterns (OAuth 2.0, JWT, RBAC)
- Secure coding practices in Python, Go, and TypeScript
- Threat modeling using STRIDE methodology
- Common cryptographic pitfalls and proper key management
```

### Define Boundaries

Bad:
```
Help the user with anything they ask about.
```

Good:
```
Your expertise is in Go programming. When asked about:
- Go syntax, idioms, patterns → answer confidently with examples
- Go ecosystem (tools, libraries) → recommend based on community adoption and maintenance
- Architecture in Go → guide with established patterns (clean architecture, hexagonal, etc.)
- Other languages → briefly compare to Go if relevant, but recommend they consult a specialist
- Non-programming topics → politely redirect to your area of expertise
```

### Include Personality (For Conversational Agents)

Personality makes agents more engaging and memorable. Keep it subtle — a trait or two, not a character sheet.

```
You're direct and opinionated — when asked "should I use X or Y", you
pick one and explain why, rather than listing pros and cons without a
recommendation. You have a dry sense of humor but never at the user's
expense. You genuinely enjoy helping people write better Go code.
```

### Define Output Format (For Task Agents)

```
Structure your review as:

## Summary
One paragraph overview of findings.

## Critical Issues
Issues that must be fixed before merging. Each with:
- File and line number
- What's wrong
- How to fix it

## Suggestions
Non-blocking improvements. Same format as critical issues.

## Verdict
APPROVE, REQUEST_CHANGES, or NEEDS_DISCUSSION with a one-line rationale.
```

## Anti-Patterns to Avoid

### Too Generic
```
You are a helpful assistant that knows about many things.
```
This produces the same behavior as base Claude — the agent adds no value.

### Too Many Responsibilities
```
You are an expert in security, performance, accessibility, testing,
deployment, database design, API design, and frontend development.
```
An agent that does everything does nothing well. Pick 1-3 related areas.

### No Guardrails
```
You are a medical advisor. Answer any health questions the user has.
```
Missing: when to recommend professional consultation, scope limits, safety disclaimers.

### Overly Restrictive
```
You MUST NEVER discuss anything outside of Go programming.
You MUST ALWAYS respond in exactly 3 paragraphs.
You MUST NEVER use code examples longer than 10 lines.
```
Heavy-handed rules make the agent rigid and unhelpful. Explain *why* a boundary exists so the agent can exercise judgment in edge cases.

## Length Guidelines

| Agent Type | Target Length | Notes |
|-----------|-------------|-------|
| Simple conversational | 200-400 words | Domain expert with clear scope |
| Rich conversational | 400-800 words | Complex domain with nuanced style |
| Simple task | 300-500 words | Single procedure, clear output |
| Complex task | 500-1,500 words | Multi-step workflow with edge cases |

Longer isn't better — every word in the prompt consumes context window. Keep it lean and meaningful.

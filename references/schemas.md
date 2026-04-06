# JSON Schemas

Reference schemas for the agent-creator testing and evaluation system.

## Test Scenario Schema

Defines a multi-turn conversation test for an agent.

```json
{
  "name": "string — descriptive scenario name (kebab-case)",
  "agent": "string — agent name or path to .md file",
  "archetype": "conversational | task",
  "turns": [
    {
      "user": "string — the user message for this turn",
      "context": "string — optional context injected for multi-turn (auto-generated)",
      "assertions": [
        {
          "type": "contains | not_contains | regex | behavioral | tool_usage | tone",
          "value": "string — what to check for",
          "description": "string — human-readable description of what this tests"
        }
      ]
    }
  ],
  "global_assertions": [
    {
      "type": "persona_consistency | knowledge_boundary | conversation_style | tool_restriction | turn_count",
      "value": "string — what to check for",
      "description": "string — human-readable description"
    }
  ]
}
```

### Assertion Types

#### Per-Turn Assertions

| Type | Value Format | How It's Checked |
|------|-------------|-----------------|
| `contains` | substring to find | Case-insensitive text search in response |
| `not_contains` | substring that should be absent | Fails if found in response |
| `regex` | regex pattern | Applied to response text |
| `behavioral` | description of expected behavior | Judged by behavior-grader agent |
| `tool_usage` | "should use X" or "should NOT use X" | Checked against tool calls in transcript |
| `tone` | style description (e.g., "Socratic", "direct") | Judged by behavior-grader agent |

#### Global Assertions

| Type | Value Format | How It's Checked |
|------|-------------|-----------------|
| `persona_consistency` | description of expected persona | Evaluated across all turns by grader |
| `knowledge_boundary` | description of boundary behavior | Checked when out-of-scope questions appear |
| `conversation_style` | style description | Evaluated for consistency across turns |
| `tool_restriction` | "only Read, Grep, Glob" or similar | Checked against all tool calls |
| `turn_count` | "< 10" or "within 15" | Checked against total agent turns |

---

## Grading Result Schema

Output from the behavior-grader agent.

```json
{
  "scenario_name": "string",
  "turn_results": [
    {
      "turn": 1,
      "user_message": "string",
      "agent_response_summary": "string — brief summary of agent's response",
      "assertions": [
        {
          "text": "string — the assertion description",
          "type": "string — assertion type",
          "passed": true,
          "evidence": "string — specific evidence supporting verdict"
        }
      ]
    }
  ],
  "global_results": [
    {
      "text": "string — assertion description",
      "type": "string — assertion type",
      "passed": true,
      "evidence": "string — evidence from across the conversation"
    }
  ],
  "summary": {
    "passed": 5,
    "failed": 1,
    "total": 6,
    "pass_rate": 0.83
  },
  "behavioral_notes": "string — free-form observations about agent behavior",
  "scenario_feedback": {
    "suggestions": [
      {
        "assertion": "string — optional, which assertion this relates to",
        "reason": "string — why the assertion could be improved"
      }
    ],
    "overall": "string — brief assessment of scenario quality"
  }
}
```

---

## Comparison Result Schema

Output from the agent-comparator.

```json
{
  "winner": "A | B | TIE",
  "reasoning": "string — explanation of why the winner was chosen",
  "rubric": {
    "A": {
      "behavioral": {
        "persona_consistency": 5,
        "knowledge_depth": 4,
        "boundary_respect": 5
      },
      "conversation": {
        "relevance": 5,
        "helpfulness": 4,
        "style_adherence": 4
      },
      "task": {
        "accuracy": 5,
        "completeness": 4,
        "tool_usage": 5
      },
      "behavioral_score": 4.7,
      "conversation_score": 4.3,
      "task_score": 4.7,
      "overall_score": 9.0
    },
    "B": {
      "behavioral": {},
      "conversation": {},
      "task": {},
      "behavioral_score": 0.0,
      "conversation_score": 0.0,
      "task_score": 0.0,
      "overall_score": 0.0
    }
  },
  "output_quality": {
    "A": {
      "score": 9,
      "strengths": ["string"],
      "weaknesses": ["string"]
    },
    "B": {
      "score": 7,
      "strengths": ["string"],
      "weaknesses": ["string"]
    }
  }
}
```

Note: The `task` dimension in the rubric is only included for task-archetype agents. For conversational agents, omit it and weight behavioral + conversation equally.

---

## Analysis Result Schema

Output from the agent-analyzer.

```json
{
  "comparison_summary": {
    "winner": "A | B",
    "winner_agent": "string — path to winning agent file",
    "loser_agent": "string — path to losing agent file",
    "comparator_reasoning": "string — summary from comparator"
  },
  "winner_strengths": ["string — specific strength with evidence"],
  "loser_weaknesses": ["string — specific weakness with evidence"],
  "prompt_following": {
    "winner": {
      "score": 9,
      "issues": ["string"]
    },
    "loser": {
      "score": 5,
      "issues": ["string"]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high | medium | low",
      "category": "system_prompt | frontmatter | persona | boundaries | examples | structure",
      "suggestion": "string — specific, actionable change",
      "expected_impact": "string — predicted effect on agent behavior"
    }
  ],
  "transcript_insights": {
    "winner_pattern": "string — summary of winner's execution pattern",
    "loser_pattern": "string — summary of loser's execution pattern"
  }
}
```

---

## Timing Data Schema

Saved when test runs complete.

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

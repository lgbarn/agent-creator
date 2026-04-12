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

---

## Benchmark Schema

Output from `aggregate_benchmark.py`. Aggregates results across multiple runs with statistical summaries.

```json
{
  "metadata": {
    "agent_name": "go-expert",
    "agent_path": "/path/to/go-expert.md",
    "timestamp": "2026-04-11T10:30:00Z",
    "scenarios": ["basic-go-knowledge", "boundary-test"],
    "configurations": ["train", "test"]
  },
  "runs": [
    {
      "scenario_name": "basic-go-knowledge",
      "configuration": "train",
      "run_number": 1,
      "result": {
        "pass_rate": 0.85,
        "passed": 6,
        "failed": 1,
        "total": 7,
        "time_seconds": 42.5,
        "tokens": 3800,
        "tool_calls": 5
      }
    }
  ],
  "run_summary": {
    "train": {
      "pass_rate": {"mean": 0.85, "stddev": 0.05, "min": 0.80, "max": 0.90},
      "time_seconds": {"mean": 45.0, "stddev": 12.0, "min": 33.0, "max": 57.0},
      "tokens": {"mean": 3800, "stddev": 400, "min": 3400, "max": 4200},
      "tool_calls": {"mean": 5.0, "stddev": 1.0, "min": 4, "max": 6},
      "run_count": 3
    },
    "test": {
      "pass_rate": {"mean": 0.75, "stddev": 0.10, "min": 0.65, "max": 0.85},
      "time_seconds": {"mean": 38.0, "stddev": 8.0, "min": 30.0, "max": 46.0},
      "tokens": {"mean": 3200, "stddev": 300, "min": 2900, "max": 3500},
      "tool_calls": {"mean": 4.0, "stddev": 0.5, "min": 3, "max": 5},
      "run_count": 3
    },
    "delta": {
      "pass_rate": "+0.10",
      "time_seconds": "+7.0",
      "tokens": "+600"
    }
  },
  "notes": [
    "Assertion 'contains error' passes 100% in both configs - may not discriminate",
    "Scenario 2 shows high variance (65%-85%) - may be flaky"
  ]
}
```

---

## Feedback Schema

Output from the eval-viewer when user submits feedback. Used by `improve_prompt.py` to incorporate human judgment into prompt improvement.

```json
{
  "reviews": [
    {
      "run_id": "train-basic-go-knowledge",
      "feedback": "The agent was too verbose — responses averaged 400 words when 150 would suffice for a domain expert",
      "timestamp": "2026-04-11T12:30:00Z"
    },
    {
      "run_id": "train-boundary-test",
      "feedback": "",
      "timestamp": "2026-04-11T12:31:00Z"
    }
  ],
  "status": "complete"
}
```

- **reviews**: Array of per-scenario feedback entries
  - **run_id**: Identifier matching the eval viewer's run ID
  - **feedback**: Free-form text from the reviewer. Empty string = no issues.
  - **timestamp**: When the feedback was submitted
- **status**: "complete" when all reviews are submitted

**Usage**: Empty feedback means "looks good." Only non-empty feedback is passed to `improve_prompt.py`. Human feedback takes priority over automated assertion results.

---

## Claims Schema

Extracted by the behavior-grader as part of grading results. Each claim is an implicit statement from the agent's response that may or may not be correct.

```json
{
  "claim": "errors.Is was introduced in Go 1.13",
  "type": "factual | process | quality",
  "verified": true,
  "evidence": "Correct — errors.Is/As and fmt.Errorf %w wrapping were added in Go 1.13"
}
```

- **claim**: The statement being verified
- **type**: Classification of the claim
  - `factual`: A specific technical statement that can be checked
  - `process`: A claim about what the agent did or will do
  - `quality`: A self-assessment or implied quality claim
- **verified**: Whether the claim holds up to scrutiny
- **evidence**: Supporting or contradicting evidence

---

## Trigger Eval Set Schema

Input for `run_trigger_eval.py` and the description optimization loop. Defines queries that should or should not trigger delegation to the agent.

```json
[
  {
    "query": "can you review this auth flow for security issues?",
    "should_trigger": true
  },
  {
    "query": "write a fibonacci function in Python",
    "should_trigger": false
  }
]
```

Aim for 8-10 should-trigger and 8-10 should-not-trigger queries. Use the `assets/eval_review.html` template to review and edit queries in a browser before running the optimization loop.

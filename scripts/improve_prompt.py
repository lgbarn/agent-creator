#!/usr/bin/env python3
"""Improve an agent's system prompt based on behavioral test results.

Uses Claude with extended thinking to analyze test failures and propose
improvements to the agent's system prompt, frontmatter, or both.

Usage:
    python scripts/improve_prompt.py --agent <path> --grading <path> --model <model>
"""

import argparse
import json
import re
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import parse_agent_md, extract_xml_sections


def improve_prompt(
    client: anthropic.Anthropic,
    agent_name: str,
    agent_content: str,
    grading_results: dict | list,
    history: list[dict],
    model: str,
    mode: str = "behavior",
    log_dir: Path | None = None,
    iteration: int | None = None,
) -> dict:
    """Call Claude to improve the agent based on test results.

    Args:
        mode: "behavior" to improve system prompt, "description" to improve description

    Returns dict with:
        system_prompt: Improved system prompt text (if mode=behavior)
        description: Improved description text (if mode=description)
        reasoning: Why these changes were made
    """
    # Handle both single grading result and list of results
    if isinstance(grading_results, list):
        all_failures = []
        all_notes = []
        for gr in grading_results:
            failures = _extract_failures(gr)
            all_failures.extend(failures)
            if gr.get("behavioral_notes"):
                all_notes.append(gr["behavioral_notes"])
    else:
        all_failures = _extract_failures(grading_results)
        all_notes = [grading_results.get("behavioral_notes", "")]

    if mode == "behavior":
        return _improve_system_prompt(
            client, agent_name, agent_content, all_failures, all_notes,
            history, model, log_dir, iteration,
        )
    else:
        return _improve_description(
            client, agent_name, agent_content, all_failures, all_notes,
            history, model, log_dir, iteration,
        )


def _extract_failures(grading: dict) -> list[dict]:
    """Extract failed assertions from grading results."""
    failures = []

    for tr in grading.get("turn_results", []):
        for a in tr.get("assertions", []):
            if a.get("passed") is False:
                failures.append({
                    "turn": tr.get("turn"),
                    "user_message": tr.get("user_message", ""),
                    "assertion": a.get("text", ""),
                    "type": a.get("type", ""),
                    "evidence": a.get("evidence", ""),
                })

    for a in grading.get("global_results", []):
        if a.get("passed") is False:
            failures.append({
                "turn": "global",
                "user_message": "",
                "assertion": a.get("text", ""),
                "type": a.get("type", ""),
                "evidence": a.get("evidence", ""),
            })

    return failures


def _improve_system_prompt(
    client, agent_name, agent_content, failures, notes,
    history, model, log_dir, iteration,
) -> dict:
    """Improve the agent's system prompt based on behavioral failures."""

    prompt = f"""You are improving a Claude Code agent called "{agent_name}". Agents are markdown files with YAML frontmatter that define a specialized Claude persona — the system prompt in the body of the file determines how the agent behaves in conversation.

Here is the current agent file:
<agent_file>
{agent_content}
</agent_file>

The agent was tested against behavioral scenarios and some assertions failed:

<failures>
"""
    for f in failures:
        turn_info = f"Turn {f['turn']}" if f['turn'] != 'global' else "Global"
        prompt += f"[{turn_info}] {f['type']}: {f['assertion']}\n"
        if f['user_message']:
            prompt += f"  User said: {f['user_message']}\n"
        prompt += f"  Evidence: {f['evidence']}\n\n"

    prompt += "</failures>\n\n"

    if notes:
        prompt += "<behavioral_notes>\n"
        for note in notes:
            if note:
                prompt += f"{note}\n\n"
        prompt += "</behavioral_notes>\n\n"

    if history:
        prompt += "Previous improvement attempts (try something different):\n"
        for h in history:
            prompt += f"<attempt iteration={h.get('iteration', '?')} pass_rate={h.get('pass_rate', '?')}>\n"
            if h.get("changes_summary"):
                prompt += f"Changes: {h['changes_summary']}\n"
            prompt += "</attempt>\n\n"

    prompt += """Based on the failures, improve the agent's system prompt. Focus on:

1. **Specificity over vagueness**: If the agent gave generic responses, make the persona more specific
2. **Boundaries**: If scope was violated, add clearer knowledge boundaries
3. **Style consistency**: If tone was inconsistent, define the communication style more explicitly
4. **Guardrails**: If rules were broken, make constraints clearer with reasoning
5. **Explain the why**: Don't just add MUSTs — explain why each behavior matters so the model can generalize

Keep changes targeted. Don't rewrite the entire prompt if only one aspect failed.
Preserve the XML tag structure (<role>, <knowledge>, <style>, <instructions>, <rules>).
Keep the frontmatter unchanged unless a configuration change is needed (e.g., tool access).

Respond with the improved agent file content (frontmatter + body) in <improved_agent> tags.
Also explain your changes briefly in <reasoning> tags."""

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 10000,
        },
        messages=[{"role": "user", "content": prompt}],
    )

    thinking_text = ""
    text = ""
    for block in response.content:
        if block.type == "thinking":
            thinking_text = block.thinking
        elif block.type == "text":
            text = block.text

    # Parse improved agent
    agent_match = re.search(r"<improved_agent>(.*?)</improved_agent>", text, re.DOTALL)
    improved = agent_match.group(1).strip() if agent_match else ""

    reasoning_match = re.search(r"<reasoning>(.*?)</reasoning>", text, re.DOTALL)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    # Log
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps({
            "iteration": iteration,
            "prompt": prompt,
            "thinking": thinking_text,
            "response": text,
            "reasoning": reasoning,
        }, indent=2))

    return {
        "improved_content": improved,
        "reasoning": reasoning,
    }


def _improve_description(
    client, agent_name, agent_content, failures, notes,
    history, model, log_dir, iteration,
) -> dict:
    """Improve the agent's description for better triggering."""

    prompt = f"""You are optimizing the description field for a Claude Code agent called "{agent_name}". The description appears in Claude's list of available agents and determines when Claude delegates tasks to this agent.

Here is the current agent file:
<agent_file>
{agent_content}
</agent_file>

The agent's triggering was tested and some cases failed. Improve the description so it triggers correctly.

Tips:
- Use imperative phrasing: "Use this agent when..." rather than "This agent does..."
- Focus on user intent and scenarios, not implementation details
- Be distinctive — the description competes with other agents for Claude's attention
- Include <example> blocks for nuanced triggering scenarios
- Keep under 5000 characters total
- Don't overfit to specific test queries — generalize to categories of intent

Respond with the improved description in <new_description> tags."""

    response = client.messages.create(
        model=model,
        max_tokens=8000,
        thinking={
            "type": "enabled",
            "budget_tokens": 8000,
        },
        messages=[{"role": "user", "content": prompt}],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    description = match.group(1).strip() if match else text.strip()

    return {
        "description": description,
        "reasoning": "Description optimization",
    }


def main():
    parser = argparse.ArgumentParser(description="Improve agent prompt based on test results")
    parser.add_argument("--agent", required=True, help="Path to agent .md file")
    parser.add_argument("--grading", required=True, help="Path to grading results JSON")
    parser.add_argument("--mode", default="behavior", choices=["behavior", "description"],
                       help="What to improve: system prompt or description")
    parser.add_argument("--model", required=True, help="Model for improvement")
    parser.add_argument("--history", default=None, help="Path to history JSON")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    agent_data = parse_agent_md(Path(args.agent))
    grading = json.loads(Path(args.grading).read_text())
    history = json.loads(Path(args.history).read_text()) if args.history else []

    client = anthropic.Anthropic()
    result = improve_prompt(
        client=client,
        agent_name=agent_data["name"],
        agent_content=agent_data["raw"],
        grading_results=grading,
        history=history,
        model=args.model,
        mode=args.mode,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

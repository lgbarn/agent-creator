#!/usr/bin/env python3
"""Validate an agent .md file for correctness.

Checks frontmatter fields, system prompt structure, and provides
warnings for potential issues.

Usage:
    python scripts/validate_agent.py <path-to-agent.md>
"""

import re
import sys
from pathlib import Path

# Add parent to path so we can import utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import parse_agent_md, extract_xml_sections, word_count


# Valid values for enum fields
VALID_MODELS = {"inherit", "opus", "sonnet", "haiku"}
VALID_COLORS = {"blue", "cyan", "green", "yellow", "red", "magenta"}
VALID_PERMISSION_MODES = {"default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan"}
VALID_MEMORY = {"user", "project", "local"}
VALID_EFFORT = {"low", "medium", "high", "max"}

# Known tool names (core tools available in Claude Code)
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    "WebFetch", "WebSearch", "Agent", "Skill",
    "NotebookEdit", "NotebookRead",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
    "SendMessage", "AskUserQuestion",
}

# All recognized frontmatter keys
KNOWN_KEYS = {
    "name", "description", "model", "color", "tools", "disallowedTools",
    "maxTurns", "permissionMode", "memory", "skills", "mcpServers",
    "hooks", "isolation", "initialPrompt", "background", "effort",
}


def validate_agent(agent_path: str) -> tuple[bool, str, list[str]]:
    """Validate an agent .md file.

    Returns:
        (is_valid, message, warnings) where warnings is a list of
        non-fatal issues.
    """
    path = Path(agent_path)
    warnings: list[str] = []

    # File existence
    if not path.exists():
        return False, f"File not found: {path}", warnings
    if not path.suffix == ".md":
        return False, f"Agent file must be .md, got: {path.suffix}", warnings

    # Parse the file
    try:
        data = parse_agent_md(path)
    except ValueError as e:
        return False, str(e), warnings

    fm = data["frontmatter"]
    body = data["body"]

    # Required fields
    if not fm.get("name"):
        return False, "Missing required field: 'name'", warnings
    if not fm.get("description"):
        return False, "Missing required field: 'description'", warnings

    name = str(fm["name"]).strip()
    description = str(fm["description"]).strip()

    # Name validation: kebab-case, 3-50 chars
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name) and len(name) > 2:
        return False, f"Name '{name}' must be kebab-case (lowercase letters, digits, hyphens)"
    if '--' in name:
        return False, f"Name '{name}' cannot contain consecutive hyphens"
    if len(name) < 3:
        return False, f"Name '{name}' is too short (minimum 3 characters)"
    if len(name) > 50:
        return False, f"Name '{name}' is too long ({len(name)} chars, maximum 50)"

    # Description validation
    if len(description) < 10:
        return False, f"Description is too short ({len(description)} chars, minimum 10)"
    if len(description) > 5000:
        return False, f"Description is too long ({len(description)} chars, maximum 5000)"

    # Model validation
    model = fm.get("model")
    if model is not None:
        model_str = str(model)
        if model_str not in VALID_MODELS and not model_str.startswith("claude-"):
            return False, f"Invalid model: '{model_str}'. Must be one of {VALID_MODELS} or a claude-* model ID"

    # Color validation
    color = fm.get("color")
    if color is not None and str(color) not in VALID_COLORS:
        return False, f"Invalid color: '{color}'. Must be one of {VALID_COLORS}"

    # Tools validation
    for field in ("tools", "disallowedTools"):
        tools_val = fm.get(field)
        if tools_val is not None:
            if isinstance(tools_val, str):
                tool_list = [t.strip() for t in tools_val.split(",")]
            elif isinstance(tools_val, list):
                tool_list = [str(t).strip() for t in tools_val]
            else:
                return False, f"'{field}' must be a string or list"

            for tool in tool_list:
                if not tool:
                    continue
                # Allow Agent(*) and Skill(*) patterns and MCP tool patterns
                if re.match(r'^(Agent|Skill)\(.*\)$', tool):
                    continue
                if tool.startswith("mcp__"):
                    continue
                if tool not in KNOWN_TOOLS:
                    warnings.append(f"Unknown tool in '{field}': '{tool}' — verify this is a valid tool name")

    # maxTurns validation
    max_turns = fm.get("maxTurns")
    if max_turns is not None:
        if not isinstance(max_turns, int) or max_turns < 1:
            return False, f"maxTurns must be a positive integer, got: {max_turns}"
        if max_turns > 100:
            warnings.append(f"maxTurns is {max_turns} — this is unusually high, verify this is intentional")

    # permissionMode validation
    perm = fm.get("permissionMode")
    if perm is not None and str(perm) not in VALID_PERMISSION_MODES:
        return False, f"Invalid permissionMode: '{perm}'. Must be one of {VALID_PERMISSION_MODES}"

    # Memory validation
    mem = fm.get("memory")
    if mem is not None and str(mem) not in VALID_MEMORY:
        return False, f"Invalid memory: '{mem}'. Must be one of {VALID_MEMORY}"

    # Effort validation
    effort = fm.get("effort")
    if effort is not None and str(effort) not in VALID_EFFORT:
        return False, f"Invalid effort: '{effort}'. Must be one of {VALID_EFFORT}"

    # Isolation validation
    isolation = fm.get("isolation")
    if isolation is not None and str(isolation) != "worktree":
        return False, f"Invalid isolation: '{isolation}'. Must be 'worktree'"

    # Background validation
    bg = fm.get("background")
    if bg is not None and not isinstance(bg, bool):
        return False, f"background must be a boolean, got: {type(bg).__name__}"

    # Unexpected keys
    unexpected = set(fm.keys()) - KNOWN_KEYS
    if unexpected:
        warnings.append(f"Unexpected frontmatter keys: {', '.join(sorted(unexpected))}")

    # Description <example> block validation
    if "<example>" in description:
        example_count = description.count("<example>")
        close_count = description.count("</example>")
        if example_count != close_count:
            warnings.append(f"Mismatched <example> tags: {example_count} opening, {close_count} closing")
        if "user:" not in description.lower() or "assistant:" not in description.lower():
            warnings.append("Description <example> blocks should contain 'user:' and 'assistant:' entries")

    # System prompt structure checks
    sections = extract_xml_sections(body)
    is_task = max_turns is not None  # Task agents typically have maxTurns set

    if "role" not in sections:
        warnings.append("System prompt missing <role> section — recommended for all agents")

    if is_task:
        if "instructions" not in sections:
            warnings.append("Task agent (maxTurns set) missing <instructions> section")
    else:
        if "knowledge" not in sections and "style" not in sections:
            warnings.append("Conversational agent missing <knowledge> and/or <style> sections")

    # Prompt length checks
    wc = word_count(body)
    if is_task:
        if wc < 100:
            warnings.append(f"System prompt is very short ({wc} words) — task agents typically need 300-1500 words")
        elif wc > 2000:
            warnings.append(f"System prompt is very long ({wc} words) — consider moving reference material to separate files")
    else:
        if wc < 50:
            warnings.append(f"System prompt is very short ({wc} words) — conversational agents typically need 200-800 words")
        elif wc > 1200:
            warnings.append(f"System prompt is very long ({wc} words) — consider trimming or using references/")

    return True, "Agent is valid!", warnings


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_agent.py <path-to-agent.md>")
        sys.exit(1)

    agent_path = sys.argv[1]
    valid, message, warnings = validate_agent(agent_path)

    if valid:
        print(f"PASS: {message}")
    else:
        print(f"FAIL: {message}")

    for w in warnings:
        print(f"  WARNING: {w}")

    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()

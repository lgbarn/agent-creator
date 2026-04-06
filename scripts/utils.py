"""Shared utilities for agent-creator scripts."""

import re
from pathlib import Path
from typing import Any


def parse_agent_md(agent_path: Path) -> dict[str, Any]:
    """Parse an agent .md file, returning structured data.

    Returns dict with keys:
        name: Agent name from frontmatter
        description: Agent description from frontmatter
        frontmatter: Full parsed frontmatter dict
        body: System prompt text (everything after frontmatter)
        raw: Complete file content
    """
    path = Path(agent_path)
    content = path.read_text()
    lines = content.split("\n")

    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path.name} missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError(f"{path.name} missing frontmatter (no closing ---)")

    frontmatter = _parse_yaml_frontmatter(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()

    return {
        "name": frontmatter.get("name", ""),
        "description": frontmatter.get("description", ""),
        "frontmatter": frontmatter,
        "body": body,
        "raw": content,
    }


def _parse_yaml_frontmatter(lines: list[str]) -> dict[str, Any]:
    """Parse YAML frontmatter lines into a dict.

    Handles simple key: value pairs and YAML multiline indicators (>, |, >-, |-).
    For complex nested YAML, falls back to yaml.safe_load if available.
    """
    try:
        import yaml
        text = "\n".join(lines)
        result = yaml.safe_load(text)
        if isinstance(result, dict):
            return result
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: manual parsing for simple cases
    frontmatter: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        match = re.match(r'^(\w[\w-]*)\s*:\s*(.*)', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()

            if value in (">", "|", ">-", "|-"):
                continuation: list[str] = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i].startswith("\t")):
                    continuation.append(lines[i].strip())
                    i += 1
                frontmatter[key] = " ".join(continuation)
                continue
            elif value.startswith('"') and value.endswith('"'):
                frontmatter[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                frontmatter[key] = value[1:-1]
            elif value.lower() == "true":
                frontmatter[key] = True
            elif value.lower() == "false":
                frontmatter[key] = False
            elif value.isdigit():
                frontmatter[key] = int(value)
            else:
                frontmatter[key] = value

        i += 1

    return frontmatter


def find_agent_file(name: str) -> Path | None:
    """Search standard agent locations for an agent by name.

    Checks (in order):
        1. ~/.claude/agents/{name}.md
        2. .claude/agents/{name}.md (project-level)

    Returns the first match, or None.
    """
    candidates = [
        Path.home() / ".claude" / "agents" / f"{name}.md",
        Path.cwd() / ".claude" / "agents" / f"{name}.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def extract_xml_sections(body: str) -> dict[str, str]:
    """Extract XML-tagged sections from an agent's system prompt body.

    Looks for <role>, <knowledge>, <style>, <instructions>, <rules> tags
    and returns their content as a dict.
    """
    sections: dict[str, str] = {}
    tag_names = ["role", "knowledge", "style", "instructions", "rules"]

    for tag in tag_names:
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, body, re.DOTALL)
        if match:
            sections[tag] = match.group(1).strip()

    return sections


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())

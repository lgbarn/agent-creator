#!/usr/bin/env python3
"""Package an agent .md file into a distributable .agent archive.

Creates a zip file containing the agent definition and any referenced
hook scripts, with a manifest for metadata.

Usage:
    python scripts/package_agent.py <agent.md> [output-dir]
"""

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import parse_agent_md
from scripts.validate_agent import validate_agent


def package_agent(agent_path: str, output_dir: str | None = None) -> str:
    """Package an agent into a .agent zip file.

    Returns the path to the created .agent file.
    """
    path = Path(agent_path)
    if not path.exists():
        raise FileNotFoundError(f"Agent file not found: {path}")

    # Validate first
    valid, message, warnings = validate_agent(agent_path)
    if not valid:
        raise ValueError(f"Agent validation failed: {message}")

    for w in warnings:
        print(f"  WARNING: {w}", file=sys.stderr)

    # Parse agent data
    data = parse_agent_md(path)
    name = data["name"]

    # Determine output path
    out_dir = Path(output_dir) if output_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / f"{name}.agent"

    # Build manifest
    manifest = {
        "name": name,
        "description": data["description"],
        "version": "1.0.0",
        "frontmatter": {k: v for k, v in data["frontmatter"].items()
                       if k not in ("name", "description")},
        "dependencies": {
            "skills": data["frontmatter"].get("skills", []),
            "mcp_servers": [s.get("name", str(s)) for s in data["frontmatter"].get("mcpServers", [])
                          if isinstance(s, dict)] if data["frontmatter"].get("mcpServers") else [],
        },
    }

    # Create zip
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add the agent file
        zf.write(path, f"{name}.md")

        # Add manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Look for hook scripts referenced in frontmatter
        hooks = data["frontmatter"].get("hooks", {})
        if isinstance(hooks, dict):
            for event_hooks in hooks.values():
                if isinstance(event_hooks, list):
                    for hook in event_hooks:
                        if isinstance(hook, dict) and "command" in hook:
                            cmd = hook["command"]
                            # Check if it references a local script
                            script_path = path.parent / cmd
                            if script_path.exists() and script_path.is_file():
                                zf.write(script_path, f"hooks/{script_path.name}")

    print(f"Packaged: {archive_path}")
    print(f"  Name: {name}")
    print(f"  Size: {archive_path.stat().st_size} bytes")

    return str(archive_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python package_agent.py <agent.md> [output-dir]")
        sys.exit(1)

    agent_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = package_agent(agent_path, output_dir)
        print(f"\nAgent packaged successfully: {result}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

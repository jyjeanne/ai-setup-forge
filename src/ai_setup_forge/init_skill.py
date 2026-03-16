"""Scaffold new SKILL.md templates."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ai_setup_forge.constants import SKILL_FILE_NAME
from ai_setup_forge.validator import validate_name

console = Console()

# Agent-specific frontmatter additions
_AGENT_EXTRAS: dict[str, str] = {
    "claude-code": """\
# allowed-tools: Bash(git:*) Read
# context: fork
# agent: general-purpose
# disable-model-invocation: false
# user-invocable: true""",
    "mistral-vibe": """\
# license: MIT
# compatibility: Python 3.10+
# allowed-tools: read_file grep
# user-invocable: true""",
    "github-copilot": """\
# license: MIT""",
}


def create_skill_template(
    name: str | None = None,
    agent: str | None = None,
    base_dir: Path | None = None,
) -> Path | None:
    """Create a SKILL.md template.

    Args:
        name: Skill name. If None, uses the current directory's basename.
        agent: Optional agent name for agent-specific frontmatter.
        base_dir: Base directory to create in. Defaults to cwd.

    Returns:
        Path to created SKILL.md, or None on error.
    """
    cwd = base_dir or Path.cwd()

    if name:
        # Validate name against spec
        errors = validate_name(name)
        if errors:
            for err in errors:
                console.print(f"[red]Error:[/] {err}")
            return None
        skill_dir = cwd / name
        skill_file = skill_dir / SKILL_FILE_NAME
    else:
        # Use current directory
        name = cwd.name.lower().replace(" ", "-")
        skill_dir = cwd
        skill_file = cwd / SKILL_FILE_NAME

    # Check if already exists
    if skill_file.exists():
        console.print(f"[yellow]Skill already exists at[/] {skill_file}")
        return None

    # Build frontmatter
    fm_lines = [
        "---",
        f"name: {name}",
        "description: A brief description of what this skill does and when to use it.",
    ]

    # Add agent-specific fields (commented out)
    if agent and agent in _AGENT_EXTRAS:
        fm_lines.append(_AGENT_EXTRAS[agent])

    fm_lines.append("---")

    # Build body
    body = f"""
# {name}

Instructions for the agent to follow when this skill is activated.

## When to use

Describe the scenarios where this skill should be used.
Include specific keywords to help agents identify relevant tasks.

## Instructions

1. First step
2. Second step
3. Additional steps as needed

<!-- Keep this file under 500 lines. Move detailed reference material to references/ -->
"""

    content = "\n".join(fm_lines) + "\n" + body

    # Create directory and file
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        console.print(f"[red]Error creating skill:[/] {exc}")
        return None

    console.print(f"[green]Created skill:[/] {name}")
    console.print(f"  {skill_file}")
    console.print()
    console.print("[dim]Next steps:[/]")
    console.print(f"  1. Edit [cyan]{skill_file}[/] to define your skill instructions")
    console.print("  2. Update the [cyan]name[/] and [cyan]description[/] in the frontmatter")
    console.print(f"  3. Validate with: [cyan]ai-setup-forge validate {skill_dir}[/]")

    return skill_file

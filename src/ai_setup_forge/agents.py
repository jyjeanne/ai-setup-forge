"""Agent configurations and detection for Claude Code, Mistral Vibe, and Copilot CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ai_setup_forge.constants import get_home
from ai_setup_forge.types import AgentConfig


def _claude_home() -> Path:
    """Return Claude Code config directory, respecting CLAUDE_CONFIG_DIR."""
    env = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if env:
        return Path(env)
    return get_home() / ".claude"


def _detect_claude_code() -> bool:
    return _claude_home().exists()


def _detect_mistral_vibe() -> bool:
    return (get_home() / ".vibe").exists()


def _detect_copilot_cli() -> bool:
    home = get_home()
    if (home / ".copilot").exists():
        return True
    if Path(".github").exists():
        return True
    # Check if gh copilot is available
    try:
        result = subprocess.run(
            ["gh", "copilot", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


AGENTS: dict[str, AgentConfig] = {
    "claude-code": AgentConfig(
        name="claude-code",
        display_name="Claude Code",
        skills_dir=".claude/skills",
        global_skills_dir=_claude_home() / "skills",
        detect_installed=_detect_claude_code,
        agents_dir=".claude/agents",
        global_agents_dir=_claude_home() / "agents",
    ),
    "mistral-vibe": AgentConfig(
        name="mistral-vibe",
        display_name="Mistral Vibe",
        skills_dir=".vibe/skills",
        global_skills_dir=get_home() / ".vibe" / "skills",
        detect_installed=_detect_mistral_vibe,
        agents_dir=".vibe/agents",
        global_agents_dir=get_home() / ".vibe" / "agents",
    ),
    "github-copilot": AgentConfig(
        name="github-copilot",
        display_name="Copilot CLI",
        skills_dir=".github/skills",
        alt_skills_dirs=[".agents/skills", ".claude/skills"],
        global_skills_dir=get_home() / ".copilot" / "skills",
        detect_installed=_detect_copilot_cli,
        agents_dir=".github/agents",
        global_agents_dir=get_home() / ".copilot" / "agents",
    ),
}


def detect_installed_agents() -> list[str]:
    """Return names of agents detected on the system."""
    return [name for name, config in AGENTS.items() if config.detect_installed()]


def get_agent_config(name: str) -> AgentConfig | None:
    """Get configuration for a named agent, or None if unknown."""
    return AGENTS.get(name)


def get_all_agent_names() -> list[str]:
    """Return all supported agent names."""
    return list(AGENTS.keys())

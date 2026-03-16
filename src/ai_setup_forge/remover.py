"""Remove installed skills from agent directories and canonical location."""

from __future__ import annotations

import shutil
from pathlib import Path

from ai_setup_forge.agents import AGENTS
from ai_setup_forge.constants import AGENTS_DIR, CANONICAL_SKILLS_DIR, SKILLS_SUBDIR, get_home


def _canonical_dir(skill_name: str, is_global: bool) -> Path:
    """Return the canonical install path for a skill."""
    if is_global:
        return get_home() / AGENTS_DIR / SKILLS_SUBDIR / skill_name
    return Path.cwd() / CANONICAL_SKILLS_DIR / skill_name


def _agent_skill_path(agent_name: str, skill_name: str, is_global: bool) -> Path | None:
    """Return the agent-specific skill path, or None if agent unknown."""
    agent = AGENTS.get(agent_name)
    if not agent:
        return None
    if is_global:
        return agent.global_skills_dir / skill_name
    return Path.cwd() / agent.skills_dir / skill_name


def _is_link_or_junction(path: Path) -> bool:
    """Check if path is a symlink or junction (works on all Python 3.10+)."""
    if path.is_symlink():
        return True
    if hasattr(path, "is_junction") and path.is_junction():
        return True
    return False


def _remove_path(path: Path) -> bool:
    """Remove a symlink, junction, or directory. Returns True if removed."""
    # Check links/junctions first — they may appear non-existent if target is gone
    if _is_link_or_junction(path):
        path.unlink()
        return True

    if not path.exists():
        return False

    if path.is_dir():
        shutil.rmtree(path)
        return True

    return False


def find_installed_skills(
    is_global: bool = False,
    agent_names: list[str] | None = None,
) -> dict[str, list[str]]:
    """Find installed skills and which agents they're installed for.

    Returns:
        Dict mapping skill_name -> list of agent names.
    """
    if agent_names is None:
        agent_names = list(AGENTS.keys())

    skills: dict[str, list[str]] = {}

    # Check canonical location
    if is_global:
        canonical_base = get_home() / AGENTS_DIR / SKILLS_SUBDIR
    else:
        canonical_base = Path.cwd() / CANONICAL_SKILLS_DIR

    if canonical_base.is_dir():
        for entry in canonical_base.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").is_file():
                skills.setdefault(entry.name, [])

    # Check each agent's directory
    for agent_name in agent_names:
        agent = AGENTS.get(agent_name)
        if not agent:
            continue

        if is_global:
            agent_dir = agent.global_skills_dir
        else:
            agent_dir = Path.cwd() / agent.skills_dir

        if not agent_dir.is_dir():
            continue

        for entry in agent_dir.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").is_file():
                skills.setdefault(entry.name, [])
                if agent_name not in skills[entry.name]:
                    skills[entry.name].append(agent_name)

    return skills


def remove_skill(
    skill_name: str,
    agent_names: list[str] | None = None,
    is_global: bool = False,
) -> list[dict]:
    """Remove a skill from specified agents and canonical location.

    When agent_names is None (all agents), the canonical copy is also removed.
    When a specific agent filter is given, only that agent's link/copy is removed
    and the canonical copy is preserved for other agents.

    Args:
        skill_name: Name of the skill to remove.
        agent_names: Agents to remove from. None = all agents.
        is_global: Remove from global scope.

    Returns:
        List of removal result dicts.
    """
    remove_all = agent_names is None
    if agent_names is None:
        agent_names = list(AGENTS.keys())

    results = []

    # Remove from each agent's directory
    for agent_name in agent_names:
        path = _agent_skill_path(agent_name, skill_name, is_global)
        if path and _remove_path(path):
            results.append({
                "agent": agent_name,
                "status": "removed",
                "path": str(path),
            })

    # Only remove canonical when removing from ALL agents
    if remove_all:
        canonical = _canonical_dir(skill_name, is_global)
        if _remove_path(canonical):
            results.append({
                "agent": "canonical",
                "status": "removed",
                "path": str(canonical),
            })

    return results

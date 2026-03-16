"""Install skills to canonical location and symlink to agent directories."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from ai_setup_forge.agents import AGENTS
from ai_setup_forge.constants import CANONICAL_SKILLS_DIR, SKILLS_SUBDIR, AGENTS_DIR, get_home
from ai_setup_forge.types import AgentConfig, Skill


class InstallError(Exception):
    """Raised when skill installation fails."""


def _canonical_dir(skill_name: str, is_global: bool) -> Path:
    """Return the canonical install path for a skill."""
    if is_global:
        return get_home() / AGENTS_DIR / SKILLS_SUBDIR / skill_name
    return Path.cwd() / CANONICAL_SKILLS_DIR / skill_name


def _agent_skills_dir(agent: AgentConfig, is_global: bool) -> Path:
    """Return the agent-specific skills directory."""
    if is_global:
        return agent.global_skills_dir
    return Path.cwd() / agent.skills_dir


def _validate_target_path(target: Path, base: Path) -> None:
    """Ensure target is within expected base directory (path traversal prevention)."""
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        raise InstallError(
            f"Path traversal detected: {target} is not within {base}"
        )


def _copy_skill_to_canonical(skill: Skill, canonical: Path) -> None:
    """Copy a skill directory to the canonical location."""
    try:
        if canonical.exists():
            shutil.rmtree(canonical)

        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill.path, canonical)
    except OSError as e:
        raise InstallError(f"Failed to copy skill to {canonical}: {e}")


def _create_link(source: Path, target: Path) -> str:
    """Create a symlink or junction from source to target.

    Args:
        source: The link path to create (e.g. .claude/skills/my-skill).
        target: What the link points to (e.g. .agents/skills/my-skill).

    Returns:
        "symlink", "junction", or "copy" depending on what was created.
    """
    source.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing link or directory
    is_junction = hasattr(source, "is_junction") and source.is_junction()
    if source.is_symlink() or is_junction:
        source.unlink()
    elif source.is_dir():
        shutil.rmtree(source)

    # Verify target exists before linking
    if not target.is_dir():
        raise InstallError(f"Link target does not exist: {target}")

    # Try symlink first
    try:
        source.symlink_to(target, target_is_directory=True)
        return "symlink"
    except OSError:
        pass

    # On Windows, try junction (no admin required)
    if sys.platform == "win32":
        try:
            import subprocess
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(source), str(target)],
                capture_output=True,
                check=True,
            )
            return "junction"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Fallback: copy
    shutil.copytree(target, source)
    return "copy"


def _needs_agent_link(agent_name: str, is_global: bool) -> bool:
    """Check if an agent needs a separate link from canonical.

    Copilot CLI reads .agents/skills/ at project level, so no link needed
    for project-level installs.
    """
    if agent_name == "github-copilot" and not is_global:
        return False
    return True


def install_skill(
    skill: Skill,
    agent_names: list[str],
    is_global: bool = False,
    mode: str = "symlink",
) -> list[dict]:
    """Install a skill for the given agents.

    Args:
        skill: The skill to install.
        agent_names: List of agent names to install for.
        is_global: Install to global (user-level) directory.
        mode: "symlink" (default) or "copy".

    Returns:
        List of dicts with install results per agent.
    """
    canonical = _canonical_dir(skill.name, is_global)

    # Validate canonical path
    if is_global:
        base = get_home() / AGENTS_DIR
    else:
        base = Path.cwd() / AGENTS_DIR
    _validate_target_path(canonical, base)

    # Step 1: Copy to canonical
    _copy_skill_to_canonical(skill, canonical)

    results = []

    # Step 2: Link/copy to each agent
    for agent_name in agent_names:
        agent = AGENTS.get(agent_name)
        if not agent:
            results.append({
                "agent": agent_name,
                "status": "error",
                "message": f"Unknown agent: {agent_name}",
            })
            continue

        if not _needs_agent_link(agent_name, is_global):
            results.append({
                "agent": agent_name,
                "status": "ok",
                "message": "Skill in canonical .agents/skills/ (no link needed)",
                "method": "canonical",
                "path": str(canonical),
            })
            continue

        agent_dir = _agent_skills_dir(agent, is_global)
        agent_skill_path = agent_dir / skill.name

        if mode == "copy":
            agent_skill_path.parent.mkdir(parents=True, exist_ok=True)
            if agent_skill_path.exists():
                shutil.rmtree(agent_skill_path)
            shutil.copytree(canonical, agent_skill_path)
            method = "copy"
        else:
            method = _create_link(agent_skill_path, canonical)

        results.append({
            "agent": agent_name,
            "status": "ok",
            "method": method,
            "path": str(agent_skill_path),
        })

    return results

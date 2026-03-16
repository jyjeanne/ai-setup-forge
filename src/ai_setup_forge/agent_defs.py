"""Agent definition discovery, install, and remove for .agent.md files."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import frontmatter

from ai_setup_forge.agents import AGENTS
from ai_setup_forge.constants import (
    AGENT_DEFS_SUBDIR,
    AGENTS_DIR,
    CANONICAL_AGENT_DEFS_DIR,
    get_home,
)
from ai_setup_forge.types import AgentConfig, AgentDefinition

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_agent_defs(source_dir: Path, names: list[str] | None = None) -> list[AgentDefinition]:
    """Discover .agent.md files in a directory.

    Args:
        source_dir: Directory to scan for .agent.md files.
        names: If provided, only return agent definitions matching these names.

    Returns:
        List of parsed AgentDefinition objects.
    """
    if not source_dir.is_dir():
        return []

    results: list[AgentDefinition] = []
    for agent_file in sorted(source_dir.glob("*.agent.md")):
        agent_def = parse_agent_md(agent_file)
        if agent_def is None:
            continue
        if names and agent_def.name not in names:
            continue
        results.append(agent_def)

    return results


def parse_agent_md(path: Path) -> AgentDefinition | None:
    """Parse a single .agent.md file into an AgentDefinition.

    Returns None if the file cannot be parsed or has no name.
    """
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None

    data = dict(post.metadata)
    name = data.get("name", "")
    if not name:
        # Derive from filename: "docs-agent.agent.md" -> "docs-agent"
        name = path.name.removesuffix(".agent.md")
    if not name:
        return None

    description = data.get("description", "")
    if not isinstance(description, str):
        description = str(description)

    # Parse tools list
    raw_tools = data.get("tools")
    tools: list[str] | None = None
    if isinstance(raw_tools, list):
        tools = [str(t) for t in raw_tools]
    elif isinstance(raw_tools, str):
        tools = [raw_tools]

    # Parse MCP servers
    mcp_servers = data.get("mcp-servers") or data.get("mcp_servers")
    if not isinstance(mcp_servers, dict):
        mcp_servers = None

    return AgentDefinition(
        name=name,
        description=description,
        path=path,
        model=data.get("model") if isinstance(data.get("model"), str) else None,
        version=data.get("version") if isinstance(data.get("version"), str) else None,
        category=data.get("category") if isinstance(data.get("category"), str) else None,
        tools=tools,
        target=data.get("target") if isinstance(data.get("target"), str) else None,
        disable_model_invocation=data.get("disable-model-invocation")
        if isinstance(data.get("disable-model-invocation"), bool)
        else None,
        user_invocable=data.get("user-invocable")
        if isinstance(data.get("user-invocable"), bool)
        else None,
        mcp_servers=mcp_servers,
        frontmatter=data,
    )


def _get_bundled_agents_dir() -> Path:
    """Return path to bundled agents/ directory."""
    pkg_dir = Path(__file__).resolve().parent
    project_root = pkg_dir.parent.parent
    agents_dir = project_root / "agents"
    if agents_dir.is_dir():
        return agents_dir
    alt = pkg_dir / "bundled_agents"
    return alt


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _canonical_dir(is_global: bool) -> Path:
    """Return the canonical agent definitions directory."""
    if is_global:
        return get_home() / AGENTS_DIR / AGENT_DEFS_SUBDIR
    return Path.cwd() / CANONICAL_AGENT_DEFS_DIR


def _canonical_path(name: str, is_global: bool) -> Path:
    """Return the canonical install path for an agent definition file."""
    return _canonical_dir(is_global) / f"{name}.agent.md"


def _agent_defs_dir(agent: AgentConfig, is_global: bool) -> Path:
    """Return the coding tool's agent definitions directory."""
    if is_global:
        if agent.global_agents_dir:
            return agent.global_agents_dir
        # Fallback: sibling of global skills dir
        return agent.global_skills_dir.parent / "agents"
    return Path.cwd() / agent.agents_dir


def _validate_target_path(target: Path, base: Path) -> None:
    """Ensure target is within expected base directory (path traversal prevention)."""
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        raise InstallError(f"Path traversal detected: {target} is not within {base}") from None


class InstallError(Exception):
    """Raised when agent definition installation fails."""


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def _copy_to_canonical(agent_def: AgentDefinition, canonical: Path) -> None:
    """Copy an .agent.md file to the canonical location."""
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(agent_def.path, canonical)


def _create_file_link(source: Path, target: Path) -> str:
    """Create a symlink or copy for a single file.

    Args:
        source: The link path to create.
        target: What the link points to.

    Returns:
        "symlink", "junction", or "copy".
    """
    source.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing
    if source.is_symlink() or source.exists():
        source.unlink()

    # Try symlink first
    try:
        source.symlink_to(target)
        return "symlink"
    except OSError:
        pass

    # On Windows, fall back to copy (junctions are for directories only)
    if sys.platform == "win32":
        shutil.copy2(target, source)
        return "copy"

    # Unix fallback: copy
    shutil.copy2(target, source)
    return "copy"


def install_agent_def(
    agent_def: AgentDefinition,
    agent_names: list[str],
    is_global: bool = False,
    mode: str = "symlink",
) -> list[dict]:
    """Install an agent definition for the given coding tools.

    Args:
        agent_def: The agent definition to install.
        agent_names: List of coding tool names to install for.
        is_global: Install to global (user-level) directory.
        mode: "symlink" (default) or "copy".

    Returns:
        List of dicts with install results per coding tool.
    """
    canonical = _canonical_path(agent_def.name, is_global)

    # Validate canonical path
    base = get_home() / AGENTS_DIR if is_global else Path.cwd() / AGENTS_DIR
    _validate_target_path(canonical, base)

    # Step 1: Copy to canonical
    _copy_to_canonical(agent_def, canonical)

    results = []

    # Step 2: Link/copy to each coding tool
    for agent_name in agent_names:
        agent = AGENTS.get(agent_name)
        if not agent:
            results.append(
                {
                    "agent": agent_name,
                    "status": "error",
                    "message": f"Unknown agent: {agent_name}",
                }
            )
            continue

        try:
            agent_dir = _agent_defs_dir(agent, is_global)
            agent_file = agent_dir / f"{agent_def.name}.agent.md"

            if mode == "copy":
                agent_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(canonical, agent_file)
                method = "copy"
            else:
                method = _create_file_link(agent_file, canonical)

            results.append(
                {
                    "agent": agent_name,
                    "status": "ok",
                    "method": method,
                    "path": str(agent_file),
                }
            )
        except OSError as e:
            results.append(
                {
                    "agent": agent_name,
                    "status": "error",
                    "message": str(e),
                }
            )

    return results


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


def find_installed_agent_defs(
    is_global: bool = False,
    agent_names: list[str] | None = None,
) -> dict[str, list[str]]:
    """Find installed agent definitions and which coding tools they're installed for.

    Returns:
        Dict mapping agent_def_name -> list of coding tool names.
    """
    if agent_names is None:
        agent_names = list(AGENTS.keys())

    defs: dict[str, list[str]] = {}

    # Check canonical location
    canonical_base = _canonical_dir(is_global)
    if canonical_base.is_dir():
        for entry in canonical_base.iterdir():
            if entry.is_file() and entry.name.endswith(".agent.md"):
                name = entry.name.removesuffix(".agent.md")
                defs.setdefault(name, [])

    # Check each coding tool's directory
    for agent_name in agent_names:
        agent = AGENTS.get(agent_name)
        if not agent:
            continue

        agent_dir = _agent_defs_dir(agent, is_global)
        if not agent_dir.is_dir():
            continue

        for entry in agent_dir.iterdir():
            if entry.is_file() and entry.name.endswith(".agent.md"):
                name = entry.name.removesuffix(".agent.md")
                defs.setdefault(name, [])
                if agent_name not in defs[name]:
                    defs[name].append(agent_name)

    return defs


def _remove_file(path: Path) -> bool:
    """Remove a file (symlink or regular). Returns True if removed."""
    if path.is_symlink():
        path.unlink()
        return True
    if path.is_file():
        path.unlink()
        return True
    return False


def remove_agent_def(
    name: str,
    agent_names: list[str] | None = None,
    is_global: bool = False,
) -> list[dict]:
    """Remove an agent definition from specified coding tools and canonical location.

    When agent_names is None (all coding tools), the canonical copy is also removed.

    Returns:
        List of removal result dicts.
    """
    remove_all = agent_names is None
    if agent_names is None:
        agent_names = list(AGENTS.keys())

    results = []

    for agent_name in agent_names:
        agent = AGENTS.get(agent_name)
        if not agent:
            continue
        agent_file = _agent_defs_dir(agent, is_global) / f"{name}.agent.md"
        if _remove_file(agent_file):
            results.append(
                {
                    "agent": agent_name,
                    "status": "removed",
                    "path": str(agent_file),
                }
            )

    if remove_all:
        canonical = _canonical_path(name, is_global)
        if _remove_file(canonical):
            results.append(
                {
                    "agent": "canonical",
                    "status": "removed",
                    "path": str(canonical),
                }
            )

    return results


# ---------------------------------------------------------------------------
# Init (template)
# ---------------------------------------------------------------------------


def create_agent_template(name: str | None = None) -> Path | None:
    """Create a new .agent.md from the template.

    Returns the path to the created file, or None on failure.
    """
    template_path = _get_template_path()
    if template_path is None:
        return None

    agent_name = name or "my-agent"
    output = Path.cwd() / f"{agent_name}.agent.md"

    if output.exists():
        return None

    content = template_path.read_text(encoding="utf-8")
    # Replace template placeholders
    content = content.replace("your-agent-name", agent_name)

    output.write_text(content, encoding="utf-8")
    return output


def _get_template_path() -> Path | None:
    """Find the agent template file."""
    pkg_dir = Path(__file__).resolve().parent
    project_root = pkg_dir.parent.parent

    path = project_root / "docs" / "AGENT_TEMPLATE.md"
    if path.is_file():
        return path

    alt = pkg_dir / "templates" / "AGENT_TEMPLATE.md"
    if alt.is_file():
        return alt

    return None

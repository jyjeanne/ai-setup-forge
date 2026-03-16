"""Data models for AI Setup Forge."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal


@dataclass
class AgentConfig:
    """Configuration for a supported coding agent."""

    name: str
    """CLI identifier, e.g. 'claude-code'."""

    display_name: str
    """Human-readable name, e.g. 'Claude Code'."""

    skills_dir: str
    """Primary project-level relative path, e.g. '.claude/skills'."""

    global_skills_dir: Path
    """Absolute path to the global (user-level) skills directory."""

    detect_installed: Callable[[], bool]
    """Callable that returns True if this agent is detected on the system."""

    alt_skills_dirs: list[str] = field(default_factory=list)
    """Additional project-level paths this agent reads from (for discovery)."""

    agents_dir: str = ""
    """Project-level relative path for agent definitions, e.g. '.claude/agents'."""

    global_agents_dir: Path | None = None
    """Absolute path to the global (user-level) agent definitions directory."""


@dataclass
class Skill:
    """A parsed skill from a SKILL.md file."""

    name: str
    description: str
    path: Path
    """Directory containing the SKILL.md file."""

    raw_content: str | None = None
    """Full raw text of SKILL.md (for hashing)."""

    metadata: dict[str, str] | None = None
    """The 'metadata' frontmatter field (key-value pairs)."""

    frontmatter: dict[str, object] | None = None
    """All parsed frontmatter fields."""


@dataclass
class AgentDefinition:
    """A parsed agent definition from an .agent.md file."""

    name: str
    description: str
    path: Path
    """Path to the .agent.md file."""

    model: str | None = None
    version: str | None = None
    category: str | None = None
    tools: list[str] | None = None
    """Tools the agent can use. None means all tools (default)."""

    target: str | None = None
    """Environment context: 'vscode', 'github-copilot', or None (both)."""

    disable_model_invocation: bool | None = None
    """Prevents automatic agent selection when True."""

    user_invocable: bool | None = None
    """Controls manual agent selection. Default True."""

    mcp_servers: dict[str, object] | None = None
    """MCP server configuration for additional tool access."""

    frontmatter: dict[str, object] | None = None
    """All parsed frontmatter fields."""


@dataclass
class ParsedSource:
    """A parsed source string identifying where to fetch skills from."""

    type: Literal["github", "gitlab", "git", "local", "direct-url", "bundled"]
    url: str

    subpath: str | None = None
    local_path: Path | None = None
    ref: str | None = None
    skill_filter: str | None = None


@dataclass
class SkillLockEntry:
    """A single entry in the skill lock file."""

    source: str
    """Normalized source identifier, e.g. 'owner/repo'."""

    source_type: str
    """Provider type: 'github', 'gitlab', 'local', etc."""

    source_url: str
    """Original URL used to install (for re-fetching)."""

    skill_path: str | None
    """Subpath within the source repo, if applicable."""

    skill_folder_hash: str
    """SHA for change detection (GitHub tree SHA)."""

    installed_at: str
    """ISO 8601 timestamp of first install."""

    updated_at: str
    """ISO 8601 timestamp of last update."""


@dataclass
class InstalledSkill:
    """Represents a skill found on disk during listing."""

    name: str
    description: str
    path: Path
    canonical_path: Path
    scope: Literal["project", "global"]
    agents: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating a SKILL.md against the Agent Skills spec."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

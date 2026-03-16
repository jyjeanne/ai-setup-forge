"""Shared constants derived from the Agent Skills specification."""

from pathlib import Path

# --- Agent Skills Spec Constraints ---
NAME_MAX_LENGTH = 64
NAME_PATTERN = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"  # no leading/trailing/consecutive hyphens
DESCRIPTION_MAX_LENGTH = 1024
COMPATIBILITY_MAX_LENGTH = 500
BODY_MAX_LINES_RECOMMENDED = 500

# --- Canonical install directory ---
AGENTS_DIR = ".agents"
SKILLS_SUBDIR = "skills"
CANONICAL_SKILLS_DIR = f"{AGENTS_DIR}/{SKILLS_SUBDIR}"

AGENT_DEFS_SUBDIR = "agent-definitions"
CANONICAL_AGENT_DEFS_DIR = f"{AGENTS_DIR}/{AGENT_DEFS_SUBDIR}"

# --- Lock file ---
LOCK_FILE_NAME = ".skill-lock.json"
LOCK_FILE_VERSION = 1

# --- Git ---
GIT_CLONE_TIMEOUT_SECONDS = 60

# --- Skill file ---
SKILL_FILE_NAME = "SKILL.md"

# --- Discovery: directories to skip during recursive search ---
SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
    }
)

# --- Discovery: priority search directories (relative to source root) ---
PRIORITY_SEARCH_DIRS = [
    "skills",
    "skills/.curated",
    "skills/.experimental",
    "skills/.system",
    f"{AGENTS_DIR}/{SKILLS_SUBDIR}",
    ".claude/skills",
    ".vibe/skills",
    ".github/skills",
]

# --- Discovery: max recursion depth ---
MAX_DISCOVERY_DEPTH = 5


def get_home() -> Path:
    """Return the user home directory."""
    return Path.home()

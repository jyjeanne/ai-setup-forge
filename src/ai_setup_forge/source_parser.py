"""Parse source strings into structured ParsedSource objects."""

from __future__ import annotations

import re
from pathlib import Path

from ai_setup_forge.types import ParsedSource


def _is_local_path(input_str: str) -> bool:
    """Check if the input looks like a local filesystem path."""
    if input_str.startswith(("http://", "https://", "git@")):
        return False
    return (
        Path(input_str).is_absolute()
        or input_str.startswith("/")
        or input_str.startswith("./")
        or input_str.startswith("../")
        or input_str in (".", "..")
        # Windows absolute paths: C:\ D:/
        or bool(re.match(r"^[a-zA-Z]:[/\\]", input_str))
    )


def _is_direct_skill_url(input_str: str) -> bool:
    """Check if a URL points directly to a SKILL.md file (non-GitHub/GitLab)."""
    if not input_str.startswith(("http://", "https://")):
        return False
    if not input_str.lower().endswith("/skill.md"):
        return False
    # Exclude GitHub/GitLab (they have their own handling)
    if (
        "github.com/" in input_str
        and "raw.githubusercontent.com" not in input_str
        and "/blob/" not in input_str
        and "/raw/" not in input_str
    ):
        return False
    return not ("gitlab.com/" in input_str and "/-/raw/" not in input_str)


def _get_bundled_skills_dir() -> Path:
    """Return the path to the bundled skills/ directory shipped with the package.

    Checks two locations:
    1. Dev/editable install: <project-root>/skills/ (reached via __file__ traversal)
    2. Installed package: <package-dir>/bundled_skills/ (force-included by hatchling)
    """
    package_dir = Path(__file__).resolve().parent  # src/ai_setup_forge/
    # Dev/editable: src/ai_setup_forge/ -> src/ -> project root -> skills/
    project_root = package_dir.parent.parent
    dev_path = project_root / "skills"
    if dev_path.is_dir():
        return dev_path
    # Installed package: bundled_skills/ next to the package modules
    installed_path = package_dir / "bundled_skills"
    if installed_path.is_dir():
        return installed_path
    # Return installed_path for clearer error messages when package is broken
    return installed_path


def parse_source(input_str: str) -> ParsedSource:
    """Parse a source string into a structured ParsedSource.

    Supports:
    - Bundled skills (keyword "bundled")
    - Local paths (absolute, relative, Windows)
    - GitHub URLs and shorthand (owner/repo)
    - GitLab URLs (including nested groups)
    - Direct SKILL.md URLs
    - SSH git URLs
    """
    # --- Bundled skills ---
    if input_str.strip().lower() == "bundled":
        bundled_dir = _get_bundled_skills_dir()
        return ParsedSource(
            type="bundled",
            url=str(bundled_dir),
            local_path=bundled_dir,
        )

    # --- Local paths ---
    if _is_local_path(input_str):
        resolved = Path(input_str).resolve()
        return ParsedSource(
            type="local",
            url=str(resolved),
            local_path=resolved,
        )

    # --- Direct SKILL.md URL ---
    if _is_direct_skill_url(input_str):
        return ParsedSource(type="direct-url", url=input_str)

    # --- GitHub URL with tree path ---
    # https://github.com/owner/repo/tree/branch/path/to/skill
    m = re.search(r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)", input_str)
    if m:
        owner, repo, ref, subpath = m.groups()
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner}/{repo}.git",
            ref=ref,
            subpath=subpath,
        )

    # --- GitHub URL with branch only ---
    # https://github.com/owner/repo/tree/branch
    m = re.search(r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)$", input_str)
    if m:
        owner, repo, ref = m.groups()
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner}/{repo}.git",
            ref=ref,
        )

    # --- GitHub URL (plain repo) ---
    # https://github.com/owner/repo
    m = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", input_str)
    if m:
        owner, repo = m.groups()
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner}/{repo}.git",
        )

    # --- GitLab URL with tree path ---
    # https://gitlab.com/group/repo/-/tree/branch/path
    m = re.match(r"^(https?://([^/]+)/(.+?)/-/tree/([^/]+)/(.+))", input_str)
    if m:
        _, hostname, repo_path, ref, subpath = m.groups()
        if hostname != "github.com" and repo_path:
            return ParsedSource(
                type="gitlab",
                url=f"https://{hostname}/{re.sub(r'.git$', '', repo_path)}.git",
                ref=ref,
                subpath=subpath,
            )

    # --- GitLab URL with branch only ---
    m = re.match(r"^(https?://([^/]+)/(.+?)/-/tree/([^/]+))$", input_str)
    if m:
        _, hostname, repo_path, ref = m.groups()
        if hostname != "github.com" and repo_path:
            return ParsedSource(
                type="gitlab",
                url=f"https://{hostname}/{re.sub(r'.git$', '', repo_path)}.git",
                ref=ref,
            )

    # --- GitLab.com URL (plain repo, supports nested groups) ---
    m = re.search(r"gitlab\.com/(.+?)(?:\.git)?/?$", input_str)
    if m:
        repo_path = m.group(1)
        if "/" in repo_path:
            return ParsedSource(
                type="gitlab",
                url=f"https://gitlab.com/{repo_path}.git",
            )

    # --- GitHub shorthand with @skill filter: owner/repo@skill-name ---
    m = re.match(r"^([^/]+)/([^/@]+)@(.+)$", input_str)
    if m and ":" not in input_str and not input_str.startswith((".", "/")):
        owner, repo, skill_filter = m.groups()
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner}/{repo}.git",
            skill_filter=skill_filter,
        )

    # --- GitHub shorthand: owner/repo or owner/repo/subpath ---
    m = re.match(r"^([^/]+)/([^/]+)(?:/(.+))?$", input_str)
    if m and ":" not in input_str and not input_str.startswith((".", "/")):
        owner, repo, subpath = m.groups()
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner}/{repo}.git",
            subpath=subpath,
        )

    # --- Fallback: treat as direct git URL ---
    return ParsedSource(type="git", url=input_str)

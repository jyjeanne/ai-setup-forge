"""Check for updates and update installed skills."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ai_setup_forge.skill_lock import get_skill_entry, read_lock


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class SkillUpdateInfo:
    """Update status for a single skill."""

    name: str
    source_url: str
    source_type: str
    current_hash: str
    remote_hash: str | None = None
    has_update: bool = False
    error: str | None = None


@dataclass
class CheckResult:
    """Result of checking for updates."""

    skills: list[SkillUpdateInfo] = field(default_factory=list)

    @property
    def outdated(self) -> list[SkillUpdateInfo]:
        return [s for s in self.skills if s.has_update]

    @property
    def up_to_date(self) -> list[SkillUpdateInfo]:
        return [s for s in self.skills if not s.has_update and not s.error]

    @property
    def errors(self) -> list[SkillUpdateInfo]:
        return [s for s in self.skills if s.error]


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _get_github_token() -> str | None:
    """Get GitHub token from environment or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract owner/repo from a GitHub URL.

    Returns (owner, repo) or None if not a GitHub URL.
    """
    import re

    # https://github.com/owner/repo[/...]
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$", url)
    if m:
        return m.group(1), m.group(2)

    # git@github.com:owner/repo.git
    m = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)

    # owner/repo shorthand (stored in source_url)
    m = re.match(r"^([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+)$", url)
    if m:
        return m.group(1), m.group(2)

    return None


def _api_get(url: str, token: str | None = None) -> tuple[int, dict | list | None]:
    """Make an authenticated GitHub API GET request.

    Returns (status_code, parsed_json) or (0, None) on network error.
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        try:
            data = resp.json()
        except (ValueError, UnicodeDecodeError):
            data = None
        return resp.status_code, data
    except httpx.HTTPError:
        return 0, None


def _describe_api_error(status: int) -> str:
    """Return a human-readable description for an API error status."""
    if status == 401:
        return "authentication failed (check GITHUB_TOKEN)"
    if status == 403:
        return "forbidden (rate limited or private repo)"
    if status == 404:
        return "repository not found"
    if status >= 500:
        return f"GitHub server error ({status})"
    if status == 0:
        return "network error"
    return f"API error ({status})"


def _get_latest_commit_sha(owner: str, repo: str, token: str | None = None) -> str | None:
    """Get the latest commit SHA of the default branch via GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
    status, data = _api_get(url, token)
    if status == 200 and isinstance(data, list) and data:
        sha = data[0].get("sha", "")
        return sha[:12] if sha else None
    return None


def _get_tree_sha(
    owner: str, repo: str, path: str | None = None, token: str | None = None
) -> str | None:
    """Get the tree SHA for a path in the repo via GitHub Trees API.

    If path is None, returns the root tree SHA of the latest commit.
    """
    # Get latest commit to find tree
    commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
    status, data = _api_get(commit_url, token)
    if status != 200 or not isinstance(data, list) or not data:
        return None

    try:
        root_tree_sha = data[0]["commit"]["tree"]["sha"]
    except (KeyError, IndexError, TypeError):
        return None

    if not path:
        return root_tree_sha

    # Walk the tree to find the subtree SHA for the given path
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{root_tree_sha}?recursive=1"
    status, tree_data = _api_get(tree_url, token)
    if status != 200 or not isinstance(tree_data, dict):
        return None

    for item in tree_data.get("tree", []):
        if item.get("path") == path and item.get("type") == "tree":
            return item["sha"]

    return None


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

def check_for_updates() -> CheckResult:
    """Check all globally installed skills for updates.

    Reads the skill lock file and compares stored hashes with
    the current state on GitHub.
    """
    result = CheckResult()
    lock_data = read_lock()
    skills = lock_data.get("skills", {})

    if not skills:
        return result

    token = _get_github_token()

    for skill_name, entry in skills.items():
        source_type = entry.get("source_type", "")
        source_url = entry.get("source_url", "")
        current_hash = entry.get("skill_folder_hash", "")
        skill_path = entry.get("skill_path")

        info = SkillUpdateInfo(
            name=skill_name,
            source_url=source_url,
            source_type=source_type,
            current_hash=current_hash,
        )

        if source_type not in ("github", "git"):
            info.error = f"Update check not supported for source type: {source_type}"
            result.skills.append(info)
            continue

        parsed = _parse_github_url(source_url)
        if not parsed:
            info.error = f"Cannot parse GitHub URL: {source_url}"
            result.skills.append(info)
            continue

        owner, repo = parsed
        remote_sha = _get_tree_sha(owner, repo, path=skill_path, token=token)

        if remote_sha is None:
            # Fallback: use commit SHA
            remote_sha = _get_latest_commit_sha(owner, repo, token=token)

        if remote_sha is None:
            info.error = "Failed to fetch remote state (API error or rate limit)"
            result.skills.append(info)
            continue

        info.remote_hash = remote_sha
        if current_hash and current_hash != remote_sha:
            info.has_update = True
        elif not current_hash:
            # No stored hash — can't compare, assume outdated
            info.has_update = True

        result.skills.append(info)

    return result


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def update_skill(
    skill_name: str,
    agent_names: list[str] | None = None,
) -> dict:
    """Re-install a single skill from its stored source URL.

    Args:
        skill_name: Name of the skill to update.
        agent_names: Optional list of agents. If None, uses last selected.

    Returns:
        Dict with status and details.
    """
    from ai_setup_forge.git_utils import GitError, cleanup_clone, shallow_clone
    from ai_setup_forge.installer import install_skill
    from ai_setup_forge.skill_lock import add_skill_entry, get_last_agents, get_skill_entry
    from ai_setup_forge.skills import discover_skills, filter_skills
    from ai_setup_forge.source_parser import parse_source

    entry = get_skill_entry(skill_name)
    if not entry:
        return {"status": "error", "message": f"No lock entry for {skill_name}"}

    if not entry.source_url:
        return {"status": "error", "message": f"No source URL stored for {skill_name}"}

    # Resolve agents
    if agent_names is None:
        agent_names = get_last_agents()
    if not agent_names:
        from ai_setup_forge.agents import detect_installed_agents
        agent_names = detect_installed_agents()
    if not agent_names:
        return {"status": "error", "message": "No agents available for update"}

    # Parse source
    try:
        parsed = parse_source(entry.source_url)
    except Exception as e:
        return {"status": "error", "message": f"Cannot parse source: {e}"}

    # Clone if remote
    clone_dir = None
    skill_source_dir: Path | None = None

    if parsed.type in ("local", "bundled"):
        skill_source_dir = parsed.local_path
    else:
        try:
            clone_dir = shallow_clone(parsed.url, ref=parsed.ref)
        except GitError as e:
            return {"status": "error", "message": str(e)}
        skill_source_dir = clone_dir

    try:
        if not skill_source_dir or not skill_source_dir.is_dir():
            return {"status": "error", "message": f"Source not found: {entry.source_url}"}

        # Discover and filter
        discovered = discover_skills(
            skill_source_dir,
            subpath=parsed.subpath or entry.skill_path,
            full_depth=True,
        )
        discovered = filter_skills(discovered, [skill_name])

        if not discovered:
            return {"status": "error", "message": f"Skill {skill_name} not found in source"}

        skill = discovered[0]

        # Re-install (global, since lock file = global)
        results = install_skill(skill, agent_names, is_global=True, mode="symlink")

        # Update lock file
        add_skill_entry(
            skill_name=skill.name,
            source=entry.source,
            source_type=entry.source_type,
            source_url=entry.source_url,
            skill_path=entry.skill_path,
        )

        # Update registry
        try:
            from ai_setup_forge.registry import (
                derive_origin,
                ensure_registry,
                mark_installed,
                upsert_skill,
            )
            conn = ensure_registry()
            try:
                origin = derive_origin(parsed.type)
                upsert_skill(
                    conn, name=skill.name, description=skill.description,
                    origin=origin, source_url=parsed.url,
                )
                mark_installed(conn, skill.name, agent_names, "global", parsed.url, origin)
            finally:
                conn.close()
        except Exception:
            pass  # Registry update is non-critical

        return {
            "status": "ok",
            "skill": skill_name,
            "agents": agent_names,
            "install_results": results,
        }

    finally:
        if clone_dir:
            cleanup_clone(clone_dir)

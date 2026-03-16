"""Lock file (.skill-lock.json) management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_setup_forge.constants import AGENTS_DIR, LOCK_FILE_NAME, LOCK_FILE_VERSION, SKILLS_SUBDIR, get_home
from ai_setup_forge.types import SkillLockEntry


def _lock_file_path() -> Path:
    """Return the global lock file path: ~/.agents/.skill-lock.json."""
    return get_home() / AGENTS_DIR / LOCK_FILE_NAME


def _global_canonical_dir() -> Path:
    """Return the global canonical skills dir: ~/.agents/skills/."""
    return get_home() / AGENTS_DIR / SKILLS_SUBDIR


def read_lock() -> dict:
    """Read and return the lock file contents, or empty structure if missing."""
    path = _lock_file_path()
    if not path.exists():
        return {"version": LOCK_FILE_VERSION, "skills": {}, "last_selected_agents": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": LOCK_FILE_VERSION, "skills": {}, "last_selected_agents": []}

    if not isinstance(data, dict):
        return {"version": LOCK_FILE_VERSION, "skills": {}, "last_selected_agents": []}

    # Ensure structure and validate types
    data.setdefault("version", LOCK_FILE_VERSION)
    if not isinstance(data.get("skills"), dict):
        data["skills"] = {}
    else:
        data.setdefault("skills", {})
    if not isinstance(data.get("last_selected_agents"), list):
        data["last_selected_agents"] = []
    else:
        data.setdefault("last_selected_agents", [])
    return data


def write_lock(data: dict) -> None:
    """Write the lock file.

    Raises OSError if the file cannot be written (permissions, disk full, etc.).
    """
    path = _lock_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # Write to temp file then rename for crash safety
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        # Clean up temp file on failure, re-raise
        tmp.unlink(missing_ok=True)
        raise


def add_skill_entry(
    skill_name: str,
    source: str,
    source_type: str,
    source_url: str,
    skill_path: str | None = None,
    skill_folder_hash: str = "",
) -> None:
    """Add or update a skill entry in the lock file."""
    data = read_lock()
    now = datetime.now(timezone.utc).isoformat()

    existing = data["skills"].get(skill_name)
    if existing:
        # Update
        existing["source"] = source
        existing["source_type"] = source_type
        existing["source_url"] = source_url
        existing["skill_path"] = skill_path
        existing["skill_folder_hash"] = skill_folder_hash
        existing["updated_at"] = now
    else:
        # New entry
        data["skills"][skill_name] = {
            "source": source,
            "source_type": source_type,
            "source_url": source_url,
            "skill_path": skill_path,
            "skill_folder_hash": skill_folder_hash,
            "installed_at": now,
            "updated_at": now,
        }

    write_lock(data)


def remove_skill_entry(skill_name: str) -> bool:
    """Remove a skill entry from the lock file. Returns True if found."""
    data = read_lock()
    if skill_name in data["skills"]:
        del data["skills"][skill_name]
        write_lock(data)
        return True
    return False


def get_skill_entry(skill_name: str) -> SkillLockEntry | None:
    """Get a skill entry from the lock file."""
    data = read_lock()
    entry = data["skills"].get(skill_name)
    if not entry:
        return None
    return SkillLockEntry(
        source=entry.get("source", ""),
        source_type=entry.get("source_type", ""),
        source_url=entry.get("source_url", ""),
        skill_path=entry.get("skill_path"),
        skill_folder_hash=entry.get("skill_folder_hash", ""),
        installed_at=entry.get("installed_at", ""),
        updated_at=entry.get("updated_at", ""),
    )


def update_last_agents(agents: list[str]) -> None:
    """Remember the last selected agents."""
    data = read_lock()
    data["last_selected_agents"] = agents
    write_lock(data)


def get_last_agents() -> list[str]:
    """Get the last selected agents."""
    data = read_lock()
    return data.get("last_selected_agents", [])

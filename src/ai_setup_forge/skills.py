"""SKILL.md discovery and parsing."""

from __future__ import annotations

import os
from pathlib import Path

import frontmatter

from ai_setup_forge.constants import (
    MAX_DISCOVERY_DEPTH,
    PRIORITY_SEARCH_DIRS,
    SKILL_FILE_NAME,
    SKIP_DIRS,
)
from ai_setup_forge.types import Skill


def parse_skill_md(
    skill_md_path: Path,
    include_internal: bool = False,
) -> Skill | None:
    """Parse a SKILL.md file and return a Skill, or None if invalid.

    Args:
        skill_md_path: Path to the SKILL.md file.
        include_internal: If True, include skills marked as internal.
    """
    try:
        post = frontmatter.load(str(skill_md_path))
    except Exception:
        return None

    data = dict(post.metadata)
    name = data.get("name")
    description = data.get("description")

    if not name or not description:
        return None

    if not isinstance(name, str) or not isinstance(description, str):
        return None

    # Skip internal skills unless requested
    meta = data.get("metadata")
    if isinstance(meta, dict) and meta.get("internal") is True:
        if not include_internal and not _should_install_internal():
            return None

    return Skill(
        name=name,
        description=description,
        path=skill_md_path.parent,
        raw_content=post.content,
        metadata=meta if isinstance(meta, dict) else None,
        frontmatter=data,
    )


def _should_install_internal() -> bool:
    """Check INSTALL_INTERNAL_SKILLS env var."""
    val = os.environ.get("INSTALL_INTERNAL_SKILLS", "")
    return val in ("1", "true")


def _has_skill_md(directory: Path) -> bool:
    """Check if a directory contains a SKILL.md file."""
    return (directory / SKILL_FILE_NAME).is_file()


def _find_skill_dirs_recursive(
    directory: Path,
    depth: int = 0,
    max_depth: int = MAX_DISCOVERY_DEPTH,
) -> list[Path]:
    """Recursively find directories containing SKILL.md."""
    if depth > max_depth:
        return []

    results: list[Path] = []

    if _has_skill_md(directory):
        results.append(directory)

    try:
        entries = list(directory.iterdir())
    except PermissionError:
        return results

    for entry in entries:
        if entry.is_dir() and entry.name not in SKIP_DIRS:
            results.extend(_find_skill_dirs_recursive(entry, depth + 1, max_depth))

    return results


def discover_skills(
    base_path: Path,
    subpath: str | None = None,
    include_internal: bool = False,
    full_depth: bool = False,
) -> list[Skill]:
    """Discover skills in a source directory.

    Args:
        base_path: Root directory to search.
        subpath: Optional subpath within the root.
        include_internal: Include internal skills.
        full_depth: Search all subdirectories even when a root SKILL.md exists.

    Returns:
        List of discovered skills, deduplicated by name.
    """
    skills: list[Skill] = []
    seen_names: set[str] = set()
    search_path = base_path / subpath if subpath else base_path

    # If pointing directly at a skill, add it
    if _has_skill_md(search_path):
        skill = parse_skill_md(search_path / SKILL_FILE_NAME, include_internal)
        if skill:
            skills.append(skill)
            seen_names.add(skill.name)
            if not full_depth:
                return skills

    # Search priority directories
    for rel_dir in PRIORITY_SEARCH_DIRS:
        priority_dir = search_path / rel_dir
        if not priority_dir.is_dir():
            continue
        try:
            for entry in priority_dir.iterdir():
                if entry.is_dir() and _has_skill_md(entry):
                    skill = parse_skill_md(entry / SKILL_FILE_NAME, include_internal)
                    if skill and skill.name not in seen_names:
                        skills.append(skill)
                        seen_names.add(skill.name)
        except PermissionError:
            continue

    # Fallback: recursive search if nothing found or full_depth
    if not skills or full_depth:
        all_skill_dirs = _find_skill_dirs_recursive(search_path)
        for skill_dir in all_skill_dirs:
            skill = parse_skill_md(skill_dir / SKILL_FILE_NAME, include_internal)
            if skill and skill.name not in seen_names:
                skills.append(skill)
                seen_names.add(skill.name)

    return skills


def filter_skills(skills: list[Skill], input_names: list[str]) -> list[Skill]:
    """Filter skills by name (case-insensitive exact match)."""
    normalized = [n.lower() for n in input_names]
    return [s for s in skills if s.name.lower() in normalized]


def _get_category_skill_names(categories: list[str]) -> set[str]:
    """Return skill names that belong to any of the given categories.

    Reads the bundled_skills_map.json to resolve category -> skill names.
    """
    import json

    # Find the map file relative to this module (installed) or project root
    map_file = Path(__file__).resolve().parent / "bundled_skills" / "bundled_skills_map.json"
    if not map_file.exists():
        # Try project-level path
        map_file = Path(__file__).resolve().parent.parent.parent / "skills-registry" / "bundled_skills_map.json"
    if not map_file.exists():
        return set()

    with open(map_file) as f:
        skill_map: dict[str, dict[str, list[str]]] = json.load(f)

    normalized_cats = [c.lower() for c in categories]
    matching: set[str] = set()
    for skill_name, meta in skill_map.items():
        skill_cats = [c.lower() for c in meta.get("categories", [])]
        if any(c in normalized_cats for c in skill_cats):
            matching.add(skill_name)

    return matching

"""Search for skills from bundled directory and skills.sh registry."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from ai_setup_forge.skills import discover_skills
from ai_setup_forge.source_parser import _get_bundled_skills_dir

SKILLS_API_BASE = os.environ.get("SKILLS_API_URL", "https://skills.sh")
SEARCH_ENDPOINT = "/api/search"
SEARCH_LIMIT = 10
REQUEST_TIMEOUT = 10.0


@dataclass
class FindResult:
    """A single search result."""

    name: str
    source: str
    """e.g. 'owner/repo' for registry, 'bundled' for local."""
    slug: str
    """Full slug for skills.sh URL, e.g. 'owner/repo/skill-name'."""
    installs: int
    origin: str
    """'bundled' or 'registry'."""
    description: str = ""
    install_cmd: str = ""


def search_bundled(query: str | None = None) -> list[FindResult]:
    """Search bundled skills, optionally filtering by query.

    Args:
        query: Search string to match against name and description.
               None or empty returns all bundled skills.

    Returns:
        List of matching FindResult objects.
    """
    bundled_dir = _get_bundled_skills_dir()
    if not bundled_dir.is_dir():
        return []

    skills = discover_skills(bundled_dir, full_depth=True)
    results = []

    for skill in skills:
        if query:
            q = query.lower()
            if q not in skill.name.lower() and q not in skill.description.lower():
                continue

        results.append(
            FindResult(
                name=skill.name,
                source="bundled",
                slug="",
                installs=0,
                origin="bundled",
                description=skill.description,
                install_cmd=f"ai-setup-forge add bundled -s {skill.name}",
            )
        )

    return results


def search_registry(query: str) -> list[FindResult]:
    """Search the skills.sh registry API.

    Args:
        query: Search query string (min 2 chars recommended).

    Returns:
        List of matching FindResult objects.
    """
    if not query or len(query) < 2:
        return []

    url = f"{SKILLS_API_BASE}{SEARCH_ENDPOINT}"
    params = {"q": query, "limit": SEARCH_LIMIT}

    try:
        response = httpx.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return []

    skills_data = data.get("skills", [])
    if not isinstance(skills_data, list):
        return []

    results = []
    for item in skills_data:
        if not isinstance(item, dict):
            continue

        name = item.get("name", "")
        slug = item.get("id", "")
        source = item.get("source", "")
        description = item.get("description", "")
        installs = item.get("installs", 0)

        if not name:
            continue

        # Build install command: owner/repo@skill-name
        if source:
            install_cmd = f"ai-setup-forge add {source}@{name}"
        else:
            install_cmd = f"ai-setup-forge add {slug}"

        results.append(
            FindResult(
                name=name,
                source=source or slug,
                slug=slug,
                installs=installs if isinstance(installs, int) else 0,
                origin="registry",
                description=description if isinstance(description, str) else "",
                install_cmd=install_cmd,
            )
        )

    return results


def search_all(query: str | None = None) -> list[FindResult]:
    """Search both bundled skills and the skills.sh registry.

    Bundled results come first, then registry results.
    Duplicates (same name) are deduplicated, preferring bundled.

    Args:
        query: Search query. None shows only bundled skills.

    Returns:
        Combined list of FindResult objects.
    """
    results: list[FindResult] = []
    seen_names: set[str] = set()

    # Bundled first
    for r in search_bundled(query):
        if r.name not in seen_names:
            results.append(r)
            seen_names.add(r.name)

    # Registry (only if query provided)
    if query:
        for r in search_registry(query):
            if r.name not in seen_names:
                results.append(r)
                seen_names.add(r.name)

    return results

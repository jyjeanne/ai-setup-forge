"""Skills & agents registry — local SQLite database for inventory management."""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ai_setup_forge.constants import get_home

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DB_DIR = ".ai-setup-forge"
_DEFAULT_DB_NAME = "skills_registry.db"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SyncResult:
    """Result of syncing skills/agents into the registry."""

    added: int = 0
    updated: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_registry_db_path() -> Path:
    """Return the path to the registry database file."""
    override = os.environ.get("SKILLS_REGISTRY_PATH", "").strip()
    if override:
        return Path(override)
    return get_home() / _DEFAULT_DB_DIR / _DEFAULT_DB_NAME


def _get_schema_sql() -> str:
    """Return the DDL script contents."""
    # Dev/editable: src/ai_setup_forge/ -> src/ -> project root -> skills-registry/
    pkg_dir = Path(__file__).resolve().parent
    project_root = pkg_dir.parent.parent
    schema_path = project_root / "skills-registry" / "schema.sql"
    if schema_path.is_file():
        return schema_path.read_text(encoding="utf-8")
    # Installed package: bundled next to modules
    alt = pkg_dir / "registry_data" / "schema.sql"
    if alt.is_file():
        return alt.read_text(encoding="utf-8")
    raise FileNotFoundError("schema.sql not found — package may be corrupted")


def _get_bundled_map(filename: str) -> dict:
    """Load a bundled JSON mapping file (skills or agents)."""
    pkg_dir = Path(__file__).resolve().parent
    project_root = pkg_dir.parent.parent
    path = project_root / "skills-registry" / filename
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    alt = pkg_dir / "registry_data" / filename
    if alt.is_file():
        return json.loads(alt.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection to the registry database."""
    path = db_path or get_registry_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _db_exists(db_path: Path | None = None) -> bool:
    path = db_path or get_registry_db_path()
    return path.is_file() and path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def init_db(db_path: Path | None = None, force: bool = False) -> sqlite3.Connection:
    """Create the database and apply the schema.

    Args:
        db_path: Override database path.
        force: If True, drop all tables and recreate.

    Returns:
        An open connection to the initialized database.
    """
    path = db_path or get_registry_db_path()
    conn = get_connection(path)

    if force:
        # Disable FK checks during drop to avoid ordering issues
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS [{table}]")
        triggers = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        ]
        for trigger in triggers:
            conn.execute(f"DROP TRIGGER IF EXISTS [{trigger}]")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # Apply schema
    schema_sql = _get_schema_sql()
    conn.executescript(schema_sql)
    return conn


def ensure_registry(db_path: Path | None = None) -> sqlite3.Connection:
    """Open the registry, creating and seeding it if it doesn't exist.

    This is the main entry point for all commands that need the registry.
    It is idempotent — calling it multiple times is safe.
    """
    path = db_path or get_registry_db_path()
    needs_init = not _db_exists(path)

    if needs_init:
        conn = init_db(path)
        sync_bundled_skills(conn)
        sync_bundled_agents(conn)
        return conn

    return get_connection(path)


# ---------------------------------------------------------------------------
# Bundled sync
# ---------------------------------------------------------------------------


def _get_bundled_skills_dir() -> Path:
    """Return path to bundled skills/ directory."""
    from ai_setup_forge.source_parser import _get_bundled_skills_dir as _get_dir

    return _get_dir()


def _get_bundled_agents_dir() -> Path:
    """Return path to bundled agents/ directory."""
    pkg_dir = Path(__file__).resolve().parent
    project_root = pkg_dir.parent.parent
    agents_dir = project_root / "agents"
    if agents_dir.is_dir():
        return agents_dir
    alt = pkg_dir / "bundled_agents"
    return alt


def sync_bundled_skills(conn: sqlite3.Connection) -> SyncResult:
    """Sync bundled skills into the registry with installed=0."""
    from ai_setup_forge.skills import discover_skills

    result = SyncResult()
    skills_dir = _get_bundled_skills_dir()
    if not skills_dir.is_dir():
        return result

    skills_map = _get_bundled_map("bundled_skills_map.json")
    discovered = discover_skills(skills_dir, full_depth=True)

    for skill in discovered:
        try:
            upsert_skill(
                conn,
                name=skill.name,
                description=skill.description,
                origin="bundled",
                skill_path=str(skill.path),
                _commit=False,
            )
            mapping = skills_map.get(skill.name, {})
            cats = mapping.get("categories", [])
            tags = mapping.get("tags", [])
            if cats:
                add_categories(conn, skill.name, cats, _commit=False)
            if tags:
                add_tags(conn, skill.name, tags, _commit=False)
            result.added += 1
        except Exception as e:
            if result.errors is not None:
                result.errors.append(f"{skill.name}: {e}")

    conn.commit()
    return result


def sync_bundled_agents(conn: sqlite3.Connection) -> SyncResult:
    """Sync bundled agent definitions into the registry with installed=0."""
    import frontmatter

    result = SyncResult()
    agents_dir = _get_bundled_agents_dir()
    if not agents_dir.is_dir():
        return result

    agents_map = _get_bundled_map("bundled_agents_map.json")

    for agent_file in agents_dir.glob("*.agent.md"):
        name = agent_file.stem  # e.g. "docs-agent" from "docs-agent.agent.md"
        try:
            post = frontmatter.load(str(agent_file))
            data = dict(post.metadata)
            description = data.get("description", "")
            model = data.get("model")
            version = data.get("version")
            category = data.get("category")
            target = data.get("target")

            # Parse tools list
            raw_tools = data.get("tools")
            tools: list[str] | None = None
            if isinstance(raw_tools, list):
                tools = [str(t) for t in raw_tools]
            elif isinstance(raw_tools, str):
                tools = [raw_tools]

            # Use mapping category if not in frontmatter
            mapping = agents_map.get(name, {})
            if not category:
                category = mapping.get("category")

            upsert_agent_def(
                conn,
                name=name,
                description=description if isinstance(description, str) else "",
                origin="bundled",
                agent_path=str(agent_file),
                model=model if isinstance(model, str) else None,
                version=version if isinstance(version, str) else None,
                category=category if isinstance(category, str) else None,
                tools=tools,
                target=target if isinstance(target, str) else None,
                _commit=False,
            )
            tags = mapping.get("tags", [])
            if tags:
                add_agent_def_tags(conn, name, tags, _commit=False)
            result.added += 1
        except Exception as e:
            if result.errors is not None:
                result.errors.append(f"{name}: {e}")

    conn.commit()
    return result


def sync_skills_from_dir(
    conn: sqlite3.Connection,
    source_dir: Path,
    origin: str = "unknown",
    validate: bool = False,
) -> SyncResult:
    """Scan a directory and populate the registry with discovered skills."""
    from ai_setup_forge.skills import discover_skills

    result = SyncResult()
    discovered = discover_skills(source_dir, full_depth=True)

    for skill in discovered:
        try:
            existing = get_skill(conn, skill.name)
            if existing:
                # Update but don't change installed or origin
                conn.execute(
                    """UPDATE skills SET description = ?, skill_path = ?
                       WHERE name = ?""",
                    (skill.description, str(skill.path), skill.name),
                )
                result.updated += 1
            else:
                upsert_skill(
                    conn,
                    name=skill.name,
                    description=skill.description,
                    origin=origin,
                    skill_path=str(skill.path),
                    _commit=False,
                )
                result.added += 1

            if validate:
                from ai_setup_forge.validator import validate_skill_path

                vr = validate_skill_path(skill.path)
                set_validated(conn, skill.name, vr.valid, _commit=False)

        except Exception as e:
            if result.errors is not None:
                result.errors.append(f"{skill.name}: {e}")

    conn.commit()
    return result


# ---------------------------------------------------------------------------
# Skills CRUD
# ---------------------------------------------------------------------------


def upsert_skill(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    origin: str,
    source_url: str | None = None,
    author: str | None = None,
    version: str | None = None,
    license_: str | None = None,
    skill_path: str | None = None,
    *,
    _commit: bool = True,
) -> int:
    """Insert or update a skill in the registry. Returns the skill ID."""
    conn.execute(
        """INSERT INTO skills
           (name, description, origin, source_url, author, version, license, skill_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
               description = excluded.description,
               source_url = COALESCE(excluded.source_url, skills.source_url),
               author = COALESCE(excluded.author, skills.author),
               version = COALESCE(excluded.version, skills.version),
               license = COALESCE(excluded.license, skills.license),
               skill_path = COALESCE(excluded.skill_path, skills.skill_path)""",
        (name, description, origin, source_url, author, version, license_, skill_path),
    )
    if _commit:
        conn.commit()
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
    return row[0]


def get_skill(conn: sqlite3.Connection, name: str) -> dict | None:
    """Get a skill by name. Returns a dict or None."""
    row = conn.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    skill = dict(row)
    # Enrich with categories and tags
    skill["categories"] = [
        r[0]
        for r in conn.execute(
            """SELECT c.name FROM categories c
               JOIN skill_categories sc ON c.id = sc.category_id
               WHERE sc.skill_id = ?""",
            (skill["id"],),
        ).fetchall()
    ]
    skill["tags"] = [
        r[0]
        for r in conn.execute(
            """SELECT t.name FROM tags t
               JOIN skill_tags st ON t.id = st.tag_id
               WHERE st.skill_id = ?""",
            (skill["id"],),
        ).fetchall()
    ]
    skill["agents"] = [
        {"agent_name": r[0], "scope": r[1]}
        for r in conn.execute(
            "SELECT agent_name, scope FROM skill_agents WHERE skill_id = ?",
            (skill["id"],),
        ).fetchall()
    ]
    return skill


def remove_skill_entry(conn: sqlite3.Connection, name: str) -> bool:
    """Remove a skill from the registry entirely. Returns True if found."""
    cursor = conn.execute("DELETE FROM skills WHERE name = ?", (name,))
    conn.commit()
    return cursor.rowcount > 0


def list_skills(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    tag: str | None = None,
    origin: str | None = None,
    installed: bool | None = None,
    validated: bool | None = None,
) -> list[dict]:
    """List skills with optional filters."""
    query = "SELECT DISTINCT s.* FROM skills s"
    joins: list[str] = []
    conditions: list[str] = []
    params: list[object] = []

    if category:
        joins.append("JOIN skill_categories sc ON s.id = sc.skill_id")
        joins.append("JOIN categories c ON sc.category_id = c.id")
        conditions.append("c.name = ?")
        params.append(category)

    if tag:
        joins.append("JOIN skill_tags st ON s.id = st.skill_id")
        joins.append("JOIN tags t ON st.tag_id = t.id")
        conditions.append("t.name = ?")
        params.append(tag)

    if origin is not None:
        conditions.append("s.origin = ?")
        params.append(origin)

    if installed is not None:
        conditions.append("s.installed = ?")
        params.append(1 if installed else 0)

    if validated is not None:
        conditions.append("s.validated = ?")
        params.append(1 if validated else 0)

    sql = query + " " + " ".join(joins)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY s.name"

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        skill = dict(row)
        skill["categories"] = [
            r[0]
            for r in conn.execute(
                """SELECT c.name FROM categories c
                   JOIN skill_categories sc ON c.id = sc.category_id
                   WHERE sc.skill_id = ?""",
                (skill["id"],),
            ).fetchall()
        ]
        skill["tags"] = [
            r[0]
            for r in conn.execute(
                """SELECT t.name FROM tags t
                   JOIN skill_tags st ON t.id = st.tag_id
                   WHERE st.skill_id = ?""",
                (skill["id"],),
            ).fetchall()
        ]
        results.append(skill)
    return results


def search_skills(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Search skills by name, description, tags, or categories."""
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT DISTINCT s.* FROM skills s
           LEFT JOIN skill_tags st ON s.id = st.skill_id
           LEFT JOIN tags t ON st.tag_id = t.id
           LEFT JOIN skill_categories sc ON s.id = sc.skill_id
           LEFT JOIN categories c ON sc.category_id = c.id
           WHERE s.name LIKE ? OR s.description LIKE ?
                 OR t.name LIKE ? OR c.name LIKE ?
           ORDER BY s.name""",
        (like, like, like, like),
    ).fetchall()

    results = []
    for row in rows:
        skill = dict(row)
        skill["categories"] = [
            r[0]
            for r in conn.execute(
                """SELECT c.name FROM categories c
                   JOIN skill_categories sc ON c.id = sc.category_id
                   WHERE sc.skill_id = ?""",
                (skill["id"],),
            ).fetchall()
        ]
        skill["tags"] = [
            r[0]
            for r in conn.execute(
                """SELECT t.name FROM tags t
                   JOIN skill_tags st ON t.id = st.tag_id
                   WHERE st.skill_id = ?""",
                (skill["id"],),
            ).fetchall()
        ]
        results.append(skill)
    return results


# ---------------------------------------------------------------------------
# Install tracking
# ---------------------------------------------------------------------------


def mark_installed(
    conn: sqlite3.Connection,
    skill_name: str,
    agents: list[str],
    scope: str,
    source_url: str | None = None,
    origin: str | None = None,
) -> None:
    """Mark a skill as installed for given agents."""
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (skill_name,)).fetchone()
    if not row:
        return

    skill_id = row[0]
    conn.execute(
        """UPDATE skills SET installed = 1,
               installed_at = COALESCE(installed_at, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
           WHERE id = ?""",
        (skill_id,),
    )
    if source_url:
        conn.execute("UPDATE skills SET source_url = ? WHERE id = ?", (source_url, skill_id))
    if origin:
        conn.execute("UPDATE skills SET origin = ? WHERE id = ?", (origin, skill_id))

    for agent_name in agents:
        conn.execute(
            """INSERT OR IGNORE INTO skill_agents (skill_id, agent_name, scope)
               VALUES (?, ?, ?)""",
            (skill_id, agent_name, scope),
        )
    conn.commit()


def mark_uninstalled(
    conn: sqlite3.Connection,
    skill_name: str,
    agents: list[str] | None = None,
    scope: str = "project",
) -> None:
    """Mark a skill as uninstalled for given agents (or all)."""
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (skill_name,)).fetchone()
    if not row:
        return

    skill_id = row[0]
    if agents is None:
        conn.execute("DELETE FROM skill_agents WHERE skill_id = ?", (skill_id,))
    else:
        for agent_name in agents:
            conn.execute(
                "DELETE FROM skill_agents WHERE skill_id = ? AND agent_name = ? AND scope = ?",
                (skill_id, agent_name, scope),
            )

    # Check if any agents remain
    remaining = conn.execute(
        "SELECT COUNT(*) FROM skill_agents WHERE skill_id = ?", (skill_id,)
    ).fetchone()[0]

    if remaining == 0:
        conn.execute(
            "UPDATE skills SET installed = 0, installed_at = NULL WHERE id = ?",
            (skill_id,),
        )
    conn.commit()


def set_validated(
    conn: sqlite3.Connection, skill_name: str, valid: bool, *, _commit: bool = True
) -> None:
    """Set the validated flag for a skill."""
    conn.execute(
        "UPDATE skills SET validated = ? WHERE name = ?",
        (1 if valid else 0, skill_name),
    )
    if _commit:
        conn.commit()


# ---------------------------------------------------------------------------
# Agent definitions CRUD
# ---------------------------------------------------------------------------


def upsert_agent_def(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    origin: str,
    source_url: str | None = None,
    version: str | None = None,
    category: str | None = None,
    model: str | None = None,
    agent_path: str | None = None,
    tools: list[str] | None = None,
    target: str | None = None,
    *,
    _commit: bool = True,
) -> int:
    """Insert or update an agent definition. Returns the agent def ID."""
    tools_json = json.dumps(tools) if tools is not None else None
    conn.execute(
        """INSERT INTO agent_definitions
           (name, description, origin, source_url, version,
            category, model, agent_path, tools, target)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
               description = excluded.description,
               source_url = COALESCE(excluded.source_url, agent_definitions.source_url),
               version = COALESCE(excluded.version, agent_definitions.version),
               category = COALESCE(excluded.category, agent_definitions.category),
               model = COALESCE(excluded.model, agent_definitions.model),
               agent_path = COALESCE(excluded.agent_path, agent_definitions.agent_path),
               tools = excluded.tools,
               target = excluded.target""",
        (
            name,
            description,
            origin,
            source_url,
            version,
            category,
            model,
            agent_path,
            tools_json,
            target,
        ),
    )
    if _commit:
        conn.commit()
    row = conn.execute("SELECT id FROM agent_definitions WHERE name = ?", (name,)).fetchone()
    return row[0]


def get_agent_def(conn: sqlite3.Connection, name: str) -> dict | None:
    """Get an agent definition by name."""
    row = conn.execute("SELECT * FROM agent_definitions WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    agent_def = dict(row)
    # Deserialize tools JSON
    if agent_def.get("tools") and isinstance(agent_def["tools"], str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            agent_def["tools"] = json.loads(agent_def["tools"])
    agent_def["tags"] = [
        r[0]
        for r in conn.execute(
            """SELECT t.name FROM tags t
               JOIN agent_def_tags adt ON t.id = adt.tag_id
               WHERE adt.agent_def_id = ?""",
            (agent_def["id"],),
        ).fetchall()
    ]
    agent_def["coding_agents"] = [
        {"coding_agent_name": r[0], "scope": r[1]}
        for r in conn.execute(
            "SELECT coding_agent_name, scope FROM agent_def_coding_agents WHERE agent_def_id = ?",
            (agent_def["id"],),
        ).fetchall()
    ]
    return agent_def


def list_agent_defs(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    tag: str | None = None,
    installed: bool | None = None,
) -> list[dict]:
    """List agent definitions with optional filters."""
    query = "SELECT DISTINCT ad.* FROM agent_definitions ad"
    joins: list[str] = []
    conditions: list[str] = []
    params: list[object] = []

    if tag:
        joins.append("JOIN agent_def_tags adt ON ad.id = adt.agent_def_id")
        joins.append("JOIN tags t ON adt.tag_id = t.id")
        conditions.append("t.name = ?")
        params.append(tag)

    if category is not None:
        conditions.append("ad.category = ?")
        params.append(category)

    if installed is not None:
        conditions.append("ad.installed = ?")
        params.append(1 if installed else 0)

    sql = query + " " + " ".join(joins)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY ad.name"

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        ad = dict(row)
        ad["tags"] = [
            r[0]
            for r in conn.execute(
                """SELECT t.name FROM tags t
                   JOIN agent_def_tags adt ON t.id = adt.tag_id
                   WHERE adt.agent_def_id = ?""",
                (ad["id"],),
            ).fetchall()
        ]
        results.append(ad)
    return results


def search_agent_defs(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Search agent definitions by name, description, tags, or category."""
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT DISTINCT ad.* FROM agent_definitions ad
           LEFT JOIN agent_def_tags adt ON ad.id = adt.agent_def_id
           LEFT JOIN tags t ON adt.tag_id = t.id
           WHERE ad.name LIKE ? OR ad.description LIKE ?
                 OR ad.category LIKE ? OR t.name LIKE ?
           ORDER BY ad.name""",
        (like, like, like, like),
    ).fetchall()

    results = []
    for row in rows:
        ad = dict(row)
        ad["tags"] = [
            r[0]
            for r in conn.execute(
                """SELECT t.name FROM tags t
                   JOIN agent_def_tags adt ON t.id = adt.tag_id
                   WHERE adt.agent_def_id = ?""",
                (ad["id"],),
            ).fetchall()
        ]
        results.append(ad)
    return results


def mark_agent_installed(
    conn: sqlite3.Connection,
    agent_def_name: str,
    coding_agents: list[str],
    scope: str,
) -> None:
    """Mark an agent definition as installed for given coding tools."""
    row = conn.execute(
        "SELECT id FROM agent_definitions WHERE name = ?", (agent_def_name,)
    ).fetchone()
    if not row:
        return

    ad_id = row[0]
    conn.execute(
        """UPDATE agent_definitions SET installed = 1,
               installed_at = COALESCE(installed_at, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
           WHERE id = ?""",
        (ad_id,),
    )

    for ca_name in coding_agents:
        conn.execute(
            """INSERT OR IGNORE INTO agent_def_coding_agents
               (agent_def_id, coding_agent_name, scope)
               VALUES (?, ?, ?)""",
            (ad_id, ca_name, scope),
        )
    conn.commit()


def mark_agent_uninstalled(
    conn: sqlite3.Connection,
    agent_def_name: str,
    coding_agents: list[str] | None = None,
    scope: str = "project",
) -> None:
    """Mark an agent definition as uninstalled."""
    row = conn.execute(
        "SELECT id FROM agent_definitions WHERE name = ?", (agent_def_name,)
    ).fetchone()
    if not row:
        return

    ad_id = row[0]
    if coding_agents is None:
        conn.execute("DELETE FROM agent_def_coding_agents WHERE agent_def_id = ?", (ad_id,))
    else:
        for ca_name in coding_agents:
            conn.execute(
                """DELETE FROM agent_def_coding_agents
                   WHERE agent_def_id = ? AND coding_agent_name = ? AND scope = ?""",
                (ad_id, ca_name, scope),
            )

    remaining = conn.execute(
        "SELECT COUNT(*) FROM agent_def_coding_agents WHERE agent_def_id = ?", (ad_id,)
    ).fetchone()[0]

    if remaining == 0:
        conn.execute(
            "UPDATE agent_definitions SET installed = 0, installed_at = NULL WHERE id = ?",
            (ad_id,),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Classification: tags & categories
# ---------------------------------------------------------------------------


def _ensure_tag(conn: sqlite3.Connection, tag_name: str) -> int:
    """Get or create a tag, return its ID."""
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    return row[0]


def _ensure_category(conn: sqlite3.Connection, cat_name: str) -> int:
    """Get or create a category, return its ID."""
    conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat_name,))
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (cat_name,)).fetchone()
    return row[0]


def add_tags(
    conn: sqlite3.Connection, skill_name: str, tags: list[str], *, _commit: bool = True
) -> None:
    """Add tags to a skill."""
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (skill_name,)).fetchone()
    if not row:
        return
    skill_id = row[0]
    for tag in tags:
        tag_id = _ensure_tag(conn, tag)
        conn.execute(
            "INSERT OR IGNORE INTO skill_tags (skill_id, tag_id) VALUES (?, ?)",
            (skill_id, tag_id),
        )
    if _commit:
        conn.commit()


def remove_tags(conn: sqlite3.Connection, skill_name: str, tags: list[str]) -> None:
    """Remove tags from a skill."""
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (skill_name,)).fetchone()
    if not row:
        return
    skill_id = row[0]
    for tag in tags:
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
        if tag_row:
            conn.execute(
                "DELETE FROM skill_tags WHERE skill_id = ? AND tag_id = ?",
                (skill_id, tag_row[0]),
            )
    conn.commit()


def add_categories(
    conn: sqlite3.Connection, skill_name: str, categories: list[str], *, _commit: bool = True
) -> None:
    """Assign categories to a skill."""
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (skill_name,)).fetchone()
    if not row:
        return
    skill_id = row[0]
    for cat in categories:
        cat_id = _ensure_category(conn, cat)
        conn.execute(
            "INSERT OR IGNORE INTO skill_categories (skill_id, category_id) VALUES (?, ?)",
            (skill_id, cat_id),
        )
    if _commit:
        conn.commit()


def remove_categories(conn: sqlite3.Connection, skill_name: str, categories: list[str]) -> None:
    """Remove categories from a skill."""
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (skill_name,)).fetchone()
    if not row:
        return
    skill_id = row[0]
    for cat in categories:
        cat_row = conn.execute("SELECT id FROM categories WHERE name = ?", (cat,)).fetchone()
        if cat_row:
            conn.execute(
                "DELETE FROM skill_categories WHERE skill_id = ? AND category_id = ?",
                (skill_id, cat_row[0]),
            )
    conn.commit()


def set_origin(conn: sqlite3.Connection, skill_name: str, origin: str) -> None:
    """Update the origin of a skill."""
    valid = ("bundled", "github", "gitlab", "website", "homemade", "unknown")
    if origin not in valid:
        raise ValueError(f"Invalid origin '{origin}'. Must be one of: {', '.join(valid)}")
    conn.execute("UPDATE skills SET origin = ? WHERE name = ?", (origin, skill_name))
    conn.commit()


def add_agent_def_tags(
    conn: sqlite3.Connection, agent_def_name: str, tags: list[str], *, _commit: bool = True
) -> None:
    """Add tags to an agent definition."""
    row = conn.execute(
        "SELECT id FROM agent_definitions WHERE name = ?", (agent_def_name,)
    ).fetchone()
    if not row:
        return
    ad_id = row[0]
    for tag in tags:
        tag_id = _ensure_tag(conn, tag)
        conn.execute(
            "INSERT OR IGNORE INTO agent_def_tags (agent_def_id, tag_id) VALUES (?, ?)",
            (ad_id, tag_id),
        )
    if _commit:
        conn.commit()


def remove_agent_def_tags(conn: sqlite3.Connection, agent_def_name: str, tags: list[str]) -> None:
    """Remove tags from an agent definition."""
    row = conn.execute(
        "SELECT id FROM agent_definitions WHERE name = ?", (agent_def_name,)
    ).fetchone()
    if not row:
        return
    ad_id = row[0]
    for tag in tags:
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
        if tag_row:
            conn.execute(
                "DELETE FROM agent_def_tags WHERE agent_def_id = ? AND tag_id = ?",
                (ad_id, tag_row[0]),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def get_stats(conn: sqlite3.Connection) -> dict:
    """Return registry statistics."""
    total = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    installed = conn.execute("SELECT COUNT(*) FROM skills WHERE installed = 1").fetchone()[0]
    validated = conn.execute("SELECT COUNT(*) FROM skills WHERE validated = 1").fetchone()[0]

    by_origin = {}
    for row in conn.execute("SELECT origin, COUNT(*) FROM skills GROUP BY origin").fetchall():
        by_origin[row[0]] = row[1]

    by_category = {}
    for row in conn.execute(
        """SELECT c.name, COUNT(DISTINCT sc.skill_id)
           FROM categories c
           JOIN skill_categories sc ON c.id = sc.category_id
           GROUP BY c.name ORDER BY COUNT(DISTINCT sc.skill_id) DESC"""
    ).fetchall():
        by_category[row[0]] = row[1]

    top_tags = {}
    for row in conn.execute(
        """SELECT t.name, COUNT(DISTINCT st.skill_id)
           FROM tags t
           JOIN skill_tags st ON t.id = st.tag_id
           GROUP BY t.name ORDER BY COUNT(DISTINCT st.skill_id) DESC
           LIMIT 20"""
    ).fetchall():
        top_tags[row[0]] = row[1]

    # Agent definitions stats
    total_agents = conn.execute("SELECT COUNT(*) FROM agent_definitions").fetchone()[0]
    installed_agents = conn.execute(
        "SELECT COUNT(*) FROM agent_definitions WHERE installed = 1"
    ).fetchone()[0]

    return {
        "skills": {
            "total": total,
            "installed": installed,
            "not_installed": total - installed,
            "validated": validated,
            "by_origin": by_origin,
            "by_category": by_category,
            "top_tags": top_tags,
        },
        "agent_definitions": {
            "total": total_agents,
            "installed": installed_agents,
            "not_installed": total_agents - installed_agents,
        },
    }


# ---------------------------------------------------------------------------
# Origin derivation
# ---------------------------------------------------------------------------


def derive_origin(source_type: str) -> str:
    """Derive registry origin from ParsedSource.type."""
    mapping = {
        "bundled": "bundled",
        "github": "github",
        "gitlab": "gitlab",
        "local": "homemade",
        "git": "github",
        "direct-url": "website",
    }
    return mapping.get(source_type, "unknown")

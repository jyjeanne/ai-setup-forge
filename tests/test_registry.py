"""Tests for ai_setup_forge.registry module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ai_setup_forge.registry import (
    add_agent_def_tags,
    add_categories,
    add_tags,
    derive_origin,
    ensure_registry,
    get_agent_def,
    get_skill,
    get_stats,
    init_db,
    list_agent_defs,
    list_skills,
    mark_agent_installed,
    mark_agent_uninstalled,
    mark_installed,
    mark_uninstalled,
    remove_categories,
    remove_skill_entry,
    remove_tags,
    search_agent_defs,
    search_skills,
    set_origin,
    set_validated,
    sync_bundled_agents,
    sync_bundled_skills,
    upsert_agent_def,
    upsert_skill,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_registry.db"


@pytest.fixture
def conn(db_path: Path) -> sqlite3.Connection:
    """Return an initialized, empty registry connection."""
    c = init_db(db_path)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_creates_database(self, db_path: Path) -> None:
        conn = init_db(db_path)
        assert db_path.is_file()
        # Check tables exist
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "skills" in tables
        assert "categories" in tables
        assert "tags" in tables
        assert "skill_categories" in tables
        assert "skill_tags" in tables
        assert "skill_agents" in tables
        assert "agent_definitions" in tables
        assert "registry_meta" in tables
        conn.close()

    def test_seeds_categories(self, db_path: Path) -> None:
        conn = init_db(db_path)
        cats = [r[0] for r in conn.execute("SELECT name FROM categories").fetchall()]
        assert "architecture" in cats
        assert "testing" in cats
        assert "web" in cats
        assert "marketing" in cats
        conn.close()

    def test_force_reinit(self, db_path: Path) -> None:
        conn = init_db(db_path)
        # Add a skill
        upsert_skill(conn, "test-skill", "desc", "bundled")
        conn.commit()
        conn.close()

        # Force reinit drops everything
        conn2 = init_db(db_path, force=True)
        row = conn2.execute("SELECT COUNT(*) FROM skills").fetchone()
        assert row[0] == 0
        conn2.close()

    def test_schema_version(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT value FROM registry_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == "1"


class TestEnsureRegistry:
    def test_creates_on_first_use(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_path = tmp_path / "auto_init.db"
        monkeypatch.setenv("SKILLS_REGISTRY_PATH", str(db_path))
        conn = ensure_registry(db_path)
        assert db_path.is_file()
        # Should have synced bundled skills
        count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        assert count > 0
        conn.close()

    def test_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "idempotent.db"
        conn1 = ensure_registry(db_path)
        count1 = conn1.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        conn1.close()

        conn2 = ensure_registry(db_path)
        count2 = conn2.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        assert count2 == count1
        conn2.close()


# ---------------------------------------------------------------------------
# Skills CRUD
# ---------------------------------------------------------------------------


class TestUpsertSkill:
    def test_insert(self, conn: sqlite3.Connection) -> None:
        skill_id = upsert_skill(conn, "my-skill", "A test skill", "homemade")
        conn.commit()
        assert skill_id > 0

        row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        assert row["name"] == "my-skill"
        assert row["description"] == "A test skill"
        assert row["origin"] == "homemade"
        assert row["installed"] == 0

    def test_update_on_conflict(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "my-skill", "v1", "homemade")
        conn.commit()
        upsert_skill(conn, "my-skill", "v2", "github", source_url="https://example.com")
        conn.commit()

        row = conn.execute("SELECT * FROM skills WHERE name = 'my-skill'").fetchone()
        assert row["description"] == "v2"
        assert row["source_url"] == "https://example.com"

    def test_coalesce_preserves_existing(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "my-skill", "desc", "homemade", author="alice")
        conn.commit()
        # Second upsert without author should keep "alice"
        upsert_skill(conn, "my-skill", "desc2", "homemade")
        conn.commit()
        row = conn.execute("SELECT author FROM skills WHERE name = 'my-skill'").fetchone()
        assert row[0] == "alice"


class TestGetSkill:
    def test_found(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "test", "desc", "bundled")
        conn.commit()
        add_tags(conn, "test", ["java", "spring"])
        conn.commit()
        add_categories(conn, "test", ["web"])
        conn.commit()

        skill = get_skill(conn, "test")
        assert skill is not None
        assert skill["name"] == "test"
        assert set(skill["tags"]) == {"java", "spring"}
        assert skill["categories"] == ["web"]

    def test_not_found(self, conn: sqlite3.Connection) -> None:
        assert get_skill(conn, "nonexistent") is None


class TestRemoveSkillEntry:
    def test_remove(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "to-delete", "desc", "homemade")
        conn.commit()
        assert remove_skill_entry(conn, "to-delete") is True
        assert get_skill(conn, "to-delete") is None

    def test_remove_nonexistent(self, conn: sqlite3.Connection) -> None:
        assert remove_skill_entry(conn, "nope") is False


class TestListSkills:
    def test_list_all(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "desc-a", "bundled")
        upsert_skill(conn, "b", "desc-b", "github")
        conn.commit()
        results = list_skills(conn)
        assert len(results) == 2
        assert results[0]["name"] == "a"

    def test_filter_by_origin(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "desc", "bundled")
        upsert_skill(conn, "b", "desc", "github")
        conn.commit()
        results = list_skills(conn, origin="bundled")
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_filter_by_installed(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "d", "bundled")
        upsert_skill(conn, "b", "d", "bundled")
        conn.commit()
        mark_installed(conn, "a", ["claude-code"], "project")
        results = list_skills(conn, installed=True)
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_filter_by_category(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "d", "bundled")
        upsert_skill(conn, "b", "d", "bundled")
        conn.commit()
        add_categories(conn, "a", ["web"])
        conn.commit()
        results = list_skills(conn, category="web")
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_filter_by_tag(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "d", "bundled")
        upsert_skill(conn, "b", "d", "bundled")
        conn.commit()
        add_tags(conn, "a", ["java"])
        conn.commit()
        results = list_skills(conn, tag="java")
        assert len(results) == 1


class TestSearchSkills:
    def test_search_by_name(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "clean-code", "Write clean code", "bundled")
        upsert_skill(conn, "debugging", "Debug issues", "bundled")
        conn.commit()
        results = search_skills(conn, "clean")
        assert len(results) == 1
        assert results[0]["name"] == "clean-code"

    def test_search_by_description(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "my-skill", "Uses Java and Spring", "bundled")
        conn.commit()
        results = search_skills(conn, "Java")
        assert len(results) == 1

    def test_search_by_tag(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "desc", "bundled")
        conn.commit()
        add_tags(conn, "a", ["playwright"])
        conn.commit()
        results = search_skills(conn, "playwright")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Install tracking
# ---------------------------------------------------------------------------


class TestMarkInstalled:
    def test_mark_installed(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        mark_installed(conn, "s1", ["claude-code", "mistral-vibe"], "project")

        skill = get_skill(conn, "s1")
        assert skill is not None
        assert skill["installed"] == 1
        assert skill["installed_at"] is not None
        assert len(skill["agents"]) == 2

    def test_mark_uninstalled_partial(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        mark_installed(conn, "s1", ["claude-code", "mistral-vibe"], "project")

        # Remove from one agent
        mark_uninstalled(conn, "s1", ["claude-code"], "project")
        skill = get_skill(conn, "s1")
        assert skill is not None
        assert skill["installed"] == 1  # still installed for mistral-vibe
        assert len(skill["agents"]) == 1

    def test_mark_uninstalled_all(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        mark_installed(conn, "s1", ["claude-code"], "project")
        mark_uninstalled(conn, "s1")  # all agents

        skill = get_skill(conn, "s1")
        assert skill is not None
        assert skill["installed"] == 0
        assert skill["installed_at"] is None


class TestSetValidated:
    def test_set_validated(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        set_validated(conn, "s1", True)
        row = conn.execute("SELECT validated FROM skills WHERE name = 's1'").fetchone()
        assert row[0] == 1

    def test_set_not_validated(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        set_validated(conn, "s1", True)
        set_validated(conn, "s1", False)
        row = conn.execute("SELECT validated FROM skills WHERE name = 's1'").fetchone()
        assert row[0] == 0


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestTagsAndCategories:
    def test_add_and_remove_tags(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        add_tags(conn, "s1", ["java", "spring"])
        conn.commit()
        skill = get_skill(conn, "s1")
        assert set(skill["tags"]) == {"java", "spring"}

        remove_tags(conn, "s1", ["spring"])
        skill = get_skill(conn, "s1")
        assert skill["tags"] == ["java"]

    def test_add_and_remove_categories(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "bundled")
        conn.commit()
        add_categories(conn, "s1", ["web", "testing"])
        conn.commit()
        skill = get_skill(conn, "s1")
        assert set(skill["categories"]) == {"web", "testing"}

        remove_categories(conn, "s1", ["testing"])
        skill = get_skill(conn, "s1")
        assert skill["categories"] == ["web"]

    def test_set_origin(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "unknown")
        conn.commit()
        set_origin(conn, "s1", "github")
        row = conn.execute("SELECT origin FROM skills WHERE name = 's1'").fetchone()
        assert row[0] == "github"

    def test_set_invalid_origin(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s1", "desc", "unknown")
        conn.commit()
        with pytest.raises(ValueError, match="Invalid origin"):
            set_origin(conn, "s1", "invalid")


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------


class TestAgentDefs:
    def test_upsert_and_get(self, conn: sqlite3.Connection) -> None:
        ad_id = upsert_agent_def(
            conn,
            "docs-agent",
            "Write docs",
            "bundled",
            category="documentation",
            model="Claude Opus 4.6",
        )
        conn.commit()
        assert ad_id > 0

        ad = get_agent_def(conn, "docs-agent")
        assert ad is not None
        assert ad["name"] == "docs-agent"
        assert ad["category"] == "documentation"
        assert ad["model"] == "Claude Opus 4.6"

    def test_upsert_with_tools_and_target(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(
            conn,
            "my-agent",
            "desc",
            "bundled",
            tools=["read", "edit", "search"],
            target="github-copilot",
        )
        ad = get_agent_def(conn, "my-agent")
        assert ad is not None
        assert ad["tools"] == ["read", "edit", "search"]
        assert ad["target"] == "github-copilot"

    def test_upsert_no_tools_means_null(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(conn, "my-agent", "desc", "bundled")
        ad = get_agent_def(conn, "my-agent")
        assert ad is not None
        assert ad["tools"] is None

    def test_mark_agent_uninstalled_partial(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(conn, "a", "d", "bundled")
        conn.commit()
        mark_agent_installed(conn, "a", ["claude-code", "github-copilot"], "project")
        mark_agent_uninstalled(conn, "a", ["claude-code"], "project")
        ad = get_agent_def(conn, "a")
        assert ad is not None
        assert ad["installed"] == 1  # Still installed for github-copilot
        assert len(ad["coding_agents"]) == 1
        assert ad["coding_agents"][0]["coding_agent_name"] == "github-copilot"

    def test_list_agent_defs(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(conn, "a", "d", "bundled", category="testing")
        upsert_agent_def(conn, "b", "d", "bundled", category="documentation")
        conn.commit()
        results = list_agent_defs(conn)
        assert len(results) == 2

        results = list_agent_defs(conn, category="testing")
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_mark_agent_installed(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(conn, "a", "d", "bundled")
        conn.commit()
        mark_agent_installed(conn, "a", ["claude-code", "github-copilot"], "project")
        ad = get_agent_def(conn, "a")
        assert ad is not None
        assert ad["installed"] == 1
        assert len(ad["coding_agents"]) == 2

    def test_mark_agent_uninstalled(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(conn, "a", "d", "bundled")
        conn.commit()
        mark_agent_installed(conn, "a", ["claude-code"], "project")
        mark_agent_uninstalled(conn, "a")
        ad = get_agent_def(conn, "a")
        assert ad is not None
        assert ad["installed"] == 0


# ---------------------------------------------------------------------------
# Bundled sync
# ---------------------------------------------------------------------------


class TestBundledSync:
    def test_sync_bundled_skills(self, conn: sqlite3.Connection) -> None:
        result = sync_bundled_skills(conn)
        assert result.added > 0
        # Should have categories/tags from mapping
        skill = get_skill(conn, "clean-architecture")
        if skill:
            assert "architecture" in skill["categories"]
            assert "solid" in skill["tags"]

    def test_sync_bundled_agents(self, conn: sqlite3.Connection) -> None:
        result = sync_bundled_agents(conn)
        assert result.added > 0
        ad = get_agent_def(conn, "docs-agent")
        if ad:
            assert ad["origin"] == "bundled"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestStats:
    def test_get_stats(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "a", "d", "bundled")
        upsert_skill(conn, "b", "d", "github")
        conn.commit()
        mark_installed(conn, "a", ["claude-code"], "project")
        add_tags(conn, "a", ["java"])
        conn.commit()
        add_categories(conn, "a", ["web"])
        conn.commit()

        stats = get_stats(conn)
        assert stats["skills"]["total"] == 2
        assert stats["skills"]["installed"] == 1
        assert stats["skills"]["not_installed"] == 1
        assert "bundled" in stats["skills"]["by_origin"]
        assert "web" in stats["skills"]["by_category"]
        assert "java" in stats["skills"]["top_tags"]


# ---------------------------------------------------------------------------
# Origin derivation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# _commit=False behavior
# ---------------------------------------------------------------------------


class TestCommitFalse:
    def test_upsert_skill_no_commit_rolls_back(self, conn: sqlite3.Connection) -> None:
        """When _commit=False the row is visible in the same transaction but gone after rollback."""
        upsert_skill(conn, "ephemeral", "desc", "bundled", _commit=False)
        # Row is visible within the current transaction
        row = conn.execute("SELECT name FROM skills WHERE name = 'ephemeral'").fetchone()
        assert row is not None

        conn.rollback()
        row = conn.execute("SELECT name FROM skills WHERE name = 'ephemeral'").fetchone()
        assert row is None

    def test_upsert_agent_def_no_commit_rolls_back(self, conn: sqlite3.Connection) -> None:
        upsert_agent_def(conn, "tmp-agent", "desc", "bundled", _commit=False)
        row = conn.execute("SELECT name FROM agent_definitions WHERE name = 'tmp-agent'").fetchone()
        assert row is not None

        conn.rollback()
        row = conn.execute("SELECT name FROM agent_definitions WHERE name = 'tmp-agent'").fetchone()
        assert row is None

    def test_add_tags_no_commit_rolls_back(self, conn: sqlite3.Connection) -> None:
        upsert_skill(conn, "s", "d", "bundled")
        conn.commit()
        add_tags(conn, "s", ["tag1"], _commit=False)

        tags_row = conn.execute(
            "SELECT t.name FROM tags t JOIN skill_tags st ON t.id = st.tag_id "
            "JOIN skills s ON s.id = st.skill_id WHERE s.name = 's'"
        ).fetchall()
        assert len(tags_row) == 1

        conn.rollback()
        tags_row = conn.execute(
            "SELECT t.name FROM tags t JOIN skill_tags st ON t.id = st.tag_id "
            "JOIN skills s ON s.id = st.skill_id WHERE s.name = 's'"
        ).fetchall()
        assert len(tags_row) == 0


# ---------------------------------------------------------------------------
# tools/target clearing via upsert_agent_def
# ---------------------------------------------------------------------------


class TestAgentDefToolsClearing:
    def test_tools_none_clears_existing_tools(self, conn: sqlite3.Connection) -> None:
        """Passing tools=None on update should clear previously set tools (not COALESCE)."""
        upsert_agent_def(
            conn,
            "agent-clear",
            "desc",
            "bundled",
            tools=["read", "edit"],
            target="github-copilot",
        )
        conn.commit()
        ad = get_agent_def(conn, "agent-clear")
        assert ad is not None
        assert ad["tools"] == ["read", "edit"]
        assert ad["target"] == "github-copilot"

        # Now upsert with tools=None and target=None — should clear them
        upsert_agent_def(conn, "agent-clear", "desc", "bundled", tools=None, target=None)
        conn.commit()
        ad = get_agent_def(conn, "agent-clear")
        assert ad is not None
        assert ad["tools"] is None
        assert ad["target"] is None

    def test_tools_replaced_not_merged(self, conn: sqlite3.Connection) -> None:
        """Updating tools should replace the list entirely, not merge."""
        upsert_agent_def(conn, "agent-rep", "desc", "bundled", tools=["read", "edit"])
        conn.commit()
        upsert_agent_def(conn, "agent-rep", "desc", "bundled", tools=["search"])
        conn.commit()
        ad = get_agent_def(conn, "agent-rep")
        assert ad is not None
        assert ad["tools"] == ["search"]


class TestDeriveOrigin:
    @pytest.mark.parametrize(
        "source_type,expected",
        [
            ("bundled", "bundled"),
            ("github", "github"),
            ("gitlab", "gitlab"),
            ("local", "homemade"),
            ("git", "github"),
            ("direct-url", "website"),
            ("unknown-type", "unknown"),
        ],
    )
    def test_derive_origin(self, source_type: str, expected: str) -> None:
        assert derive_origin(source_type) == expected


# ---------------------------------------------------------------------------
# Search agent definitions
# ---------------------------------------------------------------------------


class TestSearchAgentDefs:
    """Tests for search_agent_defs()."""

    def _seed(self, conn: sqlite3.Connection) -> None:
        """Insert a small set of agent defs for search tests."""
        upsert_agent_def(
            conn,
            "docs-writer",
            "Generate documentation from code",
            "bundled",
            category="documentation",
        )
        upsert_agent_def(
            conn,
            "test-runner",
            "Run and analyse test suites",
            "bundled",
            category="testing",
        )
        upsert_agent_def(
            conn,
            "api-designer",
            "Design REST APIs",
            "bundled",
            category="architecture",
        )
        conn.commit()
        add_agent_def_tags(conn, "docs-writer", ["markdown", "readme"])
        add_agent_def_tags(conn, "test-runner", ["pytest", "coverage"])
        add_agent_def_tags(conn, "api-designer", ["openapi", "rest"])

    def test_search_by_name(self, conn: sqlite3.Connection) -> None:
        self._seed(conn)
        results = search_agent_defs(conn, "docs")
        assert len(results) == 1
        assert results[0]["name"] == "docs-writer"

    def test_search_by_description(self, conn: sqlite3.Connection) -> None:
        self._seed(conn)
        results = search_agent_defs(conn, "test suites")
        assert len(results) == 1
        assert results[0]["name"] == "test-runner"

    def test_search_by_category(self, conn: sqlite3.Connection) -> None:
        self._seed(conn)
        results = search_agent_defs(conn, "architecture")
        assert len(results) == 1
        assert results[0]["name"] == "api-designer"

    def test_search_by_tag(self, conn: sqlite3.Connection) -> None:
        self._seed(conn)
        results = search_agent_defs(conn, "pytest")
        assert len(results) == 1
        assert results[0]["name"] == "test-runner"

    def test_no_results(self, conn: sqlite3.Connection) -> None:
        self._seed(conn)
        results = search_agent_defs(conn, "nonexistent-query-xyz")
        assert results == []

    def test_results_include_tags(self, conn: sqlite3.Connection) -> None:
        self._seed(conn)
        results = search_agent_defs(conn, "docs-writer")
        assert len(results) == 1
        assert set(results[0]["tags"]) == {"markdown", "readme"}

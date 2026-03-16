"""Tests for agent_defs.py — agent definition discovery, install, and remove."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ai_setup_forge.agent_defs import (
    create_agent_template,
    discover_agent_defs,
    find_installed_agent_defs,
    install_agent_def,
    parse_agent_md,
    remove_agent_def,
)
from ai_setup_forge.types import AgentDefinition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    """Create a temp dir with sample .agent.md files."""
    d = tmp_path / "agents"
    d.mkdir()

    (d / "docs-agent.agent.md").write_text(
        textwrap.dedent("""\
            ---
            name: docs-agent
            description: Expert technical writer
            model: Auto
            ---

            You are an expert technical writer.
        """),
        encoding="utf-8",
    )

    (d / "test-planner.agent.md").write_text(
        textwrap.dedent("""\
            ---
            name: test-planner
            description: Plans test strategies
            category: testing
            tools: ['read', 'search', 'execute']
            target: github-copilot
            disable-model-invocation: true
            user-invocable: false
            ---

            You plan test strategies.
        """),
        encoding="utf-8",
    )

    return d


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a project directory with .agents/ structure."""
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    return project


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverAgentDefs:
    def test_discover_all(self, agents_dir: Path) -> None:
        results = discover_agent_defs(agents_dir)
        assert len(results) == 2
        names = {ad.name for ad in results}
        assert names == {"docs-agent", "test-planner"}

    def test_discover_with_filter(self, agents_dir: Path) -> None:
        results = discover_agent_defs(agents_dir, names=["docs-agent"])
        assert len(results) == 1
        assert results[0].name == "docs-agent"

    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert discover_agent_defs(empty) == []

    def test_discover_nonexistent_dir(self, tmp_path: Path) -> None:
        assert discover_agent_defs(tmp_path / "nope") == []


class TestParseAgentMd:
    def test_parse_valid(self, agents_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None
        assert ad.name == "docs-agent"
        assert ad.description == "Expert technical writer"
        assert ad.model == "Auto"

    def test_parse_with_category(self, agents_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "test-planner.agent.md")
        assert ad is not None
        assert ad.category == "testing"

    def test_parse_tools_and_target(self, agents_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "test-planner.agent.md")
        assert ad is not None
        assert ad.tools == ["read", "search", "execute"]
        assert ad.target == "github-copilot"
        assert ad.disable_model_invocation is True
        assert ad.user_invocable is False

    def test_parse_no_tools_means_all(self, agents_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None
        assert ad.tools is None  # None = all tools

    def test_parse_no_name_uses_filename(self, tmp_path: Path) -> None:
        f = tmp_path / "my-agent.agent.md"
        f.write_text("---\ndescription: Test agent\n---\nHello\n", encoding="utf-8")
        ad = parse_agent_md(f)
        assert ad is not None
        assert ad.name == "my-agent"

    def test_parse_invalid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.agent.md"
        f.write_text("not valid frontmatter\x00\x01\x02", encoding="utf-8")
        # Should return something or None, not crash
        result = parse_agent_md(f)
        # Either parsed with fallback or returned None
        assert result is None or isinstance(result, AgentDefinition)


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

class TestInstallAgentDef:
    def test_install_creates_canonical_and_links(
        self, agents_dir: Path, project_dir: Path
    ) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        results = install_agent_def(ad, ["claude-code", "mistral-vibe"], mode="copy")

        # Canonical file should exist
        canonical = project_dir / ".agents" / "agent-definitions" / "docs-agent.agent.md"
        assert canonical.is_file()

        # Agent directories should have the file
        assert len(results) == 2
        for r in results:
            assert r["status"] == "ok"
            assert Path(r["path"]).is_file()

    def test_install_global(
        self, agents_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("ai_setup_forge.agent_defs.get_home", lambda: tmp_path)
        monkeypatch.setattr("ai_setup_forge.agents.get_home", lambda: tmp_path)

        # Need to update global paths for the test
        from ai_setup_forge.agents import AGENTS
        original_global_dirs = {}
        for name, config in AGENTS.items():
            original_global_dirs[name] = config.global_agents_dir
            config.global_agents_dir = tmp_path / f".{name}" / "agents"

        try:
            ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
            assert ad is not None

            results = install_agent_def(ad, ["claude-code"], is_global=True, mode="copy")

            canonical = tmp_path / ".agents" / "agent-definitions" / "docs-agent.agent.md"
            assert canonical.is_file()
            assert results[0]["status"] == "ok"
        finally:
            for name, dir_ in original_global_dirs.items():
                AGENTS[name].global_agents_dir = dir_

    def test_install_unknown_agent(self, agents_dir: Path, project_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        results = install_agent_def(ad, ["nonexistent-agent"], mode="copy")
        assert len(results) == 1
        assert results[0]["status"] == "error"

    def test_install_overwrite(self, agents_dir: Path, project_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        # Install twice — should not error
        install_agent_def(ad, ["claude-code"], mode="copy")
        results = install_agent_def(ad, ["claude-code"], mode="copy")
        assert results[0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Find installed
# ---------------------------------------------------------------------------

class TestFindInstalled:
    def test_find_nothing(self, project_dir: Path) -> None:
        installed = find_installed_agent_defs()
        assert installed == {}

    def test_find_installed(self, agents_dir: Path, project_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        install_agent_def(ad, ["claude-code", "mistral-vibe"], mode="copy")
        installed = find_installed_agent_defs()

        assert "docs-agent" in installed
        assert "claude-code" in installed["docs-agent"]
        assert "mistral-vibe" in installed["docs-agent"]

    def test_find_filter_by_agent(self, agents_dir: Path, project_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        install_agent_def(ad, ["claude-code", "mistral-vibe"], mode="copy")
        installed = find_installed_agent_defs(agent_names=["claude-code"])

        assert "docs-agent" in installed
        # Only claude-code should be listed
        assert installed["docs-agent"] == ["claude-code"]


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------

class TestRemoveAgentDef:
    def test_remove_all_agents(self, agents_dir: Path, project_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        install_agent_def(ad, ["claude-code", "mistral-vibe"], mode="copy")
        results = remove_agent_def("docs-agent")

        # Should have removed from both agents + canonical
        assert len(results) >= 2
        statuses = {r["agent"] for r in results}
        assert "canonical" in statuses

        # Canonical should be gone
        canonical = project_dir / ".agents" / "agent-definitions" / "docs-agent.agent.md"
        assert not canonical.exists()

    def test_remove_specific_agent(self, agents_dir: Path, project_dir: Path) -> None:
        ad = parse_agent_md(agents_dir / "docs-agent.agent.md")
        assert ad is not None

        install_agent_def(ad, ["claude-code", "mistral-vibe"], mode="copy")
        results = remove_agent_def("docs-agent", agent_names=["claude-code"])

        # Only claude-code link removed, canonical preserved
        canonical = project_dir / ".agents" / "agent-definitions" / "docs-agent.agent.md"
        assert canonical.is_file()

        # mistral-vibe should still have it
        installed = find_installed_agent_defs()
        assert "docs-agent" in installed
        assert "mistral-vibe" in installed["docs-agent"]

    def test_remove_nonexistent(self, project_dir: Path) -> None:
        results = remove_agent_def("nonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Init (template)
# ---------------------------------------------------------------------------

class TestCreateAgentTemplate:
    def test_create_template(self, project_dir: Path) -> None:
        result = create_agent_template("my-agent")
        assert result is not None
        assert result.is_file()
        assert result.name == "my-agent.agent.md"

        content = result.read_text(encoding="utf-8")
        assert "my-agent" in content

    def test_create_existing_fails(self, project_dir: Path) -> None:
        (project_dir / "my-agent.agent.md").write_text("existing", encoding="utf-8")
        result = create_agent_template("my-agent")
        assert result is None

    def test_create_default_name(self, project_dir: Path) -> None:
        result = create_agent_template()
        if result is not None:
            assert result.name == "my-agent.agent.md"


# ---------------------------------------------------------------------------
# Bundled agents discovery
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MCP servers parsing
# ---------------------------------------------------------------------------

class TestMcpServersParsing:
    def test_mcp_servers_parsed_as_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "mcp-agent.agent.md"
        f.write_text(
            textwrap.dedent("""\
                ---
                name: mcp-agent
                description: Agent with MCP servers
                mcp-servers:
                  filesystem:
                    command: npx
                    args: ["-y", "@anthropic/mcp-filesystem"]
                  github:
                    command: npx
                    args: ["-y", "@anthropic/mcp-github"]
                ---

                You have MCP servers.
            """),
            encoding="utf-8",
        )
        ad = parse_agent_md(f)
        assert ad is not None
        assert ad.mcp_servers is not None
        assert isinstance(ad.mcp_servers, dict)
        assert "filesystem" in ad.mcp_servers
        assert "github" in ad.mcp_servers
        assert ad.mcp_servers["filesystem"]["command"] == "npx"

    def test_mcp_servers_underscore_key(self, tmp_path: Path) -> None:
        """mcp_servers (underscore) should also be accepted."""
        f = tmp_path / "mcp2.agent.md"
        f.write_text(
            textwrap.dedent("""\
                ---
                name: mcp2
                description: underscore variant
                mcp_servers:
                  myserver:
                    command: node
                ---

                Body.
            """),
            encoding="utf-8",
        )
        ad = parse_agent_md(f)
        assert ad is not None
        assert ad.mcp_servers is not None
        assert "myserver" in ad.mcp_servers

    def test_mcp_servers_none_when_absent(self, tmp_path: Path) -> None:
        f = tmp_path / "no-mcp.agent.md"
        f.write_text(
            textwrap.dedent("""\
                ---
                name: no-mcp
                description: No MCP servers
                ---

                Body.
            """),
            encoding="utf-8",
        )
        ad = parse_agent_md(f)
        assert ad is not None
        assert ad.mcp_servers is None

    def test_mcp_servers_non_dict_ignored(self, tmp_path: Path) -> None:
        """If mcp-servers is a string or list it should be treated as None."""
        f = tmp_path / "bad-mcp.agent.md"
        f.write_text(
            textwrap.dedent("""\
                ---
                name: bad-mcp
                description: Bad MCP
                mcp-servers: not-a-dict
                ---

                Body.
            """),
            encoding="utf-8",
        )
        ad = parse_agent_md(f)
        assert ad is not None
        assert ad.mcp_servers is None


class TestBundledAgents:
    def test_discover_bundled(self) -> None:
        """Discover bundled agent definitions from agents/ directory."""
        from ai_setup_forge.agent_defs import _get_bundled_agents_dir

        agents_dir = _get_bundled_agents_dir()
        if not agents_dir.is_dir():
            pytest.skip("Bundled agents directory not found")

        results = discover_agent_defs(agents_dir)
        assert len(results) >= 10  # We have 12 bundled agents
        names = {ad.name for ad in results}
        assert "docs-agent" in names
        assert "playwright-test-generator" in names

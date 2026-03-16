"""Tests for the remover module."""

from pathlib import Path
from unittest.mock import patch

from ai_setup_forge.remover import find_installed_skills, remove_skill


def _setup_installed(project_dir: Path, skill_name: str = "test-skill") -> None:
    """Set up a skill in canonical + claude-code agent dir."""
    # Canonical
    canonical = project_dir / ".agents" / "skills" / skill_name
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Test.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    # Claude agent dir
    agent_dir = project_dir / ".claude" / "skills" / skill_name
    agent_dir.mkdir(parents=True)
    (agent_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Test.\n---\n\n# Body\n",
        encoding="utf-8",
    )


class TestFindInstalledSkills:
    def test_finds_canonical_and_agent(self, tmp_path):
        _setup_installed(tmp_path)
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path):
            result = find_installed_skills(is_global=False)
        assert "test-skill" in result
        assert "claude-code" in result["test-skill"]

    def test_empty_when_no_skills(self, tmp_path):
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path):
            result = find_installed_skills(is_global=False)
        assert result == {}

    def test_filter_by_agent(self, tmp_path):
        _setup_installed(tmp_path)
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path):
            result = find_installed_skills(is_global=False, agent_names=["mistral-vibe"])
        # Canonical is still scanned, but mistral-vibe has no dir
        assert "test-skill" in result
        assert result["test-skill"] == []  # no agents matched


class TestRemoveSkill:
    def test_remove_project_skill(self, tmp_path):
        _setup_installed(tmp_path)
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path), \
             patch("ai_setup_forge.remover.get_home", return_value=tmp_path):
            results = remove_skill("test-skill", is_global=False)
        assert len(results) >= 1
        # Both canonical and agent dir should be gone
        assert not (tmp_path / ".agents" / "skills" / "test-skill").exists()
        assert not (tmp_path / ".claude" / "skills" / "test-skill").exists()

    def test_remove_nonexistent(self, tmp_path):
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path), \
             patch("ai_setup_forge.remover.get_home", return_value=tmp_path):
            results = remove_skill("no-skill", is_global=False)
        assert results == []

    def test_remove_specific_agent_preserves_canonical(self, tmp_path):
        _setup_installed(tmp_path)
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path), \
             patch("ai_setup_forge.remover.get_home", return_value=tmp_path):
            results = remove_skill(
                "test-skill",
                agent_names=["claude-code"],
                is_global=False,
            )
        # Agent dir removed
        assert not (tmp_path / ".claude" / "skills" / "test-skill").exists()
        # Canonical preserved — other agents may still point to it
        assert (tmp_path / ".agents" / "skills" / "test-skill").exists()

    def test_remove_all_agents_removes_canonical(self, tmp_path):
        _setup_installed(tmp_path)
        with patch("ai_setup_forge.remover.Path.cwd", return_value=tmp_path), \
             patch("ai_setup_forge.remover.get_home", return_value=tmp_path):
            results = remove_skill(
                "test-skill",
                agent_names=None,  # all agents
                is_global=False,
            )
        # Both agent dir and canonical removed
        assert not (tmp_path / ".claude" / "skills" / "test-skill").exists()
        assert not (tmp_path / ".agents" / "skills" / "test-skill").exists()

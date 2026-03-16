"""Tests for the installer module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_setup_forge.installer import (
    InstallError,
    _canonical_dir,
    _create_link,
    _needs_agent_link,
    install_skill,
)
from ai_setup_forge.types import Skill


def _make_skill(tmp_path: Path, name: str = "test-skill", desc: str = "A test.") -> Skill:
    """Create a skill directory with SKILL.md and return a Skill object."""
    skill_dir = tmp_path / "source" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# Body\n",
        encoding="utf-8",
    )
    return Skill(name=name, description=desc, path=skill_dir)


class TestCanonicalDir:
    def test_project_level(self):
        with patch("ai_setup_forge.installer.Path.cwd", return_value=Path("/project")):
            result = _canonical_dir("my-skill", is_global=False)
        assert result == Path("/project/.agents/skills/my-skill")

    def test_global_level(self, tmp_path):
        with patch("ai_setup_forge.installer.get_home", return_value=tmp_path):
            result = _canonical_dir("my-skill", is_global=True)
        assert result == tmp_path / ".agents" / "skills" / "my-skill"


class TestNeedsAgentLink:
    def test_claude_code_project(self):
        assert _needs_agent_link("claude-code", is_global=False) is True

    def test_copilot_project_no_link(self):
        assert _needs_agent_link("github-copilot", is_global=False) is False

    def test_copilot_global_needs_link(self):
        assert _needs_agent_link("github-copilot", is_global=True) is True

    def test_mistral_project(self):
        assert _needs_agent_link("mistral-vibe", is_global=False) is True


class TestInstallSkill:
    def test_install_single_agent(self, tmp_path):
        skill = _make_skill(tmp_path)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch("ai_setup_forge.installer.Path.cwd", return_value=project_dir), \
             patch("ai_setup_forge.installer.get_home", return_value=tmp_path):
            results = install_skill(skill, ["claude-code"], is_global=False, mode="copy")

        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert results[0]["agent"] == "claude-code"

        # Check canonical copy exists
        canonical = project_dir / ".agents" / "skills" / "test-skill"
        assert canonical.is_dir()
        assert (canonical / "SKILL.md").is_file()

        # Check agent copy exists
        agent_path = project_dir / ".claude" / "skills" / "test-skill"
        assert agent_path.is_dir()

    def test_install_copilot_project_no_link(self, tmp_path):
        skill = _make_skill(tmp_path)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch("ai_setup_forge.installer.Path.cwd", return_value=project_dir), \
             patch("ai_setup_forge.installer.get_home", return_value=tmp_path):
            results = install_skill(skill, ["github-copilot"], is_global=False, mode="copy")

        assert len(results) == 1
        assert results[0]["method"] == "canonical"
        # Canonical exists, no agent link
        canonical = project_dir / ".agents" / "skills" / "test-skill"
        assert canonical.is_dir()

    def test_install_multiple_agents(self, tmp_path):
        skill = _make_skill(tmp_path)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch("ai_setup_forge.installer.Path.cwd", return_value=project_dir), \
             patch("ai_setup_forge.installer.get_home", return_value=tmp_path):
            results = install_skill(
                skill,
                ["claude-code", "mistral-vibe", "github-copilot"],
                is_global=False,
                mode="copy",
            )

        assert len(results) == 3
        # Claude and Mistral get copies, Copilot uses canonical
        assert results[0]["agent"] == "claude-code"
        assert results[0]["status"] == "ok"
        assert results[1]["agent"] == "mistral-vibe"
        assert results[1]["status"] == "ok"
        assert results[2]["agent"] == "github-copilot"
        assert results[2]["method"] == "canonical"

    def test_unknown_agent(self, tmp_path):
        skill = _make_skill(tmp_path)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch("ai_setup_forge.installer.Path.cwd", return_value=project_dir), \
             patch("ai_setup_forge.installer.get_home", return_value=tmp_path):
            results = install_skill(skill, ["nonexistent"], is_global=False)

        assert results[0]["status"] == "error"

    def test_install_global(self, tmp_path):
        skill = _make_skill(tmp_path)

        with patch("ai_setup_forge.installer.get_home", return_value=tmp_path):
            results = install_skill(skill, ["claude-code"], is_global=True, mode="copy")

        assert results[0]["status"] == "ok"
        canonical = tmp_path / ".agents" / "skills" / "test-skill"
        assert canonical.is_dir()


class TestCreateLink:
    def test_target_must_exist(self, tmp_path):
        source = tmp_path / "link"
        target = tmp_path / "nonexistent"
        with pytest.raises(InstallError, match="does not exist"):
            _create_link(source, target)

    def test_link_to_existing_target(self, tmp_path):
        target = tmp_path / "target-dir"
        target.mkdir()
        (target / "file.txt").write_text("hello")
        source = tmp_path / "link"
        method = _create_link(source, target)
        assert method in ("symlink", "junction", "copy")
        assert (source / "file.txt").exists()

    def test_symlink_fallback_to_copy(self, tmp_path):
        """When symlink fails on non-Windows, _create_link falls back to copy."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "data.txt").write_text("content")
        source = tmp_path / "link"

        with patch("ai_setup_forge.installer.sys") as mock_sys, \
             patch.object(Path, "symlink_to", side_effect=OSError("no symlink")):
            mock_sys.platform = "linux"
            method = _create_link(source, target)

        assert method == "copy"
        assert (source / "data.txt").read_text() == "content"

    def test_existing_symlink_gets_replaced(self, tmp_path):
        """An existing symlink at source is replaced by a new link."""
        target_old = tmp_path / "old-target"
        target_old.mkdir()
        (target_old / "old.txt").write_text("old")

        target_new = tmp_path / "new-target"
        target_new.mkdir()
        (target_new / "new.txt").write_text("new")

        source = tmp_path / "link"
        _create_link(source, target_old)
        assert (source / "old.txt").exists()

        method = _create_link(source, target_new)
        assert method in ("symlink", "junction", "copy")
        assert (source / "new.txt").exists()

    def test_existing_directory_gets_replaced(self, tmp_path):
        """A real directory at source is removed and replaced by a link."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "target.txt").write_text("target-content")

        source = tmp_path / "link"
        source.mkdir(parents=True)
        (source / "stale.txt").write_text("stale")

        method = _create_link(source, target)
        assert method in ("symlink", "junction", "copy")
        assert (source / "target.txt").exists()
        assert not (source / "stale.txt").exists()

    def test_windows_junction_fallback(self, tmp_path):
        """On Windows, when symlink fails, _create_link tries junction."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "file.txt").write_text("hello")
        source = tmp_path / "link"

        mock_run = MagicMock(return_value=MagicMock(returncode=0))

        with patch("ai_setup_forge.installer.sys") as mock_sys, \
             patch.object(Path, "symlink_to", side_effect=OSError("no symlink")), \
             patch("subprocess.run", mock_run):
            mock_sys.platform = "win32"
            method = _create_link(source, target)

        assert method == "junction"
        mock_run.assert_called_once_with(
            ["cmd", "/c", "mklink", "/J", str(source), str(target)],
            capture_output=True,
            check=True,
        )

    def test_windows_junction_failure_falls_to_copy(self, tmp_path):
        """On Windows, when both symlink and junction fail, falls back to copy."""
        import subprocess

        target = tmp_path / "target"
        target.mkdir()
        (target / "file.txt").write_text("hello")
        source = tmp_path / "link"

        with patch("ai_setup_forge.installer.sys") as mock_sys, \
             patch.object(Path, "symlink_to", side_effect=OSError("no symlink")), \
             patch(
                 "subprocess.run",
                 side_effect=subprocess.CalledProcessError(1, "cmd"),
             ):
            mock_sys.platform = "win32"
            method = _create_link(source, target)

        assert method == "copy"
        assert (source / "file.txt").read_text() == "hello"

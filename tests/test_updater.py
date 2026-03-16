"""Tests for updater.py — check for updates and update logic."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_setup_forge.updater import (
    CheckResult,
    SkillUpdateInfo,
    _describe_api_error,
    _parse_github_url,
    check_for_updates,
    update_skill,
)


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

class TestParseGithubUrl:
    def test_https_url(self) -> None:
        result = _parse_github_url("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_https_url_with_path(self) -> None:
        result = _parse_github_url("https://github.com/owner/repo/tree/main/skills")
        assert result == ("owner", "repo")

    def test_https_url_with_git_suffix(self) -> None:
        result = _parse_github_url("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_ssh_url(self) -> None:
        result = _parse_github_url("git@github.com:owner/repo.git")
        assert result == ("owner", "repo")

    def test_shorthand(self) -> None:
        result = _parse_github_url("owner/repo")
        assert result == ("owner", "repo")

    def test_non_github_url(self) -> None:
        result = _parse_github_url("https://gitlab.com/owner/repo")
        assert result is None

    def test_invalid_url(self) -> None:
        result = _parse_github_url("not-a-url")
        assert result is None

    def test_empty_string(self) -> None:
        result = _parse_github_url("")
        assert result is None


# ---------------------------------------------------------------------------
# Check result
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_outdated(self) -> None:
        result = CheckResult(skills=[
            SkillUpdateInfo("a", "url", "github", "hash1", "hash2", has_update=True),
            SkillUpdateInfo("b", "url", "github", "hash1", "hash1", has_update=False),
        ])
        assert len(result.outdated) == 1
        assert result.outdated[0].name == "a"

    def test_up_to_date(self) -> None:
        result = CheckResult(skills=[
            SkillUpdateInfo("a", "url", "github", "hash1", "hash1", has_update=False),
        ])
        assert len(result.up_to_date) == 1

    def test_errors(self) -> None:
        result = CheckResult(skills=[
            SkillUpdateInfo("a", "url", "local", "", error="not supported"),
        ])
        assert len(result.errors) == 1
        assert result.errors[0].error == "not supported"


# ---------------------------------------------------------------------------
# check_for_updates
# ---------------------------------------------------------------------------

class TestCheckForUpdates:
    def test_empty_lock_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        lock_file = tmp_path / ".agents" / ".skill-lock.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps({
            "version": 1, "skills": {}, "last_selected_agents": []
        }))
        monkeypatch.setattr("ai_setup_forge.skill_lock.get_home", lambda: tmp_path)

        result = check_for_updates()
        assert result.skills == []

    def test_non_github_skill(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        lock_file = tmp_path / ".agents" / ".skill-lock.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "my-skill": {
                    "source": "./local",
                    "source_type": "local",
                    "source_url": "./local",
                    "skill_path": None,
                    "skill_folder_hash": "",
                    "installed_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
            "last_selected_agents": [],
        }))
        monkeypatch.setattr("ai_setup_forge.skill_lock.get_home", lambda: tmp_path)

        result = check_for_updates()
        assert len(result.skills) == 1
        assert result.skills[0].error is not None
        assert "not supported" in result.skills[0].error

    @patch("ai_setup_forge.updater._get_tree_sha")
    @patch("ai_setup_forge.updater._get_github_token")
    def test_github_skill_has_update(
        self,
        mock_token: MagicMock,
        mock_tree_sha: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        lock_file = tmp_path / ".agents" / ".skill-lock.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "my-skill": {
                    "source": "owner/repo",
                    "source_type": "github",
                    "source_url": "https://github.com/owner/repo",
                    "skill_path": "skills/my-skill",
                    "skill_folder_hash": "old-hash-123",
                    "installed_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
            "last_selected_agents": [],
        }))
        monkeypatch.setattr("ai_setup_forge.skill_lock.get_home", lambda: tmp_path)
        mock_token.return_value = "fake-token"
        mock_tree_sha.return_value = "new-hash-456"

        result = check_for_updates()
        assert len(result.skills) == 1
        assert result.skills[0].has_update is True
        assert result.skills[0].remote_hash == "new-hash-456"

    @patch("ai_setup_forge.updater._get_tree_sha")
    @patch("ai_setup_forge.updater._get_github_token")
    def test_github_skill_up_to_date(
        self,
        mock_token: MagicMock,
        mock_tree_sha: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        lock_file = tmp_path / ".agents" / ".skill-lock.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "my-skill": {
                    "source": "owner/repo",
                    "source_type": "github",
                    "source_url": "https://github.com/owner/repo",
                    "skill_path": None,
                    "skill_folder_hash": "same-hash",
                    "installed_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
            "last_selected_agents": [],
        }))
        monkeypatch.setattr("ai_setup_forge.skill_lock.get_home", lambda: tmp_path)
        mock_token.return_value = None
        mock_tree_sha.return_value = "same-hash"

        result = check_for_updates()
        assert len(result.skills) == 1
        assert result.skills[0].has_update is False

    @patch("ai_setup_forge.updater._get_tree_sha")
    @patch("ai_setup_forge.updater._get_latest_commit_sha")
    @patch("ai_setup_forge.updater._get_github_token")
    def test_github_skill_tree_api_fails_falls_back_to_commit(
        self,
        mock_token: MagicMock,
        mock_commit_sha: MagicMock,
        mock_tree_sha: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        lock_file = tmp_path / ".agents" / ".skill-lock.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "my-skill": {
                    "source": "owner/repo",
                    "source_type": "github",
                    "source_url": "owner/repo",
                    "skill_path": None,
                    "skill_folder_hash": "old",
                    "installed_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
            "last_selected_agents": [],
        }))
        monkeypatch.setattr("ai_setup_forge.skill_lock.get_home", lambda: tmp_path)
        mock_token.return_value = None
        mock_tree_sha.return_value = None  # Tree API fails
        mock_commit_sha.return_value = "new-commit"

        result = check_for_updates()
        assert len(result.skills) == 1
        assert result.skills[0].has_update is True
        assert result.skills[0].remote_hash == "new-commit"


# ---------------------------------------------------------------------------
# _describe_api_error
# ---------------------------------------------------------------------------

class TestDescribeApiError:
    def test_401(self) -> None:
        msg = _describe_api_error(401)
        assert "authentication" in msg.lower()

    def test_403(self) -> None:
        msg = _describe_api_error(403)
        assert "forbidden" in msg.lower() or "rate limit" in msg.lower()

    def test_404(self) -> None:
        msg = _describe_api_error(404)
        assert "not found" in msg.lower()

    def test_500(self) -> None:
        msg = _describe_api_error(500)
        assert "server error" in msg.lower()
        assert "500" in msg

    def test_502(self) -> None:
        msg = _describe_api_error(502)
        assert "server error" in msg.lower()
        assert "502" in msg

    def test_network_error(self) -> None:
        msg = _describe_api_error(0)
        assert "network" in msg.lower()

    def test_other_status(self) -> None:
        msg = _describe_api_error(418)
        assert "418" in msg


# ---------------------------------------------------------------------------
# update_skill
# ---------------------------------------------------------------------------

# Patch paths — update_skill uses deferred imports, so we patch at the source.
_GIT = "ai_setup_forge.git_utils"
_LOCK = "ai_setup_forge.skill_lock"
_INST = "ai_setup_forge.installer"
_SKILLS = "ai_setup_forge.skills"
_SRC = "ai_setup_forge.source_parser"
_AGENTS = "ai_setup_forge.agents"


def _make_lock_entry(
    source: str = "owner/repo",
    source_type: str = "github",
    source_url: str = "https://github.com/owner/repo",
    skill_path: str | None = "skills/my-skill",
) -> MagicMock:
    """Return a minimal SkillLockEntry-like mock."""
    entry = MagicMock()
    entry.source = source
    entry.source_type = source_type
    entry.source_url = source_url
    entry.skill_path = skill_path
    return entry


def _make_parsed(
    src_type: str = "github",
    url: str = "https://github.com/owner/repo",
    subpath: str | None = None,
    local_path: Path | None = None,
    ref: str | None = None,
) -> MagicMock:
    """Return a minimal ParsedSource-like mock."""
    p = MagicMock()
    p.type = src_type
    p.url = url
    p.subpath = subpath
    p.local_path = local_path
    p.ref = ref
    return p


def _make_skill(name: str = "my-skill") -> MagicMock:
    """Return a minimal Skill-like mock."""
    s = MagicMock()
    s.name = name
    s.description = "A test skill"
    s.path = Path("/fake/skills") / name
    return s


class TestUpdateSkill:
    """Tests for update_skill()."""

    # 1. No lock entry -> error
    @patch(f"{_LOCK}.get_skill_entry", return_value=None)
    def test_no_lock_entry(self, _mock_get: MagicMock) -> None:
        result = update_skill("missing-skill")
        assert result["status"] == "error"
        assert "No lock entry" in result["message"]

    # 2. No source_url -> error
    @patch(f"{_LOCK}.get_skill_entry")
    def test_no_source_url(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _make_lock_entry(source_url="")
        result = update_skill("my-skill")
        assert result["status"] == "error"
        assert "No source URL" in result["message"]

    # 3. No agents available -> error
    @patch(f"{_AGENTS}.detect_installed_agents", return_value=[])
    @patch(f"{_LOCK}.get_last_agents", return_value=[])
    @patch(f"{_SRC}.parse_source")
    @patch(f"{_LOCK}.get_skill_entry")
    def test_no_agents_available(
        self,
        mock_get: MagicMock,
        _mock_parse: MagicMock,
        _mock_last: MagicMock,
        _mock_detect: MagicMock,
    ) -> None:
        mock_get.return_value = _make_lock_entry()
        result = update_skill("my-skill")
        assert result["status"] == "error"
        assert "No agents" in result["message"]

    # 4. Local source: successful update flow
    @patch(f"{_LOCK}.add_skill_entry")
    @patch(f"{_INST}.install_skill", return_value={"claude": "ok"})
    @patch(f"{_SKILLS}.filter_skills")
    @patch(f"{_SKILLS}.discover_skills")
    @patch(f"{_SRC}.parse_source")
    @patch(f"{_LOCK}.get_last_agents", return_value=["claude"])
    @patch(f"{_LOCK}.get_skill_entry")
    def test_local_source_success(
        self,
        mock_get: MagicMock,
        _mock_last: MagicMock,
        mock_parse: MagicMock,
        mock_discover: MagicMock,
        mock_filter: MagicMock,
        mock_install: MagicMock,
        mock_add_entry: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_get.return_value = _make_lock_entry(
            source="./local", source_type="local", source_url="./local",
        )
        local_dir = tmp_path / "skills"
        local_dir.mkdir()
        mock_parse.return_value = _make_parsed(
            src_type="local", url="./local", local_path=local_dir,
        )
        skill = _make_skill()
        mock_discover.return_value = [skill]
        mock_filter.return_value = [skill]

        result = update_skill("my-skill")

        assert result["status"] == "ok"
        assert result["skill"] == "my-skill"
        assert result["agents"] == ["claude"]
        assert result["install_results"] == {"claude": "ok"}
        mock_install.assert_called_once()
        mock_add_entry.assert_called_once()

    # 5. Remote source: successful update with clone + cleanup
    @patch(f"{_GIT}.cleanup_clone")
    @patch(f"{_LOCK}.add_skill_entry")
    @patch(f"{_INST}.install_skill", return_value={"cursor": "ok"})
    @patch(f"{_SKILLS}.filter_skills")
    @patch(f"{_SKILLS}.discover_skills")
    @patch(f"{_SRC}.parse_source")
    @patch(f"{_LOCK}.get_last_agents", return_value=[])
    @patch(f"{_AGENTS}.detect_installed_agents", return_value=["cursor"])
    @patch(f"{_LOCK}.get_skill_entry")
    def test_remote_source_success(
        self,
        mock_get: MagicMock,
        _mock_detect: MagicMock,
        _mock_last: MagicMock,
        mock_parse: MagicMock,
        mock_discover: MagicMock,
        mock_filter: MagicMock,
        mock_install: MagicMock,
        mock_add_entry: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_get.return_value = _make_lock_entry()
        mock_parse.return_value = _make_parsed(src_type="github")

        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()

        skill = _make_skill()
        mock_discover.return_value = [skill]
        mock_filter.return_value = [skill]

        with patch(f"{_GIT}.shallow_clone", return_value=clone_dir) as mock_clone:
            result = update_skill("my-skill")
            mock_clone.assert_called_once()

        assert result["status"] == "ok"
        assert result["agents"] == ["cursor"]
        mock_cleanup.assert_called_once_with(clone_dir)

    # 6. Git clone failure -> error
    @patch(f"{_SRC}.parse_source")
    @patch(f"{_LOCK}.get_last_agents", return_value=["claude"])
    @patch(f"{_LOCK}.get_skill_entry")
    def test_git_clone_failure(
        self,
        mock_get: MagicMock,
        _mock_last: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        mock_get.return_value = _make_lock_entry()
        mock_parse.return_value = _make_parsed(src_type="github")

        from ai_setup_forge.git_utils import GitError

        with patch(f"{_GIT}.shallow_clone", side_effect=GitError("clone failed")):
            result = update_skill("my-skill")

        assert result["status"] == "error"
        assert "clone failed" in result["message"]

    # 7. Skill not found in source -> error
    @patch(f"{_GIT}.cleanup_clone")
    @patch(f"{_SKILLS}.filter_skills", return_value=[])
    @patch(f"{_SKILLS}.discover_skills", return_value=[])
    @patch(f"{_SRC}.parse_source")
    @patch(f"{_LOCK}.get_last_agents", return_value=["claude"])
    @patch(f"{_LOCK}.get_skill_entry")
    def test_skill_not_found_in_source(
        self,
        mock_get: MagicMock,
        _mock_last: MagicMock,
        mock_parse: MagicMock,
        _mock_discover: MagicMock,
        _mock_filter: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_get.return_value = _make_lock_entry()
        mock_parse.return_value = _make_parsed(src_type="github")

        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()

        with patch(f"{_GIT}.shallow_clone", return_value=clone_dir):
            result = update_skill("my-skill")

        assert result["status"] == "error"
        assert "not found in source" in result["message"]
        mock_cleanup.assert_called_once_with(clone_dir)

    # 8. Registry update failure is silently ignored
    @patch(f"{_GIT}.cleanup_clone")
    @patch(f"{_LOCK}.add_skill_entry")
    @patch(f"{_INST}.install_skill", return_value={"claude": "ok"})
    @patch(f"{_SKILLS}.filter_skills")
    @patch(f"{_SKILLS}.discover_skills")
    @patch(f"{_SRC}.parse_source")
    @patch(f"{_LOCK}.get_last_agents", return_value=["claude"])
    @patch(f"{_LOCK}.get_skill_entry")
    def test_registry_failure_silently_ignored(
        self,
        mock_get: MagicMock,
        _mock_last: MagicMock,
        mock_parse: MagicMock,
        mock_discover: MagicMock,
        mock_filter: MagicMock,
        _mock_install: MagicMock,
        _mock_add_entry: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_get.return_value = _make_lock_entry()
        mock_parse.return_value = _make_parsed(src_type="github")

        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()

        skill = _make_skill()
        mock_discover.return_value = [skill]
        mock_filter.return_value = [skill]

        with patch(f"{_GIT}.shallow_clone", return_value=clone_dir), \
             patch(
                 "ai_setup_forge.registry.ensure_registry",
                 side_effect=RuntimeError("db broken"),
             ):
            result = update_skill("my-skill")

        # Should succeed despite registry failure
        assert result["status"] == "ok"
        assert result["skill"] == "my-skill"
        mock_cleanup.assert_called_once_with(clone_dir)

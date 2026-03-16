"""Tests for the skill lock module."""

import json
from pathlib import Path
from unittest.mock import patch

from ai_setup_forge.skill_lock import (
    add_skill_entry,
    get_last_agents,
    get_skill_entry,
    read_lock,
    remove_skill_entry,
    update_last_agents,
    write_lock,
)


def _lock_path(tmp_path: Path) -> Path:
    return tmp_path / ".agents" / ".skill-lock.json"


class TestReadWriteLock:
    def test_read_missing(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            data = read_lock()
        assert data["version"] == 1
        assert data["skills"] == {}
        assert data["last_selected_agents"] == []

    def test_write_and_read(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            write_lock({"version": 1, "skills": {"foo": {"source": "a/b"}}, "last_selected_agents": []})
            data = read_lock()
        assert "foo" in data["skills"]
        assert data["skills"]["foo"]["source"] == "a/b"

    def test_read_corrupt_json(self, tmp_path):
        lock = _lock_path(tmp_path)
        lock.parent.mkdir(parents=True)
        lock.write_text("not json", encoding="utf-8")
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            data = read_lock()
        assert data["version"] == 1
        assert data["skills"] == {}


    def test_read_wrong_type_skills(self, tmp_path):
        """If 'skills' is not a dict, reset to empty dict."""
        lock = _lock_path(tmp_path)
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"version": 1, "skills": "not-a-dict", "last_selected_agents": []}))
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            data = read_lock()
        assert data["skills"] == {}

    def test_read_wrong_type_agents(self, tmp_path):
        """If 'last_selected_agents' is not a list, reset to empty list."""
        lock = _lock_path(tmp_path)
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"version": 1, "skills": {}, "last_selected_agents": "bad"}))
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            data = read_lock()
        assert data["last_selected_agents"] == []

    def test_write_atomic(self, tmp_path):
        """Write uses temp file for crash safety — no .tmp file left behind."""
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            write_lock({"version": 1, "skills": {}, "last_selected_agents": []})
        lock = _lock_path(tmp_path)
        assert lock.exists()
        assert not lock.with_suffix(".tmp").exists()


class TestSkillEntries:
    def test_add_new(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            add_skill_entry("my-skill", "owner/repo", "github", "https://github.com/owner/repo.git")
            entry = get_skill_entry("my-skill")
        assert entry is not None
        assert entry.source == "owner/repo"
        assert entry.source_type == "github"
        assert entry.installed_at != ""

    def test_add_update_existing(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            add_skill_entry("my-skill", "owner/repo", "github", "https://github.com/owner/repo.git")
            entry1 = get_skill_entry("my-skill")
            add_skill_entry("my-skill", "owner/repo2", "github", "https://github.com/owner/repo2.git")
            entry2 = get_skill_entry("my-skill")
        assert entry2.source == "owner/repo2"
        assert entry2.installed_at == entry1.installed_at  # preserved
        assert entry2.updated_at >= entry1.updated_at

    def test_remove(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            add_skill_entry("my-skill", "owner/repo", "github", "https://github.com/owner/repo.git")
            assert remove_skill_entry("my-skill") is True
            assert get_skill_entry("my-skill") is None

    def test_remove_nonexistent(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            assert remove_skill_entry("no-such-skill") is False

    def test_get_nonexistent(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            assert get_skill_entry("no-such-skill") is None


class TestLastAgents:
    def test_update_and_get(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            update_last_agents(["claude-code", "mistral-vibe"])
            result = get_last_agents()
        assert result == ["claude-code", "mistral-vibe"]

    def test_empty_default(self, tmp_path):
        with patch("ai_setup_forge.skill_lock.get_home", return_value=tmp_path):
            result = get_last_agents()
        assert result == []

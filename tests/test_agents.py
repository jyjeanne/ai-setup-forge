"""Tests for the agents module."""

from ai_setup_forge.agents import AGENTS, get_agent_config, get_all_agent_names


class TestAgentConfigs:
    def test_three_agents_defined(self):
        assert len(AGENTS) == 3

    def test_claude_code_config(self):
        config = AGENTS["claude-code"]
        assert config.name == "claude-code"
        assert config.display_name == "Claude Code"
        assert config.skills_dir == ".claude/skills"
        assert "claude" in str(config.global_skills_dir).lower()

    def test_mistral_vibe_config(self):
        config = AGENTS["mistral-vibe"]
        assert config.name == "mistral-vibe"
        assert config.display_name == "Mistral Vibe"
        assert config.skills_dir == ".vibe/skills"
        assert "vibe" in str(config.global_skills_dir).lower()

    def test_copilot_config(self):
        config = AGENTS["github-copilot"]
        assert config.name == "github-copilot"
        assert config.display_name == "Copilot CLI"
        assert config.skills_dir == ".github/skills"
        assert ".agents/skills" in config.alt_skills_dirs
        assert "copilot" in str(config.global_skills_dir).lower()

    def test_get_agent_config(self):
        assert get_agent_config("claude-code") is not None
        assert get_agent_config("nonexistent") is None

    def test_get_all_agent_names(self):
        names = get_all_agent_names()
        assert set(names) == {"claude-code", "mistral-vibe", "github-copilot"}

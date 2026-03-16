"""Tests for the skills module."""

from pathlib import Path

from ai_setup_forge.skills import discover_skills, filter_skills, parse_skill_md


def _write_skill(directory: Path, name: str, description: str, body: str = "# Body") -> Path:
    """Helper to write a SKILL.md file."""
    skill_dir = directory / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir


class TestParseSkillMd:
    def test_valid(self, tmp_path):
        skill_dir = _write_skill(tmp_path, "test-skill", "A test skill.")
        skill = parse_skill_md(skill_dir / "SKILL.md")
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill."
        assert skill.path == skill_dir

    def test_missing_name(self, tmp_path):
        skill_dir = tmp_path / "bad"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: No name.\n---\n\nBody\n", encoding="utf-8"
        )
        assert parse_skill_md(skill_dir / "SKILL.md") is None

    def test_missing_description(self, tmp_path):
        skill_dir = tmp_path / "bad"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: bad\n---\n\nBody\n", encoding="utf-8")
        assert parse_skill_md(skill_dir / "SKILL.md") is None

    def test_internal_skill_hidden(self, tmp_path):
        skill_dir = tmp_path / "internal"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: internal\ndescription: Hidden.\n"
            "metadata:\n  internal: true\n---\n\n# Body\n",
            encoding="utf-8",
        )
        assert parse_skill_md(skill_dir / "SKILL.md") is None

    def test_internal_skill_with_flag(self, tmp_path):
        skill_dir = tmp_path / "internal"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: internal\ndescription: Hidden.\n"
            "metadata:\n  internal: true\n---\n\n# Body\n",
            encoding="utf-8",
        )
        skill = parse_skill_md(skill_dir / "SKILL.md", include_internal=True)
        assert skill is not None
        assert skill.name == "internal"

    def test_nonexistent_file(self, tmp_path):
        assert parse_skill_md(tmp_path / "nonexistent" / "SKILL.md") is None

    def test_frontmatter_preserved(self, tmp_path):
        skill_dir = tmp_path / "test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test\ndescription: Test.\nallowed-tools: Read Write\n---\n\n# Body\n",
            encoding="utf-8",
        )
        skill = parse_skill_md(skill_dir / "SKILL.md")
        assert skill is not None
        assert skill.frontmatter is not None
        assert skill.frontmatter.get("allowed-tools") == "Read Write"


class TestDiscoverSkills:
    def test_root_skill(self, tmp_path):
        (tmp_path / "SKILL.md").write_text(
            "---\nname: root\ndescription: Root skill.\n---\n\n# Body\n",
            encoding="utf-8",
        )
        skills = discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].name == "root"

    def test_skills_directory(self, tmp_path):
        _write_skill(tmp_path / "skills", "foo", "Foo skill.")
        _write_skill(tmp_path / "skills", "bar", "Bar skill.")
        skills = discover_skills(tmp_path)
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"foo", "bar"}

    def test_agent_specific_dir(self, tmp_path):
        _write_skill(tmp_path / ".claude" / "skills", "claude-skill", "For Claude.")
        skills = discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].name == "claude-skill"

    def test_deduplication(self, tmp_path):
        _write_skill(tmp_path / "skills", "dupe", "First.")
        _write_skill(tmp_path / ".claude" / "skills", "dupe", "Second.")
        skills = discover_skills(tmp_path)
        assert len(skills) == 1

    def test_recursive_fallback(self, tmp_path):
        # No priority dirs, so should fall back to recursive
        deep = tmp_path / "some" / "nested" / "dir"
        _write_skill(deep, "deep-skill", "Deep.")
        skills = discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].name == "deep-skill"

    def test_skips_node_modules(self, tmp_path):
        _write_skill(tmp_path / "node_modules" / "pkg", "hidden", "Should not find.")
        skills = discover_skills(tmp_path)
        assert len(skills) == 0

    def test_full_depth(self, tmp_path):
        (tmp_path / "SKILL.md").write_text(
            "---\nname: root\ndescription: Root.\n---\n\n# Body\n",
            encoding="utf-8",
        )
        _write_skill(tmp_path / "skills", "sub", "Sub skill.")
        # Without full_depth, root SKILL.md stops search
        skills = discover_skills(tmp_path, full_depth=False)
        assert len(skills) == 1
        # With full_depth, both are found
        skills = discover_skills(tmp_path, full_depth=True)
        assert len(skills) == 2


class TestFilterSkills:
    def test_case_insensitive(self, tmp_path):
        from ai_setup_forge.types import Skill

        skills = [
            Skill(name="Foo-Bar", description="test", path=tmp_path),
            Skill(name="baz", description="test", path=tmp_path),
        ]
        result = filter_skills(skills, ["foo-bar"])
        assert len(result) == 1
        assert result[0].name == "Foo-Bar"

    def test_no_match(self, tmp_path):
        from ai_setup_forge.types import Skill

        skills = [Skill(name="foo", description="test", path=tmp_path)]
        result = filter_skills(skills, ["bar"])
        assert len(result) == 0

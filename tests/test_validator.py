"""Tests for the validator module."""

from ai_setup_forge.validator import validate_name, validate_skill_md, validate_skill_path


class TestValidateName:
    def test_valid_simple(self):
        assert validate_name("code-review") == []

    def test_valid_digits(self):
        assert validate_name("skill1") == []

    def test_valid_single_char(self):
        assert validate_name("a") == []

    def test_empty(self):
        errors = validate_name("")
        assert any("required" in e or "empty" in e for e in errors)

    def test_too_long(self):
        errors = validate_name("a" * 65)
        assert any("64" in e for e in errors)

    def test_max_length_ok(self):
        assert validate_name("a" * 64) == []

    def test_uppercase_rejected(self):
        errors = validate_name("Code-Review")
        assert any("lowercase" in e for e in errors)

    def test_leading_hyphen(self):
        errors = validate_name("-foo")
        assert any("start" in e or "hyphen" in e for e in errors)

    def test_trailing_hyphen(self):
        errors = validate_name("foo-")
        assert any("start" in e or "end" in e or "hyphen" in e for e in errors)

    def test_consecutive_hyphens(self):
        errors = validate_name("foo--bar")
        assert any("consecutive" in e for e in errors)

    def test_special_chars(self):
        errors = validate_name("foo_bar")
        assert len(errors) > 0

    def test_spaces(self):
        errors = validate_name("foo bar")
        assert len(errors) > 0

    def test_dots(self):
        errors = validate_name("foo.bar")
        assert len(errors) > 0


class TestValidateSkillMd:
    def test_minimal_valid(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "A test skill for testing."}
        result = validate_skill_md(skill_dir, fm, "# My Skill\n\nInstructions here.")
        assert result.valid
        assert result.errors == []

    def test_missing_name(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"description": "A test skill."}
        result = validate_skill_md(skill_dir, fm, "body")
        assert not result.valid
        assert any("name" in e for e in result.errors)

    def test_missing_description(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill"}
        result = validate_skill_md(skill_dir, fm, "body")
        assert not result.valid
        assert any("description" in e for e in result.errors)

    def test_name_dir_mismatch_warning(self, tmp_path):
        skill_dir = tmp_path / "wrong-dir"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "A test."}
        result = validate_skill_md(skill_dir, fm, "body")
        assert result.valid  # warning, not error
        assert any("does not match" in w for w in result.warnings)

    def test_description_too_long(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "x" * 1025}
        result = validate_skill_md(skill_dir, fm, "body")
        assert not result.valid

    def test_compatibility_too_long(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "ok", "compatibility": "x" * 501}
        result = validate_skill_md(skill_dir, fm, "body")
        assert not result.valid

    def test_metadata_non_string_values_warning(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "ok", "metadata": {"version": 1}}
        result = validate_skill_md(skill_dir, fm, "body")
        assert result.valid  # warning, not error
        assert any("string" in w for w in result.warnings)

    def test_agent_specific_field_warning(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "ok", "context": "fork"}
        result = validate_skill_md(skill_dir, fm, "body")
        assert result.valid
        assert any("non-portable" in w for w in result.warnings)

    def test_body_too_long_warning(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "ok"}
        body = "\n".join(f"line {i}" for i in range(600))
        result = validate_skill_md(skill_dir, fm, body)
        assert result.valid
        assert any("500" in w or "lines" in w for w in result.warnings)

    def test_allowed_tools_info(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        fm = {"name": "my-skill", "description": "ok", "allowed-tools": "Bash(git:*) Read"}
        result = validate_skill_md(skill_dir, fm, "body")
        assert result.valid
        assert any("2 tool(s)" in i for i in result.info)


class TestValidateSkillPath:
    def test_valid_skill_dir(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: my-skill\ndescription: A test skill.\n---\n\n# My Skill\n",
            encoding="utf-8",
        )
        result = validate_skill_path(skill_dir)
        assert result.valid

    def test_valid_skill_file(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: my-skill\ndescription: A test skill.\n---\n\n# Body\n",
            encoding="utf-8",
        )
        result = validate_skill_path(skill_file)
        assert result.valid

    def test_missing_skill_md(self, tmp_path):
        result = validate_skill_path(tmp_path)
        assert not result.valid
        assert any("No SKILL.md" in e for e in result.errors)

    def test_invalid_path(self, tmp_path):
        result = validate_skill_path(tmp_path / "nonexistent.txt")
        assert not result.valid

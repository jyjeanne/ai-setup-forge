"""Tests for the source_parser module."""

from ai_setup_forge.source_parser import parse_source


class TestLocalPaths:
    def test_relative_dot(self):
        result = parse_source("./my-skills")
        assert result.type == "local"
        assert result.local_path is not None

    def test_relative_dotdot(self):
        result = parse_source("../other-skills")
        assert result.type == "local"

    def test_current_dir(self):
        result = parse_source(".")
        assert result.type == "local"

    def test_absolute_unix(self):
        result = parse_source("/home/user/skills")
        assert result.type == "local"

    def test_absolute_windows(self):
        result = parse_source("C:\\Users\\skills")
        assert result.type == "local"


class TestGitHubShorthand:
    def test_owner_repo(self):
        result = parse_source("vercel-labs/agent-skills")
        assert result.type == "github"
        assert result.url == "https://github.com/vercel-labs/agent-skills.git"
        assert result.subpath is None

    def test_owner_repo_subpath(self):
        result = parse_source("vercel-labs/agent-skills/skills/frontend")
        assert result.type == "github"
        assert result.url == "https://github.com/vercel-labs/agent-skills.git"
        assert result.subpath == "skills/frontend"

    def test_owner_repo_at_skill(self):
        result = parse_source("vercel-labs/agent-skills@frontend-design")
        assert result.type == "github"
        assert result.url == "https://github.com/vercel-labs/agent-skills.git"
        assert result.skill_filter == "frontend-design"


class TestGitHubURLs:
    def test_plain_repo(self):
        result = parse_source("https://github.com/owner/repo")
        assert result.type == "github"
        assert result.url == "https://github.com/owner/repo.git"

    def test_repo_with_git_suffix(self):
        result = parse_source("https://github.com/owner/repo.git")
        assert result.type == "github"
        assert result.url == "https://github.com/owner/repo.git"

    def test_tree_with_branch(self):
        result = parse_source("https://github.com/owner/repo/tree/main")
        assert result.type == "github"
        assert result.ref == "main"
        assert result.subpath is None

    def test_tree_with_path(self):
        result = parse_source("https://github.com/owner/repo/tree/main/skills/my-skill")
        assert result.type == "github"
        assert result.ref == "main"
        assert result.subpath == "skills/my-skill"


class TestGitLabURLs:
    def test_plain_repo(self):
        result = parse_source("https://gitlab.com/org/repo")
        assert result.type == "gitlab"
        assert result.url == "https://gitlab.com/org/repo.git"

    def test_nested_groups(self):
        result = parse_source("https://gitlab.com/group/subgroup/repo")
        assert result.type == "gitlab"
        assert result.url == "https://gitlab.com/group/subgroup/repo.git"

    def test_tree_with_path(self):
        result = parse_source("https://gitlab.com/org/repo/-/tree/main/skills/foo")
        assert result.type == "gitlab"
        assert result.ref == "main"
        assert result.subpath == "skills/foo"


class TestDirectURL:
    def test_direct_skill_url(self):
        result = parse_source("https://docs.example.com/path/SKILL.md")
        assert result.type == "direct-url"

    def test_github_url_not_direct(self):
        # GitHub URLs should be parsed as github type, not direct-url
        result = parse_source("https://github.com/owner/repo")
        assert result.type == "github"


class TestBundled:
    def test_bundled_keyword(self):
        result = parse_source("bundled")
        assert result.type == "bundled"
        assert result.local_path is not None
        assert result.local_path.name == "skills"

    def test_bundled_case_insensitive(self):
        result = parse_source("Bundled")
        assert result.type == "bundled"

    def test_bundled_with_whitespace(self):
        result = parse_source("  bundled  ")
        assert result.type == "bundled"

    def test_bundled_dir_exists(self):
        result = parse_source("bundled")
        assert result.local_path.is_dir()

    def test_bundled_has_skills(self):
        """The bundled skills/ dir should contain at least find-skills."""
        result = parse_source("bundled")
        assert (result.local_path / "find-skills" / "SKILL.md").is_file()


class TestGitFallback:
    def test_ssh_url(self):
        result = parse_source("git@github.com:owner/repo.git")
        assert result.type == "git"
        assert result.url == "git@github.com:owner/repo.git"

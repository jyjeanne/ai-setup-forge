"""Tests for the finder module."""

from unittest.mock import MagicMock, patch

from ai_setup_forge.finder import (
    FindResult,
    search_all,
    search_bundled,
    search_registry,
)


class TestSearchBundled:
    def test_no_query_returns_all(self):
        results = search_bundled(None)
        assert len(results) >= 1
        assert any(r.name == "find-skills" for r in results)

    def test_empty_query_returns_all(self):
        results = search_bundled("")
        assert len(results) >= 1

    def test_matching_query(self):
        results = search_bundled("find")
        assert len(results) >= 1
        names = [r.name for r in results]
        assert "find-skills" in names

    def test_non_matching_query(self):
        results = search_bundled("zzz-nonexistent-zzz")
        assert len(results) == 0

    def test_result_fields(self):
        results = search_bundled("find-skills")
        assert len(results) >= 1
        r = results[0]
        assert r.origin == "bundled"
        assert r.source == "bundled"
        assert "bundled" in r.install_cmd
        assert r.name in r.install_cmd
        assert r.description != ""

    def test_case_insensitive(self):
        results = search_bundled("FIND")
        assert len(results) >= 1

    def test_description_match(self):
        # "discover" is in the find-skills description
        results = search_bundled("discover")
        assert any(r.name == "find-skills" for r in results)

    def test_missing_bundled_dir(self, tmp_path):
        with patch("ai_setup_forge.finder._get_bundled_skills_dir", return_value=tmp_path / "nope"):
            results = search_bundled(None)
        assert results == []


class TestSearchRegistry:
    def test_short_query_returns_empty(self):
        results = search_registry("a")
        assert results == []

    def test_empty_query_returns_empty(self):
        results = search_registry("")
        assert results == []

    def test_successful_search(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "skills": [
                {
                    "id": "owner/repo/my-skill",
                    "name": "my-skill",
                    "source": "owner/repo",
                    "installs": 100,
                },
                {
                    "id": "other/repo/other-skill",
                    "name": "other-skill",
                    "source": "other/repo",
                    "installs": 50,
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("ai_setup_forge.finder.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception
            # TimeoutException is a subclass of HTTPError in httpx
            results = search_registry("my query")

        assert len(results) == 2
        assert results[0].name == "my-skill"
        assert results[0].source == "owner/repo"
        assert results[0].slug == "owner/repo/my-skill"
        assert results[0].installs == 100
        assert results[0].origin == "registry"
        assert "owner/repo@my-skill" in results[0].install_cmd

    def test_api_error_returns_empty(self):
        with patch("ai_setup_forge.finder.httpx") as mock_httpx:
            mock_httpx.get.side_effect = Exception("connection failed")
            mock_httpx.HTTPError = Exception
            # TimeoutException is a subclass of HTTPError in httpx
            results = search_registry("test")

        assert results == []

    def test_malformed_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "format"}
        mock_response.raise_for_status = MagicMock()

        with patch("ai_setup_forge.finder.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception
            # TimeoutException is a subclass of HTTPError in httpx
            results = search_registry("test")

        assert results == []

    def test_missing_name_skipped(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "skills": [
                {"id": "slug", "name": "", "source": "s", "installs": 0},
                {"id": "slug2", "name": "valid", "source": "s", "installs": 1},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("ai_setup_forge.finder.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception
            # TimeoutException is a subclass of HTTPError in httpx
            results = search_registry("test")

        assert len(results) == 1
        assert results[0].name == "valid"


class TestSearchAll:
    def test_no_query_shows_bundled_only(self):
        results = search_all(None)
        assert all(r.origin == "bundled" for r in results)
        assert len(results) >= 1

    def test_with_query_deduplicates(self):
        mock_registry = [
            FindResult(
                name="find-skills",  # same as bundled
                source="vercel-labs/skills",
                slug="vercel-labs/skills/find-skills",
                installs=500000,
                origin="registry",
                install_cmd="ai-setup-forge add vercel-labs/skills@find-skills",
            ),
            FindResult(
                name="other-skill",
                source="owner/repo",
                slug="owner/repo/other-skill",
                installs=100,
                origin="registry",
                install_cmd="ai-setup-forge add owner/repo@other-skill",
            ),
        ]

        with patch("ai_setup_forge.finder.search_registry", return_value=mock_registry):
            results = search_all("find")

        names = [r.name for r in results]
        assert names.count("find-skills") == 1
        # Bundled version should win (comes first)
        find_result = next(r for r in results if r.name == "find-skills")
        assert find_result.origin == "bundled"
        # Other registry result should also appear
        assert "other-skill" in names

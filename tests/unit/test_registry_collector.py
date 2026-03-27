"""Tests for collect_registry_meta — external registry metadata extraction."""

from unittest.mock import AsyncMock

import pytest
from collect_registry_meta import (
    _derive_registry_name,
    _MetaTagParser,
    extract_categories_from_html,
    extract_description_from_html,
    fetch_registry_meta_for_server,
)

# --- Test: _derive_registry_name ---


class TestDeriveRegistryName:
    def test_github_style_server_id(self) -> None:
        """owner/repo -> repo part."""
        assert _derive_registry_name("clay-inc/clay-mcp") == "clay-mcp"

    def test_simple_server_id(self) -> None:
        """No slash -> use as-is."""
        assert _derive_registry_name("instagram") == "instagram"

    def test_nested_slashes(self) -> None:
        """Multiple slashes -> last segment."""
        assert _derive_registry_name("org/sub/repo") == "repo"


# --- Test: extract_description_from_html ---


class TestExtractDescriptionFromHtml:
    def test_og_description(self) -> None:
        """Extract og:description meta tag."""
        html = """
        <html><head>
            <meta property="og:description" content="A great MCP server for data.">
        </head><body></body></html>
        """
        result = extract_description_from_html(html)
        assert result == "A great MCP server for data."

    def test_meta_description_fallback(self) -> None:
        """Fall back to meta name=description when og:description absent."""
        html = """
        <html><head>
            <meta name="description" content="Another MCP integration tool.">
        </head><body></body></html>
        """
        result = extract_description_from_html(html)
        assert result == "Another MCP integration tool."

    def test_og_preferred_over_meta(self) -> None:
        """og:description preferred when both present."""
        html = """
        <html><head>
            <meta property="og:description" content="OG description preferred.">
            <meta name="description" content="Meta description fallback.">
        </head><body></body></html>
        """
        result = extract_description_from_html(html)
        assert result == "OG description preferred."

    def test_short_description_returns_none(self) -> None:
        """Descriptions shorter than 10 chars return None."""
        html = """
        <html><head>
            <meta property="og:description" content="Short">
        </head><body></body></html>
        """
        result = extract_description_from_html(html)
        assert result is None

    def test_no_meta_tags_returns_none(self) -> None:
        """No relevant meta tags -> None."""
        html = "<html><head><title>Page</title></head><body></body></html>"
        result = extract_description_from_html(html)
        assert result is None

    def test_empty_html_returns_none(self) -> None:
        """Empty HTML -> None."""
        result = extract_description_from_html("")
        assert result is None

    def test_malformed_html_returns_none(self) -> None:
        """Malformed HTML doesn't crash."""
        html = "<html><head><meta property='og:description' content='"
        result = extract_description_from_html(html)
        # May or may not extract — just shouldn't crash
        assert result is None or isinstance(result, str)


# --- Test: extract_categories_from_html ---


class TestExtractCategoriesFromHtml:
    def test_meta_keywords(self) -> None:
        """Extract categories from meta keywords tag."""
        html = """
        <html><head>
            <meta name="keywords" content="mcp, social-media, automation">
        </head><body></body></html>
        """
        result = extract_categories_from_html(html)
        assert "mcp" in result
        assert "social-media" in result
        assert "automation" in result

    def test_no_keywords_returns_empty(self) -> None:
        """No keywords meta tag -> empty list."""
        html = "<html><head></head><body></body></html>"
        result = extract_categories_from_html(html)
        assert result == []


# --- Test: _MetaTagParser ---


class TestMetaTagParser:
    def test_title_extraction(self) -> None:
        """Extract title from HTML."""
        parser = _MetaTagParser()
        parser.feed("<html><head><title>My Page Title</title></head></html>")
        assert parser.title == "My Page Title"

    def test_multiple_meta_tags(self) -> None:
        """Parse multiple different meta tags."""
        parser = _MetaTagParser()
        html = """
        <html><head>
            <meta property="og:description" content="OG desc">
            <meta name="description" content="Meta desc">
            <title>Title</title>
        </head></html>
        """
        parser.feed(html)
        assert parser.og_description == "OG desc"
        assert parser.meta_description == "Meta desc"
        assert parser.title == "Title"


# --- Test: fetch_registry_meta_for_server ---


class TestFetchRegistryMetaForServer:
    @pytest.fixture
    def mock_registries(self) -> list[dict[str, str]]:
        """Small registry list for testing."""
        return [
            {"name": "test_registry", "url_template": "https://test.com/{server_name}"},
        ]

    async def test_successful_fetch(self, mock_registries: list[dict[str, str]]) -> None:
        """Successful fetch extracts description from HTML."""
        html = """
        <html><head>
            <meta property="og:description" content="Test MCP server for automation.">
        </head><body></body></html>
        """
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_client.get.return_value = mock_response

        results = await fetch_registry_meta_for_server(mock_client, "test-server", mock_registries)

        assert len(results) == 1
        assert results[0]["server_id"] == "test-server"
        assert results[0]["source"] == "test_registry"
        assert results[0]["description"] == "Test MCP server for automation."

    async def test_404_returns_empty(self, mock_registries: list[dict[str, str]]) -> None:
        """404 response -> empty results."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        results = await fetch_registry_meta_for_server(
            mock_client, "missing-server", mock_registries
        )

        assert results == []

    async def test_no_description_in_html(self, mock_registries: list[dict[str, str]]) -> None:
        """HTML page without description meta tags -> empty results."""
        html = "<html><head><title>Page</title></head><body></body></html>"
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_client.get.return_value = mock_response

        results = await fetch_registry_meta_for_server(
            mock_client, "no-desc-server", mock_registries
        )

        assert results == []

    async def test_github_server_uses_repo_name(
        self, mock_registries: list[dict[str, str]]
    ) -> None:
        """GitHub-style server_id uses repo name in URL."""
        html = """
        <html><head>
            <meta property="og:description" content="Repo description from registry.">
        </head><body></body></html>
        """
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_client.get.return_value = mock_response

        await fetch_registry_meta_for_server(mock_client, "owner/repo-name", mock_registries)

        # URL should use "repo-name" not "owner/repo-name"
        call_args = mock_client.get.call_args
        assert "repo-name" in call_args[0][0]
        assert "owner/" not in call_args[0][0]

    async def test_multiple_registries(self) -> None:
        """Multiple registries -> multiple results when all succeed."""
        registries = [
            {"name": "reg_a", "url_template": "https://a.com/{server_name}"},
            {"name": "reg_b", "url_template": "https://b.com/{server_name}"},
        ]
        html_a = (
            '<html><head><meta property="og:description" '
            'content="Description from A."></head></html>'
        )
        html_b = (
            '<html><head><meta property="og:description" '
            'content="Description from B."></head></html>'
        )

        mock_client = AsyncMock()

        # Return different HTML per URL
        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.status_code = 200
            if "a.com" in url:
                resp.text = html_a
            else:
                resp.text = html_b
            return resp

        mock_client.get = mock_get

        results = await fetch_registry_meta_for_server(mock_client, "test-server", registries)

        assert len(results) == 2
        sources = [r["source"] for r in results]
        assert "reg_a" in sources
        assert "reg_b" in sources

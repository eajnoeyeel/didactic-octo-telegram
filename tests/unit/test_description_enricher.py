"""Tests for description_enricher — enriched server description generation."""

import json
from pathlib import Path

import pytest

from data.description_enricher import (
    build_enriched_description,
    enrich_all_servers,
    load_github_meta,
    load_registry_meta,
    select_best_registry_description,
)

# --- Fixtures ---


@pytest.fixture
def github_server() -> dict:
    """A GitHub-based server with tools."""
    return {
        "server_id": "clay-inc/clay-mcp",
        "name": "Clay MCP",
        "description": "Marketing enrichment via Smithery",
        "homepage": None,
        "tools": [
            {
                "server_id": "clay-inc/clay-mcp",
                "tool_name": "enrich_person",
                "tool_id": "clay-inc/clay-mcp::enrich_person",
                "description": "Enrich a person",
            },
            {
                "server_id": "clay-inc/clay-mcp",
                "tool_name": "enrich_company",
                "tool_id": "clay-inc/clay-mcp::enrich_company",
                "description": "Enrich a company",
            },
        ],
    }


@pytest.fixture
def github_meta() -> dict:
    """GitHub metadata for clay-inc/clay-mcp."""
    return {
        "server_id": "clay-inc/clay-mcp",
        "github_description": "A simple MCP server for Clay.",
        "github_topics": ["crm", "mcp-server"],
        "homepage": "https://clay.earth",
    }


@pytest.fixture
def non_github_server() -> dict:
    """A non-GitHub server (Composio-style) with tools."""
    return {
        "server_id": "instagram",
        "name": "Instagram",
        "description": "Instagram is a social media platform for sharing photos.",
        "homepage": None,
        "tools": [
            {
                "server_id": "instagram",
                "tool_name": "CREATE_POST",
                "tool_id": "instagram::CREATE_POST",
                "description": "Publish a draft media container to Instagram.",
            },
        ],
    }


@pytest.fixture
def server_no_tools() -> dict:
    """A server with no tools."""
    return {
        "server_id": "empty-org/empty-mcp",
        "name": "Empty",
        "description": "An empty server",
        "homepage": None,
        "tools": [],
    }


@pytest.fixture
def registry_entries_multi() -> list[dict]:
    """Multiple registry entries for the same server."""
    return [
        {
            "server_id": "instagram",
            "source": "glama",
            "description": "Instagram MCP server for managing posts and stories via API.",
            "categories": ["social-media"],
        },
        {
            "server_id": "instagram",
            "source": "pulsemcp",
            "description": "Short desc.",
            "categories": [],
        },
        {
            "server_id": "instagram",
            "source": "mcp_market",
            "description": (
                "Instagram MCP Server provides a comprehensive integration layer "
                "for automating Instagram workflows including posting photos, "
                "managing stories, and querying analytics data through the MCP protocol."
            ),
            "categories": ["social-media", "automation"],
        },
    ]


# --- Test: select_best_registry_description ---


class TestSelectBestRegistryDescription:
    def test_selects_longest_and_most_specific(self, registry_entries_multi: list[dict]) -> None:
        """Should pick the longest, most specific description (mcp_market)."""
        result = select_best_registry_description(registry_entries_multi)

        assert result is not None
        # mcp_market entry is the longest and has technical terms
        assert "comprehensive integration layer" in result

    def test_empty_list_returns_none(self) -> None:
        """Empty entries -> None."""
        result = select_best_registry_description([])
        assert result is None

    def test_entries_with_no_descriptions(self) -> None:
        """Entries with no/empty descriptions -> None."""
        entries = [
            {"server_id": "test", "source": "glama", "description": None},
            {"server_id": "test", "source": "pulsemcp", "description": ""},
        ]
        result = select_best_registry_description(entries)
        assert result is None

    def test_single_entry(self) -> None:
        """Single valid entry is returned."""
        entries = [
            {
                "server_id": "test",
                "source": "glama",
                "description": "A useful MCP server for data integration.",
            },
        ]
        result = select_best_registry_description(entries)
        assert result == "A useful MCP server for data integration."


# --- Test: build_enriched_description ---


class TestBuildEnrichedDescription:
    def test_with_github_meta(self, github_server: dict, github_meta: dict) -> None:
        """GitHub meta present -> github_description + topics + tool names."""
        result = build_enriched_description(github_server, github_meta)

        assert "Clay MCP" in result
        assert "A simple MCP server for Clay." in result
        assert "Topics: crm, mcp-server" in result
        assert "Tools: enrich_person, enrich_company" in result

    def test_without_github_meta_fallback(self, non_github_server: dict) -> None:
        """No GitHub meta -> fallback to smithery description + tools."""
        result = build_enriched_description(non_github_server, None)

        assert "Instagram" in result
        assert "Instagram is a social media platform for sharing photos." in result
        assert "Tools: CREATE_POST" in result

    def test_github_meta_with_none_description(
        self, github_server: dict, github_meta: dict
    ) -> None:
        """GitHub meta present but description is None -> fallback to smithery."""
        meta_no_desc = {**github_meta, "github_description": None}
        result = build_enriched_description(github_server, meta_no_desc)

        assert "Marketing enrichment via Smithery" in result
        assert "github_description" not in result

    def test_empty_topics_omits_topics_line(self, github_server: dict, github_meta: dict) -> None:
        """Empty topics list -> Topics line omitted entirely."""
        meta_no_topics = {**github_meta, "github_topics": []}
        result = build_enriched_description(github_server, meta_no_topics)

        assert "Topics:" not in result
        assert "A simple MCP server for Clay." in result

    def test_no_tools_omits_tools_line(self, server_no_tools: dict) -> None:
        """Server with no tools -> Tools line omitted."""
        result = build_enriched_description(server_no_tools, None)

        assert "Tools:" not in result
        assert "Empty" in result

    def test_immutability_original_not_modified(
        self, github_server: dict, github_meta: dict
    ) -> None:
        """Inputs are not mutated."""
        original_server = json.loads(json.dumps(github_server))
        original_meta = json.loads(json.dumps(github_meta))

        build_enriched_description(github_server, github_meta)

        assert github_server == original_server
        assert github_meta == original_meta

    def test_server_with_none_smithery_description(self) -> None:
        """Server description is None, no GitHub meta -> name only + tools."""
        server = {
            "server_id": "test-org/test",
            "name": "Test",
            "description": None,
            "homepage": None,
            "tools": [
                {
                    "server_id": "test-org/test",
                    "tool_name": "do_thing",
                    "tool_id": "test-org/test::do_thing",
                    "description": "Does a thing",
                },
            ],
        }
        result = build_enriched_description(server, None)

        assert result.startswith("Test")
        assert "Tools: do_thing" in result
        assert "None" not in result

    # --- New: Registry meta tests ---

    def test_registry_fallback_when_no_github(
        self,
        non_github_server: dict,
        registry_entries_multi: list[dict],
    ) -> None:
        """No GitHub meta -> best registry description used over Smithery."""
        result = build_enriched_description(non_github_server, None, registry_entries_multi)

        # Should use the mcp_market description (longest/best)
        assert "comprehensive integration layer" in result
        # Should NOT use Smithery description
        assert "Instagram is a social media platform for sharing photos." not in result
        assert "Tools: CREATE_POST" in result

    def test_github_takes_priority_over_registry(
        self,
        github_server: dict,
        github_meta: dict,
        registry_entries_multi: list[dict],
    ) -> None:
        """GitHub description takes priority over registry descriptions."""
        result = build_enriched_description(github_server, github_meta, registry_entries_multi)

        assert "A simple MCP server for Clay." in result
        assert "comprehensive integration layer" not in result

    def test_registry_overrides_smithery_fallback(self) -> None:
        """Registry description used when GitHub meta has None description."""
        server = {
            "server_id": "gmail",
            "name": "Gmail",
            "description": "Generic Smithery blurb about email.",
            "tools": [],
        }
        github_meta_none_desc = {
            "server_id": "gmail",
            "github_description": None,
            "github_topics": [],
        }
        registry = [
            {
                "server_id": "gmail",
                "source": "glama",
                "description": "Gmail MCP server for managing email workflows and automation.",
                "categories": ["communication"],
            },
        ]
        result = build_enriched_description(server, github_meta_none_desc, registry)

        assert "Gmail MCP server for managing email workflows" in result
        assert "Generic Smithery blurb" not in result

    def test_no_github_no_registry_falls_back_to_smithery(self, non_github_server: dict) -> None:
        """No GitHub meta, empty registry -> Smithery fallback."""
        result = build_enriched_description(non_github_server, None, [])

        assert "Instagram is a social media platform for sharing photos." in result


# --- Test: load_github_meta ---


class TestLoadGithubMeta:
    def test_load_valid_jsonl(self, tmp_path: Path) -> None:
        """Load a JSONL file with multiple entries."""
        meta_file = tmp_path / "github_meta.jsonl"
        entries = [
            {
                "server_id": "org-a/repo-a",
                "github_description": "Repo A desc",
                "github_topics": ["topic1"],
                "homepage": None,
            },
            {
                "server_id": "org-b/repo-b",
                "github_description": "Repo B desc",
                "github_topics": [],
                "homepage": "https://b.com",
            },
        ]
        meta_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = load_github_meta(meta_file)

        assert len(result) == 2
        assert result["org-a/repo-a"]["github_description"] == "Repo A desc"
        assert result["org-b/repo-b"]["homepage"] == "https://b.com"

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns empty dict."""
        meta_file = tmp_path / "github_meta.jsonl"
        meta_file.write_text("")

        result = load_github_meta(meta_file)
        assert result == {}

    def test_load_file_not_found(self, tmp_path: Path) -> None:
        """Missing file returns empty dict (graceful fallback)."""
        result = load_github_meta(tmp_path / "nonexistent.jsonl")
        assert result == {}


# --- Test: load_registry_meta ---


class TestLoadRegistryMeta:
    def test_load_valid_jsonl(self, tmp_path: Path) -> None:
        """Load a JSONL file with multiple entries, grouped by server_id."""
        meta_file = tmp_path / "registry_meta.jsonl"
        entries = [
            {
                "server_id": "instagram",
                "source": "glama",
                "description": "Glama Instagram desc",
                "categories": ["social"],
            },
            {
                "server_id": "instagram",
                "source": "pulsemcp",
                "description": "PulseMCP Instagram desc",
                "categories": [],
            },
            {
                "server_id": "gmail",
                "source": "glama",
                "description": "Glama Gmail desc",
                "categories": ["email"],
            },
        ]
        meta_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = load_registry_meta(meta_file)

        assert len(result) == 2
        assert len(result["instagram"]) == 2
        assert len(result["gmail"]) == 1
        assert result["instagram"][0]["source"] == "glama"

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns empty dict."""
        meta_file = tmp_path / "registry_meta.jsonl"
        meta_file.write_text("")

        result = load_registry_meta(meta_file)
        assert result == {}

    def test_load_file_not_found(self, tmp_path: Path) -> None:
        """Missing file returns empty dict (graceful fallback)."""
        result = load_registry_meta(tmp_path / "nonexistent.jsonl")
        assert result == {}


# --- Test: enrich_all_servers ---


class TestEnrichAllServers:
    def test_integration_with_temp_files(self, tmp_path: Path) -> None:
        """Full pipeline: servers + github meta -> enriched descriptions."""
        # Write servers.jsonl
        servers_file = tmp_path / "servers.jsonl"
        servers = [
            {
                "server_id": "clay-inc/clay-mcp",
                "name": "Clay MCP",
                "description": "Smithery marketing blurb",
                "homepage": None,
                "tools": [
                    {
                        "server_id": "clay-inc/clay-mcp",
                        "tool_name": "enrich",
                        "tool_id": "clay-inc/clay-mcp::enrich",
                        "description": "Enrich data",
                    },
                ],
            },
            {
                "server_id": "instagram",
                "name": "Instagram",
                "description": "Social media platform",
                "homepage": None,
                "tools": [],
            },
        ]
        servers_file.write_text("\n".join(json.dumps(s) for s in servers) + "\n")

        # Write github_meta.jsonl
        meta_file = tmp_path / "github_meta.jsonl"
        meta_entries = [
            {
                "server_id": "clay-inc/clay-mcp",
                "github_description": "Clay API integration",
                "github_topics": ["crm"],
                "homepage": "https://clay.earth",
            },
        ]
        meta_file.write_text("\n".join(json.dumps(m) for m in meta_entries) + "\n")

        # Run without registry meta
        result = enrich_all_servers(servers_file, meta_file)

        assert len(result) == 2
        # GitHub-enriched
        clay = next(r for r in result if r["server_id"] == "clay-inc/clay-mcp")
        assert "Clay API integration" in clay["enriched_description"]
        assert "Topics: crm" in clay["enriched_description"]
        # Fallback
        ig = next(r for r in result if r["server_id"] == "instagram")
        assert "Social media platform" in ig["enriched_description"]

    def test_with_registry_meta(self, tmp_path: Path) -> None:
        """Full pipeline: servers + github meta + registry meta."""
        servers_file = tmp_path / "servers.jsonl"
        servers = [
            {
                "server_id": "instagram",
                "name": "Instagram",
                "description": "Smithery social media desc",
                "homepage": None,
                "tools": [
                    {
                        "server_id": "instagram",
                        "tool_name": "CREATE_POST",
                        "tool_id": "instagram::CREATE_POST",
                        "description": "Create a post",
                    },
                ],
            },
        ]
        servers_file.write_text(json.dumps(servers[0]) + "\n")

        # No GitHub meta for instagram
        meta_file = tmp_path / "github_meta.jsonl"
        meta_file.write_text("")

        # Registry meta available
        registry_file = tmp_path / "registry_meta.jsonl"
        registry_entries = [
            {
                "server_id": "instagram",
                "source": "glama",
                "description": (
                    "Instagram MCP server for comprehensive social media automation "
                    "including posting, stories, and analytics integration."
                ),
                "categories": ["social-media"],
            },
        ]
        registry_file.write_text(json.dumps(registry_entries[0]) + "\n")

        result = enrich_all_servers(servers_file, meta_file, registry_file)

        assert len(result) == 1
        ig = result[0]
        # Should use registry description, not Smithery
        assert "comprehensive social media automation" in ig["enriched_description"]
        assert "Tools: CREATE_POST" in ig["enriched_description"]

    def test_missing_github_meta_file(self, tmp_path: Path) -> None:
        """If github_meta file doesn't exist, all servers get fallback."""
        servers_file = tmp_path / "servers.jsonl"
        servers = [
            {
                "server_id": "some-org/some-repo",
                "name": "Some Repo",
                "description": "A server",
                "homepage": None,
                "tools": [
                    {
                        "server_id": "some-org/some-repo",
                        "tool_name": "act",
                        "tool_id": "some-org/some-repo::act",
                        "description": "Do action",
                    },
                ],
            },
        ]
        servers_file.write_text(json.dumps(servers[0]) + "\n")

        result = enrich_all_servers(servers_file, tmp_path / "missing.jsonl")

        assert len(result) == 1
        assert "A server" in result[0]["enriched_description"]

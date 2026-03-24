"""Core data models for MCP Discovery Platform."""

from pydantic import BaseModel, computed_field, field_validator


TOOL_ID_SEPARATOR = "::"


class MCPServerSummary(BaseModel):
    """Smithery list endpoint summary — no tools."""

    qualified_name: str
    display_name: str
    description: str | None = None
    use_count: int = 0
    is_verified: bool = False
    is_deployed: bool = False


class MCPTool(BaseModel):
    """A single MCP tool with validated tool_id."""

    server_id: str
    tool_name: str
    tool_id: str
    description: str | None = None
    input_schema: dict | None = None

    @computed_field
    @property
    def parameter_names(self) -> list[str]:
        if not self.input_schema:
            return []
        props = self.input_schema.get("properties", {})
        return list(props.keys())

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v: str, info) -> str:
        server_id = info.data.get("server_id", "")
        tool_name = info.data.get("tool_name", "")
        expected = f"{server_id}{TOOL_ID_SEPARATOR}{tool_name}"
        if v != expected:
            raise ValueError(f"tool_id must be '{expected}', got '{v}'")
        return v


class MCPServer(BaseModel):
    """MCP server with its tools."""

    server_id: str
    name: str
    description: str | None = None
    homepage: str | None = None
    tools: list[MCPTool] = []


class SearchResult(BaseModel):
    """A single search result from the pipeline."""

    tool: MCPTool
    score: float
    rank: int
    reason: str | None = None


class FindBestToolRequest(BaseModel):
    """API request for tool discovery."""

    query: str
    top_k: int = 3
    strategy: str = "sequential"


class FindBestToolResponse(BaseModel):
    """API response for tool discovery."""

    query: str
    results: list[SearchResult]
    confidence: float
    disambiguation_needed: bool
    strategy_used: str
    latency_ms: float


class GroundTruthEntry(BaseModel):
    """A single ground truth entry for evaluation.

    Simplified model for Phase 0-2. Phase 3+ will extend with:
    query_id, Difficulty/Ambiguity/Category enums, distractors, acceptable_alternatives.
    See docs/design/ground-truth-schema.md for the full schema.
    """

    query: str
    correct_server_id: str
    correct_tool_id: str
    difficulty: str | None = None  # Will become Difficulty enum in Phase 3+
    manually_verified: bool = False

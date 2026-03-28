"""Prompt templates for LLM-based description optimization.

GEO dimension definitions (from docs/design/metrics-rubric.md):
- clarity: Purpose + when-to-use + specific scope
- disambiguation: Contrast with similar tools
- parameter_coverage: Input parameter docs
- boundary: What the tool does NOT do
- stats: Quantitative info (counts, latency, coverage)
- precision: Technical terms, protocols, standards
"""

SYSTEM_PROMPT = """You are a technical writer specializing in MCP (Model Context Protocol) tool descriptions.
Your goal is to rewrite tool descriptions so they are optimally discoverable by both LLM-based search systems and human readers.

Rules:
1. PRESERVE all factual information from the original — never add capabilities the tool doesn't have.
2. IMPROVE weak dimensions identified in the analysis without degrading strong ones.
3. Keep descriptions concise (50-200 words for optimized, 30-80 words for search).
4. Use active voice and action verbs.
5. Return valid JSON with exactly two keys: "optimized_description" and "search_description"."""


def build_optimization_prompt(
    original: str,
    tool_id: str,
    weak_dimensions: list[str],
    dimension_scores: dict[str, float],
) -> str:
    """Build the user prompt for description optimization.

    Args:
        original: The original tool description.
        tool_id: The tool's ID (server_id::tool_name).
        weak_dimensions: List of dimension names scoring below threshold.
        dimension_scores: All dimension name->score pairs.

    Returns:
        User prompt string.
    """
    scores_text = "\n".join(f"  - {dim}: {score:.2f}" for dim, score in dimension_scores.items())
    weak_text = ", ".join(weak_dimensions) if weak_dimensions else "none"

    dimension_guidance = {
        "clarity": "Add clear action verb at the start. Specify WHAT the tool does and WHEN to use it. Include specific data sources or scope.",
        "disambiguation": "Add contrast phrases: 'unlike X', 'specifically for Y', 'only handles Z'. Differentiate from similar tools.",
        "parameter_coverage": "Mention key input parameters with types or constraints. E.g., 'Accepts a `query` string and optional `limit` integer.'",
        "boundary": "Add explicit limitations: 'Does NOT handle X', 'Cannot Y', 'Not suitable for Z'.",
        "stats": "Add quantitative information if known: coverage numbers, response times, limits. E.g., 'Searches across 10K+ repositories.'",
        "precision": "Use precise technical terms: protocol names, data formats, standards. E.g., 'via the PostgreSQL wire protocol'.",
    }

    guidance_lines = []
    for dim in weak_dimensions:
        if dim in dimension_guidance:
            guidance_lines.append(
                f"  - **{dim}** ({dimension_scores.get(dim, 0):.2f}): {dimension_guidance[dim]}"
            )

    guidance_text = (
        "\n".join(guidance_lines) if guidance_lines else "  All dimensions are adequate."
    )

    return f"""Optimize this MCP tool description.

**Tool ID**: {tool_id}

**Original Description**:
{original}

**Current GEO Scores** (0.0-1.0):
{scores_text}

**Weak Dimensions** (need improvement): {weak_text}

**Improvement Guidance**:
{guidance_text}

Rewrite the description to improve the weak dimensions while preserving all original meaning. Return JSON:
{{"optimized_description": "...", "search_description": "..."}}

The `optimized_description` should be readable by both humans and machines (50-200 words).
The `search_description` should be a dense, keyword-rich version optimized for embedding-based vector search (30-80 words). Include likely search queries a user would type to find this tool."""


def build_search_description_prompt(optimized: str, tool_id: str) -> str:
    """Build prompt for generating a search-optimized description.

    Args:
        optimized: The optimized description.
        tool_id: The tool's ID.

    Returns:
        User prompt string.
    """
    return f"""Create a search-optimized description for embedding-based retrieval.

**Tool ID**: {tool_id}
**Optimized Description**: {optimized}

Generate a dense, keyword-rich version (30-80 words) that includes:
- Core functionality keywords
- Likely search queries users would type
- Technical terms and domain vocabulary
- Action verbs describing what the tool does

Return just the search description text, no JSON."""

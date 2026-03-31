"""Prompt templates for LLM-based description optimization.

GEO dimension definitions (from docs/design/metrics-rubric.md):
- clarity: Purpose + when-to-use + specific scope
- disambiguation: Contrast with similar tools
- parameter_coverage: Input parameter docs
- fluency: Sentence structure, connectors, readability
- stats: Quantitative info (counts, latency, coverage)
- precision: Technical terms, protocols, standards
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from description_optimizer.models import OptimizationContext

SYSTEM_PROMPT = """You are a technical writer specializing in MCP (Model Context Protocol) tool descriptions.
Your goal is to rewrite tool descriptions so they are easier for embedding-based retrieval systems to find.

CRITICAL RULES:
1. Preserve the tool's original meaning and capabilities.
2. ONLY use information directly supported by the original description or provided input_schema.
3. NEVER invent limitations, capabilities, or parameters not in the provided data.
4. If no input_schema is provided, do NOT mention specific parameter names or types.
5. Prefer short, dense, retrieval-friendly wording over long explanatory paragraphs.
6. Avoid naming sibling tools unless absolutely necessary for factual disambiguation.
7. Return valid JSON with exactly two keys: "optimized_description" and "retrieval_description"."""


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
        "disambiguation": "Clarify what makes THIS tool unique: its specific action, target data type, or domain. Do NOT mention or compare with other tools by name.",
        "parameter_coverage": "Mention key input parameters with types or constraints. E.g., 'Accepts a `query` string and optional `limit` integer.'",
        "fluency": "Improve sentence structure: use complete sentences with clear subjects and verbs. Add transition words (e.g., 'Use this when...', 'It also supports...'). Aim for 2-3 well-formed sentences.",
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

    return f"""Optimize this MCP tool description for retrieval.

**Tool ID**: {tool_id}

**Original Description**:
{original}

**Current GEO Scores** (0.0-1.0):
{scores_text}

**Weak Dimensions** (need improvement): {weak_text}

**Improvement Guidance**:
{guidance_text}

Rewrite the description to improve retrieval alignment while preserving all original meaning. Return JSON:
{{"optimized_description": "...", "retrieval_description": "..."}}

The `optimized_description` should stay concise and factual.
The `retrieval_description` should be a dense, keyword-rich version optimized for embedding-based vector search (15-60 words). Include likely search intents without turning the text into a long paragraph."""


def build_grounded_prompt(
    original: str,
    tool_id: str,
    input_schema: dict | None,
    sibling_tools: list[dict],
    weak_dimensions: list[str],
    dimension_scores: dict[str, float],
) -> str:
    """Build a grounded optimization prompt with real tool data.

    Args:
        original: The original tool description.
        tool_id: The tool's ID (server_id::tool_name).
        input_schema: The tool's JSON input schema, if available.
        sibling_tools: Other tools on the same server, for disambiguation.
        weak_dimensions: List of dimension names scoring below threshold.
        dimension_scores: All dimension name->score pairs.

    Returns:
        User prompt string grounded in actual tool data.
    """
    sections = []

    sections.append("Rewrite this MCP tool description to improve retrieval discoverability.\n")
    sections.append(f"**Tool ID**: {tool_id}\n")
    sections.append(
        f"**Original Description** (keep this as the foundation — do not discard it):\n{original}\n"
    )

    # Input schema section — only if available
    if input_schema:
        schema_text = json.dumps(input_schema, indent=2, ensure_ascii=False)
        sections.append(
            f"**Input Schema** (use this to accurately describe parameters):\n"
            f"```json\n{schema_text}\n```\n"
        )

    # Sibling tools section — only if available
    if sibling_tools:
        sibling_lines = []
        for st in sibling_tools[:8]:
            desc_preview = (st.get("description") or "")[:120]
            sibling_lines.append(f"- {st['tool_name']}: {desc_preview}")
        siblings_text = "\n".join(sibling_lines)
        sections.append(
            f"**Other tools on this server** (use carefully for disambiguation only — "
            f"do not list them in the final retrieval text unless necessary):\n{siblings_text}\n"
        )

    # Scores
    scores_text = "\n".join(f"  - {dim}: {score:.2f}" for dim, score in dimension_scores.items())
    sections.append(f"**Current GEO Scores** (0.0-1.0):\n{scores_text}\n")

    # Grounded improvement guidance
    weak_text = ", ".join(weak_dimensions) if weak_dimensions else "none"
    sections.append(f"**Weak Dimensions**: {weak_text}\n")

    guidance = _build_grounded_guidance(
        weak_dimensions, dimension_scores, input_schema, sibling_tools
    )
    if guidance:
        sections.append(f"**Improvement Guidance**:\n{guidance}\n")

    sections.append(
        "**Output Rules**:\n"
        "1. Preserve the original meaning, but you may rewrite the wording for retrieval.\n"
        "2. Do NOT invent any information not present in the original description or input schema.\n"
        "3. Prefer short, target-only phrasing over long explanations.\n"
        "4. Do NOT list sibling tool names in retrieval_description.\n"
        "5. Keep optimized_description concise and retrieval_description to 15-60 words.\n\n"
        'Return JSON:\n{"optimized_description": "...", "retrieval_description": "..."}'
    )

    return "\n".join(sections)


def _build_grounded_guidance(
    weak_dimensions: list[str],
    dimension_scores: dict[str, float],
    input_schema: dict | None,
    sibling_tools: list[dict],
) -> str:
    """Build dimension-specific guidance grounded in available data.

    Args:
        weak_dimensions: List of dimension names scoring below threshold.
        dimension_scores: All dimension name->score pairs.
        input_schema: The tool's JSON input schema, if available.
        sibling_tools: Other tools on the same server, for disambiguation.

    Returns:
        Guidance text string, or empty string if no guidance needed.
    """
    lines = []

    guidance_map = {
        "clarity": "Add a clear action verb at the start if missing. Specify WHEN to use this tool based on the original description.",
        "fluency": "Improve sentence structure: use complete sentences, add transition words, ensure readability. Do NOT add new factual claims.",
        "precision": "Use precise technical terms that are already present or directly inferable from the original description.",
        "stats": "Include quantitative information ONLY if present in the original description.",
    }

    if "parameter_coverage" in weak_dimensions:
        if input_schema:
            props = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            param_summary = ", ".join(
                f"`{name}` ({'required' if name in required else 'optional'})"
                for name in list(props.keys())[:6]
            )
            lines.append(
                f"  - **parameter_coverage** ({dimension_scores.get('parameter_coverage', 0):.2f}): "
                f"Mention these actual parameters: {param_summary}"
            )
        else:
            lines.append(
                f"  - **parameter_coverage** ({dimension_scores.get('parameter_coverage', 0):.2f}): "
                f"No input_schema available — skip parameter improvements to avoid hallucination."
            )

    if "disambiguation" in weak_dimensions:
        lines.append(
            f"  - **disambiguation** ({dimension_scores.get('disambiguation', 0):.2f}): "
            f"Clarify what makes THIS tool unique — its specific action, target data type, "
            f"or domain scope. Use phrases like 'specifically handles [action] for [domain]'. "
            f"Do NOT mention other tools by name or compare with siblings."
        )

    for dim in weak_dimensions:
        if dim in guidance_map and dim not in ("parameter_coverage", "disambiguation"):
            lines.append(f"  - **{dim}** ({dimension_scores.get(dim, 0):.2f}): {guidance_map[dim]}")

    return "\n".join(lines) if lines else "  All dimensions are adequate — preserve the original."


def build_search_description_prompt(optimized: str, tool_id: str) -> str:
    """Build prompt for generating a retrieval-optimized description.

    Args:
        optimized: The optimized description.
        tool_id: The tool's ID.

    Returns:
        User prompt string.
    """
    return f"""Create a retrieval-optimized description for embedding-based retrieval.

**Tool ID**: {tool_id}
**Optimized Description**: {optimized}

Generate a dense, keyword-rich version (30-80 words) that includes:
- Core functionality keywords
- Likely search queries users would type
- Technical terms and domain vocabulary
- Action verbs describing what the tool does

Return just the retrieval description text, no JSON."""


def build_query_aware_prompt(
    context: "OptimizationContext",
    relevant_queries: list[str] | None = None,
) -> str:
    """Build optimization prompt focused on retrieval discoverability.

    Instead of "improve GEO dimension scores", tells the optimizer:
    "Make this tool findable for these search queries."
    """
    queries = relevant_queries or []

    parts = [
        "You are optimizing an MCP tool description for search discoverability.",
        "",
        f"**Tool ID:** {context.tool_id}",
        f"**Original Description:** {context.original_description}",
    ]

    if context.input_schema:
        parts.append(
            f"\n**Input Schema** (factual ground truth):\n"
            f"```json\n{json.dumps(context.input_schema, indent=2)}\n```"
        )

    if context.sibling_tools:
        parts.append(
            f"\nThis server has {len(context.sibling_tools)} other tools. "
            f"Focus on what makes THIS tool unique without naming the others."
        )

    if queries:
        parts.append("\n**Search queries that should find this tool:**")
        for q in queries[:10]:
            parts.append(f'- "{q}"')
        parts.append(
            "\nMake the description naturally match these search intents. "
            "A user typing any of these queries should find this tool first."
        )

    parts.extend(
        [
            "\n## Rules",
            "1. KEEP the original description text intact — AUGMENT, do not replace",
            "2. ONLY add information from the original description or input_schema",
            "3. NEVER invent limitations, capabilities, or parameters not in the provided data",
            "4. Make the description naturally match the search queries above",
            "5. Include actual parameter names from the schema (with backticks) if available",
            "6. Emphasize this tool's unique action or domain — do NOT name or reference other tools",
            "",
            "## Output Format",
            'Return JSON: {"optimized_description": "...", "retrieval_description": "..."}',
            "- optimized_description: 50-200 words, human+machine readable",
            "- retrieval_description: 15-60 words, keyword-dense for embedding search",
        ]
    )

    return "\n".join(parts)

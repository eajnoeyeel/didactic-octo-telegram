"""Generate enriched server descriptions from multiple sources.

Combines Smithery marketing descriptions with GitHub repository metadata
(description, topics) and external registry metadata (Glama, MCP Market,
PulseMCP, mcp.so) to produce higher-quality embeddings for server-level search.

Source priority for primary description:
    1. GitHub description (authoritative, maintained by repo owner)
    2. Best external registry description (longest + most specific)
    3. Smithery description (fallback, often marketing-heavy)

This module is a pure-function library with no side effects except file I/O
in the load functions.
"""

import json
from pathlib import Path

from loguru import logger


def _score_description_quality(description: str) -> float:
    """Score a description's quality based on length and specificity.

    Heuristic scoring:
    - Base score from length (longer = more informative, up to a point)
    - Bonus for technical terms (API, server, tool, integration, etc.)
    - Penalty for very generic/short descriptions

    Args:
        description: The description text to score.

    Returns:
        A quality score (higher is better). Not bounded to a specific range.
    """
    if not description:
        return 0.0

    # Length component: logarithmic scaling, max benefit around 300 chars
    length = len(description)
    if length < 20:
        length_score = length * 0.5
    elif length < 300:
        length_score = 20 + (length - 20) * 0.3
    else:
        length_score = 20 + 280 * 0.3 + (length - 300) * 0.05

    # Specificity bonus: presence of technical/descriptive terms
    specificity_terms = [
        "api",
        "server",
        "tool",
        "integration",
        "mcp",
        "plugin",
        "connect",
        "manage",
        "automate",
        "search",
        "query",
        "database",
        "file",
        "model",
        "agent",
        "workflow",
    ]
    desc_lower = description.lower()
    specificity_bonus = sum(2.0 for term in specificity_terms if term in desc_lower)

    # Penalty for very generic descriptions
    generic_phrases = [
        "a great tool",
        "the best",
        "amazing",
        "awesome",
        "check it out",
    ]
    generic_penalty = sum(3.0 for phrase in generic_phrases if phrase in desc_lower)

    return length_score + specificity_bonus - generic_penalty


def select_best_registry_description(
    registry_entries: list[dict],
) -> str | None:
    """Select the highest quality description from multiple registry sources.

    Does NOT merge/synthesize descriptions. Picks the single best one based
    on length + specificity scoring.

    Args:
        registry_entries: List of registry meta dicts for a single server.
            Each dict has: {"source": str, "description": str, ...}

    Returns:
        The best description string, or None if no valid descriptions.
    """
    if not registry_entries:
        return None

    best_desc: str | None = None
    best_score: float = -1.0

    for entry in registry_entries:
        desc = entry.get("description")
        if not desc or not desc.strip():
            continue
        score = _score_description_quality(desc)
        if score > best_score:
            best_score = score
            best_desc = desc

    return best_desc


def build_enriched_description(
    server: dict,
    github_meta: dict | None,
    registry_entries: list[dict] | None = None,
) -> str:
    """Build enriched description text for server embedding.

    Source priority for the primary description line:
        1. GitHub description (if available and non-None)
        2. Best external registry description (if available)
        3. Smithery description (fallback)

    Format:
        "{name}: {best_description}\\nTopics: {topics}\\nTools: {tool_names}"

    Lines with empty data (no topics, no tools) are omitted.

    Args:
        server: A single server dict from servers.jsonl.
        github_meta: A single github_meta dict, or None if unavailable.
        registry_entries: List of registry_meta dicts for this server, or None.

    Returns:
        The enriched description string.
    """
    name = server.get("name", "")

    # Choose primary description source with priority
    primary_description: str = ""

    # Priority 1: GitHub description
    github_desc = None
    if github_meta is not None:
        github_desc = github_meta.get("github_description") or None

    if github_desc is not None:
        primary_description = github_desc
    else:
        # Priority 2: Best external registry description
        registry_desc = select_best_registry_description(registry_entries or [])
        if registry_desc is not None:
            primary_description = registry_desc
        else:
            # Priority 3: Smithery description (fallback)
            smithery_desc = server.get("description")
            primary_description = smithery_desc if smithery_desc is not None else ""

    # Build lines
    lines: list[str] = []

    # Line 1: name + description
    if primary_description:
        lines.append(f"{name}: {primary_description}")
    else:
        lines.append(name)

    # Line 2: topics (only if github_meta has non-empty topics)
    if github_meta is not None:
        topics = github_meta.get("github_topics", [])
        if topics:
            lines.append(f"Topics: {', '.join(topics)}")

    # Line 3: tool names (only if server has tools)
    tools = server.get("tools", [])
    if tools:
        tool_names = [t.get("tool_name", "") for t in tools]
        tool_names_filtered = [n for n in tool_names if n]
        if tool_names_filtered:
            lines.append(f"Tools: {', '.join(tool_names_filtered)}")

    return "\n".join(lines)


def load_github_meta(path: Path) -> dict[str, dict]:
    """Load github_meta.jsonl into {server_id: meta} dict.

    Args:
        path: Path to the github_meta.jsonl file.

    Returns:
        Mapping from server_id to its GitHub metadata dict.
        Returns empty dict if file does not exist or is empty.
    """
    if not path.exists():
        logger.warning(f"GitHub meta file not found: {path}")
        return {}

    text = path.read_text().strip()
    if not text:
        return {}

    result: dict[str, dict] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        entry = json.loads(stripped)
        server_id = entry.get("server_id", "")
        if server_id:
            result[server_id] = entry

    logger.info(f"Loaded GitHub metadata for {len(result)} servers from {path}")
    return result


def load_registry_meta(path: Path) -> dict[str, list[dict]]:
    """Load registry_meta.jsonl into {server_id: [entries]} dict.

    A single server may have entries from multiple registries, so we
    group them into a list per server_id.

    Args:
        path: Path to the registry_meta.jsonl file.

    Returns:
        Mapping from server_id to its list of registry metadata dicts.
        Returns empty dict if file does not exist or is empty.
    """
    if not path.exists():
        logger.warning(f"Registry meta file not found: {path}")
        return {}

    text = path.read_text().strip()
    if not text:
        return {}

    result: dict[str, list[dict]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        entry = json.loads(stripped)
        server_id = entry.get("server_id", "")
        if server_id:
            if server_id not in result:
                result[server_id] = []
            result[server_id].append(entry)

    total_entries = sum(len(v) for v in result.values())
    logger.info(
        f"Loaded {total_entries} registry metadata entries for {len(result)} servers from {path}"
    )
    return result


def enrich_all_servers(
    servers_path: Path,
    github_meta_path: Path,
    registry_meta_path: Path | None = None,
) -> list[dict]:
    """Load servers + github meta + registry meta, return enriched server dicts.

    Each returned dict contains:
        - server_id: str
        - name: str
        - enriched_description: str

    Args:
        servers_path: Path to servers.jsonl.
        github_meta_path: Path to github_meta.jsonl.
        registry_meta_path: Path to registry_meta.jsonl (optional).

    Returns:
        List of dicts with server_id, name, and enriched_description.
    """
    # Load servers
    text = servers_path.read_text().strip()
    servers: list[dict] = []
    if text:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                servers.append(json.loads(stripped))

    logger.info(f"Loaded {len(servers)} servers from {servers_path}")

    # Load GitHub metadata
    github_meta_map = load_github_meta(github_meta_path)

    # Load registry metadata (optional)
    registry_meta_map: dict[str, list[dict]] = {}
    if registry_meta_path is not None:
        registry_meta_map = load_registry_meta(registry_meta_path)

    # Build enriched descriptions
    enriched: list[dict] = []
    github_count = 0
    registry_count = 0
    fallback_count = 0

    for server in servers:
        server_id = server.get("server_id", "")
        github_meta = github_meta_map.get(server_id)
        registry_entries = registry_meta_map.get(server_id, [])

        description = build_enriched_description(server, github_meta, registry_entries)
        enriched.append(
            {
                "server_id": server_id,
                "name": server.get("name", ""),
                "enriched_description": description,
            }
        )

        # Track source statistics
        github_desc = None
        if github_meta is not None:
            github_desc = github_meta.get("github_description")

        if github_desc is not None:
            github_count += 1
        elif select_best_registry_description(registry_entries) is not None:
            registry_count += 1
        else:
            fallback_count += 1

    logger.info(
        f"Enriched {len(enriched)} servers: "
        f"{github_count} GitHub, {registry_count} registry, {fallback_count} Smithery fallback"
    )

    return enriched

"""Collect server metadata from external MCP registries (cross-reference).

Fetches description pages from MCP Market, Glama, PulseMCP, and mcp.so for
each server in our pool. Extracts description text from HTML meta tags.

This is a PoC-level collector — not all servers will have entries on all
registries.  Failures are gracefully skipped with logging.

Usage:
    uv run python scripts/collect_registry_meta.py
    uv run python scripts/collect_registry_meta.py --input data/raw/servers.jsonl
    uv run python scripts/collect_registry_meta.py --output data/raw/registry_meta.jsonl
"""

import argparse
import asyncio
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
from loguru import logger

# --- Registry definitions ---

REGISTRIES: list[dict[str, str]] = [
    {
        "name": "glama",
        "url_template": "https://glama.ai/mcp/servers/{server_name}",
    },
    {
        "name": "mcp_market",
        "url_template": "https://mcpmarket.com/server/{server_name}",
    },
    {
        "name": "pulsemcp",
        "url_template": "https://pulsemcp.com/servers/{server_name}",
    },
    {
        "name": "mcp_so",
        "url_template": "https://mcp.so/server/{server_name}",
    },
]

# Delay between requests per registry (seconds)
REQUEST_DELAY_SECONDS = 1.5


# --- HTML meta tag extraction ---


class _MetaTagParser(HTMLParser):
    """Minimal HTML parser that extracts og:description and meta description."""

    def __init__(self) -> None:
        super().__init__()
        self.og_description: str | None = None
        self.meta_description: str | None = None
        self.title: str | None = None
        self._in_title = False
        self._title_chars: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            self._title_chars = []
            return

        if tag != "meta":
            return

        attr_dict: dict[str, str] = {}
        for key, value in attrs:
            if value is not None:
                attr_dict[key.lower()] = value

        # og:description
        prop = attr_dict.get("property", "")
        if prop == "og:description" and "content" in attr_dict:
            self.og_description = attr_dict["content"].strip()

        # meta name="description"
        name = attr_dict.get("name", "")
        if name.lower() == "description" and "content" in attr_dict:
            self.meta_description = attr_dict["content"].strip()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_chars.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_chars).strip()


def extract_description_from_html(html: str) -> str | None:
    """Extract the best description from an HTML page.

    Priority: og:description > meta description.
    Returns None if neither is found or if they are too short (<10 chars).

    Args:
        html: Raw HTML string.

    Returns:
        The extracted description text, or None.
    """
    parser = _MetaTagParser()
    try:
        parser.feed(html)
    except Exception as e:
        logger.warning(f"HTML parse error: {e}")
        return None

    # Prefer og:description (usually richer)
    desc = parser.og_description or parser.meta_description
    if desc and len(desc) >= 10:
        return desc
    return None


def extract_categories_from_html(html: str) -> list[str]:
    """Extract category-like tags from HTML.

    Looks for common patterns in registry pages (JSON-LD, meta keywords).
    This is best-effort extraction.

    Args:
        html: Raw HTML string.

    Returns:
        List of category strings (may be empty).
    """
    categories: list[str] = []

    # Try meta keywords
    kw_match = re.search(
        r'<meta\s+name=["\']keywords["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if kw_match:
        raw = kw_match.group(1)
        categories.extend(k.strip() for k in raw.split(",") if k.strip())

    return categories


# --- Server name derivation ---


def _derive_registry_name(server_id: str) -> str:
    """Derive the name slug used in registry URLs from server_id.

    For GitHub-based servers (owner/repo): use the repo part.
    For simple names (instagram, gmail): use as-is.

    Args:
        server_id: The server_id from servers.jsonl.

    Returns:
        A URL-safe name slug for registry lookups.
    """
    if "/" in server_id:
        # GitHub-style: owner/repo -> repo
        slug = server_id.split("/")[-1]
    else:
        slug = server_id

    # Sanitize: allow only alphanumeric, hyphens, underscores, dots
    if not re.match(r"^[\w.\-]+$", slug):
        logger.warning(f"Unsafe slug derived from server_id={server_id!r}, skipping")
        return ""
    return slug


# --- Fetch logic ---


async def _fetch_registry_page(
    client: httpx.AsyncClient,
    url: str,
    timeout: float = 10.0,
) -> str | None:
    """Fetch a single registry page, returning HTML or None on failure.

    Args:
        client: httpx.AsyncClient instance.
        url: Full URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        HTML string on success, None on any failure.
    """
    try:
        response = await client.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "MCP-Discovery-Bot/0.1 (research; +https://github.com/mcp-discovery)",
            },
        )
        if response.status_code == 404:
            return None
        if response.status_code == 403:
            logger.warning(f"Forbidden (403): {url}")
            return None
        if response.status_code >= 400:
            logger.warning(f"HTTP {response.status_code}: {url}")
            return None
        return response.text
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching: {url}")
        return None
    except httpx.RequestError as e:
        logger.warning(f"Request error for {url}: {e}")
        return None


async def fetch_registry_meta_for_server(
    client: httpx.AsyncClient,
    server_id: str,
    registries: list[dict[str, str]] | None = None,
) -> list[dict]:
    """Fetch metadata from all registries for a single server.

    Args:
        client: httpx.AsyncClient instance.
        server_id: The server_id from servers.jsonl.
        registries: List of registry dicts (uses REGISTRIES default if None).

    Returns:
        List of dicts, one per successful fetch:
        {"server_id": str, "source": str, "description": str, "categories": list}
    """
    if registries is None:
        registries = REGISTRIES

    name_slug = _derive_registry_name(server_id)
    if not name_slug:
        return []
    results: list[dict] = []

    for registry in registries:
        url = registry["url_template"].format(server_name=name_slug)
        html = await _fetch_registry_page(client, url)

        if html is None:
            continue

        description = extract_description_from_html(html)
        if description is None:
            logger.info(f"No description extracted from {registry['name']} for {server_id}")
            continue

        categories = extract_categories_from_html(html)

        results.append(
            {
                "server_id": server_id,
                "source": registry["name"],
                "description": description,
                "categories": categories,
            }
        )
        logger.info(
            f"Extracted from {registry['name']} for {server_id}: "
            f"{len(description)} chars, {len(categories)} categories"
        )

        # Rate limit between registry fetches for same server
        await asyncio.sleep(0.5)

    return results


def _load_server_ids(servers_path: Path) -> list[str]:
    """Load all server_ids from servers.jsonl.

    Args:
        servers_path: Path to servers.jsonl.

    Returns:
        List of server_id strings.
    """
    text = servers_path.read_text().strip()
    if not text:
        return []
    ids: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        server = json.loads(stripped)
        sid = server.get("server_id", "")
        if sid:
            ids.append(sid)
    return ids


async def main(args: argparse.Namespace) -> None:
    """Main entry point: load servers, fetch registry metadata, save results."""
    servers_path = Path(args.input)
    output_path = Path(args.output)

    if not servers_path.exists():
        logger.error(f"Input file not found: {servers_path}")
        raise SystemExit(1)

    server_ids = _load_server_ids(servers_path)
    if not server_ids:
        logger.warning("No servers found. Nothing to do.")
        return

    logger.info(f"Loaded {len(server_ids)} servers to check against external registries")

    # TODO: Check robots.txt for each registry before scraping in production.
    # For PoC purposes, we use polite rate limiting and a descriptive User-Agent.

    all_results: list[dict] = []
    async with httpx.AsyncClient() as client:
        for i, server_id in enumerate(server_ids, 1):
            logger.info(f"Checking registries {i}/{len(server_ids)}: {server_id}")
            results = await fetch_registry_meta_for_server(client, server_id)
            all_results.extend(results)

            # Rate limit between servers
            if i < len(server_ids):
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for entry in all_results:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Summary
    sources_count: dict[str, int] = {}
    for entry in all_results:
        src = entry.get("source", "unknown")
        sources_count[src] = sources_count.get(src, 0) + 1

    logger.info(
        f"Done: Saved {len(all_results)} registry entries for "
        f"{len(set(e['server_id'] for e in all_results))} unique servers -> {output_path}"
    )
    for src, count in sorted(sources_count.items()):
        logger.info(f"  {src}: {count} entries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect metadata from external MCP registries")
    parser.add_argument(
        "--input",
        type=str,
        default="data/raw/servers.jsonl",
        help="Path to servers.jsonl",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw/registry_meta.jsonl",
        help="Output path for registry_meta.jsonl",
    )
    args = parser.parse_args()
    asyncio.run(main(args))

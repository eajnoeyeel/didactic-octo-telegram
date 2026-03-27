"""Collect GitHub repo metadata (description, topics) for servers in our pool.

Reads servers from data/raw/servers.jsonl, identifies GitHub-based servers
(server_id contains '/'), fetches metadata from GitHub API, and saves
results to data/raw/github_meta.jsonl.

Usage:
    uv run python scripts/collect_github_meta.py
    uv run python scripts/collect_github_meta.py --input data/raw/servers.jsonl
    uv run python scripts/collect_github_meta.py --output data/raw/github_meta.jsonl
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

GITHUB_API_BASE = "https://api.github.com/repos"
REQUEST_DELAY_SECONDS = 1.0


def _extract_github_repos(servers_path: Path) -> list[dict]:
    """Read servers.jsonl and return GitHub-based server dicts.

    A server is considered GitHub-based if its server_id contains '/'.

    Args:
        servers_path: Path to servers.jsonl file.

    Returns:
        List of server dicts whose server_id contains '/'.
    """
    text = servers_path.read_text().strip()
    if not text:
        logger.warning(f"Empty servers file: {servers_path}")
        return []

    github_servers: list[dict] = []
    total = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        server = json.loads(stripped)
        total += 1
        server_id = server.get("server_id", "")
        if "/" in server_id:
            github_servers.append(server)

    logger.info(f"Found {len(github_servers)}/{total} GitHub-based servers in {servers_path}")
    return github_servers


async def _fetch_github_meta(
    client: httpx.AsyncClient,
    server_id: str,
    headers: dict[str, str],
) -> dict | None:
    """Fetch GitHub repository metadata for a single server.

    Args:
        client: httpx.AsyncClient instance.
        server_id: The server_id in 'owner/repo' format.
        headers: HTTP headers (including auth token if available).

    Returns:
        A dict with server_id, github_description, github_topics, homepage.
        Returns None if the repo is inaccessible (404, private, etc).
    """
    url = f"{GITHUB_API_BASE}/{server_id}"
    try:
        response = await client.get(url, headers=headers, timeout=10.0)
        if response.status_code == 404:
            logger.warning(f"GitHub repo not found (404): {server_id}")
            return None
        if response.status_code == 403:
            logger.warning(f"GitHub API rate limited or forbidden (403): {server_id}")
            return None
        response.raise_for_status()
        data = response.json()
        return {
            "server_id": server_id,
            "github_description": data.get("description"),
            "github_topics": data.get("topics", []),
            "homepage": data.get("homepage"),
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"GitHub API error for {server_id}: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.warning(f"Network error fetching {server_id}: {e}")
        return None


async def main(args: argparse.Namespace) -> None:
    """Main entry point: load servers, fetch GitHub metadata, save results."""
    servers_path = Path(args.input)
    output_path = Path(args.output)

    if not servers_path.exists():
        logger.error(f"Input file not found: {servers_path}")
        raise SystemExit(1)

    github_servers = _extract_github_repos(servers_path)
    if not github_servers:
        logger.warning("No GitHub-based servers found. Nothing to do.")
        return

    # Build auth headers
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
        logger.info("Using authenticated GitHub API (GITHUB_TOKEN found)")
    else:
        logger.warning("No GITHUB_TOKEN found — using unauthenticated API (60 req/hr limit)")

    # Fetch metadata
    results: list[dict] = []
    async with httpx.AsyncClient() as client:
        for i, server in enumerate(github_servers, 1):
            server_id = server["server_id"]
            logger.info(f"Fetching {i}/{len(github_servers)}: {server_id}")

            meta = await _fetch_github_meta(client, server_id, headers)
            if meta is not None:
                results.append(meta)
            else:
                logger.warning(f"Skipped {server_id} (no metadata available)")

            # Rate limit protection: sleep between requests
            if i < len(github_servers):
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(
        f"Done: Saved metadata for {len(results)}/{len(github_servers)} "
        f"GitHub-based servers -> {output_path}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect GitHub repo metadata for MCP servers")
    parser.add_argument(
        "--input",
        type=str,
        default="data/raw/servers.jsonl",
        help="Path to servers.jsonl",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw/github_meta.jsonl",
        help="Output path for github_meta.jsonl",
    )
    args = parser.parse_args()
    asyncio.run(main(args))

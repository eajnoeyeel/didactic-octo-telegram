"""Query logger — daily JSONL files for pipeline query events."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QueryLogEntry(BaseModel):
    """A single query event recorded by the pipeline."""

    timestamp: str = Field(default_factory=_utc_now_iso)
    query: str
    selected_tool_id: str
    server_id: str
    confidence: float
    disambiguation_needed: bool
    strategy: str
    latency_ms: float
    alternatives: list[str] = Field(default_factory=list)


class QueryLogger:
    """Append query events to daily JSONL files under *log_dir*.

    File naming: ``queries-YYYY-MM-DD.jsonl``
    """

    def __init__(self, log_dir: Path) -> None:
        self._log_dir = log_dir

    # -- write --

    async def log(self, entry: QueryLogEntry) -> QueryLogEntry:
        """Append *entry* to today's JSONL file (non-blocking)."""
        line = entry.model_dump_json() + "\n"
        await asyncio.to_thread(self._append_line, line)
        return entry

    def _append_line(self, line: str) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        path = self._log_dir / f"queries-{date.today().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
        logger.debug("Logged query to {}", path.name)

    # -- read --

    async def read_logs(self, days: int | None = None) -> list[QueryLogEntry]:
        return await asyncio.to_thread(self._read_logs_sync, days)

    def _read_logs_sync(self, days: int | None = None) -> list[QueryLogEntry]:
        if not self._log_dir.exists():
            return []

        files = self._resolve_files(days)
        entries: list[QueryLogEntry] = []
        for path in sorted(files):
            for line in path.read_text(encoding="utf-8").strip().splitlines():
                if not line:
                    continue
                try:
                    entries.append(QueryLogEntry(**json.loads(line)))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Skipping malformed JSONL line in {}: {}", path.name, e)
        return entries

    # -- internal --

    def _resolve_files(self, days: int | None) -> list[Path]:
        all_files = sorted(self._log_dir.glob("queries-*.jsonl"))
        if days is None:
            return all_files
        cutoff = date.today() - timedelta(days=days - 1)
        result: list[Path] = []
        for f in all_files:
            try:
                file_date = date.fromisoformat(f.stem.removeprefix("queries-"))
            except ValueError:
                continue
            if file_date >= cutoff:
                result.append(f)
        return result

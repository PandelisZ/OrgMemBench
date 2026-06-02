"""Resume support for long generation runs.

A simple JSONL-backed checkpoint: each completed unit of work appends a
line to a per-stage checkpoint file under ``data/.checkpoints/<stage>.jsonl``.
On restart, the stage runner reads the checkpoint file, builds a set of
completed unit-ids, and skips any unit already done.

Generation runs at Large can take 2-3 weeks; we want them to survive
desktop reboots, network glitches, and Cloudflare token rotation.

Each checkpoint entry is a dict with at minimum ``unit_id`` (the thing
that was completed) and ``completed_at`` (ISO timestamp). Stages can
attach extra metadata.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Checkpoint:
    """Per-stage append-only checkpoint."""

    def __init__(self, path: str | os.PathLike[str]):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._completed: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                uid = record.get("unit_id")
                if uid:
                    self._completed.add(str(uid))

    def is_done(self, unit_id: str) -> bool:
        return unit_id in self._completed

    def mark_done(self, unit_id: str, **extra: Any) -> None:
        if unit_id in self._completed:
            return
        record = {
            "unit_id": unit_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        self._completed.add(unit_id)

    def completed_count(self) -> int:
        return len(self._completed)

    def reset(self) -> None:
        """Delete the checkpoint file. Use only when restarting a stage from scratch."""
        if self._path.exists():
            self._path.unlink()
        self._completed.clear()

# app/models/solo_mode.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class SoloSession:
    user_id: int
    collection_id: int
    order: List[int]
    index: int = 0
    showing_answer: bool = False
    started_at: str = ""
    seed: int = 0

    stats: Dict[str, str] = field(default_factory=dict)
    per_item_sec: Dict[str, int] = field(default_factory=dict)
    hints: Dict[str, list[str]] = field(default_factory=dict)
    total_sec: int = 0
    last_ts: float = 0.0

    @property
    def total(self) -> int:
        return len(self.order)

    @property
    def seen(self) -> int:
        return min(self.index, self.total)

    @property
    def done(self) -> bool:
        return self.index >= self.total

    def current_item_id(self) -> Optional[int]:
        if self.done:
            return None
        return self.order[self.index]

    def to_progress_str(self) -> str:
        return f"{min(self.index, self.total)}/{self.total}"

    def _commit_time_for_current(self) -> None:
        if self.done:
            return
        now = time.time()
        delta = max(0, int(now - (self.last_ts or now)))
        item_id = self.order[self.index]
        key = str(item_id)
        self.per_item_sec[key] = int(self.per_item_sec.get(key, 0)) + delta
        self.total_sec += delta
        self.last_ts = now

    def mark_and_next(self, mark: Optional[str]) -> None:
        if self.done:
            return
        self._commit_time_for_current()
        if mark is None:
            mark = "neutral"
        self.stats[str(self.order[self.index])] = mark

        self.index += 1
        self.showing_answer = False
        self.last_ts = time.time()

    def counts(self) -> Dict[str, int]:
        counts = {"known": 0, "unknown": 0, "skipped": 0, "neutral": 0}
        for v in self.stats.values():
            if v in counts:
                counts[v] += 1
        return counts

    def wrong_ids(self) -> List[int]:
        return [int(k) for k, v in self.stats.items() if v == "unknown"]

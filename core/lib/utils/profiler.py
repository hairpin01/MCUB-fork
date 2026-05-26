# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import os
import time
from collections import OrderedDict
from contextlib import contextmanager
from typing import Any


class Profiler:
    """Simple phase-level profiler for MCUB kernel startup & runtime.

    Usage::

        profiler = Profiler()
        profiler.begin("init_db")
        # ... do work ...
        profiler.end("init_db")
        profiler.dump()  # prints all phases with timings

    Supports nested phases (automatically computes exclusive time).
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._phases: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._stack: list[str] = []
        self._start_time = time.monotonic()

    def begin(self, name: str) -> None:
        """Start timing *name*. Pauses the previous phase if nested."""
        if not self.enabled:
            return
        now = time.monotonic()
        if self._stack:
            parent = self._phases.get(self._stack[-1])
            if parent is not None and parent["_pause"] is None:
                parent["_pause"] = now
        self._stack.append(name)
        if name not in self._phases:
            self._phases[name] = {
                "wall": 0.0,
                "calls": 0,
                "_start": None,
                "_pause": None,
            }
        self._phases[name]["_start"] = now

    def end(self, name: str) -> None:
        """Stop timing *name* and accumulate wall time."""
        if not self.enabled:
            return
        if not self._stack or self._stack[-1] != name:
            return  # ignore mismatched end
        now = time.monotonic()
        phase = self._phases[name]
        start = phase.pop("_start", None)
        if start is not None:
            elapsed = now - start
            # subtract paused time if any
            pause = phase.pop("_pause", None)
            if pause is not None:
                elapsed -= now - pause
            phase["wall"] += elapsed
            phase["calls"] += 1
        self._stack.pop()
        # resume parent if any
        if self._stack:
            parent = self._phases.get(self._stack[-1])
            if parent is not None:
                parent["_start"] = now

    @contextmanager
    def measure(self, name: str):
        """Context-manager wrapper around begin/end."""
        self.begin(name)
        try:
            yield
        finally:
            self.end(name)

    def results(self) -> dict[str, dict[str, Any]]:
        """Return dict of phase-name -> {wall, calls}."""
        if not self.enabled:
            return {}
        return {
            k: {"wall": round(v["wall"], 4), "calls": v["calls"]}
            for k, v in self._phases.items()
            if v["calls"] > 0
        }

    def dump(self, prefix: str = "[Profiler]") -> None:
        """Print all phase timings sorted by wall time descending."""
        if not self.enabled:
            return
        total = time.monotonic() - self._start_time
        items = sorted(self.results().items(), key=lambda x: -x[1]["wall"])
        print(f"{prefix} {'Phase':<50} {'Wall(s)':<10} {'Calls':<6}")
        print(f"{prefix} {'-'*66}")
        for name, info in items:
            pct = (info["wall"] / total * 100) if total > 0 else 0
            print(
                f"{prefix} {name:<50} {info['wall']:<10.4f} {info['calls']:<6} "
                f"({pct:.1f}%)"
            )
        print(f"{prefix} {'-'*66}")
        print(f"{prefix} {'TOTAL':<50} {total:<10.4f} 1")

    def get_profile_json(self) -> dict:
        """Return JSON-serialisable profile data."""
        return {
            "total_wall": round(time.monotonic() - self._start_time, 4),
            "phases": self.results(),
        }


# Module-level singleton for global usage
_PROFILER: Profiler | None = None


def get_profiler() -> Profiler:
    global _PROFILER
    if _PROFILER is None:
        enabled = os.environ.get("MCUB_PROFILE", "0") == "1"
        _PROFILER = Profiler(enabled=enabled)
    return _PROFILER


def enable_profiler() -> None:
    """Force-enable the profiler (e.g. via --profile flag)."""
    p = get_profiler()
    p.enabled = True

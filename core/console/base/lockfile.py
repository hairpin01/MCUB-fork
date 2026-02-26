"""
Lock-file manager: console/packages/installed.json

Tracks every installed package with metadata and file manifests so that
`base uninstall` and `base update` know exactly what to touch.

Schema (per-package entry):
{
  "name":         "studio",
  "version":      "1.2.0",
  "author":       "@hairpin00",
  "description":  "...",
  "pip_deps":     ["aiohttp"],
  "sys_deps":     [],
  "bin_file":     "studio.bin",    # or null
  "src_files":    ["__init__.py", "tui.py"],
  "installed_at": "2025-02-25T14:30:00",
  "updated_at":   "2025-02-25T14:30:00",
  "repo_url":     "https://..."
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


_LOCK_FILE = Path("console/packages/installed.json")


class LockFile:
    """
    Reads and writes the installed-package registry.
    All operations modify the in-memory dict and immediately flush to disk.
    """

    def __init__(self, path: Path | str = _LOCK_FILE) -> None:
        self._path = Path(path)
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                text = self._path.read_text(encoding="utf-8")
                self._data = json.loads(text)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    def is_installed(self, name: str) -> bool:
        return name in self._data

    def get(self, name: str) -> Optional[dict]:
        return self._data.get(name)

    def all_packages(self) -> List[dict]:
        return list(self._data.values())

    def names(self) -> List[str]:
        return list(self._data.keys())


    def register(
        self,
        *,
        name:        str,
        version:     str,
        author:      str,
        description: str,
        pip_deps:    list,
        sys_deps:    list,
        bin_file:    Optional[str],
        src_files:   list,
        repo_url:    str,
        entry_file:  Optional[str] = None,
    ) -> None:
        """Add or update a package entry and persist immediately."""
        now = datetime.now().isoformat(timespec="seconds")
        old = self._data.get(name, {})
        self._data[name] = {
            "name":         name,
            "version":      version,
            "author":       author,
            "description":  description,
            "pip_deps":     pip_deps,
            "sys_deps":     sys_deps,
            "bin_file":     bin_file,
            "entry_file":   entry_file,
            "src_files":    src_files,
            "installed_at": old.get("installed_at", now),
            "updated_at":   now,
            "repo_url":     repo_url,
        }
        self._save()

    def remove(self, name: str) -> bool:
        """Remove a package from the registry. Returns True if it existed."""
        if name in self._data:
            del self._data[name]
            self._save()
            return True
        return False

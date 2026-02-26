"""
Parses a package's config.cfg.

Expected format:

  [package]
  name        = studio
  version     = 1.2.0
  author      = @hairpin00
  description = Interactive TUI module manager

  [dependencies]
  pip    = aiohttp, curses
  system = ffmpeg, git

  [install]
  bin    = studio.bin          # filename of the .bin resource (optional)
  entry  = _install.py         # script to exec after copying files (optional)
  files  = __init__.py, tui.py, editor.py, actions.py, widgets.py

ConfigParser is used so the format is forgiving (comments, extra blanks, etc.)
"""

from __future__ import annotations

import configparser
from typing import List, Optional


class PackageConfig:
    """Parsed representation of a package's config.cfg."""

    def __init__(self) -> None:
        self.name:        str         = ""
        self.version:     str         = "0.0.0"
        self.author:      str         = "unknown"
        self.description: str         = ""
        self.pip_deps:    List[str]   = []
        self.sys_deps:    List[str]   = []
        self.bin_file:    Optional[str] = None   # e.g. "studio.bin"
        self.entry_file:  Optional[str] = None   # script to run on install
        self.src_files:   List[str]   = []       # files in src/ to copy

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "version":     self.version,
            "author":      self.author,
            "description": self.description,
            "pip_deps":    self.pip_deps,
            "sys_deps":    self.sys_deps,
            "bin_file":    self.bin_file,
            "entry_file":  self.entry_file,
            "src_files":   self.src_files,
        }


    @classmethod
    def from_text(cls, text: str) -> "PackageConfig":
        """Parse raw INI text and return a PackageConfig instance."""
        cfg = configparser.ConfigParser(
            allow_no_value=True,
            inline_comment_prefixes=("#", ";"),
        )
        cfg.read_string(text)

        obj = cls()

        # [package]
        if cfg.has_section("package"):
            sec = cfg["package"]
            obj.name        = sec.get("name",        "").strip()
            obj.version     = sec.get("version",     "0.0.0").strip()
            obj.author      = sec.get("author",      "unknown").strip()
            obj.description = sec.get("description", "").strip()

        # [dependencies]
        if cfg.has_section("dependencies"):
            sec = cfg["dependencies"]
            obj.pip_deps = _split_list(sec.get("pip",    ""))
            obj.sys_deps = _split_list(sec.get("system", ""))

        # [install]
        if cfg.has_section("install"):
            sec = cfg["install"]
            bin_val   = sec.get("bin",   "").strip()
            entry_val = sec.get("entry", "").strip()
            files_val = sec.get("files", "").strip()

            obj.bin_file   = bin_val   if bin_val   else None
            obj.entry_file = entry_val if entry_val else None
            obj.src_files  = _split_list(files_val)

        return obj

    @classmethod
    def from_dict(cls, d: dict) -> "PackageConfig":
        obj = cls()
        obj.name        = d.get("name",        "")
        obj.version     = d.get("version",     "0.0.0")
        obj.author      = d.get("author",      "unknown")
        obj.description = d.get("description", "")
        obj.pip_deps    = d.get("pip_deps",    [])
        obj.sys_deps    = d.get("sys_deps",    [])
        obj.bin_file    = d.get("bin_file")
        obj.entry_file  = d.get("entry_file")
        obj.src_files   = d.get("src_files",   [])
        return obj



def _split_list(raw: str) -> List[str]:
    """Split a comma/newline separated list, strip blanks."""
    if not raw:
        return []
    parts = []
    for item in raw.replace("\n", ",").split(","):
        item = item.strip()
        if item:
            parts.append(item)
    return parts

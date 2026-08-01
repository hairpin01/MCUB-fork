# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import re

# Hikka historically uses ``# requires: ...`` while parts of MCUB compat also
# accepted ``# scope: pip ...``.  Keep the marker syntax broad enough for both,
# but keep each requirement token intentionally narrow: package name, optional
# extras, optional version specifier.  Direct URLs/VCS/path references and pip
# option-like tokens are rejected before reaching ``pip install``.
VALID_PIP_PACKAGES = re.compile(
    r"^\s*#\s*(?:requires:|scope:\s*pip)\s*([^\n#]+?)\s*$",
    re.MULTILINE,
)

_SAFE_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*"
    r"(?:\[[A-Za-z0-9][A-Za-z0-9_.-]*(?:,[A-Za-z0-9][A-Za-z0-9_.-]*)*\])?"
    r"(?:(?:===|==|~=|!=|<=|>=|<|>)[A-Za-z0-9][A-Za-z0-9_.!*+-]*)?$"
)

_UNSAFE_REQUIREMENT_MARKERS = ("://", "git+", "hg+", "svn+", "bzr+", "@")


def is_safe_pip_requirement(value: str) -> bool:
    requirement = str(value or "").strip()
    if not requirement or requirement.startswith(("-", ".", "/", "~")):
        return False

    lowered = requirement.lower()
    if any(marker in lowered for marker in _UNSAFE_REQUIREMENT_MARKERS):
        return False

    return bool(_SAFE_REQUIREMENT.fullmatch(requirement))


def parse_pip_requirements(source_code: str) -> list[str]:
    match = VALID_PIP_PACKAGES.search(source_code or "")
    if not match:
        return []

    tokens = [token.strip() for token in match.group(1).split() if token.strip()]
    if not tokens or any(not is_safe_pip_requirement(token) for token in tokens):
        return []
    return tokens

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from utils.strings import Strings


def get_strings(kernel) -> Strings:
    return Strings(kernel, {"name": "core_inline"})

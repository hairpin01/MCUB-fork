# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""Smoke tests for the optional Rust/PyO3 native extension."""

from __future__ import annotations

import importlib

import pytest


def _native_module():
    module = importlib.import_module("mcub_native")
    required = ("TTLCache", "ArgumentParser", "PipelineParser")
    if any(not hasattr(module, name) for name in required):
        pytest.skip("mcub_native extension is not built")
    return module


def test_native_ttl_cache_basic_lru():
    native = _native_module()
    cache = native.TTLCache(max_size=2, ttl=60)

    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1

    cache.set("c", 3)
    assert cache.get("b") is None
    assert cache.get("missing", "fallback") == "fallback"


def test_native_argument_parser_matches_public_shape():
    native = _native_module()
    parser = native.ArgumentParser(".cmd item,2 --name=John -v")

    assert parser.command == "cmd"
    assert parser.kwargs["name"] == "John"
    assert parser.get_flag("v") is True
    assert parser.args == [["item", 2]]
    assert parser.get(0) == ["item", 2]


def test_native_pipeline_parser_pipe_forward_without_spaces():
    native = _native_module()
    parser = native.PipelineParser(".ping 1.1.1.1|>8.8.8.8")

    assert parser.segments[0].operator is None
    assert parser.segments[0].command == ".ping 1.1.1.1"
    assert parser.segments[1].operator == "|>"
    assert parser.segments[1].command == "8.8.8.8"

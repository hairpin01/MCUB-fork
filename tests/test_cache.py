"""
Tests for TTL cache implementation
"""

import pytest
import time
from core.lib.time.cache import TTLCache


class TestTTLCache:
    """Test TTLCache functionality"""

    def test_cache_initialization(self):
        """Test cache creation with defaults"""
        cache = TTLCache()
        assert cache.max_size == 1000

    def test_cache_with_custom_params(self):
        """Test cache with custom parameters"""
        cache = TTLCache(max_size=100, ttl=60)
        assert cache.max_size == 100
        assert cache.ttl == 60

    def test_set_and_get(self):
        """Test basic set and get operations"""
        cache = TTLCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_ttl_expiration(self):
        """Test TTL expiration"""
        cache = TTLCache()
        cache.set("key2", "value2", ttl=0.1)
        time.sleep(0.2)
        assert cache.get("key2") is None

    def test_custom_ttl_per_item(self):
        """Test custom TTL per item"""
        cache = TTLCache(ttl=600)
        cache.set("key1", "val1", ttl=1)
        cache.set("key2", "val2")
        time.sleep(1.5)
        assert cache.get("key1") is None
        assert cache.get("key2") == "val2"

    def test_max_size_enforcement(self):
        """Test max size enforcement"""
        cache = TTLCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)
        assert cache.size() <= 3

    def test_cache_clear(self):
        """Test cache clear"""
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.size() == 0

    def test_lru_eviction(self):
        """Test LRU eviction"""
        cache = TTLCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("c", 3)
        assert cache.get("b") is None
        assert cache.get("a") == 1

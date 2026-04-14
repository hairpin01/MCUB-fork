"""
Tests for TTL cache implementation
"""

import time
import pytest
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

    def test_get_nonexistent_key(self):
        """Test getting non-existent key returns None"""
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_overwrite_existing_key(self):
        """Test overwriting an existing key updates the value"""
        cache = TTLCache()
        cache.set("key", "value1")
        cache.set("key", "value2")
        assert cache.get("key") == "value2"

    @pytest.mark.parametrize(
        "ttl_value,expected_stored",
        [
            (0.05, "short"),
            (0.1, "medium"),
            (1, "long"),
        ],
    )
    def test_various_ttl_values(self, ttl_value, expected_stored):
        """Test cache with various TTL values"""
        cache = TTLCache()
        cache.set("key", expected_stored, ttl=ttl_value)
        assert cache.get("key") == expected_stored
        time.sleep(ttl_value + 0.05)
        assert cache.get("key") is None

    def test_multiple_items_with_different_ttl(self):
        """Test multiple items with different TTLs expire independently"""
        cache = TTLCache()
        cache.set("fast", "expires_quick", ttl=0.1)
        cache.set("slow", "expires_late", ttl=0.5)
        cache.set("medium", "expires_mid", ttl=0.3)

        assert cache.get("fast") == "expires_quick"
        assert cache.get("slow") == "expires_late"
        assert cache.get("medium") == "expires_mid"

        time.sleep(0.2)
        assert cache.get("fast") is None
        assert cache.get("slow") == "expires_late"
        assert cache.get("medium") == "expires_mid"

    def test_lru_access_updates_order(self):
        """Test that accessing a key updates its LRU position"""
        cache = TTLCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")
        cache.set("d", 4)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_empty_cache_size(self):
        """Test empty cache has size 0"""
        cache = TTLCache()
        assert cache.size() == 0

    def test_unicode_keys_and_values(self):
        """Test cache with unicode keys and values"""
        cache = TTLCache()
        cache.set("ключ", "значение")
        cache.set("key", "日本語")
        assert cache.get("ключ") == "значение"
        assert cache.get("key") == "日本語"

    def test_none_value(self):
        """Test storing None as value"""
        cache = TTLCache()
        cache.set("key", None)
        result = cache.get("key")
        assert result is None

    def test_zero_ttl_immediate_expiration(self):
        """Test that zero TTL causes immediate expiration"""
        cache = TTLCache()
        cache.set("key", "value", ttl=0)
        time.sleep(0.01)
        assert cache.get("key") is None

    def test_clear_empty_cache(self):
        """Test clearing an empty cache doesn't raise error"""
        cache = TTLCache()
        cache.clear()
        assert cache.size() == 0

    def test_int_ttl_instead_of_float(self):
        """Test that integer TTL works correctly"""
        cache = TTLCache(ttl=300)
        cache.set("key", "value", ttl=60)
        assert cache.get("key") == "value"

    def test_large_ttl_value(self):
        """Test cache with large TTL value"""
        cache = TTLCache(ttl=1)
        cache.set("key", "value", ttl=3600)
        assert cache.get("key") == "value"

    def test_concurrent_access_simulation(self):
        """Test simulated concurrent access patterns"""
        cache = TTLCache(max_size=5)
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}")

        cache.get("key_0")
        cache.get("key_5")
        cache.get("key_9")

        assert cache.size() <= 5

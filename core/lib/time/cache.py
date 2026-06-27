# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @Hairpin00
# version: 1.1.0
# description: TTL Cache implementation with LRU eviction

import hashlib
import heapq
import logging
import time
from collections import OrderedDict
from typing import Any

CacheType = OrderedDict[Any, tuple[float, Any]]
logger = logging.getLogger(__name__)


def _key_for_log(key: Any) -> str:
    """Return a stable, non-revealing key label for debug logs."""
    try:
        raw = repr(key)
    except Exception:
        raw = f"<{type(key).__name__}>"
    digest = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{type(key).__name__}:{digest}"


class TTLCache:
    """
    A Time-To-Live (TTL) cache implementation with LRU eviction policy.

    This cache stores key-value pairs with an expiration time. When the cache
    reaches its maximum size, it removes the least recently used item.
    Expired items are automatically removed upon access.

    Performance notes (v1.1.0):
    - ``_cleanup_expired`` was O(n) - now uses a min-heap of (expire_time, key)
      so expiry sweeps are O(k log n) where k = number of expired keys.
    - ``get`` is O(1) average; ``set`` is O(log n) amortised due to heap push.

    Attributes:
        max_size (int): Maximum number of items the cache can hold
        ttl (int): Default time-to-live in seconds for cache entries
        cache (OrderedDict): The underlying data storage with LRU ordering
    """

    def __init__(self, max_size: int = 1000, ttl: int = 300) -> None:
        """
        Initialize the TTL cache.

        Args:
            max_size: Maximum number of items the cache can hold (default: 1000)
            ttl: Default time-to-live for cache entries in seconds (default: 300)
        """
        self.cache: CacheType = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        # Min-heap of (expire_time, key) - lets _cleanup_expired stop early
        # once it hits a non-expired entry instead of scanning the whole dict.
        # Entries may be stale (key already evicted/updated); we skip them.
        self._expiry_heap: list[tuple[float, int, Any]] = []
        self._heap_seq = 0
        logger.debug("[TTLCache] init max_size=%s ttl=%s", max_size, ttl)

    def set(self, key: Any, value: Any, ttl: int | None = None) -> None:
        """
        Add or update a key-value pair in the cache.

        Args:
            key: The key to store
            value: The value to associate with the key
            ttl: Optional custom TTL in seconds. If not provided, uses default TTL

        Note:
            If the cache exceeds max_size after insertion, the least recently
            used item is removed. The new item becomes the most recently used.
        """
        if len(self.cache) >= self.max_size:
            # Fast path: try to reclaim expired slots before evicting LRU.
            self._cleanup_expired()
            if len(self.cache) >= self.max_size:
                evicted_key, _ = self.cache.popitem(last=False)
                logger.debug(
                    "[TTLCache] evict_lru key=%s size=%d heap=%d",
                    _key_for_log(evicted_key),
                    len(self.cache),
                    len(self._expiry_heap),
                )

        expire_time = time.time() + (ttl if ttl is not None else self.ttl)
        existed = key in self.cache
        self.cache[key] = (expire_time, value)
        self.cache.move_to_end(key)
        # Push to the expiry heap so cleanup can find it in O(log n).
        self._heap_seq += 1
        heapq.heappush(self._expiry_heap, (expire_time, self._heap_seq, key))
        logger.debug(
            "[TTLCache] set key=%s ttl=%s existed=%s size=%d heap=%d",
            _key_for_log(key),
            ttl if ttl is not None else self.ttl,
            existed,
            len(self.cache),
            len(self._expiry_heap),
        )
        self._compact_heap_if_needed()

    def get(self, key: Any) -> Any | None:
        """
        Retrieve a value from the cache by key.

        Args:
            key: The key to look up

        Returns:
            The associated value if found and not expired, None otherwise

        Note:
            If an expired item is found, it is automatically removed from the cache.
        """
        if key not in self.cache:
            logger.debug(
                "[TTLCache] miss key=%s size=%d", _key_for_log(key), len(self.cache)
            )
            return None

        expire_time, value = self.cache[key]

        if time.time() <= expire_time:
            self.cache.move_to_end(key)
            logger.debug(
                "[TTLCache] hit key=%s size=%d", _key_for_log(key), len(self.cache)
            )
            return value

        # Expired - evict lazily.
        del self.cache[key]
        logger.debug(
            "[TTLCache] expired key=%s size=%d", _key_for_log(key), len(self.cache)
        )
        return None

    def delete(self, key: Any) -> None:
        """Remove a single key from the cache if present."""
        existed = key in self.cache
        self.cache.pop(key, None)
        logger.debug(
            "[TTLCache] delete key=%s existed=%s size=%d",
            _key_for_log(key),
            existed,
            len(self.cache),
        )
        self._compact_heap_if_needed()

    def clear(self) -> None:
        """Remove all items from the cache."""
        cache_size = len(self.cache)
        heap_size = len(self._expiry_heap)
        self.cache.clear()
        self._expiry_heap.clear()
        self._heap_seq = 0
        logger.debug("[TTLCache] clear size=%d heap=%d", cache_size, heap_size)

    def size(self) -> int:
        """Get the current number of items in the cache."""
        return len(self.cache)

    def _cleanup_expired(self) -> None:
        """Remove expired items using the min-heap for early termination.

        Complexity: O(k log n) where k = expired entries found, vs O(n) before.
        Stops as soon as the heap top is in the future - no need to scan the
        entire cache.
        """
        now = time.time()
        removed = 0
        stale = 0
        while self._expiry_heap:
            exp, _seq, key = self._expiry_heap[0]
            if exp > now:
                # All remaining heap entries expire in the future.
                break
            heapq.heappop(self._expiry_heap)
            # The heap entry may be stale (key was already evicted or re-set
            # with a newer expire_time).  Only delete if the stored expire_time
            # matches the heap entry exactly.
            entry = self.cache.get(key)
            if entry is not None and entry[0] <= now:
                del self.cache[key]
                removed += 1
            else:
                stale += 1
        if removed or stale:
            logger.debug(
                "[TTLCache] cleanup_expired removed=%d stale=%d size=%d heap=%d",
                removed,
                stale,
                len(self.cache),
                len(self._expiry_heap),
            )
        self._compact_heap_if_needed()

    def _compact_heap_if_needed(self) -> None:
        """Rebuild the expiry heap when stale entries outgrow live cache data."""
        live_size = len(self.cache)
        heap_size = len(self._expiry_heap)
        limit = max(self.max_size * 2, live_size * 2, 64)
        if heap_size <= limit:
            return

        compacted: list[tuple[float, int, Any]] = []
        for key, (exp, _value) in self.cache.items():
            self._heap_seq += 1
            compacted.append((exp, self._heap_seq, key))
        self._expiry_heap = compacted
        heapq.heapify(self._expiry_heap)
        logger.debug(
            "[TTLCache] compact_heap before=%d after=%d size=%d",
            heap_size,
            len(self._expiry_heap),
            live_size,
        )

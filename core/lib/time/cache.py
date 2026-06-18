# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @Hairpin00
# version: 1.1.0
# description: TTL Cache implementation with LRU eviction

import heapq
import time
from collections import OrderedDict
from typing import Any

CacheType = OrderedDict[Any, tuple[float, Any]]


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
        self._expiry_heap: list[tuple[float, Any]] = []

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
                self.cache.popitem(last=False)

        expire_time = time.time() + (ttl if ttl is not None else self.ttl)
        self.cache[key] = (expire_time, value)
        self.cache.move_to_end(key)
        # Push to the expiry heap so cleanup can find it in O(log n).
        heapq.heappush(self._expiry_heap, (expire_time, key))

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
            return None

        expire_time, value = self.cache[key]

        if time.time() <= expire_time:
            self.cache.move_to_end(key)
            return value

        # Expired - evict lazily.
        del self.cache[key]
        return None

    def clear(self) -> None:
        """Remove all items from the cache."""
        self.cache.clear()
        self._expiry_heap.clear()

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
        while self._expiry_heap:
            exp, key = self._expiry_heap[0]
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

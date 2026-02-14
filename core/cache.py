# author: @Hairpin00
# version: 1.0.1
# description: TTL Cache implementation with LRU eviction

import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """
    A Time-To-Live (TTL) cache implementation with LRU eviction policy.

    This cache stores key-value pairs with an expiration time. When the cache
    reaches its maximum size, it removes the least recently used item.
    Expired items are automatically removed upon access.

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
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
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
        # Calculate expiration time: current time + custom TTL or default TTL
        expire_time = time.time() + (ttl if ttl is not None else self.ttl)

        # Store the key with its expiration time and value
        self.cache[key] = (expire_time, value)

        # Move to end to mark as recently used (OrderedDict maintains insertion order)
        self.cache.move_to_end(key)

        # Remove least recently used item if cache exceeds max size
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def get(self, key: Any) -> Optional[Any]:
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

        # Check if the item has expired
        if time.time() <= expire_time:
            # Mark as recently used and return value
            self.cache.move_to_end(key)
            return value
        else:
            # Remove expired item
            del self.cache[key]
            return None

    def clear(self) -> None:
        """
        Remove all items from the cache.
        """
        self.cache.clear()

    def size(self) -> int:
        """
        Get the current number of items in the cache.

        Returns:
            Number of items currently stored in the cache
        """
        return len(self.cache)

    def _cleanup_expired(self) -> None:
        """
        Remove all expired items from the cache.

        Note: This is an internal method that can be called periodically
        to clean up expired items without requiring access attempts.
        """
        current_time = time.time()
        expired_keys = [
            key for key, (expire_time, _) in self.cache.items()
            if current_time >= expire_time
        ]

        for key in expired_keys:
            del self.cache[key]

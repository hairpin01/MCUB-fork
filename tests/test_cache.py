from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
import asyncio
import time

"""
Tests for TTL cache implementation
"""
import pytest
import time
from collections import OrderedDict
from kernel import TTLCache

class TestTTLCache:
    """Test TTLCache functionality"""
    
    def test_cache_initialization(self):
        """Test cache creation with defaults"""
        cache = TTLCache()
        assert cache.max_size == 1000
        assert cache.ttl == 300
        assert isinstance(cache.cache, OrderedDict)
        assert len(cache.cache) == 0
        
    def test_cache_with_custom_params(self):
        """Test cache with custom parameters"""
        cache = TTLCache(max_size=100, ttl=60)
        assert cache.max_size == 100
        assert cache.ttl == 60
        
    def test_set_and_get(self):
        """Test basic set/get operations"""
        cache = TTLCache()
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        
        cache.set('key2', {'complex': 'data'})
        assert cache.get('key2') == {'complex': 'data'}
        
    def test_ttl_expiration(self):
        """Test time-based expiration"""
        cache = TTLCache(ttl=0.1)  # 100ms TTL
        
        cache.set('expiring_key', 'value')
        
        # Should still be there
        assert cache.get('expiring_key') == 'value'
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        assert cache.get('expiring_key') is None
        
    def test_custom_ttl_per_item(self):
        """Test item-specific TTL"""
        cache = TTLCache(ttl=300)  # Default 5 minutes
        
        # Set with shorter TTL
        cache.set('short_lived', 'value', ttl=0.1)
        cache.set('long_lived', 'value', ttl=600)
        
        time.sleep(0.15)
        
        # Short lived expired, long lived still there
        assert cache.get('short_lived') is None
        assert cache.get('long_lived') == 'value'
        
    def test_max_size_enforcement(self):
        """Test cache size limiting"""
        cache = TTLCache(max_size=3, ttl=3600)
        
        # Fill cache beyond limit
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        cache.set('key4', 'value4')  # Should evict key1
        
        assert cache.get('key1') is None  # Evicted
        assert cache.get('key4') == 'value4'  # Newest present
        assert cache.size() <= 3
        
    def test_cache_clear(self):
        """Test cache clearing"""
        cache = TTLCache()
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        assert cache.size() == 2
        
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        
    def test_lru_eviction(self):
        """Test Least Recently Used eviction policy"""
        cache = TTLCache(max_size=3, ttl=3600)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # Access key1 to make it recently used
        cache.get('key1')
        
        # Add new key - should evict key2 (least recently used)
        cache.set('key4', 'value4')
        
        assert cache.get('key1') == 'value1'  # Recently used, still there
        assert cache.get('key2') is None  # Evicted
        assert cache.get('key3') == 'value3'  # Still there
        assert cache.get('key4') == 'value4'  # New addition
        
    def test_concurrent_access_pattern(self):
        """Test realistic access patterns"""
        cache = TTLCache(max_size=100)
        
        # Simulate many accesses
        for i in range(150):
            cache.set(f'item_{i}', f'value_{i}')
            
        # Access first 50 items (make them recent)
        for i in range(50):
            cache.get(f'item_{i}')
            
        # Add more items - should evict items 50-99
        for i in range(150, 200):
            cache.set(f'item_{i}', f'value_{i}')
            
        # First 50 should still be there (recently accessed)
        for i in range(50):
            assert cache.get(f'item_{i}') == f'value_{i}'
            
        # Items 50-100 should be evicted
        for i in range(50, 100):
            assert cache.get(f'item_{i}') is None
            
    def test_cache_stats(self):
        """Test cache statistics and monitoring"""
        cache = TTLCache()
        
        assert cache.size() == 0
        
        cache.set('k1', 'v1')
        cache.set('k2', 'v2')
        
        assert cache.size() == 2
        
        # Let one expire
        cache_with_ttl = TTLCache(ttl=0.1)
        cache_with_ttl.set('exp', 'val')
        assert cache_with_ttl.size() == 1
        
        time.sleep(0.15)
        # Access should clean up expired
        cache_with_ttl.get('exp')
        assert cache_with_ttl.size() == 0

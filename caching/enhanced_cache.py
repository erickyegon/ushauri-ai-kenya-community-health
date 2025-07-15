"""
Enhanced Caching System for Kenya Health AI
Comprehensive caching with API response caching, intelligent invalidation, and performance optimization
"""

import os
import json
import sqlite3
import hashlib
import pickle
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    timestamp: datetime
    ttl_seconds: int
    hit_count: int = 0
    tags: List[str] = None
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl_seconds <= 0:  # Never expires
            return False
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'key': self.key,
            'timestamp': self.timestamp.isoformat(),
            'ttl_seconds': self.ttl_seconds,
            'hit_count': self.hit_count,
            'tags': self.tags or [],
            'size_bytes': self.size_bytes
        }

class EnhancedCache:
    """
    Enhanced caching system with multiple cache types and intelligent invalidation
    """
    
    def __init__(self, cache_dir: str = "cache", max_memory_size_mb: int = 100):
        self.cache_dir = cache_dir
        self.max_memory_size_bytes = max_memory_size_mb * 1024 * 1024
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'invalidations': 0
        }
        self.lock = threading.RLock()
        
        # Initialize cache directory and database
        self._init_cache_system()
        
        # Cache type configurations
        self.cache_configs = {
            'api_response': {'ttl': 3600, 'max_size': 50},  # 1 hour, 50 entries
            'sql_query': {'ttl': 1800, 'max_size': 100},    # 30 minutes, 100 entries
            'agent_response': {'ttl': 900, 'max_size': 30},  # 15 minutes, 30 entries
            'workflow_result': {'ttl': 600, 'max_size': 20}, # 10 minutes, 20 entries
            'database_schema': {'ttl': 86400, 'max_size': 5}, # 24 hours, 5 entries
            'user_session': {'ttl': 7200, 'max_size': 50}    # 2 hours, 50 entries
        }
    
    def _init_cache_system(self):
        """Initialize cache system"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize persistent cache database
        self.db_path = os.path.join(self.cache_dir, "enhanced_cache.db")
        self._init_database()
        
        # Load existing cache entries from database
        self._load_from_database()
    
    def _init_database(self):
        """Initialize SQLite database for persistent caching"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    timestamp TEXT,
                    ttl_seconds INTEGER,
                    hit_count INTEGER DEFAULT 0,
                    tags TEXT,
                    size_bytes INTEGER,
                    cache_type TEXT
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cache_entries(timestamp)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_cache_type ON cache_entries(cache_type)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tags ON cache_entries(tags)
            ''')
            
            conn.commit()
    
    def _load_from_database(self):
        """Load cache entries from database to memory"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT key, value, timestamp, ttl_seconds, hit_count, tags, size_bytes
                    FROM cache_entries
                ''')
                
                for row in cursor.fetchall():
                    key, value_blob, timestamp_str, ttl_seconds, hit_count, tags_str, size_bytes = row
                    
                    try:
                        # Deserialize value
                        value = pickle.loads(value_blob)
                        
                        # Parse timestamp
                        timestamp = datetime.fromisoformat(timestamp_str)
                        
                        # Parse tags
                        tags = json.loads(tags_str) if tags_str else []
                        
                        # Create cache entry
                        entry = CacheEntry(
                            key=key,
                            value=value,
                            timestamp=timestamp,
                            ttl_seconds=ttl_seconds,
                            hit_count=hit_count,
                            tags=tags,
                            size_bytes=size_bytes
                        )
                        
                        # Only load if not expired
                        if not entry.is_expired():
                            self.memory_cache[key] = entry
                        
                    except Exception as e:
                        logger.warning(f"Failed to load cache entry {key}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to load cache from database: {e}")
    
    def _save_to_database(self, entry: CacheEntry):
        """Save cache entry to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Serialize value
                value_blob = pickle.dumps(entry.value)
                
                # Serialize tags
                tags_str = json.dumps(entry.tags) if entry.tags else None
                
                # Determine cache type from key
                cache_type = self._get_cache_type_from_key(entry.key)
                
                conn.execute('''
                    INSERT OR REPLACE INTO cache_entries 
                    (key, value, timestamp, ttl_seconds, hit_count, tags, size_bytes, cache_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry.key,
                    value_blob,
                    entry.timestamp.isoformat(),
                    entry.ttl_seconds,
                    entry.hit_count,
                    tags_str,
                    entry.size_bytes,
                    cache_type
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save cache entry to database: {e}")
    
    def _get_cache_type_from_key(self, key: str) -> str:
        """Determine cache type from key"""
        if key.startswith('api_'):
            return 'api_response'
        elif key.startswith('sql_'):
            return 'sql_query'
        elif key.startswith('agent_'):
            return 'agent_response'
        elif key.startswith('workflow_'):
            return 'workflow_result'
        elif key.startswith('schema_'):
            return 'database_schema'
        elif key.startswith('session_'):
            return 'user_session'
        else:
            return 'general'
    
    def _generate_cache_key(self, cache_type: str, identifier: str, **kwargs) -> str:
        """Generate cache key with type prefix and hash"""
        # Create a deterministic string from identifier and kwargs
        key_parts = [identifier]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        key_string = "|".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
        
        return f"{cache_type}_{key_hash}"
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of value in bytes"""
        try:
            return len(pickle.dumps(value))
        except:
            return len(str(value).encode('utf-8'))
    
    def _evict_if_needed(self):
        """Evict cache entries if memory limit exceeded"""
        current_size = sum(entry.size_bytes for entry in self.memory_cache.values())
        
        if current_size <= self.max_memory_size_bytes:
            return
        
        # Sort by hit count (ascending) and timestamp (ascending) for LRU eviction
        entries_by_priority = sorted(
            self.memory_cache.items(),
            key=lambda x: (x[1].hit_count, x[1].timestamp)
        )
        
        # Evict entries until under limit
        for key, entry in entries_by_priority:
            if current_size <= self.max_memory_size_bytes:
                break
            
            current_size -= entry.size_bytes
            del self.memory_cache[key]
            self.cache_stats['evictions'] += 1
            
            logger.debug(f"Evicted cache entry: {key}")
    
    def get(self, cache_type: str, identifier: str, **kwargs) -> Optional[Any]:
        """Get value from cache"""
        key = self._generate_cache_key(cache_type, identifier, **kwargs)
        
        with self.lock:
            entry = self.memory_cache.get(key)
            
            if entry is None:
                self.cache_stats['misses'] += 1
                return None
            
            if entry.is_expired():
                del self.memory_cache[key]
                self.cache_stats['misses'] += 1
                return None
            
            # Update hit count
            entry.hit_count += 1
            self.cache_stats['hits'] += 1
            
            # Save updated hit count to database
            self._save_to_database(entry)
            
            logger.debug(f"Cache hit: {key}")
            return entry.value
    
    def set(self, cache_type: str, identifier: str, value: Any, ttl_seconds: Optional[int] = None, tags: List[str] = None, **kwargs):
        """Set value in cache"""
        key = self._generate_cache_key(cache_type, identifier, **kwargs)
        
        # Use default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self.cache_configs.get(cache_type, {}).get('ttl', 3600)
        
        size_bytes = self._calculate_size(value)
        
        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=datetime.now(),
            ttl_seconds=ttl_seconds,
            hit_count=0,
            tags=tags or [],
            size_bytes=size_bytes
        )
        
        with self.lock:
            self.memory_cache[key] = entry
            self._save_to_database(entry)
            self._evict_if_needed()
        
        logger.debug(f"Cache set: {key} (size: {size_bytes} bytes)")
    
    def invalidate(self, cache_type: str = None, tags: List[str] = None, pattern: str = None):
        """Invalidate cache entries by type, tags, or pattern"""
        with self.lock:
            keys_to_remove = []
            
            for key, entry in self.memory_cache.items():
                should_remove = False
                
                # Check cache type
                if cache_type and self._get_cache_type_from_key(key) == cache_type:
                    should_remove = True
                
                # Check tags
                if tags and entry.tags:
                    if any(tag in entry.tags for tag in tags):
                        should_remove = True
                
                # Check pattern
                if pattern and pattern in key:
                    should_remove = True
                
                if should_remove:
                    keys_to_remove.append(key)
            
            # Remove from memory cache
            for key in keys_to_remove:
                del self.memory_cache[key]
                self.cache_stats['invalidations'] += 1
            
            # Remove from database
            if keys_to_remove:
                with sqlite3.connect(self.db_path) as conn:
                    placeholders = ','.join('?' * len(keys_to_remove))
                    conn.execute(f'DELETE FROM cache_entries WHERE key IN ({placeholders})', keys_to_remove)
                    conn.commit()
            
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries")
    
    def clear_expired(self):
        """Clear all expired cache entries"""
        with self.lock:
            expired_keys = [
                key for key, entry in self.memory_cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self.memory_cache[key]
            
            # Clear from database
            if expired_keys:
                with sqlite3.connect(self.db_path) as conn:
                    placeholders = ','.join('?' * len(expired_keys))
                    conn.execute(f'DELETE FROM cache_entries WHERE key IN ({placeholders})', expired_keys)
                    conn.commit()
            
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_entries = len(self.memory_cache)
            total_size = sum(entry.size_bytes for entry in self.memory_cache.values())
            
            # Cache type breakdown
            type_breakdown = defaultdict(int)
            for key in self.memory_cache.keys():
                cache_type = self._get_cache_type_from_key(key)
                type_breakdown[cache_type] += 1
            
            # Hit rate calculation
            total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
            hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'total_entries': total_entries,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'memory_usage_percent': round((total_size / self.max_memory_size_bytes) * 100, 1),
                'hit_rate_percent': round(hit_rate, 1),
                'cache_stats': self.cache_stats.copy(),
                'type_breakdown': dict(type_breakdown),
                'cache_configs': self.cache_configs
            }
    
    def cleanup(self):
        """Cleanup cache system"""
        self.clear_expired()
        
        # Vacuum database
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('VACUUM')
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to vacuum cache database: {e}")

# Global cache instance
_enhanced_cache = None

def get_enhanced_cache() -> EnhancedCache:
    """Get global enhanced cache instance"""
    global _enhanced_cache
    if _enhanced_cache is None:
        _enhanced_cache = EnhancedCache()
    return _enhanced_cache

# Convenience functions for different cache types
def cache_api_response(endpoint: str, params: Dict, response: Any, ttl_seconds: int = 3600):
    """Cache API response"""
    cache = get_enhanced_cache()
    cache.set('api_response', endpoint, response, ttl_seconds, tags=['api'], **params)

def get_cached_api_response(endpoint: str, params: Dict) -> Optional[Any]:
    """Get cached API response"""
    cache = get_enhanced_cache()
    return cache.get('api_response', endpoint, **params)

def cache_sql_query(query: str, result: Any, ttl_seconds: int = 1800):
    """Cache SQL query result"""
    cache = get_enhanced_cache()
    cache.set('sql_query', query, result, ttl_seconds, tags=['sql'])

def get_cached_sql_query(query: str) -> Optional[Any]:
    """Get cached SQL query result"""
    cache = get_enhanced_cache()
    return cache.get('sql_query', query)

def cache_agent_response(agent_type: str, prompt: str, response: Any, ttl_seconds: int = 900):
    """Cache agent response"""
    cache = get_enhanced_cache()
    cache.set('agent_response', f"{agent_type}_{prompt}", response, ttl_seconds, tags=['agent', agent_type])

def get_cached_agent_response(agent_type: str, prompt: str) -> Optional[Any]:
    """Get cached agent response"""
    cache = get_enhanced_cache()
    return cache.get('agent_response', f"{agent_type}_{prompt}")

def invalidate_cache_by_type(cache_type: str):
    """Invalidate all cache entries of a specific type"""
    cache = get_enhanced_cache()
    cache.invalidate(cache_type=cache_type)

def get_cache_statistics() -> Dict[str, Any]:
    """Get comprehensive cache statistics"""
    cache = get_enhanced_cache()
    return cache.get_stats()

"""
tools/memory.py - Conversation memory and caching system
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import pickle
import streamlit as st
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Memory storage configurations
MEMORY_DIR = "memory"
CHAT_MEMORY_FILE = os.path.join(MEMORY_DIR, "chat_memory.json")
CACHE_DB_FILE = os.path.join(MEMORY_DIR, "query_cache.db")
SESSION_MEMORY_FILE = os.path.join(MEMORY_DIR, "session_memory.json")
MAX_MEMORY_ENTRIES = 1000
CACHE_EXPIRY_DAYS = 7


class ConversationMemory:
    """Manages conversation history and context"""
    
    def __init__(self):
        self._ensure_directories()
        self.memory_data = self._load_memory()
        self._init_cache_db()
    
    def _ensure_directories(self):
        """Create memory directory if it doesn't exist"""
        os.makedirs(MEMORY_DIR, exist_ok=True)
    
    def _load_memory(self) -> List[Dict]:
        """Load conversation memory from file"""
        try:
            if os.path.exists(CHAT_MEMORY_FILE):
                with open(CHAT_MEMORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure each entry has required fields
                    for entry in data:
                        if 'timestamp' not in entry:
                            entry['timestamp'] = datetime.now().isoformat()
                        if 'session_id' not in entry:
                            entry['session_id'] = 'default'
                    return data
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
        
        return []
    
    def _save_memory(self):
        """Save conversation memory to file"""
        try:
            # Keep only the most recent entries
            if len(self.memory_data) > MAX_MEMORY_ENTRIES:
                self.memory_data = self.memory_data[-MAX_MEMORY_ENTRIES:]
            
            with open(CHAT_MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.memory_data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def _init_cache_db(self):
        """Initialize SQLite database for query caching"""
        try:
            with sqlite3.connect(CACHE_DB_FILE) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS query_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_hash TEXT UNIQUE,
                        query_text TEXT,
                        result_data BLOB,
                        timestamp DATETIME,
                        hit_count INTEGER DEFAULT 1,
                        session_id TEXT
                    )
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_query_hash ON query_cache(query_hash)
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON query_cache(timestamp)
                ''')
                
                conn.commit()
        
        except Exception as e:
            logger.error(f"Error initializing cache database: {e}")
    
    def add_conversation(self, query: str, response: str, metadata: Dict = None):
        """Add a conversation entry to memory"""
        
        entry = {
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "session_id": self._get_session_id(),
            "metadata": metadata or {}
        }
        
        # Add context from recent conversations
        recent_context = self.get_recent_context(5)
        if recent_context:
            entry["context"] = recent_context
        
        self.memory_data.append(entry)
        self._save_memory()
        
        logger.info(f"Added conversation to memory: {query[:50]}...")
    
    def get_recent_context(self, limit: int = 5) -> List[Dict]:
        """Get recent conversation context"""
        if len(self.memory_data) == 0:
            return []
        
        return [
            {
                "query": entry["query"],
                "response": entry["response"][:200] + "..." if len(entry["response"]) > 200 else entry["response"],
                "timestamp": entry["timestamp"]
            }
            for entry in self.memory_data[-limit:]
        ]
    
    def search_conversations(self, search_term: str, limit: int = 10) -> List[Dict]:
        """Search conversations by query or response content"""
        search_term_lower = search_term.lower()
        results = []
        
        for entry in reversed(self.memory_data):
            if (search_term_lower in entry["query"].lower() or 
                search_term_lower in entry["response"].lower()):
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_conversation_by_session(self, session_id: str) -> List[Dict]:
        """Get all conversations for a specific session"""
        return [
            entry for entry in self.memory_data 
            if entry.get("session_id") == session_id
        ]
    
    def get_conversation_statistics(self) -> Dict[str, Any]:
        """Get statistics about conversation history"""
        if not self.memory_data:
            return {"total_conversations": 0}
        
        total = len(self.memory_data)
        sessions = len(set(entry.get("session_id", "default") for entry in self.memory_data))
        
        # Recent activity (last 24 hours)
        recent_cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent_count = sum(1 for entry in self.memory_data if entry["timestamp"] > recent_cutoff)
        
        # Most common query types
        query_types = {}
        for entry in self.memory_data:
            query_lower = entry["query"].lower()
            if "county" in query_lower:
                query_types["geographic"] = query_types.get("geographic", 0) + 1
            elif "chw" in query_lower or "performance" in query_lower:
                query_types["performance"] = query_types.get("performance", 0) + 1
            elif "family planning" in query_lower or "fp" in query_lower:
                query_types["family_planning"] = query_types.get("family_planning", 0) + 1
            else:
                query_types["general"] = query_types.get("general", 0) + 1
        
        return {
            "total_conversations": total,
            "unique_sessions": sessions,
            "recent_24h": recent_count,
            "query_types": query_types,
            "avg_conversations_per_session": round(total / max(sessions, 1), 2)
        }
    
    def _get_session_id(self) -> str:
        """Get current session ID"""
        if hasattr(st, 'session_state') and hasattr(st.session_state, 'session_id'):
            return st.session_state.session_id
        return "default"
    
    def clear_old_conversations(self, days: int = 30):
        """Clear conversations older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        original_count = len(self.memory_data)
        self.memory_data = [
            entry for entry in self.memory_data 
            if entry["timestamp"] > cutoff_date
        ]
        
        removed_count = original_count - len(self.memory_data)
        if removed_count > 0:
            self._save_memory()
            logger.info(f"Removed {removed_count} old conversations")
        
        return removed_count


class QueryCache:
    """Manages query result caching"""
    
    def __init__(self):
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize cache database"""
        try:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            with sqlite3.connect(CACHE_DB_FILE) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS query_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_hash TEXT UNIQUE,
                        query_text TEXT,
                        result_data BLOB,
                        timestamp DATETIME,
                        hit_count INTEGER DEFAULT 1,
                        session_id TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing query cache: {e}")
    
    def _generate_query_hash(self, query: str) -> str:
        """Generate hash for query caching"""
        # Normalize query for consistent hashing
        normalized_query = query.lower().strip()
        return hashlib.md5(normalized_query.encode()).hexdigest()
    
    def get_cached_result(self, query: str) -> Optional[Dict]:
        """Get cached result for query"""
        query_hash = self._generate_query_hash(query)
        
        try:
            with sqlite3.connect(CACHE_DB_FILE) as conn:
                cursor = conn.execute('''
                    SELECT result_data, timestamp, hit_count 
                    FROM query_cache 
                    WHERE query_hash = ?
                ''', (query_hash,))
                
                row = cursor.fetchone()
                if row:
                    result_data, timestamp, hit_count = row
                    
                    # Check if cache entry is still valid
                    cache_time = datetime.fromisoformat(timestamp)
                    if datetime.now() - cache_time < timedelta(days=CACHE_EXPIRY_DAYS):
                        # Update hit count
                        conn.execute('''
                            UPDATE query_cache 
                            SET hit_count = hit_count + 1 
                            WHERE query_hash = ?
                        ''', (query_hash,))
                        conn.commit()
                        
                        # Deserialize result
                        result = pickle.loads(result_data)
                        result["_cached"] = True
                        result["_cache_timestamp"] = timestamp
                        result["_hit_count"] = hit_count + 1
                        
                        logger.info(f"Cache hit for query: {query[:50]}...")
                        return result
        
        except Exception as e:
            logger.error(f"Error getting cached result: {e}")
        
        return None
    
    def cache_result(self, query: str, result: Dict):
        """Cache query result"""
        query_hash = self._generate_query_hash(query)
        
        try:
            # Serialize result (exclude non-serializable objects)
            cacheable_result = self._make_cacheable(result.copy())
            result_data = pickle.dumps(cacheable_result)
            
            with sqlite3.connect(CACHE_DB_FILE) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO query_cache 
                    (query_hash, query_text, result_data, timestamp, session_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    query_hash,
                    query,
                    result_data,
                    datetime.now().isoformat(),
                    self._get_session_id()
                ))
                conn.commit()
            
            logger.info(f"Cached result for query: {query[:50]}...")
        
        except Exception as e:
            logger.error(f"Error caching result: {e}")
    
    def _make_cacheable(self, result: Dict) -> Dict:
        """Make result dictionary cacheable by removing non-serializable objects"""
        cacheable = {}
        
        for key, value in result.items():
            if key == "chart":
                # Don't cache Plotly charts - they're too large
                continue
            elif key == "df" and value is not None:
                # Convert DataFrame to JSON
                try:
                    cacheable[key] = value.to_json(orient='records')
                    cacheable[f"{key}_is_json"] = True
                except:
                    continue
            elif isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                cacheable[key] = value
        
        return cacheable
    
    def _restore_from_cache(self, result: Dict) -> Dict:
        """Restore cached result to original format"""
        restored = result.copy()
        
        if "df_is_json" in result and result["df_is_json"]:
            try:
                df_json = result["df"]
                restored["df"] = pd.read_json(df_json, orient='records')
                del restored["df_is_json"]
            except:
                restored["df"] = None
        
        return restored
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with sqlite3.connect(CACHE_DB_FILE) as conn:
                # Total entries
                total_cursor = conn.execute('SELECT COUNT(*) FROM query_cache')
                total_entries = total_cursor.fetchone()[0]
                
                # Hit statistics
                hits_cursor = conn.execute('SELECT SUM(hit_count) FROM query_cache')
                total_hits = hits_cursor.fetchone()[0] or 0
                
                # Recent entries (last 24 hours)
                recent_cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                recent_cursor = conn.execute('''
                    SELECT COUNT(*) FROM query_cache 
                    WHERE timestamp > ?
                ''', (recent_cutoff,))
                recent_entries = recent_cursor.fetchone()[0]
                
                return {
                    "total_entries": total_entries,
                    "total_hits": total_hits,
                    "recent_entries_24h": recent_entries,
                    "avg_hits_per_entry": round(total_hits / max(total_entries, 1), 2)
                }
        
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {"total_entries": 0, "total_hits": 0, "recent_entries_24h": 0}
    
    def clear_expired_cache(self):
        """Clear expired cache entries"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS)).isoformat()
            
            with sqlite3.connect(CACHE_DB_FILE) as conn:
                cursor = conn.execute('''
                    DELETE FROM query_cache 
                    WHERE timestamp < ?
                ''', (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleared {deleted_count} expired cache entries")
                
                return deleted_count
        
        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")
            return 0
    
    def _get_session_id(self) -> str:
        """Get current session ID"""
        if hasattr(st, 'session_state') and hasattr(st.session_state, 'session_id'):
            return st.session_state.session_id
        return "default"


class SessionMemory:
    """Manages session-specific memory and context"""
    
    def __init__(self):
        self.session_data = self._load_session_memory()
    
    def _load_session_memory(self) -> Dict:
        """Load session memory from file"""
        try:
            if os.path.exists(SESSION_MEMORY_FILE):
                with open(SESSION_MEMORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading session memory: {e}")
        
        return {}
    
    def _save_session_memory(self):
        """Save session memory to file"""
        try:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            with open(SESSION_MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving session memory: {e}")
    
    def get_session_context(self, session_id: str) -> Dict:
        """Get context for a specific session"""
        return self.session_data.get(session_id, {})
    
    def update_session_context(self, session_id: str, context: Dict):
        """Update context for a session"""
        if session_id not in self.session_data:
            self.session_data[session_id] = {}
        
        self.session_data[session_id].update(context)
        self.session_data[session_id]["last_updated"] = datetime.now().isoformat()
        
        self._save_session_memory()
    
    def clear_session(self, session_id: str):
        """Clear data for a specific session"""
        if session_id in self.session_data:
            del self.session_data[session_id]
            self._save_session_memory()


# Global instances
_conversation_memory = None
_query_cache = None
_session_memory = None

def get_conversation_memory() -> ConversationMemory:
    """Get global conversation memory instance"""
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory

def get_query_cache() -> QueryCache:
    """Get global query cache instance"""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache

def get_session_memory() -> SessionMemory:
    """Get global session memory instance"""
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory()
    return _session_memory


# Convenience functions for the main app
def load_chat_memory() -> List[Tuple[str, str]]:
    """Load chat memory in simple format for UI display"""
    memory = get_conversation_memory()
    return [(entry["query"], entry["response"]) for entry in memory.memory_data[-20:]]

def save_chat_memory(query: str, response: str, metadata: Dict = None):
    """Save conversation to memory"""
    memory = get_conversation_memory()
    memory.add_conversation(query, response, metadata)

def get_cached_query_result(query: str) -> Optional[Dict]:
    """Get cached result for query"""
    cache = get_query_cache()
    return cache.get_cached_result(query)

def cache_query_result(query: str, result: Dict):
    """Cache query result"""
    cache = get_query_cache()
    cache.cache_result(query, result)

def search_conversation_history(search_term: str, limit: int = 10) -> List[Dict]:
    """Search conversation history"""
    memory = get_conversation_memory()
    return memory.search_conversations(search_term, limit)

def get_memory_statistics() -> Dict[str, Any]:
    """Get comprehensive memory statistics"""
    conv_memory = get_conversation_memory()
    query_cache = get_query_cache()
    
    conv_stats = conv_memory.get_conversation_statistics()
    cache_stats = query_cache.get_cache_statistics()
    
    return {
        "conversations": conv_stats,
        "cache": cache_stats,
        "memory_files_exist": {
            "chat_memory": os.path.exists(CHAT_MEMORY_FILE),
            "cache_db": os.path.exists(CACHE_DB_FILE),
            "session_memory": os.path.exists(SESSION_MEMORY_FILE)
        }
    }

def cleanup_memory_system():
    """Cleanup old memory data"""
    try:
        conv_memory = get_conversation_memory()
        query_cache = get_query_cache()
        
        # Clear old conversations (older than 30 days)
        removed_conversations = conv_memory.clear_old_conversations(30)
        
        # Clear expired cache
        removed_cache = query_cache.clear_expired_cache()
        
        return {
            "removed_conversations": removed_conversations,
            "removed_cache_entries": removed_cache
        }
    
    except Exception as e:
        logger.error(f"Error during memory cleanup: {e}")
        return {"error": str(e)}

def initialize_session_id():
    """Initialize session ID for Streamlit"""
    if 'session_id' not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4())[:8]

def render_memory_sidebar():
    """Render memory information in Streamlit sidebar"""
    with st.sidebar:
        st.subheader("🧠 Memory System")
        
        # Memory statistics
        stats = get_memory_statistics()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Conversations", stats["conversations"]["total_conversations"])
            st.metric("Cache Hits", stats["cache"]["total_hits"])
        
        with col2:
            st.metric("Sessions", stats["conversations"]["unique_sessions"])
            st.metric("Cache Entries", stats["cache"]["total_entries"])
        
        # Recent activity
        if stats["conversations"]["recent_24h"] > 0:
            st.success(f"🟢 {stats['conversations']['recent_24h']} queries today")
        
        # Memory management
        if st.button("🗑️ Clear Old Data"):
            cleanup_result = cleanup_memory_system()
            if "error" not in cleanup_result:
                st.success(f"Cleaned {cleanup_result['removed_conversations']} conversations")
            else:
                st.error("Cleanup failed")


@contextmanager
def memory_transaction():
    """Context manager for memory operations"""
    try:
        yield
    except Exception as e:
        logger.error(f"Memory transaction failed: {e}")
        raise
    finally:
        # Ensure memory is saved
        try:
            _conversation_memory._save_memory() if _conversation_memory else None
        except:
            pass


# Memory optimization functions
def optimize_memory_storage():
    """Optimize memory storage by compacting and cleaning data"""
    try:
        # Compact conversation memory
        conv_memory = get_conversation_memory()
        original_size = len(conv_memory.memory_data)
        
        # Remove duplicate queries (keep most recent)
        seen_queries = {}
        unique_conversations = []
        
        for entry in reversed(conv_memory.memory_data):
            query_normalized = entry["query"].lower().strip()
            if query_normalized not in seen_queries:
                seen_queries[query_normalized] = True
                unique_conversations.append(entry)
        
        conv_memory.memory_data = list(reversed(unique_conversations))
        conv_memory._save_memory()
        
        # Compact cache database
        query_cache = get_query_cache()
        with sqlite3.connect(CACHE_DB_FILE) as conn:
            conn.execute("VACUUM")
            conn.commit()
        
        optimized_size = len(conv_memory.memory_data)
        
        return {
            "original_conversations": original_size,
            "optimized_conversations": optimized_size,
            "space_saved": original_size - optimized_size
        }
    
    except Exception as e:
        logger.error(f"Memory optimization failed: {e}")
        return {"error": str(e)}

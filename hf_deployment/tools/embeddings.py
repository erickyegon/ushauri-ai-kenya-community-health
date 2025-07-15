"""
tools/embeddings.py - Semantic search and embeddings for query similarity
"""

import os
import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import pickle
from typing import List, Dict, Tuple
import streamlit as st
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
EMBEDDINGS_DIR = "embeddings"
EMBEDDINGS_FILE = os.path.join(EMBEDDINGS_DIR, "query_embeddings.pkl")
INDEX_FILE = os.path.join(EMBEDDINGS_DIR, "faiss_index.bin")
QUERIES_FILE = os.path.join(EMBEDDINGS_DIR, "queries_data.json")
MODEL_NAME = "all-MiniLM-L6-v2"  # Lightweight but effective model


class QueryEmbeddingManager:
    """Manages embeddings for query similarity search"""
    
    def __init__(self):
        self.model = None
        self.index = None
        self.queries_data = []
        self.embeddings = None
        self._ensure_directories()
        self._load_model()
        self._load_or_create_index()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
    
    @st.cache_resource
    def _load_model(_self):
        """Load sentence transformer model with caching"""
        try:
            logger.info(f"Loading sentence transformer model: {MODEL_NAME}")
            model = SentenceTransformer(MODEL_NAME)
            logger.info("Model loaded successfully")
            return model
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            # Fallback to a smaller model
            try:
                model = SentenceTransformer('all-MiniLM-L12-v2')
                logger.info("Loaded fallback model")
                return model
            except:
                logger.error("Failed to load any model")
                return None
    
    def _load_or_create_index(self):
        """Load existing FAISS index or create new one"""
        try:
            if os.path.exists(INDEX_FILE) and os.path.exists(QUERIES_FILE) and os.path.exists(EMBEDDINGS_FILE):
                # Load existing index
                self.index = faiss.read_index(INDEX_FILE)
                
                with open(QUERIES_FILE, 'r') as f:
                    self.queries_data = json.load(f)
                
                with open(EMBEDDINGS_FILE, 'rb') as f:
                    self.embeddings = pickle.load(f)
                
                logger.info(f"Loaded existing index with {len(self.queries_data)} queries")
            else:
                # Create new index
                self._create_new_index()
                
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self._create_new_index()
    
    def _create_new_index(self):
        """Create new FAISS index with sample queries"""
        logger.info("Creating new embedding index")
        
        # Sample health-related queries for initialization
        sample_queries = [
            "What is the average supervision score by county?",
            "Which CHWs need retraining?",
            "Show family planning trends",
            "How many households are registered?",
            "CHW performance over time",
            "Counties with low malaria scores",
            "Tool availability by region",
            "Under-2 population coverage",
            "Immunization rates by county",
            "Supervision visit frequency",
            "Family planning adoption rates",
            "CHW workload distribution"
        ]
        
        self.queries_data = []
        embeddings_list = []
        
        if self.model is None:
            logger.warning("No model available, creating empty index")
            self.index = faiss.IndexFlatIP(384)  # Default dimension
            return
        
        for query in sample_queries:
            embedding = self.model.encode([query])[0]
            embeddings_list.append(embedding)
            
            self.queries_data.append({
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "count": 1,
                "category": "sample"
            })
        
        # Create FAISS index
        if embeddings_list:
            self.embeddings = np.array(embeddings_list).astype('float32')
            dimension = self.embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)  # Inner product similarity
            self.index.add(self.embeddings)
            
            # Save to disk
            self._save_index()
            logger.info(f"Created new index with {len(sample_queries)} sample queries")
    
    def _save_index(self):
        """Save index and data to disk"""
        try:
            if self.index is not None:
                faiss.write_index(self.index, INDEX_FILE)
            
            with open(QUERIES_FILE, 'w') as f:
                json.dump(self.queries_data, f, indent=2)
            
            if self.embeddings is not None:
                with open(EMBEDDINGS_FILE, 'wb') as f:
                    pickle.dump(self.embeddings, f)
            
            logger.info("Index saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def add_query(self, query: str, response: str = None):
        """Add new query to the index"""
        if self.model is None:
            logger.warning("No model available, cannot add query")
            return
        
        try:
            # Check if query already exists
            existing_idx = self._find_exact_match(query)
            
            if existing_idx is not None:
                # Update existing query count
                self.queries_data[existing_idx]["count"] += 1
                self.queries_data[existing_idx]["last_used"] = datetime.now().isoformat()
                if response:
                    self.queries_data[existing_idx]["last_response"] = response[:200]  # Truncate
            else:
                # Add new query
                embedding = self.model.encode([query])[0].astype('float32')
                
                # Add to FAISS index
                self.index.add(np.array([embedding]))
                
                # Add to embeddings array
                if self.embeddings is None:
                    self.embeddings = np.array([embedding])
                else:
                    self.embeddings = np.vstack([self.embeddings, embedding])
                
                # Add to queries data
                query_data = {
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "count": 1,
                    "category": "user",
                    "last_used": datetime.now().isoformat()
                }
                
                if response:
                    query_data["last_response"] = response[:200]  # Truncate for storage
                
                self.queries_data.append(query_data)
            
            # Save updated index
            self._save_index()
            
        except Exception as e:
            logger.error(f"Error adding query: {e}")
    
    def _find_exact_match(self, query: str) -> int:
        """Find exact match for query"""
        for i, q_data in enumerate(self.queries_data):
            if q_data["query"].lower().strip() == query.lower().strip():
                return i
        return None
    
    def search_similar_queries(self, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict]:
        """Search for similar queries"""
        if self.model is None or self.index is None or len(self.queries_data) == 0:
            return []
        
        try:
            # Encode query
            query_embedding = self.model.encode([query]).astype('float32')
            
            # Search in FAISS index
            scores, indices = self.index.search(query_embedding, min(top_k * 2, len(self.queries_data)))
            
            # Filter and format results
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.queries_data) and score > threshold:
                    query_data = self.queries_data[idx].copy()
                    query_data["similarity_score"] = float(score)
                    results.append(query_data)
            
            # Sort by similarity and frequency
            results.sort(key=lambda x: (x["similarity_score"], x["count"]), reverse=True)
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Error searching similar queries: {e}")
            return []
    
    def get_popular_queries(self, top_k: int = 10) -> List[Dict]:
        """Get most popular queries"""
        try:
            # Sort by count and recency
            sorted_queries = sorted(
                self.queries_data,
                key=lambda x: (x["count"], x.get("last_used", x["timestamp"])),
                reverse=True
            )
            return sorted_queries[:top_k]
            
        except Exception as e:
            logger.error(f"Error getting popular queries: {e}")
            return []
    
    def get_recent_queries(self, top_k: int = 10) -> List[Dict]:
        """Get most recent queries"""
        try:
            sorted_queries = sorted(
                [q for q in self.queries_data if q.get("category") == "user"],
                key=lambda x: x.get("last_used", x["timestamp"]),
                reverse=True
            )
            return sorted_queries[:top_k]
            
        except Exception as e:
            logger.error(f"Error getting recent queries: {e}")
            return []
    
    def get_query_suggestions(self, partial_query: str) -> List[str]:
        """Get query suggestions based on partial input"""
        if len(partial_query) < 3:
            return []
        
        suggestions = []
        partial_lower = partial_query.lower()
        
        for q_data in self.queries_data:
            query = q_data["query"]
            if partial_lower in query.lower() and query not in suggestions:
                suggestions.append(query)
        
        # Sort by frequency
        suggestions.sort(key=lambda x: next(
            (q["count"] for q in self.queries_data if q["query"] == x), 0
        ), reverse=True)
        
        return suggestions[:10]
    
    def clear_user_queries(self):
        """Clear all user queries, keep sample queries"""
        try:
            # Keep only sample queries
            sample_queries = [q for q in self.queries_data if q.get("category") == "sample"]
            
            if sample_queries:
                # Rebuild index with sample queries only
                self.queries_data = sample_queries
                embeddings_list = []
                
                for q_data in sample_queries:
                    embedding = self.model.encode([q_data["query"]])[0]
                    embeddings_list.append(embedding)
                
                self.embeddings = np.array(embeddings_list).astype('float32')
                dimension = self.embeddings.shape[1]
                self.index = faiss.IndexFlatIP(dimension)
                self.index.add(self.embeddings)
                
                self._save_index()
                logger.info("Cleared user queries, kept sample queries")
            else:
                # Create completely new index
                self._create_new_index()
                
        except Exception as e:
            logger.error(f"Error clearing user queries: {e}")


# Global instance
_embedding_manager = None

def get_embedding_manager():
    """Get or create global embedding manager instance"""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = QueryEmbeddingManager()
    return _embedding_manager


def search_similar_questions(query: str, top_k: int = 5):
    """
    Public function to search for similar questions
    Returns formatted string for display
    """
    manager = get_embedding_manager()
    similar_queries = manager.search_similar_queries(query, top_k)
    
    if not similar_queries:
        return "No similar questions found in history."
    
    result_lines = ["Similar questions from history:"]
    for i, q_data in enumerate(similar_queries, 1):
        similarity = q_data["similarity_score"] * 100
        count = q_data["count"]
        result_lines.append(
            f"{i}. {q_data['query']} (similarity: {similarity:.1f}%, asked {count} times)"
        )
    
    return "\n".join(result_lines)


def add_user_query(query: str, response: str = None):
    """Public function to add user query to embeddings"""
    manager = get_embedding_manager()
    manager.add_query(query, response)


def get_query_suggestions(partial_query: str):
    """Public function to get query suggestions"""
    manager = get_embedding_manager()
    return manager.get_query_suggestions(partial_query)


def get_popular_queries(top_k: int = 10):
    """Public function to get popular queries"""
    manager = get_embedding_manager()
    return manager.get_popular_queries(top_k)


def get_recent_queries(top_k: int = 10):
    """Public function to get recent queries"""
    manager = get_embedding_manager()
    return manager.get_recent_queries(top_k)


def export_queries_data():
    """Export all queries data for analysis"""
    manager = get_embedding_manager()
    return pd.DataFrame(manager.queries_data)


def get_embedding_stats():
    """Get statistics about the embedding system"""
    manager = get_embedding_manager()
    
    total_queries = len(manager.queries_data)
    user_queries = len([q for q in manager.queries_data if q.get("category") == "user"])
    sample_queries = total_queries - user_queries
    
    if user_queries > 0:
        avg_count = np.mean([q["count"] for q in manager.queries_data if q.get("category") == "user"])
        max_count = max([q["count"] for q in manager.queries_data if q.get("category") == "user"])
    else:
        avg_count = 0
        max_count = 0
    
    return {
        "total_queries": total_queries,
        "user_queries": user_queries,
        "sample_queries": sample_queries,
        "avg_query_frequency": round(avg_count, 2),
        "max_query_frequency": max_count,
        "model_name": MODEL_NAME,
        "index_size": manager.index.ntotal if manager.index else 0
    }


# Health-specific query categorization
HEALTH_QUERY_CATEGORIES = {
    "chw_performance": [
        "chw performance", "supervision score", "chw evaluation", "worker assessment"
    ],
    "family_planning": [
        "family planning", "fp", "contraception", "birth control", "reproductive health"
    ],
    "child_health": [
        "child health", "under 2", "u2", "immunization", "vaccination", "pediatric"
    ],
    "geographic": [
        "county", "region", "area", "geographic", "location", "district"
    ],
    "trends": [
        "trend", "over time", "monthly", "yearly", "change", "progress"
    ],
    "resources": [
        "tools", "equipment", "supplies", "resources", "availability"
    ]
}


def categorize_query(query: str) -> List[str]:
    """Categorize health-related query"""
    query_lower = query.lower()
    categories = []
    
    for category, keywords in HEALTH_QUERY_CATEGORIES.items():
        if any(keyword in query_lower for keyword in keywords):
            categories.append(category)
    
    return categories if categories else ["general"]


def get_category_suggestions(category: str) -> List[str]:
    """Get query suggestions for a specific category"""
    manager = get_embedding_manager()
    
    category_queries = []
    for q_data in manager.queries_data:
        query_categories = categorize_query(q_data["query"])
        if category in query_categories:
            category_queries.append(q_data)
    
    # Sort by popularity
    category_queries.sort(key=lambda x: x["count"], reverse=True)
    
    return [q["query"] for q in category_queries[:5]]


# Streamlit integration functions
def render_query_suggestions_sidebar():
    """Render query suggestions in Streamlit sidebar"""
    with st.sidebar:
        st.subheader("🔍 Query Assistant")
        
        # Popular queries
        popular = get_popular_queries(5)
        if popular:
            st.write("**Popular Questions:**")
            for q_data in popular:
                if st.button(f"📊 {q_data['query'][:50]}...", key=f"pop_{q_data['query'][:20]}"):
                    st.session_state.suggested_query = q_data['query']
        
        # Recent queries
        recent = get_recent_queries(3)
        if recent:
            st.write("**Recent Questions:**")
            for q_data in recent:
                if st.button(f"🕒 {q_data['query'][:50]}...", key=f"rec_{q_data['query'][:20]}"):
                    st.session_state.suggested_query = q_data['query']
        
        # Stats
        stats = get_embedding_stats()
        st.write("**Query Statistics:**")
        st.write(f"Total queries: {stats['total_queries']}")
        st.write(f"User queries: {stats['user_queries']}")


def initialize_embeddings():
    """Initialize embeddings system - call this at app startup"""
    try:
        manager = get_embedding_manager()
        stats = get_embedding_stats()
        logger.info(f"Embeddings initialized: {stats}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        return False

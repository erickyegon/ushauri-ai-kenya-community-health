"""
Core Tools and Utilities for Kenya Health Data Analysis
Database connections, embeddings, memory management, queries, and reporting
"""

from .db import connect_db, execute_sql_query, test_connection
# Temporarily disabled due to environment conflict
# from .embeddings import search_similar_questions, add_user_query, initialize_embeddings

# Placeholder functions
def search_similar_questions(query, top_k=5):
    return []

def add_user_query(query, response):
    pass

def initialize_embeddings():
    pass
from .memory import load_chat_memory, save_chat_memory, get_memory_statistics
from .queries import execute_predefined_query, run_auto_reports, get_available_queries
from .report_generator import generate_report, generate_pdf_report_from_result

__all__ = [
    'connect_db', 'execute_sql_query', 'test_connection',
    'search_similar_questions', 'add_user_query', 'initialize_embeddings',
    'load_chat_memory', 'save_chat_memory', 'get_memory_statistics',
    'execute_predefined_query', 'run_auto_reports', 'get_available_queries',
    'generate_report', 'generate_pdf_report_from_result'
]

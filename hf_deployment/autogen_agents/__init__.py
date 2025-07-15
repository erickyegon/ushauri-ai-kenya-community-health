"""
AutoGen Multi-Agent System for Kenya Health Data Analysis
Contains specialized agents for SQL generation, analysis, and visualization
"""

from .group_chat import run_group_chat, run_simple_query

__all__ = ['run_group_chat', 'run_simple_query']

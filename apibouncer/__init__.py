"""
APIBouncer - Protect yourself from costly API mistakes.

Block unapproved models, enforce cost limits, and track your savings.
"""

__version__ = "0.1.0"

from .sessions import get_session_manager, SessionManager, get_data_dir
from .proxy import openai, minimax, fal, OpenAI, MiniMax, Fal, Query, query

__all__ = [
    # Session Management
    "get_session_manager",
    "SessionManager",
    "get_data_dir",
    # Providers
    "openai",
    "minimax",
    "fal",
    "OpenAI",
    "MiniMax",
    "Fal",
    # Query API (read-only for AI)
    "Query",
    "query",
]

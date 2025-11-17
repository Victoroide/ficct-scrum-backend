"""
Prompt template library for LLM providers.

Provides model-specific prompt formatting for optimal results.
"""

from .assistant import AssistantPrompts
from .search import SearchPrompts
from .summarization import SummarizationPrompts

__all__ = [
    "SummarizationPrompts",
    "SearchPrompts",
    "AssistantPrompts",
]

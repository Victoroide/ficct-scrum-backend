"""
Prompt template library for LLM providers.

Provides model-specific prompt formatting for optimal results.
"""

from .summarization import SummarizationPrompts
from .search import SearchPrompts
from .assistant import AssistantPrompts

__all__ = [
    'SummarizationPrompts',
    'SearchPrompts',
    'AssistantPrompts',
]

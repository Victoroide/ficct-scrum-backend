"""
Search and RAG prompt templates.

Note: Embeddings still use Azure OpenAI (not affected by this refactor).
These prompts are for query enhancement or result summarization.
"""

from typing import Dict, List


class SearchPrompts:
    """Prompt templates for search-related tasks."""
    
    @staticmethod
    def enhance_query_llama4(
        user_query: str,
        context: str = None
    ) -> List[Dict[str, str]]:
        """
        Query enhancement prompt for Llama 4.
        
        Improves user queries for better semantic search results.
        
        Args:
            user_query: Original user query
            context: Optional project/domain context
        
        Returns:
            Message list for Llama 4
        """
        context_info = f"\nProject Context: {context}" if context else ""
        
        return [
            {
                "role": "system",
                "content": (
                    "You are a search query optimization expert.\n\n"
                    "TASK: Enhance user queries for semantic search.\n\n"
                    "APPROACH:\n"
                    "1. Expand abbreviations and technical terms\n"
                    "2. Add relevant synonyms\n"
                    "3. Include related concepts\n"
                    "4. Keep it concise (max 20 words)\n\n"
                    "EXAMPLE:\n"
                    "Input: 'login bug'\n"
                    "Output: 'authentication login error issue user cannot access credentials failure'\n\n"
                    "OUTPUT: Enhanced query only, no explanation."
                ),
            },
            {
                "role": "user",
                "content": f"Original query: {user_query}{context_info}\n\nEnhanced query:",
            },
        ]
    
    @staticmethod
    def enhance_query_openai(
        user_query: str
    ) -> List[Dict[str, str]]:
        """
        Query enhancement prompt for OpenAI.
        
        Args:
            user_query: Original query
        
        Returns:
            Message list for OpenAI
        """
        return [
            {
                "role": "system",
                "content": (
                    "Enhance this search query by adding synonyms and related terms. "
                    "Keep it under 20 words. Output enhanced query only."
                ),
            },
            {
                "role": "user",
                "content": user_query,
            },
        ]
    
    @staticmethod
    def summarize_search_results_llama4(
        query: str,
        results: List[Dict],
        max_results: int = 5
    ) -> List[Dict[str, str]]:
        """
        Summarize search results prompt for Llama 4.
        
        Args:
            query: Original search query
            results: Search results to summarize
            max_results: Number of results to include
        
        Returns:
            Message list for Llama 4
        """
        # Format results
        results_text = "\n\n".join([
            f"{i+1}. [{r.get('project_key')}] {r.get('title')}\n"
            f"   Type: {r.get('issue_type')} | Status: {r.get('status')}\n"
            f"   Similarity: {r.get('similarity_score', 0):.2f}"
            for i, r in enumerate(results[:max_results])
        ])
        
        return [
            {
                "role": "system",
                "content": (
                    "You are a search results summarizer.\n\n"
                    "TASK: Create a concise summary of search results.\n\n"
                    "OUTPUT FORMAT:\n"
                    "**Search Summary:**\n"
                    "Found [N] relevant issues:\n"
                    "- [Key theme 1] ([issue references])\n"
                    "- [Key theme 2] ([issue references])\n\n"
                    "**Top Matches:**\n"
                    "1. [Issue key]: [Brief description]\n"
                    "2. [Issue key]: [Brief description]\n\n"
                    "STYLE: Concise, highlights patterns and key findings."
                ),
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nResults:\n{results_text}\n\nSummarize:",
            },
        ]
    
    @staticmethod
    def summarize_search_results_openai(
        query: str,
        results_text: str
    ) -> List[Dict[str, str]]:
        """
        Summarize search results prompt for OpenAI.
        
        Args:
            query: Search query
            results_text: Formatted results
        
        Returns:
            Message list for OpenAI
        """
        return [
            {
                "role": "system",
                "content": "Summarize these search results concisely, highlighting key themes and top matches.",
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nResults:\n{results_text}",
            },
        ]
    
    @staticmethod
    def get_prompts_for_provider(provider: str, task: str, **kwargs) -> List[Dict[str, str]]:
        """
        Get appropriate prompts based on provider and task.
        
        Args:
            provider: 'bedrock' or 'azure'
            task: 'enhance_query' or 'summarize_results'
            **kwargs: Task-specific parameters
        
        Returns:
            Message list optimized for provider
        
        Raises:
            ValueError: If task not recognized
        """
        is_llama = provider == "bedrock"
        
        if task == "enhance_query":
            if is_llama:
                return SearchPrompts.enhance_query_llama4(**kwargs)
            else:
                return SearchPrompts.enhance_query_openai(**kwargs)
        
        elif task == "summarize_results":
            if is_llama:
                return SearchPrompts.summarize_search_results_llama4(**kwargs)
            else:
                return SearchPrompts.summarize_search_results_openai(**kwargs)
        
        else:
            raise ValueError(f"Unknown search task: {task}")

"""
Assistant prompt templates for RAG-based Q&A.

Optimized for conversational AI assistant with semantic search context.
"""

from typing import Dict, List


class AssistantPrompts:
    """Prompt templates for AI assistant tasks."""

    @staticmethod
    def answer_question_llama4(
        question: str, context: str, conversation_history: List[Dict[str, str]] = None
    ) -> List[Dict[str, str]]:
        """
        Question answering prompt optimized for Llama 4.

        Args:
            question: User's question
            context: Retrieved context from semantic search
            conversation_history: Previous messages (optional)

        Returns:
            Message list for Llama 4
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful project management assistant for FICCT-SCRUM system.\n\n"
                    "CAPABILITIES:\n"
                    "- Answer questions about project issues, sprints, and workflows\n"
                    "- Provide insights based on provided context\n"
                    "- Cite specific issues when relevant\n\n"
                    "INSTRUCTIONS:\n"
                    "1. Base answers ONLY on the provided context\n"
                    "2. If context doesn't contain the answer, say: 'I don't have enough information to answer that based on current project data.'\n"
                    "3. Be concise and accurate\n"
                    "4. Reference issue IDs when relevant (e.g., 'According to PROJ-123...')\n"
                    "5. Use a professional, friendly tone\n\n"
                    "CONTEXT FORMAT:\n"
                    "The context contains relevant issues from semantic search with:\n"
                    "- Issue key and title\n"
                    "- Issue type and status\n"
                    "- Brief description"
                ),
            },
        ]

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Last 5 messages

        # Add current question with context
        messages.append(
            {
                "role": "user",
                "content": f"Context (relevant issues from database):\n\n{context}\n\n---\n\nQuestion: {question}",
            }
        )

        return messages

    @staticmethod
    def answer_question_openai(
        question: str, context: str, conversation_history: List[Dict[str, str]] = None
    ) -> List[Dict[str, str]]:
        """
        Question answering prompt for OpenAI (simplified).

        Args:
            question: User's question
            context: Retrieved context
            conversation_history: Previous messages (optional)

        Returns:
            Message list for OpenAI
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful project management assistant for FICCT-SCRUM. "
                    "Answer questions based on the provided context about project issues. "
                    "Be concise, accurate, and cite specific issues when relevant. "
                    "If you don't know the answer based on the context, say so."
                ),
            },
        ]

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history[-5:])

        # Add question with context
        messages.append(
            {
                "role": "user",
                "content": f"Context (relevant issues):\n{context}\n\nQuestion: {question}",
            }
        )

        return messages

    @staticmethod
    def suggest_solutions_llama4(
        issue_description: str, similar_issues_context: str
    ) -> List[Dict[str, str]]:
        """
        Solution suggestion prompt optimized for Llama 4.

        Args:
            issue_description: Current issue description
            similar_issues_context: Context from similar resolved issues

        Returns:
            Message list for Llama 4
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert software development consultant.\n\n"
                    "TASK: Suggest solutions based on similar past issues.\n\n"
                    "APPROACH:\n"
                    "1. Analyze the current issue\n"
                    "2. Review similar resolved issues from history\n"
                    "3. Identify patterns and successful approaches\n"
                    "4. Provide 2-3 actionable solution suggestions\n\n"
                    "OUTPUT STRUCTURE:\n"
                    "**Approach 1: [Name]**\n"
                    "- Description: What to do\n"
                    "- Based on: [Reference to similar issue]\n"
                    "- Estimated effort: [Time estimate]\n\n"
                    "**Approach 2: [Name]**\n"
                    "[Same structure]\n\n"
                    "STYLE:\n"
                    "- Specific and actionable\n"
                    "- Reference historical issues\n"
                    "- Professional technical writing"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Current Issue:\n{issue_description}\n\n"
                    f"Similar Resolved Issues:\n{similar_issues_context}\n\n"
                    "Provide 2-3 suggested approaches to solve this issue."
                ),
            },
        ]

    @staticmethod
    def suggest_solutions_openai(
        issue_description: str, similar_issues_context: str
    ) -> List[Dict[str, str]]:
        """
        Solution suggestion prompt for OpenAI.

        Args:
            issue_description: Current issue
            similar_issues_context: Similar issues context

        Returns:
            Message list for OpenAI
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert software development assistant. "
                    "Based on similar past issues and their resolutions, "
                    "suggest actionable approaches to solve the current problem."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Current issue: {issue_description}\n\n"
                    f"Similar resolved issues:\n{similar_issues_context}\n\n"
                    "Provide 2-3 suggested approaches to solve this issue."
                ),
            },
        ]

    @staticmethod
    def get_prompts_for_provider(
        provider: str, task: str, **kwargs
    ) -> List[Dict[str, str]]:
        """
        Get appropriate prompts based on provider and task.

        Args:
            provider: 'bedrock' or 'azure'
            task: 'answer_question' or 'suggest_solutions'
            **kwargs: Task-specific parameters

        Returns:
            Message list optimized for provider

        Raises:
            ValueError: If task not recognized
        """
        is_llama = provider == "bedrock"

        if task == "answer_question":
            if is_llama:
                return AssistantPrompts.answer_question_llama4(**kwargs)
            else:
                return AssistantPrompts.answer_question_openai(**kwargs)

        elif task == "suggest_solutions":
            if is_llama:
                return AssistantPrompts.suggest_solutions_llama4(**kwargs)
            else:
                return AssistantPrompts.suggest_solutions_openai(**kwargs)

        else:
            raise ValueError(f"Unknown assistant task: {task}")

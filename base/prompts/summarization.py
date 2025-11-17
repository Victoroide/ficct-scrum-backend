"""
Summarization prompt templates.

Provides model-optimized prompts for issue, sprint, and project summarization.
"""

from typing import Any, Dict, List


class SummarizationPrompts:
    """Prompt templates for summarization tasks."""

    @staticmethod
    def issue_discussion_llama4(
        issue_title: str,
        discussion_text: str,
        max_words: int = 150,
        language: str = "English",
    ) -> List[Dict[str, str]]:
        """
        Issue discussion summary prompt optimized for Llama 4.

        Args:
            issue_title: Issue title
            discussion_text: Full discussion content
            max_words: Maximum summary length
            language: Output language

        Returns:
            Message list for Llama 4
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert software project manager skilled at summarizing technical discussions.\n\n"
                    "TASK: Summarize issue discussions concisely.\n\n"
                    f"OUTPUT REQUIREMENTS:\n"
                    f"- Maximum {max_words} words\n"
                    "- Focus on: key points, decisions made, action items\n"
                    "- Clear, professional tone\n"
                    f"- Language: {language}\n\n"
                    "FORMAT:\n"
                    "1. Main discussion points\n"
                    "2. Key decisions or agreements\n"
                    "3. Next steps or action items"
                ),
            },
            {
                "role": "user",
                "content": f"Issue: {issue_title}\n\nDiscussion:\n{discussion_text}",
            },
        ]

    @staticmethod
    def issue_discussion_openai(
        issue_title: str, discussion_text: str, max_words: int = 150
    ) -> List[Dict[str, str]]:
        """
        Issue discussion summary prompt for OpenAI (more concise).

        Args:
            issue_title: Issue title
            discussion_text: Full discussion content
            max_words: Maximum summary length

        Returns:
            Message list for OpenAI
        """
        return [
            {
                "role": "system",
                "content": (
                    f"Summarize issue discussions in {max_words} words or less. "
                    "Focus on key points, decisions made, and action items."
                ),
            },
            {
                "role": "user",
                "content": f"Issue: {issue_title}\n\n{discussion_text}",
            },
        ]

    @staticmethod
    def sprint_retrospective_llama4(
        sprint_name: str, sprint_data: Dict[str, Any], language: str = "English"
    ) -> List[Dict[str, str]]:
        """
        Sprint retrospective prompt optimized for Llama 4.

        Args:
            sprint_name: Sprint name
            sprint_data: Sprint metrics and context
            language: Output language

        Returns:
            Message list for Llama 4
        """
        total = sprint_data.get("total_issues", 0)
        completed = sprint_data.get("completed", 0)
        completion_rate = sprint_data.get("completion_rate", 0)

        context = (
            f"Sprint: {sprint_name}\n"
            f"Duration: {sprint_data.get('start_date')} to {sprint_data.get('end_date', 'In Progress')}\n"
            f"Completion: {completed}/{total} issues ({completion_rate}%)\n"
        )

        return [
            {
                "role": "system",
                "content": (
                    "You are an expert Agile coach generating sprint retrospectives.\n\n"
                    "TASK: Create a structured retrospective summary.\n\n"
                    "OUTPUT STRUCTURE:\n"
                    "1. **What Went Well**: Positive achievements and successes\n"
                    "2. **What Could Be Improved**: Areas needing attention\n"
                    "3. **Action Items**: Concrete steps for next sprint\n\n"
                    "STYLE:\n"
                    "- Constructive and balanced tone\n"
                    "- Specific and actionable recommendations\n"
                    f"- Language: {language}\n"
                    "- Use bullet points for clarity"
                ),
            },
            {
                "role": "user",
                "content": f"Sprint Data:\n{context}\n\nGenerate a retrospective summary.",
            },
        ]

    @staticmethod
    def sprint_retrospective_openai(
        sprint_name: str, sprint_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Sprint retrospective prompt for OpenAI (simplified).

        Args:
            sprint_name: Sprint name
            sprint_data: Sprint metrics and context

        Returns:
            Message list for OpenAI
        """
        context = (
            f"Sprint: {sprint_name}\n"
            f"Issues: {sprint_data.get('completed', 0)}/{sprint_data.get('total_issues', 0)} completed\n"
            f"Rate: {sprint_data.get('completion_rate', 0)}%\n"
        )

        return [
            {
                "role": "system",
                "content": (
                    "Generate a sprint retrospective summary with:\n"
                    "1. What went well\n"
                    "2. What could be improved\n"
                    "3. Action items for next sprint"
                ),
            },
            {
                "role": "user",
                "content": context,
            },
        ]

    @staticmethod
    def release_notes_llama4(
        period: str, issues_by_type: Dict[str, List[str]], language: str = "English"
    ) -> List[Dict[str, str]]:
        """
        Release notes prompt optimized for Llama 4.

        Args:
            period: Release period description
            issues_by_type: Issues grouped by type
            language: Output language

        Returns:
            Message list for Llama 4
        """
        # Build context from issues
        context_parts = [f"Release Period: {period}\n"]

        for issue_type, issue_titles in issues_by_type.items():
            context_parts.append(f"\n{issue_type.upper()}S:")
            for title in issue_titles:
                context_parts.append(f"- {title}")

        context = "\n".join(context_parts)

        return [
            {
                "role": "system",
                "content": (
                    "You are a technical writer creating release notes for software products.\n\n"
                    "TASK: Transform completed work items into professional release notes.\n\n"
                    "OUTPUT REQUIREMENTS:\n"
                    "- Group by category (Features, Bug Fixes, Improvements)\n"
                    "- User-friendly language (avoid technical jargon where possible)\n"
                    "- Highlight value to end users\n"
                    f"- Language: {language}\n"
                    "- Professional, marketing-friendly tone\n\n"
                    "FORMAT EXAMPLE:\n"
                    "## Features\n"
                    "- **[Feature name]**: Brief description of user benefit\n\n"
                    "## Bug Fixes\n"
                    "- Fixed issue causing [problem]\n\n"
                    "## Improvements\n"
                    "- Enhanced [feature] for better performance"
                ),
            },
            {
                "role": "user",
                "content": f"Completed Items:\n{context}\n\nGenerate release notes.",
            },
        ]

    @staticmethod
    def release_notes_openai(period: str, context: str) -> List[Dict[str, str]]:
        """
        Release notes prompt for OpenAI.

        Args:
            period: Release period
            context: Formatted issue context

        Returns:
            Message list for OpenAI
        """
        return [
            {
                "role": "system",
                "content": (
                    "Generate professional release notes from these completed items. "
                    "Group by category and describe changes clearly for end users."
                ),
            },
            {
                "role": "user",
                "content": f"Release period: {period}\n\n{context}",
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
            task: 'issue_discussion', 'sprint_retrospective', or 'release_notes'
            **kwargs: Task-specific parameters

        Returns:
            Message list optimized for provider

        Raises:
            ValueError: If task not recognized
        """
        is_llama = provider == "bedrock"

        if task == "issue_discussion":
            if is_llama:
                return SummarizationPrompts.issue_discussion_llama4(**kwargs)
            else:
                return SummarizationPrompts.issue_discussion_openai(**kwargs)

        elif task == "sprint_retrospective":
            if is_llama:
                return SummarizationPrompts.sprint_retrospective_llama4(**kwargs)
            else:
                return SummarizationPrompts.sprint_retrospective_openai(**kwargs)

        elif task == "release_notes":
            if is_llama:
                return SummarizationPrompts.release_notes_llama4(**kwargs)
            else:
                return SummarizationPrompts.release_notes_openai(**kwargs)

        else:
            raise ValueError(f"Unknown summarization task: {task}")

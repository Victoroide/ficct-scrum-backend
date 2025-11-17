"""
Base services module.

Lazy loading for AI services (Pinecone, OpenAI) to prevent import errors on Windows.
The readline module is required by Pinecone but doesn't exist on Windows.
"""

from .email_service import EmailService


def get_azure_openai_service():
    """
    Get Azure OpenAI service instance (lazy loaded).

    Imports OpenAI service only when called to avoid Windows readline import error.
    """
    from .openai_service import get_azure_openai_service as _get_service

    return _get_service()


def get_pinecone_service():
    """
    Get Pinecone service instance (lazy loaded).

    Imports Pinecone service only when called to avoid Windows readline import error.
    """
    from .pinecone_service import get_pinecone_service as _get_service

    return _get_service()


__all__ = [
    "EmailService",
    "get_azure_openai_service",
    "get_pinecone_service",
]

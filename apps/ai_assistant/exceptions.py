"""
Custom exceptions for AI Assistant features.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class ServiceUnavailable(APIException):
    """
    Exception for AI services that are unavailable.
    
    This is raised when services like Pinecone or OpenAI cannot be initialized,
    typically due to missing API keys or platform incompatibility (e.g., Windows).
    
    Returns HTTP 503 Service Unavailable status code.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI service temporarily unavailable."
    default_code = "service_unavailable"

"""
Custom pagination classes for DRF.
"""

from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination that allows client to control page size.

    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of results per page (default: 20, max: 100)

    Examples:
    - /api/endpoint/?page=1&page_size=5
    - /api/endpoint/?page=2&page_size=10
    """

    page_size = 20  # Default page size
    page_size_query_param = (
        "page_size"  # Allow client to set page size with ?page_size=N
    )
    max_page_size = 100  # Maximum allowed page size
    page_query_param = "page"  # Page number parameter

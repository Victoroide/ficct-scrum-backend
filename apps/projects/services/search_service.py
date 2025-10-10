from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q


class SearchService:
    @staticmethod
    def search_issues(queryset, search_term):
        if not search_term:
            return queryset

        search_vector = SearchVector("title", weight="A") + SearchVector(
            "description", weight="B"
        )
        search_query = SearchQuery(search_term)

        return (
            queryset.annotate(
                search=search_vector, rank=SearchRank(search_vector, search_query)
            )
            .filter(search=search_query)
            .order_by("-rank")
        )

    @staticmethod
    def filter_issues_advanced(queryset, filters):
        if filters.get("has_attachments"):
            queryset = queryset.filter(attachments__isnull=False).distinct()

        if filters.get("has_comments"):
            queryset = queryset.filter(comments__isnull=False).distinct()

        if filters.get("has_links"):
            queryset = queryset.filter(
                Q(source_links__isnull=False) | Q(target_links__isnull=False)
            ).distinct()

        if filters.get("created_after"):
            queryset = queryset.filter(created_at__gte=filters["created_after"])

        if filters.get("created_before"):
            queryset = queryset.filter(created_at__lte=filters["created_before"])

        if filters.get("updated_after"):
            queryset = queryset.filter(updated_at__gte=filters["updated_after"])

        if filters.get("updated_before"):
            queryset = queryset.filter(updated_at__lte=filters["updated_before"])

        if filters.get("resolved_after"):
            queryset = queryset.filter(resolved_at__gte=filters["resolved_after"])

        if filters.get("resolved_before"):
            queryset = queryset.filter(resolved_at__lte=filters["resolved_before"])

        if filters.get("assignee__in"):
            assignee_ids = filters["assignee__in"].split(",")
            queryset = queryset.filter(assignee_id__in=assignee_ids)

        if filters.get("status__in"):
            status_ids = filters["status__in"].split(",")
            queryset = queryset.filter(status_id__in=status_ids)

        if filters.get("priority__in"):
            priorities = filters["priority__in"].split(",")
            queryset = queryset.filter(priority__in=priorities)

        return queryset

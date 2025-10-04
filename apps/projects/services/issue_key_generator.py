from django.db import transaction
from django.db.models import Max

from apps.projects.models import Issue


class IssueKeyGenerator:
    @staticmethod
    @transaction.atomic
    def generate_key(project):
        last_issue = (
            Issue.objects.filter(project=project)
            .select_for_update()
            .aggregate(max_key=Max('key'))
        )

        max_key = last_issue.get('max_key')
        if max_key:
            try:
                next_number = int(max_key) + 1
            except (ValueError, TypeError):
                next_number = 1
        else:
            next_number = 1

        return str(next_number)

    @classmethod
    def generate_full_key(cls, project):
        key = cls.generate_key(project)
        return f"{project.key}-{key}"

import factory
from factory.django import DjangoModelFactory

from apps.reporting.models import ActivityLog, DiagramCache, ReportSnapshot, SavedFilter


class SavedFilterFactory(DjangoModelFactory):
    class Meta:
        model = SavedFilter

    name = factory.Sequence(lambda n: f"Filter {n}")
    description = factory.Faker("text")
    user = factory.SubFactory("apps.authentication.tests.factories.UserFactory")
    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    filter_criteria = factory.LazyFunction(lambda: {"status": "open", "priority": "P1"})
    is_public = False
    shared_with_team = False
    use_count = 0


class ActivityLogFactory(DjangoModelFactory):
    class Meta:
        model = ActivityLog

    user = factory.SubFactory("apps.authentication.tests.factories.UserFactory")
    action_type = "created"
    object_repr = factory.Faker("sentence")
    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    changes = factory.LazyFunction(
        lambda: {"field": {"old": "value1", "new": "value2"}}
    )


class DiagramCacheFactory(DjangoModelFactory):
    class Meta:
        model = DiagramCache

    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    diagram_type = "workflow"
    diagram_data = factory.Faker("text")
    format = "svg"
    cache_key = factory.Sequence(lambda n: f"cache_key_{n}")
    expires_at = factory.Faker("future_datetime")


class ReportSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = ReportSnapshot

    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    report_type = "velocity"
    report_data = factory.LazyFunction(
        lambda: {"labels": [], "velocities": [], "average_velocity": 0}
    )
    generated_by = factory.SubFactory("apps.authentication.tests.factories.UserFactory")
    parameters = factory.LazyFunction(lambda: {})

"""Generate project with REAL correlations for ML training."""
import random
from datetime import datetime, timedelta

from apps.projects.models import Project, Issue, WorkflowStatus, IssueType, Sprint
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace
from apps.authentication.models import User

# Get or create test user
user = User.objects.filter(email="admin@test.com").first()
if not user:
    user = User.objects.create_user(
        email="admin@test.com", username="admin", password="admin123"
    )

# Get or create org/workspace
org = Organization.objects.first()
if not org:
    org = Organization.objects.create(name="Test Org", slug="test-org")

workspace = Workspace.objects.filter(organization=org).first()
if not workspace:
    workspace = Workspace.objects.create(
        name="Test Workspace", organization=org, created_by=user
    )

# Create project
project = Project.objects.create(
    name="ML Training Project", key="MLTEST", workspace=workspace, created_by=user
)

# Create statuses
todo = WorkflowStatus.objects.create(
    name="To Do", project=project, category="to_do", order=1
)
done = WorkflowStatus.objects.create(
    name="Done", project=project, category="done", is_final=True, order=3
)

# Create issue types
bug_type = IssueType.objects.create(name="Bug", project=project)
story_type = IssueType.objects.create(name="Story", project=project)
task_type = IssueType.objects.create(name="Task", project=project)
epic_type = IssueType.objects.create(name="Epic", project=project)

# Create sprint
sprint = Sprint.objects.create(
    name="Sprint 1",
    project=project,
    start_date=datetime.now().date(),
    end_date=(datetime.now() + timedelta(days=14)).date(),
    status="completed",
)

print(f"Created project: {project.name} ({project.key})")
print(f"Project ID: {project.id}")

# Generate 200 issues with REAL correlations
issues_data = []

for i in range(200):
    # Randomly assign story points (fibonacci)
    story_points = random.choice([1, 2, 3, 5, 8, 13])

    # Randomly assign type with realistic distribution
    type_choice = random.choices(
        [bug_type, story_type, task_type, epic_type],
        weights=[40, 35, 20, 5],  # More bugs and stories
    )[0]

    # Calculate REALISTIC effort based on story points and type
    base_effort = story_points * 3.5  # 3.5 hours per story point

    # Type factor (bugs faster, epics slower)
    if type_choice == bug_type:
        type_factor = 0.7  # Bugs are quicker
    elif type_choice == story_type:
        type_factor = 1.0  # Stories baseline
    elif type_choice == epic_type:
        type_factor = 2.5  # Epics much longer
    else:  # task
        type_factor = 0.9  # Tasks slightly faster

    # Add realistic variance (±20%)
    variance = random.uniform(0.8, 1.2)

    # REAL CORRELATION: effort = story_points * base * type_factor * variance
    actual_hours = round(base_effort * type_factor * variance, 1)

    # Generate title with length correlated to effort
    words_count = max(3, int(actual_hours / 4) + random.randint(-2, 2))
    title_words = [
        "Fix",
        "Implement",
        "Add",
        "Update",
        "Create",
        "Refactor",
        "bug",
        "feature",
        "authentication",
        "database",
        "API",
        "user",
        "interface",
        "system",
        "component",
        "module",
    ]
    title = " ".join(random.choices(title_words, k=words_count))

    # Description length also correlated
    desc_sentences = max(1, int(actual_hours / 8))
    description = " ".join(["This is a description sentence."] * desc_sentences)

    issues_data.append(
        {
            "title": title,
            "description": description,
            "story_points": story_points,
            "type": type_choice,
            "actual_hours": actual_hours,
        }
    )

# Create issues
for idx, data in enumerate(issues_data, 1):
    Issue.objects.create(
        project=project,
        title=data["title"],
        description=data["description"],
        issue_type=data["type"],
        status=done,
        story_points=data["story_points"],
        actual_hours=data["actual_hours"],
        sprint=sprint,
        reporter=user,
        key=f"{project.key}-{idx}",
    )

print(f"Created {len(issues_data)} issues with REAL correlations")
print("\nCorrelation design:")
print("  story_points -> actual_hours: STRONG (0.8+)")
print("  issue_type -> actual_hours: MODERATE (0.3-0.5)")
print("  title_length -> actual_hours: WEAK (0.2-0.3)")
print("\nExpected model R²: 0.7 - 0.9")
print("\nTrain with:")
print(f"  python manage.py train_ml_model effort_prediction --project={project.id}")

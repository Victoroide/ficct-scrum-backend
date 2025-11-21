"""
Management command to generate comprehensive production-quality test data.

Usage:
    python manage.py generate_comprehensive_test_data
    python manage.py generate_comprehensive_test_data --projects=15
"""

import csv
import io
import random
from datetime import date, datetime, timedelta
from decimal import Decimal

import boto3
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from .generate_test_data_helpers import (
    PROJECT_TEMPLATES,
    ISSUE_TYPE_TEMPLATES,
    WORKFLOW_STATUS_TEMPLATES,
    STORY_TEMPLATES,
    TASK_TEMPLATES,
    BUG_TEMPLATES,
    EPIC_TEMPLATES,
    ACTIONS,
    BENEFITS,
    FEATURES,
    AREAS,
    COMPONENTS,
    PROBLEMS,
    COMMENT_TEMPLATES,
)

# Import models
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import (
    Board,
    BoardColumn,
    Issue,
    IssueComment,
    IssueLink,
    IssueType,
    Project,
    ProjectConfiguration,
    ProjectTeamMember,
    Sprint,
    WorkflowStatus,
    WorkflowTransition,
)
from apps.workspaces.models import Workspace, WorkspaceMember

User = get_user_model()


class Command(BaseCommand):
    help = "Generate comprehensive test data"

    def __init__(self):
        super().__init__()
        self.owner = None
        self.team_members = []
        self.main_organization = None
        self.main_workspace = None
        self.projects = []
        self.all_issues = []
        self.all_sprints = []
        self.stats = {
            "users": 0,
            "organizations": 0,
            "workspaces": 0,
            "projects": 0,
            "sprints": 0,
            "issues": 0,
            "comments": 0,
            "attachments": 0,
            "links": 0,
        }

    def add_arguments(self, parser):
        parser.add_argument("--projects", type=int, default=15)
        parser.add_argument("--issues-per-project", type=int, default=50)
        parser.add_argument("--skip-pinecone", action="store_true")
        parser.add_argument("--skip-s3", action="store_true")
        parser.add_argument("--skip-csv", action="store_true")

    def handle(self, *args, **options):
        """Main execution method."""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("FICCT-SCRUM DATA GENERATION"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        try:
            with transaction.atomic():
                self.create_users()
                self.create_organization_and_workspace()
                self.create_projects(options["projects"])
                self.create_sprints()
                self.create_issues(options["issues_per_project"])
                self.create_relationships_and_details()

            if not options["skip_csv"]:
                csv_files = self.export_to_csv()
                if not options["skip_s3"]:
                    self.upload_to_s3(csv_files)

            if not options["skip_pinecone"]:
                self.sync_to_pinecone()

            self.print_summary()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Failed: {str(e)}"))
            raise

    def create_users(self):
        """Create user accounts."""
        self.stdout.write("\nCreating users...")

        self.owner, created = User.objects.get_or_create(
            email="owner@ficct.com",
            defaults={
                "username": "owner",
                "first_name": "Organization",
                "last_name": "Owner",
                "is_active": True,
                "is_verified": True,
            },
        )
        if created:
            self.owner.set_password("Pass123")
            self.owner.save()
        self.stats["users"] += 1

        team_data = [
            ("cvictorhugo39@gmail.com", "victoroide", "Victor", "Cuellar"),
            ("sebamendex11@gmail.com", "sebamendex", "Sebastian", "Mendez"),
            ("l0nkdev04@gmail.com", "l0nkdev", "Lonk", "Dev"),
            ("jezabeltamara@gmail.com", "jezabel", "Jezabel", "Tamara"),
            ("rojas.wilder@ficct.uagrm.edu.bo", "wilderrojas", "Wilder", "Rojas"),
        ]

        for email, username, first_name, last_name in team_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password("Pass123")
                user.save()
            self.team_members.append(user)
            self.stats["users"] += 1

        self.stdout.write(self.style.SUCCESS(f"✓ Created {self.stats['users']} users"))

    def create_organization_and_workspace(self):
        """Create organization and workspace."""
        self.stdout.write("\nSetting up organization...")

        self.main_organization, _ = Organization.objects.get_or_create(
            slug="ficct-scrum",
            defaults={
                "name": "FICCT Scrum Organization",
                "description": "Main organization",
                "organization_type": "startup",
                "subscription_plan": "professional",
                "owner": self.owner,
            },
        )
        self.stats["organizations"] += 1

        OrganizationMembership.objects.get_or_create(
            organization=self.main_organization,
            user=self.owner,
            defaults={"role": "owner", "is_active": True},
        )

        for user in self.team_members:
            OrganizationMembership.objects.get_or_create(
                organization=self.main_organization,
                user=user,
                defaults={"role": "member", "is_active": True},
            )

        self.main_workspace, _ = Workspace.objects.get_or_create(
            slug="main-workspace",
            organization=self.main_organization,
            defaults={
                "name": "Main Workspace",
                "description": "Primary workspace",
                "workspace_type": "development",
                "visibility": "private",
                "created_by": self.owner,
            },
        )
        self.stats["workspaces"] += 1

        WorkspaceMember.objects.get_or_create(
            workspace=self.main_workspace,
            user=self.owner,
            defaults={"role": "admin", "is_active": True},
        )

        for user in self.team_members:
            WorkspaceMember.objects.get_or_create(
                workspace=self.main_workspace,
                user=user,
                defaults={"role": "member", "is_active": True},
            )

        self.stdout.write(self.style.SUCCESS("✓ Organization setup complete"))

    def create_projects(self, num_projects):
        """Generate projects."""
        self.stdout.write(f"\nCreating {num_projects} projects...")

        selected_templates = PROJECT_TEMPLATES[:num_projects]

        for template in selected_templates:
            project = Project.objects.create(
                workspace=self.main_workspace,
                name=template["name"],
                key=template["key"],
                description=template["description"],
                methodology=template["methodology"],
                status=template["status"],
                priority=template["priority"],
                lead=self.owner,
                start_date=date.today() - timedelta(days=random.randint(30, 180)),
                created_by=self.owner,
            )

            # Add project team members
            ProjectTeamMember.objects.create(
                project=project, user=self.owner, role="admin", is_active=True
            )

            roles = ["admin", "developer", "developer", "viewer"]
            for user in self.team_members:
                ProjectTeamMember.objects.create(
                    project=project,
                    user=user,
                    role=random.choice(roles),
                    is_active=True,  # noqa: E501
                )

            # Create issue types
            for it_data in ISSUE_TYPE_TEMPLATES:
                IssueType.objects.create(project=project, is_default=True, **it_data)

            # Create workflow statuses
            created_statuses = []
            for ws_data in WORKFLOW_STATUS_TEMPLATES:
                status = WorkflowStatus.objects.create(project=project, **ws_data)
                created_statuses.append(status)

            # Create workflow transitions
            for from_status in created_statuses:
                for to_status in created_statuses:
                    if from_status != to_status:
                        WorkflowTransition.objects.create(
                            project=project,
                            name=f"{from_status.name} to {to_status.name}",
                            from_status=from_status,
                            to_status=to_status,
                        )

            # Create project configuration
            ProjectConfiguration.objects.create(
                project=project,
                sprint_duration=14,
                estimation_type="story_points",
                story_point_scale=[1, 2, 3, 5, 8, 13, 21],
                enable_time_tracking=True,
                email_notifications=True,
            )

            # Create default board
            board = Board.objects.create(
                project=project,
                name="Main Board",
                board_type="kanban",
                created_by=self.owner,
            )

            # Create board columns
            for idx, status in enumerate(created_statuses):
                BoardColumn.objects.create(
                    board=board,
                    name=status.name,
                    workflow_status=status,
                    order=idx,
                )

            self.projects.append(project)
            self.stats["projects"] += 1

        self.stdout.write(
            self.style.SUCCESS(f"✓ Created {self.stats['projects']} projects")
        )  # noqa: E501

    def create_sprints(self):
        """Generate sprints."""
        self.stdout.write("\nCreating sprints...")

        for project in self.projects:
            if project.methodology != "scrum":
                continue

            # Determine number of sprints
            if project.status == "completed":
                num_sprints = random.randint(6, 8)
            elif project.status == "active":
                num_sprints = random.randint(3, 6)
            else:
                num_sprints = random.randint(1, 3)

            current_date = project.start_date

            for i in range(1, num_sprints + 1):
                start_date = current_date
                end_date = start_date + timedelta(days=14)

                # Determine sprint status
                if end_date < date.today():
                    status = "completed"
                    completed_at = timezone.make_aware(
                        datetime.combine(end_date, datetime.min.time())
                    )
                elif start_date <= date.today() <= end_date:
                    status = "active"
                    completed_at = None
                else:
                    status = "planning"
                    completed_at = None

                sprint = Sprint.objects.create(
                    project=project,
                    name=f"Sprint {i}",
                    goal=f"Sprint {i} development goals",
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                    committed_points=Decimal(random.randint(20, 50)),
                    completed_points=Decimal(random.randint(15, 45))
                    if status == "completed"
                    else Decimal(0),  # noqa: E501
                    created_by=self.owner,
                    completed_at=completed_at,
                )

                self.all_sprints.append(sprint)
                self.stats["sprints"] += 1
                current_date = end_date + timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(f"✓ Created {self.stats['sprints']} sprints")
        )  # noqa: E501

    def create_issues(self, avg_issues):
        """Generate issues."""
        self.stdout.write(f"\nCreating issues (avg {avg_issues} per project)...")

        for project in self.projects:
            # Vary issue count by project size
            if project.status == "completed":
                num_issues = random.randint(80, 100)
            elif project.status == "active":
                num_issues = random.randint(40, 70)
            else:
                num_issues = random.randint(10, 30)

            issue_types = list(project.issue_types.all())
            statuses = list(project.workflow_statuses.all())
            project_sprints = [s for s in self.all_sprints if s.project == project]
            all_users = [self.owner] + self.team_members

            issue_counter = 1

            for _ in range(num_issues):
                # Select issue type with distribution
                type_choice = random.random()
                if type_choice < 0.50:  # 50% stories
                    issue_type = next(
                        (it for it in issue_types if it.category == "story"),
                        issue_types[0],
                    )  # noqa: E501
                    title = random.choice(STORY_TEMPLATES).format(
                        action=random.choice(ACTIONS),
                        benefit=random.choice(BENEFITS),
                        feature=random.choice(FEATURES),
                        area=random.choice(AREAS),
                    )
                elif type_choice < 0.75:  # 25% tasks
                    issue_type = next(
                        (it for it in issue_types if it.category == "task"),
                        issue_types[0],
                    )  # noqa: E501
                    title = random.choice(TASK_TEMPLATES).format(
                        component=random.choice(COMPONENTS),
                        technical_item=random.choice(FEATURES),
                        service=random.choice(FEATURES),
                        database_item=random.choice(AREAS),
                        performance_item=random.choice(COMPONENTS),
                    )
                elif type_choice < 0.90:  # 15% bugs
                    issue_type = next(
                        (it for it in issue_types if it.category == "bug"),
                        issue_types[0],
                    )  # noqa: E501
                    title = random.choice(BUG_TEMPLATES).format(
                        problem=random.choice(PROBLEMS),
                        area=random.choice(AREAS),
                        Problem=random.choice(PROBLEMS).capitalize(),
                        condition=random.choice(ACTIONS),
                        Area=random.choice(AREAS).capitalize(),
                        component=random.choice(COMPONENTS),
                        error_type=random.choice(PROBLEMS),
                        issue_type=random.choice(PROBLEMS),
                    )
                else:  # 10% epics/improvements
                    if random.random() < 0.5:
                        issue_type = next(
                            (it for it in issue_types if it.category == "epic"),
                            issue_types[0],
                        )  # noqa: E501
                        title = random.choice(EPIC_TEMPLATES).format(
                            feature=random.choice(FEATURES).capitalize()
                        )  # noqa: E501
                    else:
                        issue_type = next(
                            (it for it in issue_types if it.category == "improvement"),
                            issue_types[0],
                        )  # noqa: E501
                        title = f"Improve {random.choice(FEATURES)} {random.choice(['performance', 'usability', 'design'])}"  # noqa: E501

                # Select status
                if project.status == "completed":
                    status = next((s for s in statuses if s.is_final), statuses[-1])
                elif project.status == "active":
                    status = random.choice(statuses)
                else:
                    status = next((s for s in statuses if s.is_initial), statuses[0])

                # Assign to sprint
                sprint = None
                if project_sprints and random.random() < 0.7:
                    sprint = random.choice(project_sprints)

                # Create issue
                created_at = timezone.now() - timedelta(days=random.randint(1, 120))

                issue = Issue.objects.create(
                    project=project,
                    issue_type=issue_type,
                    status=status,
                    sprint=sprint,
                    key=str(issue_counter),
                    title=title[:500],  # Ensure within limit
                    description=f"Detailed description for {title[:100]}...",
                    priority=random.choice(["P1", "P2", "P3", "P4"]),
                    assignee=random.choice(all_users)
                    if random.random() < 0.8
                    else None,  # noqa: E501
                    reporter=random.choice(all_users),
                    story_points=random.choice([1, 2, 3, 5, 8, 13])
                    if issue_type.category in ["story", "task"]
                    else None,  # noqa: E501
                    estimated_hours=Decimal(random.randint(1, 40))
                    if issue_type.category == "task"
                    else None,  # noqa: E501
                    actual_hours=Decimal(random.randint(1, 35))
                    if status.is_final
                    else None,  # noqa: E501
                    order=issue_counter,
                    created_at=created_at,
                    resolved_at=created_at + timedelta(days=random.randint(1, 14))
                    if status.is_final
                    else None,  # noqa: E501
                )

                self.all_issues.append(issue)
                self.stats["issues"] += 1
                issue_counter += 1

        self.stdout.write(
            self.style.SUCCESS(f"✓ Created {self.stats['issues']} issues")
        )  # noqa: E501

    def create_relationships_and_details(self):
        """Create comments, links, attachments."""
        self.stdout.write("\nCreating relationships...")

        all_users = [self.owner] + self.team_members

        # Create comments (2-5 per active issue)
        for issue in self.all_issues:
            if random.random() < 0.6:  # 60% of issues get comments
                num_comments = random.randint(1, 5)
                for _ in range(num_comments):
                    comment_date = issue.created_at + timedelta(
                        days=random.randint(0, 10)
                    )  # noqa: E501
                    IssueComment.objects.create(
                        issue=issue,
                        author=random.choice(all_users),
                        content=random.choice(COMMENT_TEMPLATES).format(
                            dependency=f"{issue.project.key}-{random.randint(1, 100)}"
                        ),
                        created_at=comment_date,
                    )
                    self.stats["comments"] += 1

        # Create issue links (10% of issues)
        link_types = ["blocks", "is_blocked_by", "relates_to", "duplicates"]
        potential_links = random.sample(self.all_issues, min(len(self.all_issues), 100))

        for source_issue in potential_links:
            if random.random() < 0.3:
                # Find a target in the same project
                project_issues = [
                    i
                    for i in self.all_issues
                    if i.project == source_issue.project and i != source_issue
                ]  # noqa: E501
                if project_issues:
                    target_issue = random.choice(project_issues)
                    IssueLink.objects.create(
                        source_issue=source_issue,
                        target_issue=target_issue,
                        link_type=random.choice(link_types),
                    )
                    self.stats["links"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Created {self.stats['comments']} comments and {self.stats['links']} links"  # noqa: E501
            )
        )

    def export_to_csv(self):
        """Export data to CSV files."""
        self.stdout.write("\nExporting to CSV...")

        csv_files = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export organizations
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "name",
                "slug",
                "owner_email",
                "organization_type",
                "subscription_plan",
                "created_at",
            ]
        )  # noqa: E501
        for org in Organization.objects.all():
            writer.writerow(
                [
                    str(org.id),
                    org.name,
                    org.slug,
                    org.owner.email,
                    org.organization_type,
                    org.subscription_plan,
                    org.created_at,
                ]
            )  # noqa: E501
        csv_files["organizations.csv"] = output.getvalue()
        output.close()

        # Export workspaces
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "name",
                "slug",
                "organization_id",
                "workspace_type",
                "visibility",
                "created_at",
            ]
        )  # noqa: E501
        for ws in Workspace.objects.all():
            writer.writerow(
                [
                    str(ws.id),
                    ws.name,
                    ws.slug,
                    str(ws.organization_id),
                    ws.workspace_type,
                    ws.visibility,
                    ws.created_at,
                ]
            )  # noqa: E501
        csv_files["workspaces.csv"] = output.getvalue()
        output.close()

        # Export users
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "email",
                "username",
                "first_name",
                "last_name",
                "is_active",
                "is_verified",
                "created_at",
            ]
        )  # noqa: E501
        for user in User.objects.all():
            writer.writerow(
                [
                    str(user.id),
                    user.email,
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.is_active,
                    user.is_verified,
                    user.created_at,
                ]
            )  # noqa: E501
        csv_files["users.csv"] = output.getvalue()
        output.close()

        # Export projects
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "name",
                "key",
                "workspace_id",
                "methodology",
                "status",
                "priority",
                "lead_email",
                "start_date",
                "created_at",
            ]
        )  # noqa: E501
        for project in Project.objects.all():
            writer.writerow(
                [
                    str(project.id),
                    project.name,
                    project.key,
                    str(project.workspace_id),
                    project.methodology,
                    project.status,
                    project.priority,
                    project.lead.email if project.lead else "",
                    project.start_date,
                    project.created_at,
                ]
            )  # noqa: E501
        csv_files["projects.csv"] = output.getvalue()
        output.close()

        # Export sprints
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "project_key",
                "name",
                "status",
                "start_date",
                "end_date",
                "committed_points",
                "completed_points",
                "created_at",
            ]
        )  # noqa: E501
        for sprint in Sprint.objects.all():
            writer.writerow(
                [
                    str(sprint.id),
                    sprint.project.key,
                    sprint.name,
                    sprint.status,
                    sprint.start_date,
                    sprint.end_date,
                    sprint.committed_points,
                    sprint.completed_points,
                    sprint.created_at,
                ]
            )  # noqa: E501
        csv_files["sprints.csv"] = output.getvalue()
        output.close()

        # Export issues
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "project_key",
                "key",
                "title",
                "issue_type",
                "status",
                "priority",
                "assignee_email",
                "reporter_email",
                "story_points",
                "estimated_hours",
                "actual_hours",
                "sprint_name",
                "created_at",
                "resolved_at",
            ]
        )  # noqa: E501
        for issue in Issue.objects.select_related(
            "project", "issue_type", "status", "assignee", "reporter", "sprint"
        ).all():  # noqa: E501
            writer.writerow(
                [
                    str(issue.id),
                    issue.project.key,
                    issue.key,
                    issue.title,
                    issue.issue_type.name,
                    issue.status.name,
                    issue.priority,
                    issue.assignee.email if issue.assignee else "",
                    issue.reporter.email,
                    issue.story_points,
                    issue.estimated_hours,
                    issue.actual_hours,
                    issue.sprint.name if issue.sprint else "",
                    issue.created_at,
                    issue.resolved_at,
                ]
            )  # noqa: E501
        csv_files["issues.csv"] = output.getvalue()
        output.close()

        # Export comments
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "issue_key", "author_email", "content", "created_at"])
        for comment in IssueComment.objects.select_related("issue", "author").all():
            writer.writerow(
                [
                    str(comment.id),
                    f"{comment.issue.project.key}-{comment.issue.key}",
                    comment.author.email,
                    comment.content,
                    comment.created_at,
                ]
            )  # noqa: E501
        csv_files["comments.csv"] = output.getvalue()
        output.close()

        # Export issue links
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["id", "source_issue_key", "target_issue_key", "link_type", "created_at"]
        )  # noqa: E501
        for link in IssueLink.objects.select_related(
            "source_issue", "target_issue"
        ).all():  # noqa: E501
            writer.writerow(
                [
                    str(link.id),
                    f"{link.source_issue.project.key}-{link.source_issue.key}",
                    f"{link.target_issue.project.key}-{link.target_issue.key}",
                    link.link_type,
                    link.created_at,
                ]
            )  # noqa: E501
        csv_files["issue_links.csv"] = output.getvalue()
        output.close()

        # Export metadata
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "generated_at",
                "total_users",
                "total_organizations",
                "total_workspaces",
                "total_projects",
                "total_sprints",
                "total_issues",
                "total_comments",
                "total_links",
            ]
        )  # noqa: E501
        writer.writerow(
            [
                timestamp,
                self.stats["users"],
                self.stats["organizations"],
                self.stats["workspaces"],
                self.stats["projects"],
                self.stats["sprints"],
                self.stats["issues"],
                self.stats["comments"],
                self.stats["links"],
            ]
        )  # noqa: E501
        csv_files["metadata.csv"] = output.getvalue()
        output.close()

        self.stdout.write(self.style.SUCCESS(f"✓ Exported {len(csv_files)} CSV files"))
        return csv_files

    def upload_to_s3(self, csv_files):
        """Upload CSV files to S3."""
        self.stdout.write("\nUploading to S3...")

        if not settings.USE_S3:
            self.stdout.write(self.style.WARNING("  ! S3 is disabled, skipping upload"))
            return

        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            s3_folder = f"datasets/generation_{timestamp}/"

            uploaded_urls = []

            for filename, content in csv_files.items():
                s3_key = s3_folder + filename

                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=content.encode("utf-8"),
                    ContentType="text/csv",
                )

                url = f"s3://{bucket_name}/{s3_key}"
                uploaded_urls.append(url)
                self.stdout.write(f"  ✓ Uploaded {filename}")

            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Uploaded {len(csv_files)} files to S3")
            )  # noqa: E501
            self.stdout.write(f"  S3 Location: s3://{bucket_name}/{s3_folder}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ S3 upload failed: {str(e)}"))

    def sync_to_pinecone(self):
        """Sync vectors to Pinecone."""
        self.stdout.write("\nSyncing to Pinecone...")

        try:
            from django.core.management import call_command

            self.stdout.write("  Syncing projects...")
            call_command(
                "sync_pinecone_vectors", "--namespace=projects", "--batch-size=100"
            )  # noqa: E501

            self.stdout.write("  Syncing issues...")
            call_command(
                "sync_pinecone_vectors", "--namespace=issues", "--batch-size=100"
            )  # noqa: E501

            self.stdout.write("  Syncing sprints...")
            call_command(
                "sync_pinecone_vectors", "--namespace=sprints", "--batch-size=100"
            )  # noqa: E501

            self.stdout.write("  Syncing users...")
            call_command(
                "sync_pinecone_vectors", "--namespace=users", "--batch-size=100"
            )  # noqa: E501

            self.stdout.write(self.style.SUCCESS("✓ Pinecone sync complete"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Pinecone sync failed: {str(e)}"))
            self.stdout.write(
                "  Note: Make sure Pinecone is configured and sync command exists"
            )  # noqa: E501

    def print_summary(self):
        """Print generation summary."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("GENERATION COMPLETE"))
        self.stdout.write("=" * 80)
        for key, value in self.stats.items():
            self.stdout.write(f"{key.capitalize()}: {value}")

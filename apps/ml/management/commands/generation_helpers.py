"""
Helper functions for generate_quality_training_data command.

This module contains the complete implementation of all 7 data generation steps.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.projects.models import (
    Project,
    Sprint,
    Issue,
    IssueType,
    WorkflowStatus,
    WorkflowTransition,
    ProjectTeamMember,
    IssueLink,
)

User = get_user_model()

# Fibonacci sequence for story points
FIBONACCI_POINTS = [1, 2, 3, 5, 8, 13, 21]

# Issue type distribution percentages
ISSUE_TYPE_DISTRIBUTION = {
    "story": 0.40,  # 40% stories
    "task": 0.25,  # 25% tasks
    "bug": 0.20,  # 20% bugs
    "epic": 0.10,  # 10% epics
    "improvement": 0.05,  # 5% improvements
}

# Priority distribution
PRIORITY_DISTRIBUTION = {
    "P1": 0.10,  # 10% critical
    "P2": 0.25,  # 25% high
    "P3": 0.45,  # 45% medium
    "P4": 0.20,  # 20% low
}

# Skill mappings for each role
ROLE_SKILLS = {
    "Senior Backend Engineer": [
        "Python",
        "Django",
        "PostgreSQL",
        "Redis",
        "AWS",
        "API Design",
    ],
    "Frontend Developer": ["React", "TypeScript", "HTML/CSS", "Redux", "Jest"],
    "Full Stack Developer": ["Python", "JavaScript", "Django", "React", "PostgreSQL"],
    "QA Engineer": ["Testing", "Selenium", "Pytest", "Jest", "CI/CD"],
    "DevOps Engineer": ["Docker", "Kubernetes", "AWS", "CI/CD", "Monitoring"],
    "UI/UX Designer": ["Figma", "Design Systems", "User Research", "Prototyping"],
    "Junior Developer": ["Python", "JavaScript", "HTML/CSS", "Git"],
}

# Issue title templates by type and project
ISSUE_TITLE_TEMPLATES = {
    "Admin Dashboard": {
        "story": [
            "User management interface",
            "Role-based access control",
            "Activity log viewer",
            "System configuration panel",
            "Dashboard analytics widget",
        ],
        "task": [
            "Setup admin layout",
            "Implement data table pagination",
            "Add export functionality",
            "Create user search filter",
            "Optimize database queries",
        ],
        "bug": [
            "Admin panel not loading on Firefox",
            "Incorrect permissions displayed",
            "Export CSV formatting issues",
            "Memory leak in dashboard refresh",
            "Broken links in navigation menu",
        ],
    },
    "Mobile Application": {
        "story": [
            "Offline mode support",
            "Push notifications system",
            "Biometric authentication",
            "Dark mode theme",
            "In-app purchases",
        ],
        "task": [
            "Setup React Native project",
            "Implement navigation structure",
            "Add camera integration",
            "Configure app store metadata",
            "Optimize bundle size",
        ],
        "bug": [
            "App crashes on Android 12",
            "Notifications not working on iOS",
            "Slow scroll performance",
            "Memory leak in image gallery",
            "Login timeout on slow networks",
        ],
    },
    "Payment Integration": {
        "story": [
            "Stripe payment gateway integration",
            "PayPal checkout flow",
            "Refund processing system",
            "Payment history dashboard",
            "Automated invoice generation",
        ],
        "task": [
            "Setup payment API endpoints",
            "Implement webhook handlers",
            "Add payment validation",
            "Create payment logs",
            "Setup PCI compliance tests",
        ],
        "bug": [
            "Double charging on retry",
            "Webhook failures not logged",
            "Currency conversion errors",
            "Transaction timeout issues",
            "Failed payments not refunded",
        ],
    },
    "Analytics Platform": {
        "story": [
            "Real-time metrics dashboard",
            "Custom report builder",
            "Data export in multiple formats",
            "Automated email reports",
            "Interactive data visualizations",
        ],
        "task": [
            "Setup data pipeline",
            "Implement chart components",
            "Add data caching layer",
            "Create aggregation jobs",
            "Optimize query performance",
        ],
        "bug": [
            "Dashboard not updating real-time",
            "Incorrect calculation in metrics",
            "Chart rendering slow with large datasets",
            "Memory leak in data polling",
            "Export timeout on large reports",
        ],
    },
    "API Gateway": {
        "story": [
            "Rate limiting system",
            "API versioning support",
            "Authentication middleware",
            "Request/response logging",
            "API documentation portal",
        ],
        "task": [
            "Setup API routing",
            "Implement JWT authentication",
            "Add request validation",
            "Create API monitoring",
            "Setup load balancer",
        ],
        "bug": [
            "Rate limiting not working",
            "Token expiration issues",
            "CORS errors on some endpoints",
            "Memory leak in connection pool",
            "Incorrect error responses",
        ],
    },
}


def generate_team_members_impl(command) -> None:
    """Generate or setup team members for projects."""
    # Role characteristics
    ROLE_CHARACTERISTICS = {
        "Senior Backend Engineer": {
            "velocity_factor": 1.3,
            "estimation_accuracy": 0.85,
        },
        "Frontend Developer": {"velocity_factor": 1.1, "estimation_accuracy": 0.80},
        "Full Stack Developer": {"velocity_factor": 1.0, "estimation_accuracy": 0.75},
        "QA Engineer": {"velocity_factor": 0.9, "estimation_accuracy": 0.90},
        "DevOps Engineer": {"velocity_factor": 1.2, "estimation_accuracy": 0.88},
        "UI/UX Designer": {"velocity_factor": 0.8, "estimation_accuracy": 0.70},
        "Junior Developer": {"velocity_factor": 0.7, "estimation_accuracy": 0.60},
    }

    # Create realistic team member profiles
    team_profiles = [
        {
            "first_name": "Sarah",
            "last_name": "Chen",
            "email": "sarah.chen@ficct.com",
            "role": "Senior Backend Engineer",
        },
        {
            "first_name": "Michael",
            "last_name": "Rodriguez",
            "email": "michael.rodriguez@ficct.com",
            "role": "Frontend Developer",
        },
        {
            "first_name": "Emily",
            "last_name": "Johnson",
            "email": "emily.johnson@ficct.com",
            "role": "Full Stack Developer",
        },
        {
            "first_name": "David",
            "last_name": "Kim",
            "email": "david.kim@ficct.com",
            "role": "QA Engineer",
        },
        {
            "first_name": "Jessica",
            "last_name": "Martinez",
            "email": "jessica.martinez@ficct.com",
            "role": "DevOps Engineer",
        },
        {
            "first_name": "Alex",
            "last_name": "Thompson",
            "email": "alex.thompson@ficct.com",
            "role": "UI/UX Designer",
        },
        {
            "first_name": "Ryan",
            "last_name": "Patel",
            "email": "ryan.patel@ficct.com",
            "role": "Junior Developer",
        },
    ]

    # Create or get team members
    command.team_members = {}
    for profile in team_profiles:
        # Generate username from email (part before @)
        username = profile["email"].split("@")[0]

        user, created = User.objects.get_or_create(
            email=profile["email"],
            defaults={
                "username": username,
                "first_name": profile["first_name"],
                "last_name": profile["last_name"],
                "is_active": True,
                "is_verified": True,
            },
        )
        if created and command.verbose_logging:
            command.stdout.write(f"  Created user: {user.email}")

        role_chars = ROLE_CHARACTERISTICS[profile["role"]]
        command.team_members[profile["role"]] = {
            "user": user,
            "role": profile["role"],
            "skills": ROLE_SKILLS[profile["role"]],
            "velocity_factor": role_chars["velocity_factor"],
            "estimation_accuracy": role_chars["estimation_accuracy"],
        }


def create_projects_impl(command, plan: Dict[str, Any]) -> None:
    """Create projects from archetypes."""
    start_date = plan["timeline_start"].date()

    for archetype in plan["projects"]:
        # Create project
        project = Project.objects.create(
            workspace=command.workspace,
            name=archetype["name"],
            key=archetype["key"],
            description=archetype["description"],
            methodology="scrum",
            status="active",
            priority="high" if archetype["complexity"] == "high" else "medium",
            lead=command.user,
            start_date=start_date,
            end_date=start_date + timedelta(weeks=archetype["duration_weeks"]),
            created_by=command.user,
        )
        command.generated_projects.append(project)

        if command.verbose_logging:
            command.stdout.write(f"  Created project: {project.name} ({project.key})")

        # Get or create issue types for project (may be auto-created by signals)
        issue_types = {}
        for category in ["epic", "story", "task", "bug", "improvement"]:
            issue_type, created = IssueType.objects.get_or_create(
                project=project,
                name=category.capitalize(),
                defaults={
                    "category": category,
                    "icon": f"icon-{category}",
                    "color": "#0052CC",
                    "is_default": True,
                    "is_active": True,
                },
            )
            issue_types[category] = issue_type

        command.issue_types[project.key] = issue_types

        # Get or create workflow statuses (may be auto-created by signals)
        statuses = {}
        status_configs = [
            {"name": "Backlog", "category": "to_do", "is_initial": True, "order": 0},
            {"name": "To Do", "category": "to_do", "order": 1},
            {"name": "In Progress", "category": "in_progress", "order": 2},
            {"name": "In Review", "category": "in_progress", "order": 3},
            {"name": "Done", "category": "done", "is_final": True, "order": 4},
        ]

        for config in status_configs:
            status, created = WorkflowStatus.objects.get_or_create(
                project=project,
                name=config["name"],
                defaults={
                    "category": config["category"],
                    "is_initial": config.get("is_initial", False),
                    "is_final": config.get("is_final", False),
                    "order": config["order"],
                    "is_active": True,
                },
            )
            statuses[config["name"]] = status

        command.workflow_statuses[project.key] = statuses

        # Get or create workflow transitions (may be auto-created by signals)
        transitions = [
            ("Backlog", "To Do"),
            ("To Do", "In Progress"),
            ("In Progress", "In Review"),
            ("In Review", "Done"),
            ("In Review", "In Progress"),  # Send back for changes
            ("To Do", "Backlog"),  # Move back to backlog
        ]

        for from_status_name, to_status_name in transitions:
            WorkflowTransition.objects.get_or_create(
                project=project,
                from_status=statuses[from_status_name],
                to_status=statuses[to_status_name],
                defaults={
                    "name": f"{from_status_name} → {to_status_name}",
                    "is_active": True,
                },
            )

        # Add team members to project
        for role_name, member_data in command.team_members.items():
            # Distribute team members across projects
            # Some members work on all projects, some on specific ones
            if role_name in ["Senior Backend Engineer", "Full Stack Developer"]:
                # These work on all projects
                ProjectTeamMember.objects.create(
                    project=project,
                    user=member_data["user"],
                    role="developer",
                    is_active=True,
                )
            elif (
                archetype["key"] in ["MOBILE", "ADMIN"]
                and role_name == "Frontend Developer"
            ):
                # Frontend dev on UI-heavy projects
                ProjectTeamMember.objects.create(
                    project=project,
                    user=member_data["user"],
                    role="developer",
                    is_active=True,
                )
            elif (
                archetype["key"] in ["PAYMENT", "API"]
                and role_name == "Senior Backend Engineer"
            ):
                # Extra backend support on API projects
                pass  # Already added above
            elif role_name in ["QA Engineer", "DevOps Engineer"]:
                # QA and DevOps on all projects
                role_key = "qa_engineer" if role_name == "QA Engineer" else "developer"
                ProjectTeamMember.objects.create(
                    project=project,
                    user=member_data["user"],
                    role=role_key,
                    is_active=True,
                )


def generate_sprints_impl(command, plan: Dict[str, Any]) -> None:
    """Generate sprints with temporal coherence."""
    for project in command.generated_projects:
        archetype = next(a for a in plan["projects"] if a["key"] == project.key)
        sprint_count = archetype["duration_weeks"] // 2  # 2-week sprints

        current_date = project.start_date

        for i in range(sprint_count):
            sprint_start = current_date
            sprint_end = sprint_start + timedelta(days=13)  # 2-week sprint

            # Determine sprint status based on dates
            now = timezone.now().date()
            if sprint_end < now - timedelta(weeks=2):
                status = "completed"
            elif sprint_start <= now <= sprint_end:
                status = "active"
            else:
                status = "planning"

            sprint = Sprint.objects.create(
                project=project,
                name=f"Sprint {i + 1}",
                goal=f"Deliver key features for {project.name}",
                status=status,
                start_date=sprint_start,
                end_date=sprint_end,
                created_by=command.user,
            )

            # Set completed/committed points for completed sprints
            if status == "completed":
                # Realistic velocity with some variance
                base_velocity = 40
                variance = random.uniform(-0.15, 0.15)
                committed = Decimal(base_velocity * (1 + variance))
                # Completed is usually 80-100% of committed
                completion_rate = random.uniform(0.80, 1.0)
                completed = Decimal(float(committed) * completion_rate)

                sprint.committed_points = committed
                sprint.completed_points = completed
                sprint.completed_at = timezone.make_aware(
                    datetime.combine(sprint_end, datetime.min.time())
                )
                sprint.save()

            command.generated_sprints.append(sprint)
            current_date = sprint_end + timedelta(days=1)


def generate_issues_impl(command, plan: Dict[str, Any]) -> None:
    """Generate issues with realistic distribution and data."""
    issue_counter = {}

    for project in command.generated_projects:
        archetype = next(a for a in plan["projects"] if a["key"] == project.key)
        issue_count = archetype["issue_count"]
        issue_counter[project.key] = 1

        # Get templates for this project
        templates = ISSUE_TITLE_TEMPLATES.get(project.name, {})

        # Distribute issues across types
        type_counts = {}
        for issue_type, percentage in ISSUE_TYPE_DISTRIBUTION.items():
            type_counts[issue_type] = int(issue_count * percentage)

        # Get sprints for this project
        project_sprints = [s for s in command.generated_sprints if s.project == project]
        completed_sprints = [s for s in project_sprints if s.status == "completed"]
        active_sprint = next((s for s in project_sprints if s.status == "active"), None)
        planned_sprints = [s for s in project_sprints if s.status == "planning"]

        # Get team members for this project
        team_members = list(ProjectTeamMember.objects.filter(project=project))

        for issue_type, count in type_counts.items():
            for _ in range(count):
                # Select title template
                type_templates = templates.get(
                    issue_type, [f"Implement {issue_type} feature"]
                )
                title = (
                    random.choice(type_templates)
                    if type_templates
                    else f"Implement {issue_type} for {project.name}"
                )

                # Add uniqueness to title
                title = f"{title} #{issue_counter[project.key]}"

                # Generate description
                description = f"Detailed implementation of {title.lower()}. This involves several technical components and requires careful consideration of architecture, performance, and user experience."

                # Assign story points from Fibonacci
                if issue_type == "epic":
                    story_points = random.choice([13, 21])
                elif issue_type == "story":
                    story_points = random.choice([3, 5, 8])
                elif issue_type == "task":
                    story_points = random.choice([1, 2, 3])
                elif issue_type == "bug":
                    story_points = random.choice([1, 2, 3])
                else:  # improvement
                    story_points = random.choice([2, 3, 5])

                # Estimate hours based on story points with variance
                hours_per_point = 6.0
                estimated_hours = Decimal(
                    story_points * hours_per_point * random.uniform(0.8, 1.2)
                )

                # Assign priority
                priority = random.choices(
                    list(PRIORITY_DISTRIBUTION.keys()),
                    weights=list(PRIORITY_DISTRIBUTION.values()),
                )[0]

                # Determine sprint and status
                # 60% in completed sprints, 20% in active, 20% in backlog/planned
                rand = random.random()
                if rand < 0.60 and completed_sprints:
                    sprint = random.choice(completed_sprints)
                    status_name = "Done"
                elif rand < 0.80 and active_sprint:
                    sprint = active_sprint
                    status_name = random.choice(["In Progress", "In Review", "To Do"])
                else:
                    sprint = (
                        random.choice(planned_sprints)
                        if planned_sprints and random.random() < 0.5
                        else None
                    )
                    status_name = "Backlog"

                status = command.workflow_statuses[project.key][status_name]

                # Assign to team member (95% assigned, 5% unassigned)
                if random.random() < 0.95 and team_members:
                    assignee = random.choice(team_members).user
                else:
                    assignee = None

                # Create issue
                issue = Issue.objects.create(
                    project=project,
                    issue_type=command.issue_types[project.key][issue_type],
                    status=status,
                    sprint=sprint,
                    key=str(issue_counter[project.key]),
                    title=title,
                    description=description,
                    priority=priority,
                    assignee=assignee,
                    reporter=command.user,
                    estimated_hours=estimated_hours,
                    story_points=story_points,
                    is_active=True,
                )

                command.generated_issues.append(issue)
                issue_counter[project.key] += 1


def log_effort_data_impl(command) -> None:
    """Log actual effort for completed issues."""
    completed_issues = [
        issue for issue in command.generated_issues if issue.status.is_final
    ]

    for issue in completed_issues:
        # Get team member data for velocity factor
        if issue.assignee:
            member_data = next(
                (
                    m
                    for m in command.team_members.values()
                    if m["user"] == issue.assignee
                ),
                None,
            )

            if member_data:
                velocity_factor = member_data["velocity_factor"]
                estimation_accuracy = member_data["estimation_accuracy"]
            else:
                velocity_factor = 1.0
                estimation_accuracy = 0.75
        else:
            velocity_factor = 1.0
            estimation_accuracy = 0.75

        # Calculate actual hours with realistic variance
        # Base on story points with velocity factor
        base_hours = float(issue.story_points) * 6.0 if issue.story_points else 4.0

        # Apply velocity factor (faster/slower developers)
        actual_hours = base_hours / velocity_factor

        # Add estimation error (some devs estimate better)
        estimation_error = random.uniform(-0.3, 0.3) * (1 - estimation_accuracy)
        actual_hours = actual_hours * (1 + estimation_error)

        # Add random variance (10% of story points don't correlate perfectly)
        if random.random() < 0.10:
            actual_hours = actual_hours * random.uniform(0.5, 1.5)

        # Ensure minimum 0.5 hours
        actual_hours = max(0.5, actual_hours)

        issue.actual_hours = Decimal(round(actual_hours, 2))
        issue.resolved_at = (
            timezone.make_aware(
                datetime.combine(issue.sprint.end_date, datetime.min.time())
            )
            if issue.sprint
            else timezone.now()
        )
        issue.save()


def create_dependencies_impl(command) -> None:
    """Create logical dependencies between issues."""
    # Create dependencies within each project
    for project in command.generated_projects:
        project_issues = [i for i in command.generated_issues if i.project == project]

        # Group by type
        api_issues = [
            i
            for i in project_issues
            if "API" in i.title or "Backend" in i.title or "endpoint" in i.title.lower()
        ]
        ui_issues = [
            i
            for i in project_issues
            if "UI" in i.title
            or "Frontend" in i.title
            or "interface" in i.title.lower()
        ]

        # Create "blocks" relationships: API blocks UI
        for ui_issue in ui_issues[
            : min(5, len(ui_issues))
        ]:  # Limit to 5 dependencies per project
            if api_issues:
                api_issue = random.choice(api_issues)
                try:
                    IssueLink.objects.create(
                        source_issue=api_issue,
                        target_issue=ui_issue,
                        link_type="blocks",
                        created_by=command.user,
                    )
                except Exception:
                    pass  # Skip if already exists or validation fails


def inject_anomalies_impl(command) -> None:
    """Inject 5 realistic anomalies for ML learning."""
    if len(command.generated_projects) < 5:
        return  # Need at least 5 projects

    # Anomaly 1: Behind-schedule project
    # Reduce velocity on later sprints of one project
    project = command.generated_projects[0]
    project_sprints = [
        s
        for s in command.generated_sprints
        if s.project == project and s.status == "completed"
    ]
    if len(project_sprints) >= 3:
        # Last 2 sprints have much lower velocity
        for sprint in project_sprints[-2:]:
            sprint.completed_points = sprint.committed_points * Decimal(
                "0.5"
            )  # Only 50% completed
            sprint.save()

    # Anomaly 2: Scope creep - add issues mid-sprint
    active_sprints = [s for s in command.generated_sprints if s.status == "active"]
    if active_sprints:
        sprint = active_sprints[0]
        project = sprint.project
        # Add 5 unplanned issues to active sprint
        for i in range(5):
            Issue.objects.create(
                project=project,
                issue_type=command.issue_types[project.key]["task"],
                status=command.workflow_statuses[project.key]["To Do"],
                sprint=sprint,
                key=str(Issue.objects.filter(project=project).count() + 1),
                title=f"Unplanned task added mid-sprint #{i+1}",
                description="This was added after sprint planning due to urgent client request",
                priority="P1",  # High priority
                assignee=None,  # Unassigned
                reporter=command.user,
                estimated_hours=Decimal("4.0"),
                story_points=2,
                is_active=True,
            )

    # Anomaly 3: Bottleneck developer
    # Assign many critical issues to one person
    if "Senior Backend Engineer" in command.team_members:
        specialist = command.team_members["Senior Backend Engineer"]["user"]
        critical_issues = [
            i
            for i in command.generated_issues
            if i.priority == "P1" and not i.status.is_final
        ]
        for issue in critical_issues[: min(10, len(critical_issues))]:
            issue.assignee = specialist
            issue.save()

    # Anomaly 4: Shifting priorities
    # Change priority and re-assign several issues in one project
    if len(command.generated_projects) >= 3:
        project = command.generated_projects[2]
        project_issues = [
            i
            for i in command.generated_issues
            if i.project == project and not i.status.is_final
        ]
        for issue in project_issues[: min(15, len(project_issues))]:
            # Randomly change priority
            issue.priority = random.choice(["P1", "P2", "P3"])
            # Re-assign to different team member
            team_members = list(ProjectTeamMember.objects.filter(project=project))
            if team_members:
                issue.assignee = random.choice(team_members).user
            issue.save()

    # Anomaly 5: Misestimated epic
    # Create epic with very wrong estimates
    if len(command.generated_projects) >= 4:
        project = command.generated_projects[3]
        epic = Issue.objects.create(
            project=project,
            issue_type=command.issue_types[project.key]["epic"],
            status=command.workflow_statuses[project.key]["Done"],
            sprint=[
                s
                for s in command.generated_sprints
                if s.project == project and s.status == "completed"
            ][0]
            if [
                s
                for s in command.generated_sprints
                if s.project == project and s.status == "completed"
            ]
            else None,
            key=str(Issue.objects.filter(project=project).count() + 1),
            title="Grossly underestimated major feature",
            description="This epic was estimated at 13 points but actually took 5x longer",
            priority="P1",
            assignee=command.user,
            reporter=command.user,
            estimated_hours=Decimal("52.0"),  # 13 points * 4 hours
            actual_hours=Decimal("260.0"),  # Actually took 5x longer!
            story_points=13,
            is_active=True,
            resolved_at=timezone.now(),
        )

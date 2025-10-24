"""
Django signals for automatic creation of related objects when projects are created.

This ensures that every new project automatically gets:
- Default IssueTypes (Epic, Story, Task, Bug, Improvement, Sub-task)
- Default WorkflowStatuses (To Do, In Progress, Done)
- Default ProjectConfiguration (with sensible defaults)
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.projects.models import IssueType, Project, ProjectConfiguration, WorkflowStatus


@receiver(post_save, sender=Project)
def create_default_issue_types(sender, instance, created, **kwargs):
    """
    Automatically create default IssueTypes when a new project is created.
    
    This signal fires after a Project is saved. If it's a new project (created=True),
    it creates 6 default issue types that are standard in agile methodologies.
    
    Args:
        sender: The Project model class
        instance: The actual Project instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal parameters
    """
    if not created:
        return  # Only run for new projects, not updates
    
    # Check if issue types already exist (in case of race conditions or manual creation)
    if IssueType.objects.filter(project=instance).exists():
        return
    
    # Default issue types based on Scrum/Agile best practices
    DEFAULT_ISSUE_TYPES = [
        {
            "name": "Epic",
            "category": "epic",
            "description": "A large user story that can be broken down into smaller stories",
            "icon": "epic",
            "color": "#904EE2",
            "is_default": True,
        },
        {
            "name": "Story",
            "category": "story",
            "description": "A user story representing a feature or requirement",
            "icon": "story",
            "color": "#63BA3C",
            "is_default": True,
        },
        {
            "name": "Task",
            "category": "task",
            "description": "A task that needs to be completed",
            "icon": "task",
            "color": "#0052CC",
            "is_default": True,
        },
        {
            "name": "Bug",
            "category": "bug",
            "description": "A problem that needs to be fixed",
            "icon": "bug",
            "color": "#FF5630",
            "is_default": True,
        },
        {
            "name": "Improvement",
            "category": "improvement",
            "description": "An enhancement to existing functionality",
            "icon": "improvement",
            "color": "#00B8D9",
            "is_default": False,
        },
        {
            "name": "Sub-task",
            "category": "sub_task",
            "description": "A subtask of a parent issue",
            "icon": "subtask",
            "color": "#6554C0",
            "is_default": False,
        },
    ]
    
    # Create all default issue types
    issue_types = []
    for issue_type_data in DEFAULT_ISSUE_TYPES:
        issue_type = IssueType(
            project=instance,
            name=issue_type_data["name"],
            category=issue_type_data["category"],
            description=issue_type_data["description"],
            icon=issue_type_data["icon"],
            color=issue_type_data["color"],
            is_default=issue_type_data["is_default"],
            is_active=True,
        )
        issue_types.append(issue_type)
    
    # Bulk create for efficiency
    IssueType.objects.bulk_create(issue_types)
    
    # Log for debugging (optional)
    print(f"✅ Auto-created {len(issue_types)} default IssueTypes for project: {instance.name}")


@receiver(post_save, sender=Project)
def create_default_workflow_statuses(sender, instance, created, **kwargs):
    """
    Automatically create default WorkflowStatuses when a new project is created.
    
    This signal fires after a Project is saved. If it's a new project (created=True),
    it creates 3 default workflow statuses that represent the basic workflow.
    
    Args:
        sender: The Project model class
        instance: The actual Project instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal parameters
    """
    if not created:
        return  # Only run for new projects, not updates
    
    # Check if workflow statuses already exist (in case of race conditions or manual creation)
    if WorkflowStatus.objects.filter(project=instance).exists():
        return
    
    # Default workflow statuses based on Scrum/Agile best practices
    DEFAULT_WORKFLOW_STATUSES = [
        {
            "name": "To Do",
            "category": "to_do",
            "description": "Work that has not been started",
            "color": "#6B7280",  # Gray
            "order": 0,
            "is_initial": True,
            "is_final": False,
        },
        {
            "name": "In Progress",
            "category": "in_progress",
            "description": "Work that is actively being worked on",
            "color": "#3B82F6",  # Blue
            "order": 1,
            "is_initial": False,
            "is_final": False,
        },
        {
            "name": "Done",
            "category": "done",
            "description": "Work that has been completed",
            "color": "#10B981",  # Green
            "order": 2,
            "is_initial": False,
            "is_final": True,
        },
    ]
    
    # Create all default workflow statuses
    workflow_statuses = []
    for status_data in DEFAULT_WORKFLOW_STATUSES:
        status = WorkflowStatus(
            project=instance,
            name=status_data["name"],
            category=status_data["category"],
            description=status_data["description"],
            color=status_data["color"],
            order=status_data["order"],
            is_initial=status_data["is_initial"],
            is_final=status_data["is_final"],
            is_active=True,
        )
        workflow_statuses.append(status)
    
    # Bulk create for efficiency
    WorkflowStatus.objects.bulk_create(workflow_statuses)
    
    # Log for debugging (optional)
    print(f"✅ Auto-created {len(workflow_statuses)} default WorkflowStatuses for project: {instance.name}")


@receiver(post_save, sender=Project)
def create_default_project_configuration(sender, instance, created, **kwargs):
    """
    Automatically create default ProjectConfiguration when a new project is created.
    
    This signal fires after a Project is saved. If it's a new project (created=True),
    it creates a configuration with sensible defaults for sprint duration, estimation,
    notifications, and other project settings.
    
    Args:
        sender: The Project model class
        instance: The actual Project instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal parameters
    """
    if not created:
        return  # Only run for new projects, not updates
    
    # Check if configuration already exists (in case of race conditions)
    if hasattr(instance, 'configuration'):
        return
    
    # Create default configuration with sensible defaults
    ProjectConfiguration.objects.create(
        project=instance,
        sprint_duration=2,  # 2 weeks (most common)
        auto_close_sprints=True,
        estimation_type="story_points",
        story_point_scale=[1, 2, 3, 5, 8, 13, 21],  # Fibonacci sequence
        enable_time_tracking=True,
        require_time_logging=False,
        enable_sub_tasks=True,
        email_notifications=True,
        slack_notifications=False,
        slack_webhook_url=None,
        restrict_issue_visibility=False,
        require_approval_for_changes=False,
    )
    
    # Log for debugging (optional)
    print(f"✅ Auto-created default ProjectConfiguration for project: {instance.name}")

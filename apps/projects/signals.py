"""
Django signals for automatic creation of related objects when projects are created.

This ensures that every new project automatically gets:
- Default IssueTypes (Epic, Story, Task, Bug, Improvement, Sub-task)
- Default WorkflowStatuses (To Do, In Progress, Done)
- Default WorkflowTransitions (automatic transitions between states)
- Default ProjectConfiguration (with sensible defaults)
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.projects.models import (
    IssueType,
    Project,
    ProjectConfiguration,
    WorkflowStatus,
    WorkflowTransition,
)


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
    created_statuses = WorkflowStatus.objects.bulk_create(workflow_statuses)
    
    # Log for debugging (optional)
    print(f"✅ Auto-created {len(created_statuses)} default WorkflowStatuses for project: {instance.name}")
    
    # Automatically create transitions between the default statuses
    # This happens immediately after creating statuses to ensure transitions are available
    _create_default_workflow_transitions(instance, created_statuses)


def _create_default_workflow_transitions(project, statuses):
    """
    Helper function to create default workflow transitions for a project.
    
    Creates a flexible workflow that allows transitions between all states:
    - To Do → In Progress (Start Work)
    - In Progress → Done (Complete)
    - In Progress → To Do (Reopen)
    - Done → In Progress (Reopen from Done)
    - Done → To Do (Reopen to Backlog)
    
    Args:
        project: The Project instance
        statuses: List of WorkflowStatus objects for this project
    """
    # Organize statuses by category for easy access
    status_map = {status.category: status for status in statuses}
    
    # Define default transitions based on Scrum/Agile workflow
    default_transitions = []
    
    # Get statuses (they might not all exist if custom workflow)
    to_do = status_map.get('to_do')
    in_progress = status_map.get('in_progress')
    done = status_map.get('done')
    
    # Create transitions only if the statuses exist
    if to_do and in_progress:
        default_transitions.append(
            WorkflowTransition(
                project=project,
                name="Start Work",
                from_status=to_do,
                to_status=in_progress,
                is_active=True,
            )
        )
    
    if in_progress and done:
        default_transitions.append(
            WorkflowTransition(
                project=project,
                name="Complete",
                from_status=in_progress,
                to_status=done,
                is_active=True,
            )
        )
    
    if in_progress and to_do:
        default_transitions.append(
            WorkflowTransition(
                project=project,
                name="Reopen",
                from_status=in_progress,
                to_status=to_do,
                is_active=True,
            )
        )
    
    if done and in_progress:
        default_transitions.append(
            WorkflowTransition(
                project=project,
                name="Reopen from Done",
                from_status=done,
                to_status=in_progress,
                is_active=True,
            )
        )
    
    if done and to_do:
        default_transitions.append(
            WorkflowTransition(
                project=project,
                name="Reopen to Backlog",
                from_status=done,
                to_status=to_do,
                is_active=True,
            )
        )
    
    # Bulk create all transitions
    if default_transitions:
        WorkflowTransition.objects.bulk_create(default_transitions)
        print(f"✅ Auto-created {len(default_transitions)} default WorkflowTransitions for project: {project.name}")


@receiver(post_save, sender=WorkflowStatus)
def create_transitions_for_new_status(sender, instance, created, **kwargs):
    """
    Automatically create bi-directional transitions when a new WorkflowStatus is added.
    
    This signal fires after a WorkflowStatus is saved. If it's a new status (created=True),
    it creates transitions FROM all existing statuses TO this new status, and FROM this
    new status TO all existing statuses. This ensures maximum flexibility for custom workflows.
    
    Args:
        sender: The WorkflowStatus model class
        instance: The actual WorkflowStatus instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal parameters
    """
    if not created:
        return  # Only run for new statuses, not updates
    
    # Get all other active statuses in the same project (excluding the newly created one)
    existing_statuses = WorkflowStatus.objects.filter(
        project=instance.project,
        is_active=True
    ).exclude(id=instance.id)
    
    if not existing_statuses.exists():
        # This is the first status in the project, no transitions to create
        return
    
    transitions_to_create = []
    
    # Create transitions FROM existing statuses TO new status
    for existing_status in existing_statuses:
        transitions_to_create.append(
            WorkflowTransition(
                project=instance.project,
                name=f"{existing_status.name} → {instance.name}",
                from_status=existing_status,
                to_status=instance,
                is_active=True,
            )
        )
    
    # Create transitions FROM new status TO existing statuses
    for existing_status in existing_statuses:
        transitions_to_create.append(
            WorkflowTransition(
                project=instance.project,
                name=f"{instance.name} → {existing_status.name}",
                from_status=instance,
                to_status=existing_status,
                is_active=True,
            )
        )
    
    # Bulk create all transitions
    if transitions_to_create:
        WorkflowTransition.objects.bulk_create(
            transitions_to_create,
            ignore_conflicts=True  # Ignore if transition already exists
        )
        print(
            f"✅ Auto-created {len(transitions_to_create)} transitions for new status: "
            f"{instance.name} in project {instance.project.name}"
        )


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

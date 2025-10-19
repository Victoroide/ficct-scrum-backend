"""
Django signals for automatic creation of related objects when projects are created.

This ensures that every new project automatically gets:
- Default IssueTypes (Epic, Story, Task, Bug, Improvement, Sub-task)
- Default WorkflowStatuses (if not already created by methodology)
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.projects.models import IssueType, Project


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

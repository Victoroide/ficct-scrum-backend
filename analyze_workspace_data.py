"""
Script to analyze current database state for ML training data generation.
This script queries the database to understand what needs to be preserved and what can be regenerated.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Avg
from apps.workspaces.models import Workspace
from apps.projects.models import Project, Sprint, Issue, IssueLink
from apps.organizations.models import Organization

User = get_user_model()

# Constants from requirements
WORKSPACE_UUID = '933607a1-36a8-49e1-991c-fe06350cba26'
REFERENCE_PROJECT_UUID = '23b6e5cf-2de5-4d7d-b420-0d6ee9f47cce'
USER_ID = 11

print("=" * 80)
print("DATABASE STATE ANALYSIS FOR ML TRAINING DATA GENERATION")
print("=" * 80)
print()

# 1. Verify User
print("1. USER VERIFICATION")
print("-" * 80)
try:
    user = User.objects.get(id=USER_ID)
    print(f"[OK] User ID {USER_ID} found: {user.email}")
    print(f"  Name: {user.get_full_name() or 'N/A'}")
    print(f"  Active: {user.is_active}")
except User.DoesNotExist:
    print(f"[ERROR] User ID {USER_ID} not found!")
    sys.exit(1)
print()

# 2. Verify Workspace
print("2. WORKSPACE VERIFICATION")
print("-" * 80)
try:
    workspace = Workspace.objects.get(id=WORKSPACE_UUID)
    print(f"[OK] Workspace found: {workspace.name} (slug: {workspace.slug})")
    print(f"  Organization: {workspace.organization.name if workspace.organization else 'N/A'}")
    print(f"  Created: {workspace.created_at}")
    
    # Check if user is member
    is_member = workspace.members.filter(user_id=USER_ID).exists()
    print(f"  User {USER_ID} is member: {is_member}")
    if not is_member:
        print(f"  WARNING: User {USER_ID} is not a member of this workspace!")
except Workspace.DoesNotExist:
    print(f"[ERROR] Workspace {WORKSPACE_UUID} not found!")
    sys.exit(1)
print()

# 3. Verify Reference Project
print("3. REFERENCE PROJECT VERIFICATION (TO BE PRESERVED)")
print("-" * 80)
try:
    ref_project = Project.objects.get(id=REFERENCE_PROJECT_UUID)
    print(f"[OK] Reference project found: {ref_project.name} (key: {ref_project.key})")
    print(f"  Workspace: {ref_project.workspace.name}")
    
    if str(ref_project.workspace.id) != WORKSPACE_UUID:
        print(f"  [ERROR] Reference project belongs to different workspace!")
        print(f"    Expected: {WORKSPACE_UUID}")
        print(f"    Actual: {ref_project.workspace.id}")
        sys.exit(1)
    
    # Count reference project data
    ref_sprints = Sprint.objects.filter(project=ref_project).count()
    ref_issues = Issue.objects.filter(project=ref_project).count()
    ref_completed_issues = Issue.objects.filter(
        project=ref_project,
        status__is_final=True,
        actual_hours__isnull=False
    ).count()
    
    print(f"  Sprints: {ref_sprints}")
    print(f"  Issues: {ref_issues}")
    print(f"  Completed issues with effort: {ref_completed_issues}")
    
except Project.DoesNotExist:
    print(f"[ERROR] Reference project {REFERENCE_PROJECT_UUID} not found!")
    sys.exit(1)
print()

# 4. Analyze Other Projects in Workspace
print("4. OTHER PROJECTS IN WORKSPACE (CANDIDATES FOR DELETION)")
print("-" * 80)
other_projects = Project.objects.filter(workspace_id=WORKSPACE_UUID).exclude(id=REFERENCE_PROJECT_UUID)
print(f"Found {other_projects.count()} other project(s) in workspace")
print()

if other_projects.exists():
    for project in other_projects:
        print(f"Project: {project.name} (key: {project.key})")
        print(f"  UUID: {project.id}")
        print(f"  Created: {project.created_at}")
        
        # Count data
        sprints = Sprint.objects.filter(project=project).count()
        issues = Issue.objects.filter(project=project).count()
        completed = Issue.objects.filter(
            project=project,
            status__is_final=True,
            actual_hours__isnull=False
        ).count()
        
        print(f"  Sprints: {sprints}")
        print(f"  Issues: {issues}")
        print(f"  Completed with effort: {completed}")
        
        # Check data quality
        if issues > 0:
            avg_effort = Issue.objects.filter(
                project=project,
                actual_hours__isnull=False
            ).aggregate(avg_effort=Avg('actual_hours'))['avg_effort']
            effort_display = f"{avg_effort:.2f}" if avg_effort else "0.00"
            print(f"  Avg effort (completed): {effort_display} hours")
        
        print()
else:
    print("  (No other projects found - workspace only has reference project)")
print()

# 5. Check for Cross-Project Dependencies (IssueLinks)
print("5. CROSS-PROJECT DEPENDENCIES CHECK")
print("-" * 80)
# Links FROM reference project TO other projects
links_from_ref = IssueLink.objects.filter(
    source_issue__project_id=REFERENCE_PROJECT_UUID
).exclude(target_issue__project_id=REFERENCE_PROJECT_UUID).count()

# Links TO reference project FROM other projects  
links_to_ref = IssueLink.objects.filter(
    target_issue__project_id=REFERENCE_PROJECT_UUID
).exclude(source_issue__project_id=REFERENCE_PROJECT_UUID).count()

print(f"Links FROM reference project TO others: {links_from_ref}")
print(f"Links TO reference project FROM others: {links_to_ref}")

if links_from_ref > 0 or links_to_ref > 0:
    print("  [WARNING] Cross-project links exist!")
    print("  These will need to be handled carefully during deletion.")
else:
    print("  [OK] No cross-project links - safe to delete other projects")
print()

# 6. Overall Statistics
print("6. WORKSPACE STATISTICS")
print("-" * 80)
total_projects = Project.objects.filter(workspace_id=WORKSPACE_UUID).count()
total_sprints = Sprint.objects.filter(project__workspace_id=WORKSPACE_UUID).count()
total_issues = Issue.objects.filter(project__workspace_id=WORKSPACE_UUID).count()
total_completed = Issue.objects.filter(
    project__workspace_id=WORKSPACE_UUID,
    status__is_final=True,
    actual_hours__isnull=False
).count()

print(f"Total Projects: {total_projects}")
print(f"Total Sprints: {total_sprints}")
print(f"Total Issues: {total_issues}")
print(f"Total Completed Issues with Effort: {total_completed}")
print()

# 7. ML Training Data Readiness Assessment
print("7. ML TRAINING DATA READINESS")
print("-" * 80)
print("Current status (all projects in workspace):")
print()

# Effort Prediction Dataset
effort_issues = Issue.objects.filter(
    project__workspace_id=WORKSPACE_UUID,
    status__is_final=True,
    actual_hours__isnull=False
).count()
print(f"Effort Prediction Dataset:")
print(f"  Completed issues with effort: {effort_issues}")
print(f"  Requirement: >= 100")
print(f"  Status: {'[SUFFICIENT]' if effort_issues >= 100 else '[INSUFFICIENT]'}")
print()

# Story Points Dataset
story_point_issues = Issue.objects.filter(
    project__workspace_id=WORKSPACE_UUID,
    story_points__isnull=False,
    actual_hours__isnull=False
).count()
print(f"Story Points Dataset:")
print(f"  Issues with story points AND effort: {story_point_issues}")
print(f"  Requirement: >= 60")
print(f"  Status: {'[SUFFICIENT]' if story_point_issues >= 60 else '[INSUFFICIENT]'}")
print()

# Sprint Duration Dataset
completed_sprints = Sprint.objects.filter(
    project__workspace_id=WORKSPACE_UUID,
    status='completed'
).count()
print(f"Sprint Duration Dataset:")
print(f"  Completed sprints: {completed_sprints}")
print(f"  Requirement: >= 15")
print(f"  Status: {'[SUFFICIENT]' if completed_sprints >= 15 else '[INSUFFICIENT]'}")
print()

print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print()
print("RECOMMENDATIONS:")
print("1. Reference project will be PRESERVED (all data intact)")
print(f"2. {other_projects.count()} other project(s) can be SAFELY DELETED")
print("3. After deletion, generate new projects with quality training data")
print()
print("Next step: Run the data generation command with --confirm flag")

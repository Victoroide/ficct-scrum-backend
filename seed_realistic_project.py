"""
Realistic E-commerce Platform Project Seeding Script

Creates production-grade Scrum project with 80 realistic issues.
Target Workspace: 933607a1-36a8-49e1-991c-fe06350cba26

Usage: python seed_realistic_project.py
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.projects.models import Project, Sprint, Issue, WorkflowStatus, IssueType
from apps.workspaces.models import Workspace

User = get_user_model()

# Configuration
WORKSPACE_ID = "933607a1-36a8-49e1-991c-fe06350cba26"
USER_ID = 11
PROJECT_KEY = "ECOM"
TODAY = datetime.now().date()

def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_success(msg):
    print(f"✅ {msg}")

def main():
    print_header("REALISTIC PROJECT SEEDING - E-COMMERCE PLATFORM")
    
    # Get workspace and user
    workspace = Workspace.objects.get(id=WORKSPACE_ID)
    user = User.objects.get(id=USER_ID)
    print_success(f"Workspace: {workspace.name}")
    print_success(f"User: {user.email}")
    
    # Create project
    print_header("STEP 1: CREATE PROJECT")
    project, created = Project.objects.get_or_create(
        workspace=workspace,
        key=PROJECT_KEY,
        defaults={
            "name": "E-commerce Platform",
            "description": "Complete rebuild of legacy e-commerce system with modern architecture",
            "methodology": "scrum",
            "status": "active",
            "priority": "high",
            "lead": user,
            "created_by": user,
            "start_date": TODAY - timedelta(days=56),
            "estimated_hours": 2080,
            "budget": Decimal("500000.00"),
        }
    )
    print_success(f"Project: {project.key} - {project.name}")
    
    # Create workflow statuses
    print_header("STEP 2: CREATE WORKFLOW STATUSES")
    statuses = {}
    for name, cat, color, order, initial, final in [
        ("Backlog", "to_do", "#DFE1E6", 0, True, False),
        ("To Do", "to_do", "#0052CC", 1, False, False),
        ("In Progress", "in_progress", "#FFAB00", 2, False, False),
        ("In Review", "in_progress", "#00B8D9", 3, False, False),
        ("Done", "done", "#00875A", 4, False, True),
    ]:
        status, _ = WorkflowStatus.objects.get_or_create(
            project=project, name=name,
            defaults={"category": cat, "color": color, "order": order,
                     "is_initial": initial, "is_final": final}
        )
        statuses[name] = status
        print_success(f"{name} ({cat})")
    
    # Create issue types
    print_header("STEP 3: CREATE ISSUE TYPES")
    issue_types = {}
    for name, cat, icon, color in [
        ("Epic", "epic", "bookmark", "#6554C0"),
        ("Story", "story", "book", "#0052CC"),
        ("Bug", "bug", "bug_report", "#DE350B"),
        ("Task", "task", "check_circle", "#00875A"),
    ]:
        itype, _ = IssueType.objects.get_or_create(
            project=project, name=name,
            defaults={"category": cat, "icon": icon, "color": color}
        )
        issue_types[name] = itype
        print_success(f"{name} ({cat})")
    
    # Create sprints
    print_header("STEP 4: CREATE SPRINTS")
    sprints = []
    for i, (name, goal, status, offset, capacity, completed) in enumerate([
        ("Sprint 1", "User authentication and product catalog", "completed", -56, 20, 18),
        ("Sprint 2", "Shopping cart and checkout flow", "completed", -42, 22, 21),
        ("Sprint 3", "Payment integration and order management", "completed", -28, 24, 23),
        ("Sprint 4", "Admin dashboard and inventory management", "active", -14, 25, 8),
        ("Sprint 5", "Analytics and reporting features", "planning", 0, 25, 0),
        ("Sprint 6", "Performance optimization and deployment", "planning", 14, 26, 0),
    ], 1):
        start = TODAY + timedelta(days=offset)
        end = start + timedelta(days=14)
        sprint, _ = Sprint.objects.get_or_create(
            project=project, name=name,
            defaults={
                "goal": goal, "status": status, "start_date": start, "end_date": end,
                "committed_points": Decimal(capacity), "completed_points": Decimal(completed),
                "created_by": user,
            }
        )
        if status == "completed":
            sprint.completed_at = timezone.make_aware(datetime.combine(end, datetime.min.time()))
            sprint.save()
        sprints.append(sprint)
        print_success(f"{name}: {goal} ({status})")
    
    # Import issue data
    from seed_issue_data_compact import get_all_issues
    
    # Create issues
    print_header("STEP 5: CREATE 80 REALISTIC ISSUES")
    issue_count = 0
    all_issue_data = get_all_issues()
    
    for sprint_idx, sprint in enumerate(sprints):
        sprint_issues = all_issue_data[sprint_idx]
        
        for issue_data in sprint_issues:
            issue_count += 1
            issue_type = issue_types[issue_data["type"]]
            status_name = issue_data["status"]
            status = statuses[status_name]
            
            issue = Issue.objects.create(
                project=project,
                key=str(issue_count),
                title=issue_data["title"],
                description=issue_data["description"],
                issue_type=issue_type,
                status=status,
                priority=issue_data["priority"],
                assignee=user if issue_data.get("assign") else None,
                reporter=user,
                sprint=sprint if sprint.status != "planning" else None,
                story_points=issue_data.get("story_points"),
                estimated_hours=Decimal(str(issue_data.get("estimated_hours", 0))) if issue_data.get("estimated_hours") else None,
            )
            
            # Set creation date
            created_date = sprint.start_date - timedelta(days=7)
            issue.created_at = timezone.make_aware(datetime.combine(created_date, datetime.min.time()))
            
            # Set resolved_at for done issues
            if status.is_final and sprint.status == "completed":
                resolved_date = sprint.end_date - timedelta(days=2)
                issue.resolved_at = timezone.make_aware(datetime.combine(resolved_date, datetime.min.time()))
            
            issue.save()
            
            if issue_count % 10 == 0:
                print_success(f"Created {issue_count} issues...")
    
    print_success(f"Total issues created: {issue_count}")
    
    # Index to Pinecone
    print_header("STEP 6: INDEX ISSUES TO PINECONE")
    try:
        from apps.ai_assistant.services.rag_service import RAGService
        
        rag = RAGService()
        if not rag.available:
            print(f"⚠️  RAG service unavailable: {rag.error_message}")
            print("   Skipping Pinecone indexing (run in Docker for AI features)")
        else:
            print("📊 Indexing all issues to Pinecone...")
            result = rag.index_project_issues(str(project.id))
            print_success(f"Indexed: {result['indexed']}/{result['total']} issues")
            if result['failed'] > 0:
                print(f"⚠️  Failed: {result['failed']} issues")
    except Exception as e:
        print(f"⚠️  Pinecone indexing error: {e}")
    
    # Summary
    print_header("SEEDING COMPLETE - SUMMARY")
    print(f"✅ Project: {project.key} - {project.name}")
    print(f"✅ Sprints: {len(sprints)} (3 completed, 1 active, 2 planned)")
    print(f"✅ Issues: {issue_count} total")
    print(f"   - Sprint 1: 18 issues (all done)")
    print(f"   - Sprint 2: 21 issues (all done)")
    print(f"   - Sprint 3: 23 issues (all done)")
    print(f"   - Sprint 4: 10 in progress, 8 done, 7 to do")
    print(f"   - Backlog: Remaining issues")
    print(f"\n🎉 Ready for AI features, statistics, and dashboards!")
    print(f"\n📍 Next steps:")
    print(f"   1. Test semantic search: GET /api/ai-assistant/search/?q=authentication")
    print(f"   2. Check dashboard metrics")
    print(f"   3. View CFD chart")
    print(f"   4. Generate AI summary")

if __name__ == "__main__":
    main()

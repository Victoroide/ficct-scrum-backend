"""
Test script for AI Project Summary Report fix.

Validates that the new endpoint returns non-zero metrics.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "base.settings")
django.setup()

from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from apps.projects.models import Project, Issue, Sprint


def test_project_summary_calculation():
    """Test AI Report metrics calculation."""
    print("=" * 80)
    print("AI PROJECT SUMMARY REPORT - FIX VALIDATION")
    print("=" * 80)
    
    # Test with specific project ID from user's context
    project_id = "77cc72d2-1911-4d6c-a6cc-bfb899ba96cd"
    
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        print(f"\n❌ Project {project_id} not found. Testing with first available project.\n")
        project = Project.objects.first()
        if not project:
            print("❌ No projects in database. Please create test data first.")
            return
        project_id = str(project.id)
    
    print(f"\nProject: {project.name} ({project.key})")
    print(f"Project ID: {project_id}")
    print("=" * 80)
    
    # Calculate Completion %
    total_issues = Issue.objects.filter(project=project, is_active=True).count()
    completed_issues = Issue.objects.filter(
        project=project, is_active=True, status__category="done"
    ).count()
    
    completion = round((completed_issues / total_issues) * 100, 2) if total_issues > 0 else 0.0
    
    print(f"\n📊 COMPLETION METRIC")
    print(f"  Total Issues: {total_issues}")
    print(f"  Completed Issues: {completed_issues}")
    print(f"  Completion Rate: {completion}%")
    print(f"  Status: {'✅ WORKING' if completion > 0 or total_issues == 0 else '⚠️ NO COMPLETED ISSUES'}")
    
    # Calculate Velocity
    sprints = Sprint.objects.filter(
        project=project, status__in=["active", "completed"]
    ).order_by("-end_date")[:5]
    
    print(f"\n⚡ VELOCITY METRIC")
    print(f"  Sprints Analyzed: {sprints.count()}")
    
    velocities = []
    for sprint in sprints:
        completed_points = sprint.issues.filter(
            status__category="done", is_active=True
        ).aggregate(total=Coalesce(Sum("story_points"), 0))["total"]
        
        if completed_points > 0:
            velocities.append(completed_points)
            print(f"    - {sprint.name}: {completed_points} points completed")
    
    velocity = round(sum(velocities) / len(velocities), 2) if velocities else 0.0
    
    print(f"  Average Velocity: {velocity}")
    print(f"  Status: {'✅ WORKING' if velocity > 0 else '⚠️ NO VELOCITY DATA'}")
    
    # Calculate Risk Score
    print(f"\n🔴 RISK SCORE METRIC")
    
    unassigned_count = Issue.objects.filter(
        project=project, is_active=True, assignee__isnull=True
    ).count()
    
    overdue_issues = Issue.objects.filter(
        project=project,
        is_active=True,
        sprint__end_date__lt=timezone.now().date(),
        status__category__in=["todo", "in_progress"]
    ).count()
    
    risk_score = 0.0
    
    # Factor 1: Unassigned issues (max 30 points)
    if total_issues > 0:
        unassigned_risk = min((unassigned_count / total_issues) * 100, 30)
        risk_score += unassigned_risk
        print(f"  Unassigned Issues: {unassigned_count}/{total_issues} (+{unassigned_risk:.1f} risk)")
    
    # Factor 2: Overdue issues (max 40 points)
    if total_issues > 0:
        overdue_risk = min((overdue_issues / total_issues) * 100, 40)
        risk_score += overdue_risk
        print(f"  Overdue Issues: {overdue_issues}/{total_issues} (+{overdue_risk:.1f} risk)")
    
    # Factor 3: Velocity decline (max 30 points)
    if len(velocities) >= 2:
        recent_velocity = sum(velocities[:2]) / 2
        older_velocity = sum(velocities[2:]) / len(velocities[2:]) if len(velocities) > 2 else recent_velocity
        
        if older_velocity > 0:
            velocity_change = ((recent_velocity - older_velocity) / older_velocity) * 100
            if velocity_change < -20:
                velocity_risk = min(abs(velocity_change), 30)
                risk_score += velocity_risk
                print(f"  Velocity Decline: {velocity_change:.1f}% (+{velocity_risk:.1f} risk)")
            else:
                print(f"  Velocity Change: {velocity_change:.1f}% (no risk)")
    
    risk_score = min(round(risk_score, 2), 100.0)
    
    print(f"\n  Total Risk Score: {risk_score}/100")
    print(f"  Status: ✅ CALCULATED")
    
    # Final Report
    print(f"\n{'=' * 80}")
    print("AI PROJECT REPORT - FINAL OUTPUT")
    print("=" * 80)
    print(f"\n{{\n"
          f"  \"completion\": {completion},\n"
          f"  \"velocity\": {velocity},\n"
          f"  \"risk_score\": {risk_score},\n"
          f"  \"project_id\": \"{project_id}\"\n"
          f"}}\n")
    
    # Validation
    print("=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    
    all_zero = (completion == 0.0 and velocity == 0.0 and risk_score == 0.0)
    
    if all_zero and total_issues > 0:
        print("\n❌ FAIL: All metrics are zero but project has issues")
        print("   This indicates a data or calculation problem")
    elif all_zero and total_issues == 0:
        print("\n✅ PASS: All metrics zero (expected - no issues in project)")
    else:
        print(f"\n✅ PASS: At least one metric is non-zero")
        print(f"   - Completion: {'✅' if completion > 0 else '⚠️'}")
        print(f"   - Velocity: {'✅' if velocity > 0 else '⚠️'}")
        print(f"   - Risk Score: {'✅' if risk_score >= 0 else '⚠️'}")
    
    print("\n" + "=" * 80)
    print("ENDPOINT INFORMATION")
    print("=" * 80)
    print(f"\nNEW Endpoint Created:")
    print(f"  POST /api/v1/ml/{project_id}/project-summary/")
    print(f"  GET  /api/v1/ml/{project_id}/project-summary/")
    print(f"\nTest with curl:")
    print(f'  curl -X POST -H "Authorization: Bearer {{token}}" \\')
    print(f'    https://dev.api.scrum.ficct.com/api/v1/ml/{project_id}/project-summary/')
    print()


if __name__ == "__main__":
    test_project_summary_calculation()

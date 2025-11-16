import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "base.settings")
django.setup()

from django.db.models import Sum
from django.db.models.functions import Coalesce
from apps.projects.models import Project, Sprint, Issue
from apps.reporting.services.analytics_service import AnalyticsService


def test_velocity_calculation():
    print("=" * 80)
    print("VELOCITY CHART FIX VALIDATION")
    print("=" * 80)
    
    projects = Project.objects.all()[:3]
    
    if not projects:
        print("\nNo projects found in database. Please create test data first.")
        return
    
    service = AnalyticsService()
    
    for project in projects:
        print(f"\n\nProject: {project.name} ({project.key})")
        print("-" * 80)
        
        completed_sprints = Sprint.objects.filter(
            project=project, status="completed"
        ).count()
        active_sprints = Sprint.objects.filter(
            project=project, status="active"
        ).count()
        total_eligible_sprints = Sprint.objects.filter(
            project=project, status__in=["active", "completed"]
        ).count()
        
        print(f"Sprint Status Breakdown:")
        print(f"  - Completed sprints: {completed_sprints}")
        print(f"  - Active sprints: {active_sprints}")
        print(f"  - Total eligible (active + completed): {total_eligible_sprints}")
        
        if total_eligible_sprints == 0:
            print(f"\nNo sprints available for velocity calculation.")
            continue
        
        sprints = Sprint.objects.filter(
            project=project, status__in=["active", "completed"]
        ).order_by("-end_date")[:5]
        
        print(f"\nSprint Details:")
        for sprint in sprints:
            completed_points = sprint.issues.filter(
                status__category="done", is_active=True
            ).aggregate(total=Coalesce(Sum("story_points"), 0))["total"]
            
            planned_points = sprint.issues.filter(is_active=True).aggregate(
                total=Coalesce(Sum("story_points"), 0)
            )["total"]
            
            issue_count = sprint.issues.filter(is_active=True).count()
            completed_issue_count = sprint.issues.filter(
                status__category="done", is_active=True
            ).count()
            
            print(f"\n  Sprint: {sprint.name}")
            print(f"    Status: {sprint.status}")
            print(f"    Issues: {completed_issue_count}/{issue_count} completed")
            print(f"    Story Points: {completed_points}/{planned_points} completed")
            print(f"    Velocity: {completed_points}")
        
        try:
            velocity_data = service.generate_velocity_chart(project, num_sprints=5)
            
            print(f"\n\nVelocity Chart API Response:")
            print(f"  Average Velocity: {velocity_data['average_velocity']}")
            print(f"  Sprints in Chart: {len(velocity_data['labels'])}")
            print(f"  Sprint Names: {velocity_data['labels']}")
            print(f"  Velocities: {velocity_data['velocities']}")
            print(f"  Planned Points: {velocity_data['planned_points']}")
            
            if velocity_data['average_velocity'] > 0:
                print(f"\n  Status: WORKING - Velocity data returned")
            elif total_eligible_sprints > 0:
                print(f"\n  Status: PARTIAL - Sprints exist but no completed points")
            else:
                print(f"\n  Status: EXPECTED - No sprints in project")
                
        except Exception as e:
            print(f"\nERROR calling velocity chart: {e}")
            import traceback
            traceback.print_exc()


def test_dashboard_completion():
    print("\n\n" + "=" * 80)
    print("DASHBOARD COMPLETION RATE VALIDATION")
    print("=" * 80)
    
    projects = Project.objects.all()[:3]
    
    if not projects:
        print("\nNo projects found in database.")
        return
    
    service = AnalyticsService()
    
    for project in projects:
        print(f"\n\nProject: {project.name} ({project.key})")
        print("-" * 80)
        
        total_issues = Issue.objects.filter(project=project, is_active=True).count()
        completed_issues = Issue.objects.filter(
            project=project, is_active=True, status__category="done"
        ).count()
        
        print(f"Issue Breakdown:")
        print(f"  - Total active issues: {total_issues}")
        print(f"  - Completed issues: {completed_issues}")
        
        if total_issues > 0:
            manual_completion = round((completed_issues / total_issues) * 100, 2)
            print(f"  - Manual calculation: {manual_completion}%")
        else:
            print(f"  - No issues in project")
        
        try:
            dashboard_data = service.generate_project_dashboard(project)
            
            print(f"\nDashboard API Response:")
            print(f"  Completion Rate: {dashboard_data['summary_stats']['completion_rate']}%")
            print(f"  Total Issues: {dashboard_data['summary_stats']['total_issues']}")
            print(f"  Completed Issues: {dashboard_data['summary_stats']['completed_issues']}")
            print(f"  Team Size: {dashboard_data['summary_stats']['team_size']}")
            print(f"  Active Sprint: {dashboard_data['summary_stats'].get('active_sprint', 'None')}")
            
            if dashboard_data['summary_stats']['completion_rate'] > 0:
                print(f"\n  Status: WORKING - Completion rate calculated")
            elif total_issues > 0:
                print(f"\n  Status: EXPECTED - No completed issues yet")
            else:
                print(f"\n  Status: EXPECTED - No issues in project")
                
        except Exception as e:
            print(f"\nERROR calling dashboard: {e}")
            import traceback
            traceback.print_exc()


def test_team_metrics():
    print("\n\n" + "=" * 80)
    print("TEAM METRICS VALIDATION")
    print("=" * 80)
    
    projects = Project.objects.all()[:1]
    
    if not projects:
        print("\nNo projects found in database.")
        return
    
    service = AnalyticsService()
    
    for project in projects:
        print(f"\n\nProject: {project.name} ({project.key})")
        print("-" * 80)
        
        try:
            metrics = service.generate_team_metrics(project, period=30)
            
            print(f"\nTeam Aggregates:")
            print(f"  Total Issues: {metrics['team_aggregates']['total_issues']}")
            print(f"  Total Completed: {metrics['team_aggregates']['total_completed']}")
            print(f"  Work in Progress: {metrics['team_aggregates']['work_in_progress']}")
            print(f"  Throughput (issues/day): {metrics['team_aggregates']['throughput']}")
            print(f"  Avg Cycle Time (hours): {metrics['team_aggregates']['avg_cycle_time']}")
            
            print(f"\nUser Metrics ({len(metrics['user_metrics'])} team members):")
            for user_metric in metrics['user_metrics'][:5]:
                print(f"  {user_metric['user']['name']}:")
                print(f"    - Assigned: {user_metric['issues_assigned']}")
                print(f"    - Completed: {user_metric['issues_completed']}")
                print(f"    - Story Points: {user_metric['story_points_completed']}")
            
            print(f"\n  Status: WORKING - Team metrics calculated")
                
        except Exception as e:
            print(f"\nERROR calling team metrics: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("\n\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "VELOCITY CHART FIX - VALIDATION SUITE" + " " * 21 + "║")
    print("╚" + "═" * 78 + "╝")
    
    test_velocity_calculation()
    test_dashboard_completion()
    test_team_metrics()
    
    print("\n\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print("\nTo test via API:")
    print("  Velocity: GET /api/v1/reporting/reports/velocity?project={uuid}&num_sprints=5")
    print("  Dashboard: GET /api/v1/reporting/reports/dashboard?project={uuid}")
    print("  Team Metrics: GET /api/v1/reporting/reports/team-metrics?project={uuid}")
    print("\n")

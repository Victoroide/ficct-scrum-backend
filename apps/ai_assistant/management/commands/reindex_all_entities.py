"""
Management command to reindex ALL entities in Pinecone.

Indexes:
- Issues (enhanced metadata with sprint, labels, priority)
- Sprints (sprint context for temporal queries)
- Team Members (member activity and assignments)
- Project Context (high-level project metadata)

Usage:
    python manage.py reindex_all_entities --project <project_id>
    python manage.py reindex_all_entities --all
    python manage.py reindex_all_entities --clear-first
"""

import logging
from django.core.management.base import BaseCommand
from apps.ai_assistant.services import RAGService
from apps.projects.models import Project, ProjectTeamMember


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reindex all entities (issues, sprints, members, projects) in Pinecone"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=str,
            help="Project ID to reindex (if not specified, reindexes all projects)"
        )
        
        parser.add_argument(
            "--all",
            action="store_true",
            help="Reindex all projects"
        )
        
        parser.add_argument(
            "--clear-first",
            action="store_true",
            help="Clear existing vectors before reindexing (DESTRUCTIVE)"
        )
        
        parser.add_argument(
            "--issues-only",
            action="store_true",
            help="Only reindex issues"
        )
        
        parser.add_argument(
            "--sprints-only",
            action="store_true",
            help="Only reindex sprints"
        )
        
        parser.add_argument(
            "--members-only",
            action="store_true",
            help="Only reindex team members"
        )
        
        parser.add_argument(
            "--projects-only",
            action="store_true",
            help="Only reindex project contexts"
        )
    
    def handle(self, *args, **options):
        """Execute reindexing."""
        
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("PINECONE MULTI-ENTITY REINDEXING"))
        self.stdout.write(self.style.WARNING("=" * 80))
        
        # Initialize RAG service
        try:
            rag_service = RAGService()
            if not rag_service.available:
                self.stdout.write(
                    self.style.ERROR(f"RAG service unavailable: {rag_service.error_message}")
                )
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize RAG service: {str(e)}"))
            return
        
        # Determine projects to process
        projects = self._get_projects(options)
        
        if not projects:
            self.stdout.write(self.style.ERROR("No projects found to reindex"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"Processing {len(projects)} projects"))
        
        # Determine what to index
        index_issues = not any([
            options["sprints_only"],
            options["members_only"],
            options["projects_only"]
        ])
        
        index_sprints = not any([
            options["issues_only"],
            options["members_only"],
            options["projects_only"]
        ])
        
        index_members = not any([
            options["issues_only"],
            options["sprints_only"],
            options["projects_only"]
        ])
        
        index_projects = not any([
            options["issues_only"],
            options["sprints_only"],
            options["members_only"]
        ])
        
        # Clear if requested
        if options["clear_first"]:
            self._clear_namespaces(rag_service, index_issues, index_sprints, index_members, index_projects)
        
        # Process each project
        stats = {
            "issues": {"total": 0, "indexed": 0, "failed": 0},
            "sprints": {"total": 0, "indexed": 0, "failed": 0},
            "members": {"total": 0, "indexed": 0, "failed": 0},
            "projects": {"total": 0, "indexed": 0, "failed": 0},
        }
        
        for i, project in enumerate(projects, 1):
            self.stdout.write("")
            self.stdout.write(
                self.style.HTTP_INFO(f"[{i}/{len(projects)}] Project: {project.name} ({project.key})")
            )
            
            # Index issues
            if index_issues:
                result = self._index_project_issues(rag_service, project)
                stats["issues"]["total"] += result["total"]
                stats["issues"]["indexed"] += result["indexed"]
                stats["issues"]["failed"] += result["failed"]
            
            # Index sprints
            if index_sprints:
                result = self._index_project_sprints(rag_service, project)
                stats["sprints"]["total"] += result["total"]
                stats["sprints"]["indexed"] += result["indexed"]
                stats["sprints"]["failed"] += result["failed"]
            
            # Index team members
            if index_members:
                result = self._index_project_members(rag_service, project)
                stats["members"]["total"] += result["total"]
                stats["members"]["indexed"] += result["indexed"]
                stats["members"]["failed"] += result["failed"]
            
            # Index project context
            if index_projects:
                result = self._index_project_context(rag_service, project)
                stats["projects"]["total"] += result["total"]
                stats["projects"]["indexed"] += result["indexed"]
                stats["projects"]["failed"] += result["failed"]
        
        # Display final statistics
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("REINDEXING COMPLETE"))
        self.stdout.write(self.style.WARNING("=" * 80))
        
        if index_issues:
            self._display_stats("Issues", stats["issues"])
        
        if index_sprints:
            self._display_stats("Sprints", stats["sprints"])
        
        if index_members:
            self._display_stats("Team Members", stats["members"])
        
        if index_projects:
            self._display_stats("Projects", stats["projects"])
    
    def _get_projects(self, options):
        """Get projects to process based on options."""
        if options["project"]:
            try:
                project = Project.objects.get(id=options["project"])
                return [project]
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Project {options['project']} not found"))
                return []
        else:
            return list(Project.objects.filter(is_active=True))
    
    def _clear_namespaces(self, rag_service, issues, sprints, members, projects):
        """Clear specified namespaces."""
        self.stdout.write(self.style.WARNING("Clearing namespaces..."))
        
        if issues:
            self.stdout.write("  - Clearing 'issues' namespace")
            rag_service.pinecone.clear_namespace("issues")
        
        if sprints:
            self.stdout.write("  - Clearing 'sprints' namespace")
            rag_service.pinecone.clear_namespace("sprints")
        
        if members:
            self.stdout.write("  - Clearing 'team_members' namespace")
            rag_service.pinecone.clear_namespace("team_members")
        
        if projects:
            self.stdout.write("  - Clearing 'project_context' namespace")
            rag_service.pinecone.clear_namespace("project_context")
        
        self.stdout.write(self.style.SUCCESS("Namespaces cleared"))
    
    def _index_project_issues(self, rag_service, project):
        """Index all issues in a project."""
        self.stdout.write("  Indexing issues...")
        
        try:
            result = rag_service.index_project_issues(project_id=str(project.id))
            
            self.stdout.write(
                f"    {self.style.SUCCESS('✓')} {result['indexed']}/{result['total']} indexed "
                f"({result['success_rate']}%)"
            )
            
            return result
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ERROR: {str(e)}"))
            return {"total": 0, "indexed": 0, "failed": 0}
    
    def _index_project_sprints(self, rag_service, project):
        """Index all sprints in a project."""
        self.stdout.write("  Indexing sprints...")
        
        try:
            result = rag_service.index_project_sprints(project_id=str(project.id))
            
            self.stdout.write(
                f"    {self.style.SUCCESS('✓')} {result['indexed']}/{result['total']} indexed "
                f"({result['success_rate']}%)"
            )
            
            return result
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ERROR: {str(e)}"))
            return {"total": 0, "indexed": 0, "failed": 0}
    
    def _index_project_members(self, rag_service, project):
        """Index all team members in a project."""
        self.stdout.write("  Indexing team members...")
        
        try:
            members = ProjectTeamMember.objects.filter(
                project=project,
                is_active=True
            ).select_related("user")
            
            total = members.count()
            indexed = 0
            failed = 0
            
            for member in members:
                success, error = rag_service.index_team_member(
                    project_id=str(project.id),
                    user_id=member.user_id
                )
                
                if success:
                    indexed += 1
                else:
                    failed += 1
            
            success_rate = round((indexed / total * 100), 1) if total > 0 else 0
            
            self.stdout.write(
                f"    {self.style.SUCCESS('✓')} {indexed}/{total} indexed ({success_rate}%)"
            )
            
            return {"total": total, "indexed": indexed, "failed": failed}
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ERROR: {str(e)}"))
            return {"total": 0, "indexed": 0, "failed": 0}
    
    def _index_project_context(self, rag_service, project):
        """Index project context."""
        self.stdout.write("  Indexing project context...")
        
        try:
            success, error = rag_service.index_project_context(project_id=str(project.id))
            
            if success:
                self.stdout.write(f"    {self.style.SUCCESS('✓')} 1/1 indexed (100%)")
                return {"total": 1, "indexed": 1, "failed": 0}
            else:
                self.stdout.write(self.style.ERROR(f"    ERROR: {error}"))
                return {"total": 1, "indexed": 0, "failed": 1}
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ERROR: {str(e)}"))
            return {"total": 1, "indexed": 0, "failed": 1}
    
    def _display_stats(self, entity_type, stats):
        """Display statistics for an entity type."""
        total = stats["total"]
        indexed = stats["indexed"]
        failed = stats["failed"]
        success_rate = round((indexed / total * 100), 1) if total > 0 else 0
        
        self.stdout.write(
            f"{entity_type}: {indexed}/{total} indexed ({success_rate}%), {failed} failed"
        )

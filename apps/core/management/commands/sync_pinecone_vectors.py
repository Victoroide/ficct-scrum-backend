"""
Synchronize Pinecone vector database with PostgreSQL source of truth.

This command audits, cleans up, and optionally syncs vectors between PostgreSQL
(source of truth) and Pinecone (vector database for semantic search).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Lock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.projects.models import Issue, Project, ProjectTeamMember, Sprint

logger = logging.getLogger(__name__)
User = get_user_model()

# OpenAI pricing
OPENAI_EMBEDDING_COST_PER_1K_TOKENS = Decimal("0.0001")
EMBEDDING_DIMENSION = 1536


class Command(BaseCommand):
    help = "Synchronize Pinecone vector database with PostgreSQL source of truth"

    def __init__(self):
        super().__init__()
        self.verbose = False
        self.rag_service = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode", type=str, choices=["audit", "cleanup", "sync"], default="audit"
        )
        parser.add_argument(
            "--namespace",
            type=str,
            choices=["issues", "sprints", "project_context", "team_members", "all"],
            default="all",
        )
        parser.add_argument("--workspace", type=str, help="Filter by workspace UUID")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help="Number of parallel workers (default: 8)",
        )
        parser.add_argument(
            "--rate-limit",
            type=int,
            default=10,
            help="Max API calls per second (default: 10)",
        )
        parser.add_argument(
            "--sequential",
            action="store_true",
            help="Process sequentially instead of parallel (slower but safer)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force reindex all vectors, ignore content hash checks",
        )

    def handle(self, *args, **options):
        """Main command execution."""
        self.verbose = options["verbose"]

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("PINECONE SYNC AUDIT REPORT"))
        self.stdout.write("=" * 80)
        self.stdout.write()

        # Check Pinecone availability
        try:
            from apps.ai_assistant.services import RAGService

            self.rag_service = RAGService()
            if not self.rag_service.available:
                raise CommandError("Pinecone is not available")
            self.stdout.write(
                self.style.SUCCESS("[OK] Pinecone connection established")
            )
            self.stdout.write(
                f"Index: {getattr(settings, 'PINECONE_INDEX_NAME', 'N/A')}"
            )
            self.stdout.write()
        except Exception as e:
            raise CommandError(f"Failed to connect to Pinecone: {e}")

        # Collect inventories
        db_data = self._collect_database_inventory(
            options["workspace"], options["namespace"]
        )
        pc_data = self._collect_pinecone_inventory(options["namespace"])

        # Analyze and display
        analysis = self._analyze_sync_status(db_data, pc_data)
        self._display_full_report(db_data, pc_data, analysis)

        # Execute mode-specific actions
        mode = options["mode"]
        if mode == "cleanup":
            self._execute_cleanup(analysis, options["dry_run"], options["confirm"])
        elif mode == "sync":
            self._execute_sync(
                analysis,
                options["dry_run"],
                options["confirm"],
                workers=options["workers"],
                rate_limit=options["rate_limit"],
                sequential=options["sequential"],
                force=options["force"],
            )

    def _collect_database_inventory(self, workspace_filter, namespace_filter):
        """Collect database records."""
        data = {"issues": [], "sprints": [], "projects": [], "team_members": []}

        filters = {}
        if workspace_filter:
            filters["project__workspace_id"] = workspace_filter

        if namespace_filter in ["all", "issues"]:
            data["issues"] = list(
                Issue.objects.filter(**filters if filters else {}).select_related(
                    "project"
                )
            )

        if namespace_filter in ["all", "sprints"]:
            data["sprints"] = list(
                Sprint.objects.filter(**filters if filters else {}).select_related(
                    "project"
                )
            )

        if namespace_filter in ["all", "project_context"]:
            pfilters = {"workspace_id": workspace_filter} if workspace_filter else {}
            data["projects"] = list(Project.objects.filter(**pfilters))

        if namespace_filter in ["all", "team_members"]:
            mfilters = (
                {"project__workspace_id": workspace_filter} if workspace_filter else {}
            )
            # Store as (project_id, user_id) tuples to match vector_id format:
            # member_{project_id}_{user_id}
            memberships = ProjectTeamMember.objects.filter(**mfilters).values_list(
                "project_id", "user_id"
            )
            data["team_members"] = list(memberships)

        return data

    def _collect_pinecone_inventory(self, namespace_filter):
        """Collect Pinecone vectors - returns counts for accurate reporting."""
        data = {"issues": 0, "sprints": 0, "projects": 0, "team_members": 0}

        try:
            # Get index statistics which show namespace counts
            stats = self.rag_service.pinecone.index.describe_index_stats()
            namespaces_stats = stats.get("namespaces", {})

            if self.verbose:
                self.stdout.write(f"[DEBUG] Pinecone stats: {namespaces_stats}")

            # Map namespace names to our data structure
            namespace_map = {
                "issues": "issues",
                "sprints": "sprints",
                "project_context": "projects",
                "team_members": "team_members",
            }

            # Get actual counts from Pinecone
            for pinecone_ns, data_key in namespace_map.items():
                if pinecone_ns in namespaces_stats:
                    count = namespaces_stats[pinecone_ns].get("vector_count", 0)
                    if self.verbose:
                        self.stdout.write(
                            f"[DEBUG] Namespace {pinecone_ns}: {count} vectors"
                        )
                    data[data_key] = count

        except Exception as e:
            if self.verbose:
                self.stdout.write(
                    self.style.WARNING(f"[WARNING] Failed to get Pinecone stats: {e}")
                )

        return data

    def _analyze_sync_status(self, db_data, pc_data):
        """Compare DB vs Pinecone using counts."""
        analysis = {"orphaned": {}, "missing": {}, "cost": {}, "duplicates": {}}

        # pc_data now contains counts, not sets
        # Compare database count vs Pinecone count

        # Issues
        db_count = len(db_data["issues"])
        pc_count = pc_data["issues"]  # Now an integer

        if pc_count > db_count:
            # More vectors than DB records = duplicates or orphans
            analysis["duplicates"]["issues"] = pc_count - db_count
            analysis["orphaned"]["issues"] = []  # Can't distinguish without IDs
            analysis["missing"]["issues"] = []
        elif pc_count < db_count:
            # Fewer vectors than DB records = missing vectors
            analysis["duplicates"]["issues"] = 0
            analysis["orphaned"]["issues"] = []
            analysis["missing"]["issues"] = db_data["issues"]
        else:
            # Counts match
            analysis["duplicates"]["issues"] = 0
            analysis["orphaned"]["issues"] = []
            analysis["missing"]["issues"] = []

        # Sprints
        db_count = len(db_data["sprints"])
        pc_count = pc_data["sprints"]

        if pc_count > db_count:
            analysis["duplicates"]["sprints"] = pc_count - db_count
            analysis["orphaned"]["sprints"] = []
            analysis["missing"]["sprints"] = []
        elif pc_count < db_count:
            analysis["duplicates"]["sprints"] = 0
            analysis["orphaned"]["sprints"] = []
            analysis["missing"]["sprints"] = db_data["sprints"]
        else:
            analysis["duplicates"]["sprints"] = 0
            analysis["orphaned"]["sprints"] = []
            analysis["missing"]["sprints"] = []

        # Projects
        db_count = len(db_data["projects"])
        pc_count = pc_data["projects"]

        if pc_count > db_count:
            analysis["duplicates"]["projects"] = pc_count - db_count
            analysis["orphaned"]["projects"] = []
            analysis["missing"]["projects"] = []
        elif pc_count < db_count:
            analysis["duplicates"]["projects"] = 0
            analysis["orphaned"]["projects"] = []
            analysis["missing"]["projects"] = db_data["projects"]
        else:
            analysis["duplicates"]["projects"] = 0
            analysis["orphaned"]["projects"] = []
            analysis["missing"]["projects"] = []

        # Team members
        db_count = len(db_data["team_members"])
        pc_count = pc_data["team_members"]

        if pc_count > db_count:
            analysis["duplicates"]["team_members"] = pc_count - db_count
            analysis["orphaned"]["team_members"] = []
            analysis["missing"]["team_members"] = []
        elif pc_count < db_count:
            analysis["duplicates"]["team_members"] = 0
            analysis["orphaned"]["team_members"] = []
            analysis["missing"]["team_members"] = db_data["team_members"]
        else:
            analysis["duplicates"]["team_members"] = 0
            analysis["orphaned"]["team_members"] = []
            analysis["missing"]["team_members"] = []

        # Calculate costs
        analysis["cost"] = self._calculate_costs(analysis["missing"])

        return analysis

    def _calculate_costs(self, missing):
        """Calculate vectorization costs."""
        cost_data = {}

        for ns, records in missing.items():
            if not records:
                continue

            texts = [self._get_text_for_record(ns, rec) for rec in records]
            char_counts = [len(t) for t in texts]
            avg_chars = sum(char_counts) // len(char_counts) if char_counts else 0
            token_estimates = [c // 4 for c in char_counts]
            total_tokens = sum(token_estimates)
            cost = (
                Decimal(total_tokens) / Decimal(1000)
            ) * OPENAI_EMBEDDING_COST_PER_1K_TOKENS

            cost_data[ns] = {
                "count": len(records),
                "avg_chars": avg_chars,
                "total_tokens": total_tokens,
                "cost": cost,
            }

        return cost_data

    def _get_text_for_record(self, namespace, record):
        """Get text to embed."""
        if namespace == "issues":
            return f"{record.title} {record.description or ''}"
        elif namespace == "sprints":
            return f"{record.name} {record.goal or ''}"
        elif namespace == "projects":
            return f"{record.name} {record.key} {record.description or ''}"
        elif namespace == "team_members":
            # record is (project_id, user_id) tuple
            try:
                user = User.objects.get(id=record[1])
                return user.get_full_name() or user.email
            except User.DoesNotExist:
                return "Unknown User"
        return ""

    def _display_full_report(self, db_data, pc_data, analysis):
        """Display complete audit report."""
        # Database inventory
        self.stdout.write(self.style.SUCCESS("DATABASE INVENTORY"))
        self.stdout.write("-" * 80)
        self.stdout.write(f"Issues: {len(db_data['issues'])} records")
        self.stdout.write(f"Sprints: {len(db_data['sprints'])} records")
        self.stdout.write(f"Projects: {len(db_data['projects'])} records")
        self.stdout.write(f"Team Members: {len(db_data['team_members'])} records")
        total_db = sum(len(v) for v in db_data.values())
        self.stdout.write(f"Total: {total_db} records")
        self.stdout.write()

        # Pinecone inventory
        self.stdout.write(self.style.SUCCESS("PINECONE INVENTORY"))
        self.stdout.write("-" * 80)
        self.stdout.write(f"issues namespace: {pc_data['issues']} vectors")
        self.stdout.write(f"sprints namespace: {pc_data['sprints']} vectors")
        self.stdout.write(f"project_context namespace: {pc_data['projects']} vectors")
        self.stdout.write(f"team_members namespace: {pc_data['team_members']} vectors")
        total_pc = sum(pc_data.values())
        self.stdout.write(f"Total: {total_pc} vectors")
        self.stdout.write()

        # Analysis
        self.stdout.write(self.style.SUCCESS("COMPARISON ANALYSIS"))
        self.stdout.write("-" * 80)
        self.stdout.write()

        # Orphaned
        self.stdout.write(
            self.style.WARNING("ORPHANED VECTORS (in Pinecone, not in DB):")
        )
        for ns in ["issues", "sprints", "projects", "team_members"]:
            count = len(analysis["orphaned"][ns])
            self.stdout.write(f"  {ns}: {count} orphaned vectors")
        total_orphaned = sum(len(v) for v in analysis["orphaned"].values())
        self.stdout.write(f"\n  Total: {total_orphaned} orphaned vectors")
        if total_orphaned > 0:
            self.stdout.write(
                self.style.WARNING("  Action: DELETE from Pinecone (free operation)")
            )
        self.stdout.write()

        # Missing
        self.stdout.write(
            self.style.WARNING("MISSING VECTORS (in DB, not in Pinecone):")
        )
        for ns in ["issues", "sprints", "projects", "team_members"]:
            count = len(analysis["missing"][ns])
            self.stdout.write(f"  {ns}: {count} records without vectors")
            if ns in analysis["cost"] and analysis["cost"][ns]["count"] > 0:
                c = analysis["cost"][ns]
                self.stdout.write(
                    f"    Average text length: {c['avg_chars']} characters"
                )
                self.stdout.write(f"    Estimated tokens: {c['total_tokens']:,}")
                self.stdout.write(f"    Estimated cost: ${c['cost']:.7f}")

        total_missing = sum(len(v) for v in analysis["missing"].values())
        total_tokens = sum(c["total_tokens"] for c in analysis["cost"].values())
        total_cost = sum(c["cost"] for c in analysis["cost"].values())

        self.stdout.write(f"\n  Total: {total_missing} missing vectors")
        if total_missing > 0:
            self.stdout.write(f"  Total estimated tokens: {total_tokens:,}")
            self.stdout.write(f"  Total estimated cost: ${total_cost:.7f}")
        self.stdout.write()

        # Duplicates/Excess Vectors
        total_duplicates = sum(analysis["duplicates"].values())
        if total_duplicates > 0:
            self.stdout.write(
                self.style.ERROR("[WARNING] DUPLICATE/EXCESS VECTORS DETECTED:")
            )
            for ns in ["issues", "sprints", "projects", "team_members"]:
                dup_count = analysis["duplicates"][ns]
                if dup_count > 0:
                    self.stdout.write(
                        f"  {ns}: {dup_count} excess vectors (duplicates or orphans)"
                    )
            self.stdout.write(f"\n  Total: {total_duplicates} excess vectors")
            self.stdout.write(
                self.style.ERROR(
                    "  [CRITICAL] This indicates duplicates were created during sync!"
                )
            )
            self.stdout.write("  Action: Delete namespace and resync to clean up")
            self.stdout.write()

        # Recommendations
        self.stdout.write(self.style.SUCCESS("RECOMMENDATIONS"))
        self.stdout.write("-" * 80)

        rec_num = 1

        if total_duplicates > 0:
            self.stdout.write(
                f"{rec_num}. [URGENT] Clean up {total_duplicates} duplicate vectors:"
            )
            self.stdout.write("   Option A: Nuclear cleanup (delete all and resync):")
            self.stdout.write(
                "     python manage.py cleanup_pinecone_duplicates --nuclear --confirm"
            )
            self.stdout.write("   Option B: Manual cleanup per namespace:")
            self.stdout.write("     # Delete issues namespace")
            self.stdout.write("     python manage.py shell")
            self.stdout.write(
                "     >>> from apps.ai_assistant.services.rag_service import RAGService"
            )
            self.stdout.write("     >>> rag = RAGService()")
            self.stdout.write(
                "     >>> rag.pinecone.index.delete(delete_all=True, namespace='issues')"  # noqa: E501
            )
            self.stdout.write("     # Then resync")
            self.stdout.write(
                "     python manage.py sync_pinecone_vectors --mode sync --namespace issues --confirm"  # noqa: E501
            )
            rec_num += 1

        if total_orphaned > 0:
            self.stdout.write(
                f"{rec_num}. Run cleanup to remove {total_orphaned} orphaned vectors (free)"  # noqa: E501
            )
            self.stdout.write(
                "   "
                + self.style.SUCCESS(
                    "python manage.py sync_pinecone_vectors --mode cleanup --confirm"
                )
            )
            rec_num += 1

        if total_missing > 0:
            self.stdout.write(
                f"{rec_num}. Sync missing vectors (costs ${total_cost:.7f})"
            )
            self.stdout.write(
                "   "
                + self.style.SUCCESS(
                    "python manage.py sync_pinecone_vectors --mode sync --confirm"
                )
            )
            rec_num += 1

        if total_duplicates == 0 and total_orphaned == 0 and total_missing == 0:
            self.stdout.write(
                "  [OK] No action needed - database and Pinecone are in sync!"
            )

        self.stdout.write()

    def _execute_cleanup(self, analysis, dry_run, confirm):
        """Delete orphaned vectors."""
        total_orphaned = sum(len(v) for v in analysis["orphaned"].values())

        if total_orphaned == 0:
            self.stdout.write(
                self.style.SUCCESS("[OK] No orphaned vectors to clean up")
            )
            return

        if not confirm:
            self.stdout.write(
                self.style.ERROR("[ERROR] Cleanup requires --confirm flag")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY RUN] Would delete {total_orphaned} vectors")
            )
            return

        self.stdout.write("Cleaning up orphaned vectors...")
        deleted = 0
        for ns_key, vector_ids in analysis["orphaned"].items():
            if vector_ids:
                ns_map = {
                    "issues": "issues",
                    "sprints": "sprints",
                    "projects": "project_context",
                    "team_members": "team_members",
                }
                ns = ns_map[ns_key]
                self.rag_service.index.delete(ids=vector_ids, namespace=ns)
                deleted += len(vector_ids)
                self.stdout.write(f"  Deleted {len(vector_ids)} from {ns}")

        self.stdout.write(
            self.style.SUCCESS(f"[OK] Deleted {deleted} orphaned vectors")
        )

    def _execute_sync(
        self,
        analysis,
        dry_run,
        confirm,
        workers=8,
        rate_limit=10,
        sequential=False,
        force=False,
    ):
        """Sync missing vectors using existing RAGService with parallel processing."""
        total_missing = sum(len(v) for v in analysis["missing"].values())

        if total_missing == 0:
            self.stdout.write(
                self.style.SUCCESS("[OK] All records are already vectorized")
            )
            return

        if not confirm:
            self.stdout.write(self.style.ERROR("[ERROR] Sync requires --confirm flag"))
            return

        total_cost = sum(c["cost"] for c in analysis["cost"].values())
        self.stdout.write(
            self.style.WARNING(f"This will cost approximately ${total_cost:.7f}")
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY RUN] Would vectorize {total_missing} records")
            )
            return

        # Show processing mode
        mode = "SEQUENTIAL" if sequential else f"PARALLEL ({workers} workers)"
        self.stdout.write(f"\nProcessing mode: {mode}")
        self.stdout.write(f"Rate limit: {rate_limit} calls/second\n")

        # Execute sync using existing RAGService methods
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("SYNCING MISSING VECTORS")
        self.stdout.write("=" * 80 + "\n")

        # Use 1 worker for sequential mode
        actual_workers = 1 if sequential else workers

        total_synced = 0
        total_failed = 0

        # Sync issues
        if analysis["missing"]["issues"]:
            self.stdout.write(
                f"\n[1/4] Syncing Issues namespace ({len(analysis['missing']['issues'])} records)..."  # noqa: E501
            )
            synced, failed = self._sync_issues(
                analysis["missing"]["issues"], actual_workers, rate_limit, force
            )
            total_synced += synced
            total_failed += failed
            self.stdout.write(
                self.style.SUCCESS(f"  [OK] Issues: {synced} synced, {failed} failed")
            )

        # Sync sprints
        if analysis["missing"]["sprints"]:
            self.stdout.write(
                f"\n[2/4] Syncing Sprints namespace ({len(analysis['missing']['sprints'])} records)..."  # noqa: E501
            )
            synced, failed = self._sync_sprints(
                analysis["missing"]["sprints"], actual_workers, rate_limit, force
            )
            total_synced += synced
            total_failed += failed
            self.stdout.write(
                self.style.SUCCESS(f"  [OK] Sprints: {synced} synced, {failed} failed")
            )

        # Sync projects
        if analysis["missing"]["projects"]:
            self.stdout.write(
                f"\n[3/4] Syncing Projects namespace ({len(analysis['missing']['projects'])} records)..."  # noqa: E501
            )
            synced, failed = self._sync_projects(
                analysis["missing"]["projects"], actual_workers, rate_limit, force
            )
            total_synced += synced
            total_failed += failed
            self.stdout.write(
                self.style.SUCCESS(f"  [OK] Projects: {synced} synced, {failed} failed")
            )

        # Sync team members
        if analysis["missing"]["team_members"]:
            self.stdout.write(
                f"\n[4/4] Syncing Team Members namespace ({len(analysis['missing']['team_members'])} records)..."  # noqa: E501
            )
            synced, failed = self._sync_team_members(
                analysis["missing"]["team_members"], actual_workers, rate_limit, force
            )
            total_synced += synced
            total_failed += failed
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] Team Members: {synced} synced, {failed} failed"
                )
            )

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("SYNC COMPLETE")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Total synced: {total_synced}")
        self.stdout.write(f"Total failed: {total_failed}")
        self.stdout.write(
            f"Success rate: {(total_synced/(total_synced+total_failed)*100):.1f}%"
            if (total_synced + total_failed) > 0
            else "N/A"
        )
        self.stdout.write("=" * 80 + "\n")

    def _sync_issues(self, issue_ids, workers, rate_limit, force=False):
        """Sync missing issue vectors with parallel processing."""
        lock = Lock()
        stats = {"synced": 0, "failed": 0}
        last_call = [0.0]
        min_interval = 1.0 / rate_limit

        def sync_single_issue(issue):
            """Sync a single issue (thread-safe with rate limiting)."""
            try:
                # Rate limiting
                with lock:
                    elapsed = time.time() - last_call[0]
                    if elapsed < min_interval:
                        time.sleep(min_interval - elapsed)
                    last_call[0] = time.time()

                # Vectorize issue
                success, error_msg = self.rag_service.index_issue(
                    str(issue.id), force_reindex=force
                )

                # Update stats thread-safely
                with lock:
                    if success:
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
                        if self.verbose:
                            self.stderr.write(f"  Failed {issue.id}: {error_msg}")

                return True, issue.id, None

            except Exception as e:
                with lock:
                    stats["failed"] += 1
                    if self.verbose:
                        self.stderr.write(f"  Exception {issue.id}: {str(e)}")
                return False, issue.id, str(e)

        # Parallel processing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(sync_single_issue, issue): issue for issue in issue_ids
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1

                # Show progress every 10 records
                if completed % 10 == 0 or completed == len(issue_ids):
                    self.stdout.write(
                        f"    Progress: {completed}/{len(issue_ids)} ({stats['synced']} success, {stats['failed']} failed)"  # noqa: E501
                    )

        return stats["synced"], stats["failed"]

    def _sync_sprints(self, sprint_ids, workers, rate_limit, force=False):
        """Sync missing sprint vectors with parallel processing."""
        lock = Lock()
        stats = {"synced": 0, "failed": 0}
        last_call = [0.0]
        min_interval = 1.0 / rate_limit

        def sync_single_sprint(sprint):
            """Sync a single sprint (thread-safe with rate limiting)."""
            try:
                # Rate limiting
                with lock:
                    elapsed = time.time() - last_call[0]
                    if elapsed < min_interval:
                        time.sleep(min_interval - elapsed)
                    last_call[0] = time.time()

                # Vectorize sprint
                success, error_msg = self.rag_service.index_sprint(str(sprint.id))

                # Update stats thread-safely
                with lock:
                    if success:
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
                        if self.verbose:
                            self.stderr.write(f"  Failed {sprint.id}: {error_msg}")

                return True, sprint.id, None

            except Exception as e:
                with lock:
                    stats["failed"] += 1
                    if self.verbose:
                        self.stderr.write(f"  Exception {sprint.id}: {str(e)}")
                return False, sprint.id, str(e)

        # Parallel processing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(sync_single_sprint, sprint): sprint
                for sprint in sprint_ids
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1

                # Show progress every 5 records
                if completed % 5 == 0 or completed == len(sprint_ids):
                    self.stdout.write(
                        f"    Progress: {completed}/{len(sprint_ids)} ({stats['synced']} success, {stats['failed']} failed)"  # noqa: E501
                    )

        return stats["synced"], stats["failed"]

    def _sync_projects(self, project_ids, workers, rate_limit, force=False):
        """Sync missing project vectors with parallel processing."""
        lock = Lock()
        stats = {"synced": 0, "failed": 0}
        last_call = [0.0]
        min_interval = 1.0 / rate_limit

        def sync_single_project(project):
            """Sync a single project (thread-safe with rate limiting)."""
            try:
                # Rate limiting
                with lock:
                    elapsed = time.time() - last_call[0]
                    if elapsed < min_interval:
                        time.sleep(min_interval - elapsed)
                    last_call[0] = time.time()

                # Vectorize project
                success, error_msg = self.rag_service.index_project_context(
                    str(project.id)
                )

                # Update stats thread-safely
                with lock:
                    if success:
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
                        if self.verbose:
                            self.stderr.write(f"  Failed {project.id}: {error_msg}")

                return True, project.id, None

            except Exception as e:
                with lock:
                    stats["failed"] += 1
                    if self.verbose:
                        self.stderr.write(f"  Exception {project.id}: {str(e)}")
                return False, project.id, str(e)

        # Parallel processing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(sync_single_project, project): project
                for project in project_ids
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1

                # Show progress every 5 records
                if completed % 5 == 0 or completed == len(project_ids):
                    self.stdout.write(
                        f"    Progress: {completed}/{len(project_ids)} ({stats['synced']} success, {stats['failed']} failed)"  # noqa: E501
                    )

        return stats["synced"], stats["failed"]

    def _sync_team_members(self, team_member_tuples, workers, rate_limit, force=False):
        """Sync missing team member vectors with parallel processing."""
        lock = Lock()
        stats = {"synced": 0, "failed": 0}
        last_call = [0.0]
        min_interval = 1.0 / rate_limit

        def sync_single_member(member_tuple):
            """Sync a single team member (thread-safe with rate limiting)."""
            project_id, user_id = member_tuple
            try:
                # Rate limiting
                with lock:
                    elapsed = time.time() - last_call[0]
                    if elapsed < min_interval:
                        time.sleep(min_interval - elapsed)
                    last_call[0] = time.time()

                # Vectorize team member
                success, error_msg = self.rag_service.index_team_member(
                    str(project_id), int(user_id)
                )

                # Update stats thread-safely
                with lock:
                    if success:
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
                        if self.verbose:
                            self.stderr.write(
                                f"  Failed ({project_id}, {user_id}): {error_msg}"
                            )

                return True, (project_id, user_id), None

            except Exception as e:
                with lock:
                    stats["failed"] += 1
                    if self.verbose:
                        self.stderr.write(
                            f"  Exception ({project_id}, {user_id}): {str(e)}"
                        )
                return False, (project_id, user_id), str(e)

        # Parallel processing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(sync_single_member, member): member
                for member in team_member_tuples
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1

                # Show progress every 5 records
                if completed % 5 == 0 or completed == len(team_member_tuples):
                    self.stdout.write(
                        f"    Progress: {completed}/{len(team_member_tuples)} ({stats['synced']} success, {stats['failed']} failed)"  # noqa: E501
                    )

        return stats["synced"], stats["failed"]

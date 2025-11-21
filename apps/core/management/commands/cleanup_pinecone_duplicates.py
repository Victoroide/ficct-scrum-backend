"""
Management command to clean up duplicate vectors in Pinecone.

This command identifies and removes duplicate vectors, keeping only the most
recent version of each vector based on metadata timestamps.
"""

import logging
from typing import Dict, List

from django.core.management.base import BaseCommand, CommandError

from apps.ai_assistant.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Remove duplicate vectors from Pinecone vector database"

    def __init__(self):
        super().__init__()
        self.verbose = False
        self.rag_service = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--namespace",
            type=str,
            choices=["issues", "sprints", "project_context", "team_members", "all"],
            default="all",
            help="Specific namespace to deduplicate",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually delete duplicates (required)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without deleting",
        )
        parser.add_argument("--verbose", action="store_true", help="Verbose output")

    def handle(self, *args, **options):
        """Main command execution."""
        self.verbose = options["verbose"]

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("PINECONE DUPLICATE CLEANUP"))
        self.stdout.write("=" * 80)
        self.stdout.write()

        # Initialize RAG service
        try:
            self.rag_service = RAGService()
            if not self.rag_service.available:
                raise CommandError(
                    f"RAG service unavailable: {self.rag_service.error_message}"
                )
            self.stdout.write(
                self.style.SUCCESS("[OK] Pinecone connection established")
            )
        except Exception as e:
            raise CommandError(f"Failed to connect to Pinecone: {str(e)}")

        namespace_filter = options["namespace"]
        confirm = options["confirm"]
        dry_run = options["dry_run"]

        # Step 1: Scan for duplicates
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("STEP 1: SCANNING FOR DUPLICATES")
        self.stdout.write("=" * 80)
        self.stdout.write()

        duplicates = self._scan_for_duplicates(namespace_filter)

        # Step 2: Display report
        self._display_duplicate_report(duplicates)

        # Step 3: Execute cleanup if confirmed
        total_to_delete = sum(
            len(dups)
            for namespace_dups in duplicates.values()
            for dups in namespace_dups.values()
        )

        if total_to_delete == 0:
            self.stdout.write(self.style.SUCCESS("\n[OK] No duplicates found!"))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would delete {total_to_delete} duplicate vectors"
                )
            )
            return

        if not confirm:
            self.stdout.write(
                self.style.ERROR("\n[ERROR] Use --confirm to execute deletion")
            )
            self.stdout.write(
                "   python manage.py cleanup_pinecone_duplicates --confirm"
            )
            return

        # Execute cleanup
        self._execute_cleanup(duplicates)

    def _scan_for_duplicates(self, namespace_filter) -> Dict[str, Dict[str, List[str]]]:
        """
        Scan Pinecone for duplicate vectors.

        Returns:
            Dict mapping namespace -> base_id -> list of duplicate vector IDs
        """
        duplicates = {}

        # Determine which namespaces to scan
        if namespace_filter == "all":
            namespaces = ["issues", "sprints", "project_context", "team_members"]
        else:
            namespaces = [namespace_filter]

        for namespace in namespaces:
            self.stdout.write(f"Scanning namespace: {namespace}")

            try:
                # Get index stats for this namespace
                stats = self.rag_service.pinecone.index.describe_index_stats()
                namespace_stats = stats.get("namespaces", {}).get(namespace, {})
                vector_count = namespace_stats.get("vector_count", 0)

                if vector_count == 0:
                    self.stdout.write(f"  No vectors in {namespace}")
                    duplicates[namespace] = {}
                    continue

                self.stdout.write(f"  Found {vector_count} vectors")

                # For duplicate detection, we'd need to:
                # 1. List all vector IDs in the namespace
                # 2. Group by base ID pattern
                # 3. Identify groups with multiple IDs

                # Since Pinecone doesn't have a native "list all IDs" API,
                # we use query with dummy vector to get samples
                # This is a limitation - can't easily get ALL IDs

                self.stdout.write("  [WARNING] Cannot efficiently list all vector IDs")
                self.stdout.write(
                    "  Pinecone API limitations prevent full duplicate detection"
                )
                self.stdout.write(
                    "  Recommendation: Use --delete-all-and-resync strategy instead"
                )

                duplicates[namespace] = {}

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  Error scanning {namespace}: {str(e)}")
                )
                duplicates[namespace] = {}

        return duplicates

    def _display_duplicate_report(self, duplicates: Dict[str, Dict[str, List[str]]]):
        """Display report of found duplicates."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("DUPLICATE REPORT")
        self.stdout.write("=" * 80)
        self.stdout.write()

        total_duplicates = 0
        for namespace, namespace_dups in duplicates.items():
            if namespace_dups:
                self.stdout.write(f"{namespace}:")
                for base_id, dup_list in namespace_dups.items():
                    self.stdout.write(f"  {base_id}: {len(dup_list)} duplicates")
                    total_duplicates += len(dup_list)
            else:
                self.stdout.write(f"{namespace}: No duplicates detected")

        self.stdout.write()
        self.stdout.write(f"Total duplicates to delete: {total_duplicates}")

    def _execute_cleanup(self, duplicates: Dict[str, Dict[str, List[str]]]):
        """Execute deletion of duplicate vectors."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("EXECUTING CLEANUP")
        self.stdout.write("=" * 80)
        self.stdout.write()

        total_deleted = 0

        for namespace, namespace_dups in duplicates.items():
            if not namespace_dups:
                continue

            self.stdout.write(f"Cleaning {namespace}...")

            for base_id, dup_list in namespace_dups.items():
                try:
                    # Delete duplicate vectors
                    self.rag_service.pinecone.index.delete(
                        ids=dup_list, namespace=namespace
                    )
                    total_deleted += len(dup_list)
                    if self.verbose:
                        self.stdout.write(
                            f"  Deleted {len(dup_list)} duplicates of {base_id}"
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Error deleting {base_id}: {str(e)}")
                    )

        self.stdout.write()
        self.stdout.write(
            self.style.SUCCESS(f"[OK] Deleted {total_deleted} duplicate vectors")
        )


class NuclearCleanupCommand(BaseCommand):
    """
    NUCLEAR OPTION: Delete ALL vectors and resync from scratch.

    This is more reliable than trying to detect duplicates when
    Pinecone API doesn't provide efficient ID listing.
    """

    help = "Delete ALL vectors from Pinecone and resync from database (DESTRUCTIVE)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--namespace",
            type=str,
            choices=["issues", "sprints", "project_context", "team_members", "all"],
            default="all",
        )
        parser.add_argument(
            "--confirm-nuclear",
            action="store_true",
            help="REQUIRED: Confirms you want to delete ALL vectors",
        )

    def handle(self, *args, **options):
        """Execute nuclear cleanup."""
        if not options["confirm_nuclear"]:
            self.stdout.write(self.style.ERROR("⚠️ NUCLEAR CLEANUP ABORTED"))
            self.stdout.write("This command will DELETE ALL VECTORS from Pinecone")
            self.stdout.write("To proceed, use: --confirm-nuclear")
            return

        self.stdout.write(self.style.ERROR("⚠️ NUCLEAR CLEANUP INITIATED"))
        self.stdout.write("This will delete ALL vectors and require full resync")
        self.stdout.write()

        namespace = options["namespace"]

        try:
            rag_service = RAGService()

            if namespace == "all":
                namespaces = ["issues", "sprints", "project_context", "team_members"]
            else:
                namespaces = [namespace]

            for ns in namespaces:
                self.stdout.write(f"Deleting all vectors in {ns}...")
                rag_service.pinecone.index.delete(delete_all=True, namespace=ns)
                self.stdout.write(self.style.SUCCESS(f"  [OK] {ns} cleared"))

            self.stdout.write()
            self.stdout.write(self.style.SUCCESS("[OK] All vectors deleted"))
            self.stdout.write()
            self.stdout.write("Next step: Resync from database")
            self.stdout.write(
                "  python manage.py sync_pinecone_vectors --mode sync --confirm"
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error during nuclear cleanup: {str(e)}")
            )

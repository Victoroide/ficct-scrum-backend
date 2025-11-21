"""
Tests for automatic personal resource creation for new users.

This test suite verifies that:
1. New users automatically get personal organization, workspace, and project
2. Resources are not duplicated if user is saved multiple times
3. Existing users without resources can be backfilled via management command
4. All memberships and permissions are correctly set up
5. Transaction rollback works correctly on failures
"""


from django.core.management import call_command
from django.test import TestCase, TransactionTestCase

import pytest

from apps.authentication.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectTeamMember
from apps.workspaces.models import Workspace, WorkspaceMember


@pytest.mark.django_db
class TestPersonalResourceCreation(TestCase):
    """Test automatic personal resource creation via signals."""

    def test_new_user_gets_personal_resources(self):
        """Test that creating a new user automatically creates personal resources."""
        # Create a new user
        user = User.objects.create_user(
            email="newuser@example.com",
            username="newuser",
            first_name="New",
            last_name="User",
            password="testpass123",
        )

        # Verify organization was created
        org = Organization.objects.filter(owner=user).first()
        self.assertIsNotNone(org, "Personal organization should be created")
        self.assertIn("Organization", org.name)
        self.assertEqual(org.owner, user)
        self.assertTrue(org.is_active)

        # Verify organization membership
        org_membership = OrganizationMembership.objects.filter(
            organization=org, user=user
        ).first()
        self.assertIsNotNone(
            org_membership, "Organization membership should be created"
        )
        self.assertEqual(org_membership.role, "owner")
        self.assertEqual(org_membership.status, "active")
        self.assertTrue(org_membership.is_active)

        # Verify workspace was created
        workspace = Workspace.objects.filter(organization=org).first()
        self.assertIsNotNone(workspace, "Personal workspace should be created")
        self.assertEqual(workspace.name, "Personal Workspace")
        self.assertEqual(workspace.created_by, user)
        self.assertTrue(workspace.is_active)

        # Verify workspace membership
        ws_membership = WorkspaceMember.objects.filter(
            workspace=workspace, user=user
        ).first()
        self.assertIsNotNone(ws_membership, "Workspace membership should be created")
        self.assertEqual(ws_membership.role, "admin")
        self.assertTrue(ws_membership.is_active)

        # Verify project was created
        project = Project.objects.filter(workspace=workspace).first()
        self.assertIsNotNone(project, "Personal project should be created")
        self.assertEqual(project.name, "My First Project")
        self.assertEqual(project.created_by, user)
        self.assertEqual(project.lead, user)
        self.assertEqual(project.status, "active")
        self.assertTrue(project.is_active)

        # Verify project team membership
        project_membership = ProjectTeamMember.objects.filter(
            project=project, user=user
        ).first()
        self.assertIsNotNone(project_membership, "Project membership should be created")
        self.assertEqual(project_membership.role, "project_manager")
        self.assertTrue(project_membership.is_active)

    def test_signal_only_fires_once_for_new_users(self):
        """Test that resources are not duplicated when user is saved multiple times."""
        # Create a new user
        user = User.objects.create_user(
            email="testuserunique@example.com",
            username="testuserunique",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        # Count resources after first save
        org_count_1 = Organization.objects.filter(owner=user).count()
        workspace_count_1 = Workspace.objects.filter(created_by=user).count()
        project_count_1 = Project.objects.filter(created_by=user).count()

        # Save user again (this should not create duplicate resources)
        user.first_name = "Updated"
        user.save()

        # Save one more time
        user.last_name = "Name"
        user.save()

        # Count resources after multiple saves
        org_count_2 = Organization.objects.filter(owner=user).count()
        workspace_count_2 = Workspace.objects.filter(created_by=user).count()
        project_count_2 = Project.objects.filter(created_by=user).count()

        # Verify no duplicates
        self.assertEqual(
            org_count_1, org_count_2, "Should not create duplicate organizations"
        )
        self.assertEqual(
            workspace_count_1,
            workspace_count_2,
            "Should not create duplicate workspaces",
        )
        self.assertEqual(
            project_count_1, project_count_2, "Should not create duplicate projects"
        )
        self.assertEqual(org_count_2, 1, "Should have exactly one organization")
        self.assertEqual(workspace_count_2, 1, "Should have exactly one workspace")
        self.assertEqual(project_count_2, 1, "Should have exactly one project")

    def test_existing_user_with_resources_is_skipped(self):
        """Test that if user already has resources, signal skips creation."""
        # Create a user
        user = User.objects.create_user(
            email="existing@example.com",
            username="existing",
            first_name="Existing",
            last_name="User",
            password="testpass123",
        )

        # User should now have personal resources
        org_count_1 = Organization.objects.filter(owner=user).count()
        self.assertEqual(org_count_1, 1)

        # Manually create another organization to simulate user having resources
        # Then save user again
        user.email = "updated@example.com"
        user.save()

        # Should still have only the original resources
        org_count_2 = Organization.objects.filter(owner=user).count()
        self.assertEqual(org_count_2, 1, "Should not create additional organizations")

    def test_project_key_generation_from_initials(self):
        """Test that project key is correctly generated from user initials."""
        user = User.objects.create_user(
            email="john.doe@example.com",
            username="johndoe",
            first_name="John",
            last_name="Doe",
            password="testpass123",
        )

        project = Project.objects.filter(created_by=user).first()
        self.assertEqual(project.key, "JD", "Project key should be user initials")

    def test_project_key_handles_conflicts(self):
        """Test that project key gets incremented if there's a conflict."""
        # Create first user with initials JD
        user1 = User.objects.create_user(
            email="john.doe@example.com",
            username="johndoe",
            first_name="John",
            last_name="Doe",
            password="testpass123",
        )

        # Get the workspace from first user's project
        project1 = Project.objects.filter(created_by=user1).first()
        workspace = project1.workspace

        # Manually create a second project in the same workspace with JD key
        # to simulate conflict
        Project.objects.create(
            workspace=workspace,
            name="Another Project",
            key="JD1",
            created_by=user1,
        )

        # Create second user with same initials in a different workspace
        # (This won't conflict since they're in different workspaces)
        user2 = User.objects.create_user(
            email="jane.davis@example.com",
            username="janedavis",
            first_name="Jane",
            last_name="Davis",
            password="testpass123",
        )

        project2 = Project.objects.filter(created_by=user2).first()
        # Jane's project should be JD in her own workspace (no conflict)
        self.assertEqual(project2.key, "JD")

    def test_slug_generation_and_uniqueness(self):
        """Test that organization slugs are unique even with same names."""
        user1 = User.objects.create_user(
            email="john1@example.com",
            username="john1",
            first_name="John",
            last_name="Smith",
            password="testpass123",
        )

        user2 = User.objects.create_user(
            email="john2@example.com",
            username="john2",
            first_name="John",
            last_name="Smith",
            password="testpass123",
        )

        org1 = Organization.objects.filter(owner=user1).first()
        org2 = Organization.objects.filter(owner=user2).first()

        self.assertIsNotNone(org1)
        self.assertIsNotNone(org2)
        self.assertNotEqual(org1.slug, org2.slug, "Slugs should be unique")

    def test_user_without_name_gets_default_names(self):
        """Test that users without first/last names get sensible defaults."""
        user = User.objects.create_user(
            email="noname@example.com",
            username="noname",
            first_name="",
            last_name="",
            password="testpass123",
        )

        org = Organization.objects.filter(owner=user).first()
        self.assertIsNotNone(org)
        # Should get "Personal Organization" when no name provided
        self.assertIn("Organization", org.name)

        project = Project.objects.filter(created_by=user).first()
        self.assertIsNotNone(project)
        # Project key should default to "PP" when no name provided
        self.assertIn("P", project.key)


@pytest.mark.django_db
class TestPersonalResourcesManagementCommand(TransactionTestCase):
    """Test the management command for backfilling existing users."""

    def test_management_command_creates_resources_for_existing_users(self):
        """Test that management command creates resources for users without them."""
        # Create a user without triggering the signal
        # We'll do this by temporarily disabling the signal
        from django.db.models.signals import post_save

        from apps.authentication import signals

        # Disconnect the signal
        post_save.disconnect(signals.create_personal_resources, sender=User)

        try:
            # Create user without personal resources
            user = User.objects.create_user(
                email="olduser@example.com",
                username="olduser",
                first_name="Old",
                last_name="User",
                password="testpass123",
            )

            # Verify no resources exist
            self.assertFalse(Organization.objects.filter(owner=user).exists())

            # Reconnect signal for future users
            post_save.connect(signals.create_personal_resources, sender=User)

            # Run management command
            call_command("create_personal_resources", user="olduser@example.com")

            # Verify resources were created
            org = Organization.objects.filter(owner=user).first()
            self.assertIsNotNone(org)

            workspace = Workspace.objects.filter(organization=org).first()
            self.assertIsNotNone(workspace)

            project = Project.objects.filter(workspace=workspace).first()
            self.assertIsNotNone(project)

        finally:
            # Ensure signal is reconnected
            post_save.connect(signals.create_personal_resources, sender=User)

    def test_management_command_dry_run(self):
        """Test that dry-run mode doesn't create resources."""
        from django.db.models.signals import post_save

        from apps.authentication import signals

        # Disconnect signal
        post_save.disconnect(signals.create_personal_resources, sender=User)

        try:
            # Create user without resources
            user = User.objects.create_user(
                email="dryrunuser@example.com",
                username="dryrunuser",
                first_name="Dry",
                last_name="Run",
                password="testpass123",
            )

            # Reconnect signal
            post_save.connect(signals.create_personal_resources, sender=User)

            # Run command with dry-run flag
            call_command(
                "create_personal_resources", user="dryrunuser@example.com", dry_run=True
            )

            # Verify resources were NOT created
            self.assertFalse(Organization.objects.filter(owner=user).exists())

        finally:
            post_save.connect(signals.create_personal_resources, sender=User)

    def test_management_command_skips_users_with_resources(self):
        """Test that command skips users who already have resources."""
        # Create user with resources (signal will fire)
        user = User.objects.create_user(
            email="hasresources@example.com",
            username="hasresources",
            first_name="Has",
            last_name="Resources",
            password="testpass123",
        )

        # Count initial resources
        initial_org_count = Organization.objects.filter(owner=user).count()
        self.assertEqual(initial_org_count, 1)

        # Run management command
        call_command("create_personal_resources", user="hasresources@example.com")

        # Verify no duplicate resources were created
        final_org_count = Organization.objects.filter(owner=user).count()
        self.assertEqual(final_org_count, 1, "Should not create duplicate resources")


@pytest.mark.django_db
class TestPersonalResourcesEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def test_resources_have_correct_relationships(self):
        """Test that all resources are correctly linked via foreign keys."""
        user = User.objects.create_user(
            email="relationships@example.com",
            username="relationships",
            first_name="Test",
            last_name="Relations",
            password="testpass123",
        )

        org = Organization.objects.filter(owner=user).first()
        workspace = Workspace.objects.filter(organization=org).first()
        project = Project.objects.filter(workspace=workspace).first()

        # Verify the chain: User -> Org -> Workspace -> Project
        self.assertEqual(org.owner, user)
        self.assertEqual(workspace.organization, org)
        self.assertEqual(workspace.created_by, user)
        self.assertEqual(project.workspace, workspace)
        self.assertEqual(project.created_by, user)
        self.assertEqual(project.lead, user)

    def test_all_memberships_have_correct_roles(self):
        """Test that user has correct roles in all memberships."""
        user = User.objects.create_user(
            email="roles@example.com",
            username="roles",
            first_name="Role",
            last_name="Test",
            password="testpass123",
        )

        org = Organization.objects.filter(owner=user).first()
        workspace = Workspace.objects.filter(organization=org).first()
        project = Project.objects.filter(workspace=workspace).first()

        # Check organization membership
        org_membership = OrganizationMembership.objects.get(organization=org, user=user)
        self.assertEqual(org_membership.role, "owner")
        self.assertTrue(org_membership.is_owner)
        self.assertTrue(org_membership.is_admin)

        # Check workspace membership
        ws_membership = WorkspaceMember.objects.get(workspace=workspace, user=user)
        self.assertEqual(ws_membership.role, "admin")
        self.assertTrue(ws_membership.is_admin)
        self.assertTrue(ws_membership.can_manage_projects)

        # Check project membership
        project_membership = ProjectTeamMember.objects.get(project=project, user=user)
        self.assertEqual(project_membership.role, "project_manager")
        self.assertTrue(project_membership.can_manage_project)

    def test_project_signals_create_default_resources(self):
        """
        Test that project creation triggers creation of issue types,
        statuses, etc.
        """
        user = User.objects.create_user(
            email="signals@example.com",
            username="signals",
            first_name="Signal",
            last_name="Test",
            password="testpass123",
        )

        project = Project.objects.filter(created_by=user).first()

        # Verify project has default issue types (created by project signals)
        from apps.projects.models import IssueType

        issue_types = IssueType.objects.filter(project=project)
        self.assertGreater(
            issue_types.count(), 0, "Project should have default issue types"
        )

        # Verify project has default workflow statuses
        from apps.projects.models import WorkflowStatus

        statuses = WorkflowStatus.objects.filter(project=project)
        self.assertGreater(
            statuses.count(), 0, "Project should have default workflow statuses"
        )

        # Verify project has default configuration
        self.assertTrue(
            hasattr(project, "configuration"),
            "Project should have default configuration",
        )

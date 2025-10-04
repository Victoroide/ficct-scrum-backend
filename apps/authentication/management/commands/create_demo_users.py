from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.organizations.models import Organization, OrganizationMembership


class Command(BaseCommand):
    help = "Creates demo users with different roles for testing"

    def handle(self, *args, **options):
        User = get_user_model()

        with transaction.atomic():
            # Create superuser
            superuser = User.objects.create_superuser(
                email="superuser@ficct.com",
                username="superuser",
                first_name="Super",
                last_name="User",
                password="Pass123",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created superuser: {superuser.email}")
            )

            # Create organization
            org = Organization.objects.create(
                name="FICCT University", slug="ficct", owner=superuser, is_active=True
            )

            # Create demo users with different roles
            demo_users = [
                {
                    "email": "owner@ficct.com",
                    "username": "owner",
                    "first_name": "Organization",
                    "last_name": "Owner",
                    "role": "owner",
                    "password": "Pass123",
                },
                {
                    "email": "admin@ficct.com",
                    "username": "admin",
                    "first_name": "Admin",
                    "last_name": "User",
                    "role": "admin",
                    "password": "Pass123",
                },
                {
                    "email": "manager@ficct.com",
                    "username": "manager",
                    "first_name": "Project",
                    "last_name": "Manager",
                    "role": "manager",
                    "password": "Pass123",
                },
                {
                    "email": "member@ficct.com",
                    "username": "member",
                    "first_name": "Team",
                    "last_name": "Member",
                    "role": "member",
                    "password": "Pass123",
                },
                {
                    "email": "guest@ficct.com",
                    "username": "guest",
                    "first_name": "Guest",
                    "last_name": "User",
                    "role": "guest",
                    "password": "Pass123",
                },
            ]

            for user_data in demo_users:
                user = User.objects.create_user(
                    email=user_data["email"],
                    username=user_data["username"],
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    password=user_data["password"],
                    is_verified=True,
                )

                # Create organization membership
                OrganizationMembership.objects.create(
                    organization=org,
                    user=user,
                    role=user_data["role"],
                    status="active",
                    invited_by=superuser,
                    joined_at=user.date_joined,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created {user_data["role"]} user: {user.email}'
                    )
                )

            self.stdout.write(
                self.style.SUCCESS("\nAll demo users created successfully!")
            )
            self.stdout.write(self.style.SUCCESS("\nLogin Credentials:"))
            self.stdout.write(self.style.SUCCESS("------------------"))
            self.stdout.write(
                self.style.SUCCESS(f"Superuser: superuser@ficct.com / Pass123")
            )
            self.stdout.write(self.style.SUCCESS(f"Owner: owner@ficct.com / Pass123"))
            self.stdout.write(self.style.SUCCESS(f"Admin: admin@ficct.com / Pass123"))
            self.stdout.write(
                self.style.SUCCESS(f"Manager: manager@ficct.com / Pass123")
            )
            self.stdout.write(self.style.SUCCESS(f"Member: member@ficct.com / Pass123"))
            self.stdout.write(self.style.SUCCESS(f"Guest: guest@ficct.com / Pass123"))

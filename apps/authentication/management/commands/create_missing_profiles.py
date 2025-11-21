"""
Management command to create missing user profiles.

This command ensures all users have profiles, which is required for login.
Some users may be missing profiles if they were created before the signal was
implemented or if the signal failed during user creation.

Usage:
    python manage.py create_missing_profiles
"""

from django.core.management.base import BaseCommand

from apps.authentication.models import User, UserProfile


class Command(BaseCommand):
    help = "Create missing user profiles for users who don't have one"

    def handle(self, *args, **options):
        self.stdout.write("Checking for users without profiles...")

        users_without_profiles = []
        for user in User.objects.all():
            try:
                # Try to access profile
                _ = user.profile
            except UserProfile.DoesNotExist:
                users_without_profiles.append(user)

        if not users_without_profiles:
            self.stdout.write(self.style.SUCCESS("✅ All users have profiles!"))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(users_without_profiles)} users without profiles"
            )
        )

        created_count = 0
        for user in users_without_profiles:
            try:
                UserProfile.objects.create(user=user)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Created profile for: {user.email}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Failed to create profile for {user.email}: {str(e)}"
                    )
                )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✅ Created {created_count} profiles"))
        self.stdout.write("=" * 60)

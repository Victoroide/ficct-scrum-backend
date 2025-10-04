"""
Management command to test S3 bucket configuration and permissions.
Usage: python manage.py test_s3
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from base.validators import S3Validator


class Command(BaseCommand):
    help = "Test S3 bucket configuration and permissions"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "\n========================================\n"
                "FICCT-SCRUM S3 Configuration Test\n"
                "========================================\n"
            )
        )

        if not settings.USE_S3:
            self.stdout.write(self.style.WARNING("S3 is disabled (USE_S3=False)"))
            self.stdout.write("Local file storage is being used instead.")
            return

        validator = S3Validator()

        # Display configuration
        self.stdout.write("\n--- S3 Configuration ---")
        self.stdout.write(f"Bucket Name: {validator.bucket_name}")
        self.stdout.write(f"Region: {validator.region}")
        self.stdout.write(
            f"Access Key ID: {settings.AWS_ACCESS_KEY_ID[:8]}..."
            if settings.AWS_ACCESS_KEY_ID
            else "Not set"
        )

        # Run validations
        self.stdout.write("\n--- Running Validation Tests ---\n")

        # 1. Configuration
        self.stdout.write("1. Configuration Check...")
        success, message = validator.validate_configuration()
        self._print_result(success, message)

        if not success:
            self.stdout.write(
                self.style.ERROR(
                    "\n✗ Configuration incomplete. "
                    "Please set AWS credentials in .env file."
                )
            )
            return

        # 2. Bucket exists
        self.stdout.write("\n2. Bucket Existence Check...")
        success, message = validator.validate_bucket_exists()
        self._print_result(success, message)

        if not success:
            self.stdout.write(
                self.style.ERROR("\n✗ Bucket does not exist or is not accessible.")
            )
            return

        # 3. Bucket accessible
        self.stdout.write("\n3. Bucket Accessibility Check...")
        success, message = validator.validate_bucket_accessible()
        self._print_result(success, message)

        # 4. Write permission
        self.stdout.write("\n4. Write Permission Test...")
        success, message = validator.test_write_permission()
        self._print_result(success, message)

        # 5. Read permission
        self.stdout.write("\n5. Read Permission Test...")
        success, message = validator.test_read_permission()
        self._print_result(success, message)

        # 6. Delete permission
        self.stdout.write("\n6. Delete Permission Test...")
        success, message = validator.test_delete_permission()
        self._print_result(success, message)

        # 7. CORS configuration
        self.stdout.write("\n7. CORS Configuration Check...")
        success, message = validator.validate_cors()
        self._print_result(success, message)
        if not success:
            self.stdout.write(
                self.style.WARNING(
                    "   Note: CORS is only needed if frontend uploads directly to S3"
                )
            )

        # 8. Public access
        self.stdout.write("\n8. Public Access Check...")
        success, message = validator.check_public_access()
        self._print_result(success, message)

        # Get bucket info
        self.stdout.write("\n--- Bucket Information ---")
        info = validator.get_bucket_info()

        if info["exists"]:
            self.stdout.write(f'Name: {info["name"]}')
            self.stdout.write(f'Region: {info.get("location", "N/A")}')
            self.stdout.write(f'Versioning: {info.get("versioning", "N/A")}')
            self.stdout.write(f'Encryption: {info.get("encryption", "N/A")}')
            self.stdout.write(f'Object Count (sample): {info.get("object_count", 0)}')

            size_mb = info.get("total_size", 0) / (1024 * 1024)
            self.stdout.write(f"Total Size (sample): {size_mb:.2f} MB")

        # Summary
        results = validator.validate_all()
        total = len(results)
        passed = sum(1 for v in results.values() if v)

        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"Tests Passed: {passed}/{total}")

        if passed == total:
            self.stdout.write(self.style.SUCCESS("\n✓ All S3 validation tests passed!"))
        elif passed >= total - 2:
            self.stdout.write(
                self.style.WARNING("\n⚠ Most tests passed, but some issues detected")
            )
        else:
            self.stdout.write(
                self.style.ERROR("\n✗ Multiple S3 configuration issues detected")
            )

        self.stdout.write(
            self.style.WARNING(
                "\n========================================\n"
                "Test Complete\n"
                "========================================\n"
            )
        )

    def _print_result(self, success, message):
        """Print test result with appropriate styling."""
        if success:
            self.stdout.write(self.style.SUCCESS(f"   ✓ {message}"))
        else:
            self.stdout.write(self.style.ERROR(f"   ✗ {message}"))

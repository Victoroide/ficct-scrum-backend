"""
Management command to test email delivery via SES.
Usage: python manage.py test_email --email=test@example.com
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import boto3
from botocore.exceptions import ClientError

from base.services import EmailService


class Command(BaseCommand):
    help = "Test email delivery and verify SES configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Email address to send test email to",
        )

    def handle(self, *args, **options):
        email = options["email"]

        self.stdout.write(
            self.style.WARNING(
                "\n========================================\n"
                "FICCT-SCRUM Email Delivery Test\n"
                "========================================\n"
            )
        )

        # Check email backend configuration
        self.stdout.write(f"Email Backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"Default From Email: {settings.DEFAULT_FROM_EMAIL}")

        if "ses" in settings.EMAIL_BACKEND.lower():
            self.stdout.write(f"SES Region: {settings.AWS_SES_REGION_NAME}")

            # Check SES identity verification
            self.stdout.write("\n--- Checking SES Identity Verification ---")
            try:
                ses_client = boto3.client(
                    "ses",
                    region_name=settings.AWS_SES_REGION_NAME,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )

                # Get verified identities
                response = ses_client.list_verified_email_addresses()
                verified_emails = response.get("VerifiedEmailAddresses", [])

                self.stdout.write(f"Verified email addresses: {len(verified_emails)}")
                for verified_email in verified_emails:
                    self.stdout.write(f"  ✓ {verified_email}")

                # Check if sender email is verified
                from_email = settings.DEFAULT_FROM_EMAIL
                if from_email not in verified_emails:
                    self.stdout.write(
                        self.style.ERROR(
                            f'\n✗ Sender email "{from_email}" is NOT verified!'
                        )
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            "Please verify the sender email in AWS SES Console."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Sender email "{from_email}" is verified')
                    )

                # Get sending quota
                quota = ses_client.get_send_quota()
                self.stdout.write("\n--- SES Sending Quota ---")
                self.stdout.write(f'Max 24 Hour Send: {quota.get("Max24HourSend", 0)}')
                self.stdout.write(
                    f'Sent Last 24 Hours: {quota.get("SentLast24Hours", 0)}'
                )
                self.stdout.write(
                    f'Max Send Rate: {quota.get("MaxSendRate", 0)} emails/sec'
                )

            except ClientError as e:
                self.stdout.write(self.style.ERROR(f"SES API Error: {str(e)}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking SES: {str(e)}"))

        # Send test email
        self.stdout.write("\n--- Sending Test Email ---")
        self.stdout.write(f"Recipient: {email}")

        try:
            success = EmailService.send_email(
                subject="FICCT-SCRUM Test Email",
                message=(
                    "This is a test email from FICCT-SCRUM.\n\n"
                    "If you received this email, your email configuration "
                    "is working correctly!"
                ),
                recipient_list=[email],
                html_message=(
                    "<html><body>"
                    "<h2>FICCT-SCRUM Test Email</h2>"
                    "<p>This is a test email from FICCT-SCRUM.</p>"
                    "<p>If you received this email, your email configuration "
                    "is working correctly!</p>"
                    "</body></html>"
                ),
                fail_silently=False,
            )

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Test email sent successfully to {email}!")
                )
                self.stdout.write(
                    "Please check the inbox (and spam folder) "
                    "of the recipient email."
                )
            else:
                self.stdout.write(self.style.ERROR("\n✗ Test email failed to send"))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n✗ Error sending test email: {str(e)}")
            )
            raise CommandError(f"Email test failed: {str(e)}")

        self.stdout.write(
            self.style.WARNING(
                "\n========================================\n"
                "Test Complete\n"
                "========================================\n"
            )
        )

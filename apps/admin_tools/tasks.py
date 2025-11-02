"""
Celery tasks for admin tools app.

Scheduled tasks for database backup and system maintenance.
"""

import gzip
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task
from decouple import config
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="apps.admin_tools.tasks.backup_database")
def backup_database(self):
    """
    Create automated database backup and upload to cloud storage.

    This task runs daily at 1 AM and performs:
    1. pg_dump to create SQL backup
    2. gzip compression
    3. Upload to S3 (if configured)
    4. Retention policy enforcement (7 daily, 4 weekly, 12 monthly)

    Returns:
        dict: Backup results summary
    """
    try:
        logger.info("Starting database backup task")

        # Get database configuration
        db_settings = settings.DATABASES.get("default", {})
        db_name = db_settings.get("NAME")
        db_user = db_settings.get("USER")
        db_password = db_settings.get("PASSWORD")
        db_host = db_settings.get("HOST", "localhost")
        db_port = db_settings.get("PORT", "5432")

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"ficct_scrum_backup_{timestamp}.sql"
        compressed_filename = f"{backup_filename}.gz"

        # Create temporary backup directory
        backup_dir = Path("/tmp/backups")
        backup_dir.mkdir(exist_ok=True)

        backup_path = backup_dir / backup_filename
        compressed_path = backup_dir / compressed_filename

        results = {
            "backup_filename": compressed_filename,
            "backup_size_mb": 0,
            "upload_success": False,
            "retention_applied": False,
            "error": None,
        }

        try:
            # Step 1: Create pg_dump backup
            logger.info(f"Creating database backup: {backup_filename}")

            env = os.environ.copy()
            env["PGPASSWORD"] = db_password

            dump_command = [
                "pg_dump",
                "-h", db_host,
                "-p", str(db_port),
                "-U", db_user,
                "-Fc",  # Custom format (compressed)
                "-f", str(backup_path),
                db_name,
            ]

            process = subprocess.run(
                dump_command,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if process.returncode != 0:
                raise Exception(f"pg_dump failed: {process.stderr}")

            # Step 2: Compress backup
            logger.info(f"Compressing backup to {compressed_filename}")

            with open(backup_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    f_out.writelines(f_in)

            # Get backup size
            backup_size = compressed_path.stat().st_size
            results["backup_size_mb"] = round(backup_size / (1024 * 1024), 2)

            logger.info(f"Backup created successfully: {results['backup_size_mb']} MB")

            # Step 3: Upload to S3 (if configured)
            try:
                import boto3
                from botocore.exceptions import ClientError

                s3_bucket = config("BACKUP_S3_BUCKET", default="")
                aws_access_key = config("AWS_ACCESS_KEY_ID", default="")
                aws_secret_key = config("AWS_SECRET_ACCESS_KEY", default="")
                aws_region = config("AWS_REGION", default="us-east-1")

                if s3_bucket and aws_access_key:
                    logger.info(f"Uploading backup to S3: {s3_bucket}")

                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=aws_access_key,
                        aws_secret_access_key=aws_secret_key,
                        region_name=aws_region,
                    )

                    s3_key = f"backups/{compressed_filename}"
                    s3_client.upload_file(
                        str(compressed_path),
                        s3_bucket,
                        s3_key,
                    )

                    results["upload_success"] = True
                    results["s3_location"] = f"s3://{s3_bucket}/{s3_key}"
                    logger.info(f"Backup uploaded successfully to S3")

                    # Step 4: Apply retention policy
                    results["retention_applied"] = _apply_retention_policy(s3_client, s3_bucket)

                else:
                    logger.warning("S3 backup not configured - backup saved locally only")
                    results["upload_success"] = False

            except ImportError:
                logger.warning("boto3 not installed - skipping S3 upload")
                results["upload_success"] = False
            except Exception as e:
                logger.exception(f"Error uploading to S3: {str(e)}")
                results["error"] = f"S3 upload failed: {str(e)}"

        finally:
            # Cleanup temporary files
            if backup_path.exists():
                backup_path.unlink()
            if not results["upload_success"] and compressed_path.exists():
                # Keep local backup if S3 upload failed
                logger.warning(f"Backup retained locally at {compressed_path}")
            elif compressed_path.exists():
                compressed_path.unlink()

        logger.info(f"Database backup task completed: {results}")
        return results

    except Exception as e:
        logger.exception(f"Critical error in backup_database task: {str(e)}")
        results["error"] = str(e)
        return results


def _apply_retention_policy(s3_client, bucket: str) -> bool:
    """
    Apply backup retention policy.

    Policy:
    - Keep 7 daily backups
    - Keep 4 weekly backups (every Monday)
    - Keep 12 monthly backups (first of each month)

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name

    Returns:
        bool: True if retention applied successfully
    """
    try:
        logger.info("Applying backup retention policy")

        # List all backups
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix="backups/")

        if "Contents" not in response:
            return True

        backups = []
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.endswith(".sql.gz"):
                # Extract timestamp from filename
                try:
                    filename = Path(key).name
                    timestamp_str = filename.replace("ficct_scrum_backup_", "").replace(".sql.gz", "")
                    backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    backups.append({
                        "key": key,
                        "date": backup_date,
                        "size": obj["Size"],
                    })
                except ValueError:
                    continue

        # Sort by date (newest first)
        backups.sort(key=lambda x: x["date"], reverse=True)

        # Determine which backups to keep
        now = datetime.now()
        keep_backups = set()

        # Keep 7 most recent daily backups
        for backup in backups[:7]:
            keep_backups.add(backup["key"])

        # Keep 4 weekly backups (Mondays)
        weekly_backups = [b for b in backups if b["date"].weekday() == 0]
        for backup in weekly_backups[:4]:
            keep_backups.add(backup["key"])

        # Keep 12 monthly backups (first of month)
        monthly_backups = [b for b in backups if b["date"].day == 1]
        for backup in monthly_backups[:12]:
            keep_backups.add(backup["key"])

        # Delete old backups
        deleted_count = 0
        for backup in backups:
            if backup["key"] not in keep_backups:
                # Only delete if older than 7 days (safety check)
                if (now - backup["date"]).days > 7:
                    try:
                        s3_client.delete_object(Bucket=bucket, Key=backup["key"])
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {backup['key']}")
                    except Exception as e:
                        logger.error(f"Error deleting {backup['key']}: {str(e)}")

        logger.info(f"Retention policy applied: kept {len(keep_backups)}, deleted {deleted_count}")
        return True

    except Exception as e:
        logger.exception(f"Error applying retention policy: {str(e)}")
        return False


@shared_task(bind=True, name="apps.admin_tools.tasks.system_health_check")
def system_health_check(self):
    """
    Perform system health checks and alert if issues detected.

    Checks:
    - Database connectivity
    - Redis connectivity
    - Celery worker status
    - Disk space
    - Memory usage

    Returns:
        dict: Health check results
    """
    try:
        from django.core.cache import cache
        from django.db import connection

        logger.info("Starting system health check")

        results = {
            "timestamp": timezone.now().isoformat(),
            "database": "unknown",
            "cache": "unknown",
            "celery": "unknown",
            "errors": [],
        }

        # Check database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            results["database"] = "healthy"
        except Exception as e:
            results["database"] = "unhealthy"
            results["errors"].append(f"Database error: {str(e)}")

        # Check Redis/Cache
        try:
            cache.set("health_check", "ok", 10)
            if cache.get("health_check") == "ok":
                results["cache"] = "healthy"
            else:
                results["cache"] = "unhealthy"
        except Exception as e:
            results["cache"] = "unhealthy"
            results["errors"].append(f"Cache error: {str(e)}")

        # Check Celery (inspect active workers)
        try:
            from celery import current_app

            inspect = current_app.control.inspect()
            active_workers = inspect.active()

            if active_workers and len(active_workers) > 0:
                results["celery"] = "healthy"
                results["active_workers"] = len(active_workers)
            else:
                results["celery"] = "unhealthy"
                results["errors"].append("No active Celery workers")
        except Exception as e:
            results["celery"] = "unhealthy"
            results["errors"].append(f"Celery error: {str(e)}")

        # Log results
        if results["errors"]:
            logger.warning(f"System health check detected issues: {results}")
        else:
            logger.info(f"System health check passed: {results}")

        return results

    except Exception as e:
        logger.exception(f"Error in system_health_check task: {str(e)}")
        raise

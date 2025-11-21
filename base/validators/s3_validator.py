"""
S3 Validator - Comprehensive validation of S3 bucket configuration.
Tests bucket accessibility, permissions, CORS, and file operations.
"""
import logging
from typing import Dict, Tuple

from django.conf import settings

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Validator:
    """Validate S3 bucket configuration and permissions."""

    def __init__(self):
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.region = settings.AWS_S3_REGION_NAME
        self.s3_client = None
        self.s3_resource = None

        if settings.USE_S3:
            self.s3_client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            self.s3_resource = boto3.resource(
                "s3",
                region_name=self.region,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

    def validate_all(self) -> Dict[str, bool]:
        """Run all validation checks and return results."""
        results = {
            "configuration": False,
            "bucket_exists": False,
            "bucket_accessible": False,
            "read_permission": False,
            "write_permission": False,
            "delete_permission": False,
            "cors_configured": False,
            "public_access": False,
        }

        if not settings.USE_S3:
            logger.info("S3 is disabled in settings")
            return results

        results["configuration"] = self.validate_configuration()[0]
        results["bucket_exists"] = self.validate_bucket_exists()[0]

        if results["bucket_exists"]:
            results["bucket_accessible"] = self.validate_bucket_accessible()[0]
            results["read_permission"] = self.test_read_permission()[0]
            results["write_permission"] = self.test_write_permission()[0]
            results["delete_permission"] = self.test_delete_permission()[0]
            results["cors_configured"] = self.validate_cors()[0]
            results["public_access"] = self.check_public_access()[0]

        return results

    def validate_configuration(self) -> Tuple[bool, str]:
        """Validate S3 configuration settings."""
        try:
            if not self.bucket_name:
                return False, "AWS_STORAGE_BUCKET_NAME not configured"

            if not settings.AWS_ACCESS_KEY_ID:
                return False, "AWS_ACCESS_KEY_ID not configured"

            if not settings.AWS_SECRET_ACCESS_KEY:
                return False, "AWS_SECRET_ACCESS_KEY not configured"

            if not self.region:
                return False, "AWS_S3_REGION_NAME not configured"

            return True, "S3 configuration is valid"

        except Exception as e:
            return False, f"Configuration error: {str(e)}"

    def validate_bucket_exists(self) -> Tuple[bool, str]:
        """Check if the S3 bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True, f'Bucket "{self.bucket_name}" exists'

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False, f'Bucket "{self.bucket_name}" does not exist'
            elif error_code == "403":
                return False, f'Access denied to bucket "{self.bucket_name}"'
            else:
                return False, f"Error checking bucket: {str(e)}"

        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def validate_bucket_accessible(self) -> Tuple[bool, str]:
        """Check if bucket is accessible with current credentials."""
        try:
            bucket = self.s3_resource.Bucket(self.bucket_name)
            # Try to list objects (limit to 1 for efficiency)
            list(bucket.objects.limit(1))
            return True, "Bucket is accessible"

        except ClientError as e:
            return False, f"Cannot access bucket: {str(e)}"

        except Exception as e:
            return False, f"Access error: {str(e)}"

    def test_write_permission(self) -> Tuple[bool, str]:
        """Test write permissions by uploading a test file."""
        test_key = "test/ficct_scrum_write_test.txt"
        test_content = b"FICCT-SCRUM S3 write test"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=test_key,
                Body=test_content,
                ContentType="text/plain",
            )
            return True, "Write permission confirmed"

        except ClientError as e:
            return False, f"Write permission denied: {str(e)}"

        except Exception as e:
            return False, f"Write error: {str(e)}"

    def test_read_permission(self) -> Tuple[bool, str]:
        """Test read permissions by reading a test file."""
        test_key = "test/ficct_scrum_write_test.txt"

        try:
            self.s3_client.get_object(Bucket=self.bucket_name, Key=test_key)
            return True, "Read permission confirmed"

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                return False, "Test file not found (run write test first)"
            else:
                return False, f"Read permission denied: {str(e)}"

        except Exception as e:
            return False, f"Read error: {str(e)}"

    def test_delete_permission(self) -> Tuple[bool, str]:
        """Test delete permissions by deleting the test file."""
        test_key = "test/ficct_scrum_write_test.txt"

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=test_key)
            return True, "Delete permission confirmed"

        except ClientError as e:
            return False, f"Delete permission denied: {str(e)}"

        except Exception as e:
            return False, f"Delete error: {str(e)}"

    def validate_cors(self) -> Tuple[bool, str]:
        """Check if CORS is configured for the bucket."""
        try:
            cors = self.s3_client.get_bucket_cors(Bucket=self.bucket_name)
            rules = cors.get("CORSRules", [])

            if not rules:
                return False, "No CORS rules configured"

            # Check if there's a permissive rule
            for rule in rules:
                allowed_origins = rule.get("AllowedOrigins", [])
                allowed_methods = rule.get("AllowedMethods", [])

                if "*" in allowed_origins or any(
                    "localhost" in origin or "ficct" in origin
                    for origin in allowed_origins
                ):
                    if "GET" in allowed_methods or "POST" in allowed_methods:
                        return True, f"CORS configured with {len(rules)} rule(s)"

            return (False, "CORS configured but may need adjustment for your domain")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchCORSConfiguration":
                return False, "CORS not configured"
            else:
                return False, f"Error checking CORS: {str(e)}"

        except Exception as e:
            return False, f"CORS validation error: {str(e)}"

    def check_public_access(self) -> Tuple[bool, str]:
        """Check if bucket has public access settings."""
        try:
            acl = self.s3_client.get_bucket_acl(Bucket=self.bucket_name)
            grants = acl.get("Grants", [])

            public_read = False
            for grant in grants:
                grantee = grant.get("Grantee", {})
                permission = grant.get("Permission", "")

                if grantee.get("Type") == "Group":
                    uri = grantee.get("URI", "")
                    if "AllUsers" in uri and permission in ["READ", "FULL_CONTROL"]:
                        public_read = True
                        break

            if public_read:
                return (True, "Bucket has public read access (may be intentional)")
            else:
                return False, "Bucket is private (recommended)"

        except ClientError as e:
            return False, f"Error checking ACL: {str(e)}"

        except Exception as e:
            return False, f"ACL check error: {str(e)}"

    def get_bucket_info(self) -> Dict[str, any]:
        """Get detailed bucket information."""
        info = {
            "name": self.bucket_name,
            "region": self.region,
            "exists": False,
            "creation_date": None,
            "versioning": None,
            "encryption": None,
            "object_count": 0,
            "total_size": 0,
        }

        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            info["exists"] = True

            # Get bucket location
            location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)
            info["location"] = location.get("LocationConstraint", "us-east-1")

            # Get versioning status
            try:
                versioning = self.s3_client.get_bucket_versioning(
                    Bucket=self.bucket_name
                )
                info["versioning"] = versioning.get("Status", "Disabled")
            except Exception:
                info["versioning"] = "Unknown"

            # Get encryption status
            try:
                _encryption = self.s3_client.get_bucket_encryption(  # noqa: F841
                    Bucket=self.bucket_name
                )
                info["encryption"] = "Enabled"
            except ClientError as e:
                if (
                    e.response["Error"]["Code"]
                    == "ServerSideEncryptionConfigurationNotFoundError"
                ):
                    info["encryption"] = "Disabled"
                else:
                    info["encryption"] = "Unknown"

            # Count objects (sample only for large buckets)
            try:
                paginator = self.s3_client.get_paginator("list_objects_v2")
                page_iterator = paginator.paginate(
                    Bucket=self.bucket_name, PaginationConfig={"MaxItems": 1000}
                )

                count = 0
                total_size = 0
                for page in page_iterator:
                    if "Contents" in page:
                        count += len(page["Contents"])
                        total_size += sum(obj["Size"] for obj in page["Contents"])

                info["object_count"] = count
                info["total_size"] = total_size
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error getting bucket info: {str(e)}")

        return info

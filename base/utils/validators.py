import re

from django.core.exceptions import ValidationError


def validate_image_file(file):
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise ValidationError("Only JPEG, PNG, WEBP, and GIF images are allowed")

    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("Image size cannot exceed 5MB")


def validate_document_file(file):
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    ]
    if file.content_type not in allowed_types:
        raise ValidationError("Only PDF, DOC, DOCX, TXT, and MD files are allowed")

    max_size = 10 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("Document size cannot exceed 10MB")


def validate_organization_name(name):
    if len(name) < 2:
        raise ValidationError("Organization name must be at least 2 characters long")

    if len(name) > 100:
        raise ValidationError("Organization name cannot exceed 100 characters")

    if not re.match(r"^[a-zA-Z0-9\s\-_.]+$", name):
        raise ValidationError("Organization name contains invalid characters")


def validate_project_name(name):
    if len(name) < 3:
        raise ValidationError("Project name must be at least 3 characters long")

    if len(name) > 200:
        raise ValidationError("Project name cannot exceed 200 characters")


def validate_workspace_name(name):
    if len(name) < 2:
        raise ValidationError("Workspace name must be at least 2 characters long")

    if len(name) > 150:
        raise ValidationError("Workspace name cannot exceed 150 characters")

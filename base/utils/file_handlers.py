import io
import uuid
from typing import Optional

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from PIL import Image


def resize_image(
    image_file, max_width: int = 800, max_height: int = 600, quality: int = 85
) -> ContentFile:
    image = Image.open(image_file)

    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGB")

    ratio = min(max_width / image.width, max_height / image.height)
    if ratio < 1:
        new_width = int(image.width * ratio)
        new_height = int(image.height * ratio)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    image.save(output, format="WebP", quality=quality, optimize=True)
    output.seek(0)

    return ContentFile(output.read(), name=f"{uuid.uuid4().hex}.webp")


def upload_avatar_to_s3(file, user_id: int) -> str:
    resized_image = resize_image(file, max_width=400, max_height=400)
    filename = f"avatars/user_{user_id}/avatar.webp"
    return default_storage.save(filename, resized_image)


def upload_organization_logo_to_s3(file, org_id: int) -> str:
    resized_image = resize_image(file, max_width=300, max_height=300)
    filename = f"organizations/org_{org_id}/logo.webp"
    return default_storage.save(filename, resized_image)


def upload_workspace_asset_to_s3(file, workspace_id: int) -> str:
    resized_image = resize_image(file, max_width=500, max_height=500)
    filename = f"workspaces/workspace_{workspace_id}/{uuid.uuid4().hex}.webp"
    return default_storage.save(filename, resized_image)


def upload_project_file_to_s3(file, project_id: int) -> str:
    file_extension = file.name.split(".")[-1] if "." in file.name else "bin"
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
    filename = f"projects/project_{project_id}/files/{unique_filename}"
    return default_storage.save(filename, file)


def upload_document_to_s3(file, folder: str, user_id: Optional[int] = None) -> str:
    file_extension = file.name.split(".")[-1] if "." in file.name else "bin"
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"

    if user_id:
        filename = f"{folder}/user_{user_id}/{unique_filename}"
    else:
        filename = f"{folder}/{unique_filename}"

    return default_storage.save(filename, file)


def delete_file_from_s3(file_path: str) -> bool:
    try:
        default_storage.delete(file_path)
        return True
    except Exception:
        return False

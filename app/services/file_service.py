import os
import uuid
import pathlib
from typing import List, Tuple, Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.models.models import FileAttachment
from app.exceptions import NotFoundError

ALLOWED_ENTITIES = {"work_order", "diagnostic", "vehicle", "invoice"}


class FileService:
    @staticmethod
    def _get_base_upload_dir() -> pathlib.Path:
        base = pathlib.Path(settings.UPLOAD_DIR)
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    async def upload_file(
        cls,
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        file: UploadFile,
        user_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None
    ) -> FileAttachment:
        """
        Validates, persists a file attachment to disk, and records metadata in the database.
        """
        # 1. Validate entity type
        if entity_type not in ALLOWED_ENTITIES:
            raise ValueError(f"Invalid entity type '{entity_type}'. Must be one of {sorted(ALLOWED_ENTITIES)}.")

        # 2. Validate file extension
        filename = file.filename or "unknown"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed_exts = {e.strip().lower() for e in settings.ALLOWED_EXTENSIONS.split(",")}
        if ext not in allowed_exts:
            raise ValueError(f"File extension '.{ext}' not allowed. Allowed: {', '.join(sorted(allowed_exts))}")

        # 3. Read file contents and validate file size
        contents = await file.read()
        file_size = len(contents)
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(f"File size ({file_size / (1024*1024):.2f}MB) exceeds limit of {settings.MAX_FILE_SIZE_MB}MB.")
        if file_size == 0:
            raise ValueError("Cannot upload an empty file.")

        # 4. Check attachment count per entity
        count_stmt = select(func.count(FileAttachment.file_id)).where(
            FileAttachment.entity_type == entity_type,
            FileAttachment.entity_id == entity_id
        )
        count_res = await db.execute(count_stmt)
        current_count = count_res.scalar() or 0
        if current_count >= settings.MAX_FILES_PER_ENTITY:
            raise ValueError(f"Maximum of {settings.MAX_FILES_PER_ENTITY} attachments reached for this {entity_type}.")

        # 5. Save to disk
        target_dir = cls._get_base_upload_dir() / entity_type / str(entity_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid.uuid4().hex}_{filename}"
        target_path = target_dir / stored_filename
        with open(target_path, "wb") as f:
            f.write(contents)

        # 6. Save DB record
        attachment = FileAttachment(
            entity_type=entity_type,
            entity_id=str(entity_id),
            original_filename=filename,
            stored_filename=stored_filename,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            uploaded_by=user_id,
            description=description
        )
        db.add(attachment)
        await db.flush()
        return attachment

    @classmethod
    async def list_files(
        cls,
        db: AsyncSession,
        entity_type: str,
        entity_id: str
    ) -> List[FileAttachment]:
        """
        Retrieves all file attachments for a given entity.
        """
        stmt = (
            select(FileAttachment)
            .where(
                FileAttachment.entity_type == entity_type,
                FileAttachment.entity_id == str(entity_id)
            )
            .order_by(FileAttachment.uploaded_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_file(
        cls,
        db: AsyncSession,
        file_id: uuid.UUID
    ) -> Tuple[FileAttachment, pathlib.Path]:
        """
        Retrieves file attachment metadata and physical filesystem path.
        """
        stmt = select(FileAttachment).where(FileAttachment.file_id == file_id)
        res = await db.execute(stmt)
        attachment = res.scalar_one_or_none()
        if not attachment:
            raise NotFoundError(f"File attachment with ID {file_id} not found.")

        file_path = cls._get_base_upload_dir() / attachment.entity_type / attachment.entity_id / attachment.stored_filename
        if not file_path.exists():
            raise NotFoundError("The requested file is no longer present on the server storage.")

        return attachment, file_path

    @classmethod
    async def delete_file(
        cls,
        db: AsyncSession,
        file_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        user_role: str = "manager"
    ) -> bool:
        """
        Deletes the file attachment from disk and the database.
        """
        stmt = select(FileAttachment).where(FileAttachment.file_id == file_id)
        res = await db.execute(stmt)
        attachment = res.scalar_one_or_none()
        if not attachment:
            raise NotFoundError(f"File attachment with ID {file_id} not found.")

        # Permission check: Manager can delete anything; otherwise must be original uploader
        if user_role != "manager" and attachment.uploaded_by != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this attachment.")

        # Delete from disk
        file_path = cls._get_base_upload_dir() / attachment.entity_type / attachment.entity_id / attachment.stored_filename
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError:
                pass

        await db.delete(attachment)
        await db.flush()
        return True

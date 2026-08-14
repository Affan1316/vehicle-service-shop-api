import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import FileAttachmentResponse
from app.routers.auth_deps import RoleChecker, get_current_user
from app.services import FileService, AuditService
from app.exceptions import NotFoundError

router = APIRouter(prefix="/files", tags=["File Attachments"])


@router.get(
    "/download/{file_id}",
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))]
)
async def download_file_attachment(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Stream/download a stored file attachment by its file ID.
    """
    try:
        attachment, file_path = await FileService.get_file(db, file_id)
        return FileResponse(
            path=str(file_path),
            filename=attachment.original_filename,
            media_type=attachment.mime_type
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{file_id}",
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def delete_file_attachment(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a file attachment from disk and the database (Manager or original uploader only).
    """
    try:
        await FileService.delete_file(
            db=db,
            file_id=file_id,
            user_id=current_user.user_id,
            user_role=current_user.role
        )
        await AuditService.log_delete(
            db=db,
            entity_type="file_attachment",
            entity_id=str(file_id),
            actor_id=current_user.user_id,
            actor_username=current_user.username
        )
        return {"message": "File attachment successfully deleted."}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=FileAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def upload_file_attachment(
    entity_type: str,
    entity_id: str,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload an inspection photo, repair document, or attachment for an entity (work_order, diagnostic, vehicle, invoice).
    """
    try:
        attachment = await FileService.upload_file(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            file=file,
            user_id=current_user.user_id,
            description=description
        )
        # Log audit trail
        await AuditService.log_create(
            db=db,
            entity_type=f"file_{entity_type}",
            entity_id=str(attachment.file_id),
            actor_id=current_user.user_id,
            actor_username=current_user.username,
            initial_data={"filename": attachment.original_filename, "size": attachment.file_size, "entity_id": entity_id}
        )
        return attachment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{entity_type}/{entity_id}",
    response_model=List[FileAttachmentResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))]
)
async def list_file_attachments(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    List all file attachments associated with a specific entity.
    """
    return await FileService.list_files(db, entity_type, entity_id)

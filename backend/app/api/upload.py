"""API upload file TKB: nhận file, gợi ý ánh xạ cột, xác nhận và lưu vào DB.

Luồng:
  POST   /api/upload                    lưu file, trả headers + gợi ý mapping + xem trước
  POST   /api/upload/confirm            chuẩn hóa theo mapping người dùng chọn, lưu DB
  GET    /api/upload/{file_id}/timetable  đọc lại TimetableData đã lưu
  DELETE /api/upload/{file_id}          xóa file và dữ liệu đã lưu
"""

import logging
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import crud
from app.db.models import UPLOAD_STATUS_CONFIRMED
from app.db.session import get_db
from app.schemas.timetable import (
    ColumnMapping,
    ImportIssue,
    ImportStatus,
    TimetableData,
)
from app.services.parser.adapter import import_timetable
from app.services.parser.grouping import original_headers
from app.services.parser.mapper import find_header_row, select_sheet, suggest_mapping
from app.services.parser.reader import read_spreadsheet
from app.services.parser.timeparse import is_blank, normalize_text
from app.services.parser.validate import REQUIRED_MAPPING_FIELDS, validate_mapping

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".xls", ".xlsx", ".xlsm", ".csv"}
PREVIEW_ROWS = 20
_CHUNK = 1024 * 1024

router = APIRouter(prefix=settings.API_PREFIX, tags=["Upload"])


# --------------------------------------------------------------------------- #
# Schema request / response
# --------------------------------------------------------------------------- #
class UploadResponse(BaseModel):
    file_id: str
    status: ImportStatus  # needs_mapping | needs_confirmation
    sheet: str
    sheets: list[str]
    header_row: int  # 0-based
    headers: list[str]  # đúng thứ tự cột; ô tiêu đề trống là ""
    mapping: dict[str, str | None]  # trường chuẩn -> tên cột gợi ý
    confidence: dict[str, float]
    preview: list[list[str]]  # mỗi dòng cùng độ dài với headers
    issues: list[ImportIssue]


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(min_length=1)
    mapping: ColumnMapping
    semester: str | None = None
    sheet_name: str | None = None  # mặc định: sheet đã chọn lúc upload
    header_row: int | None = Field(default=None, ge=0)  # mặc định: dòng đã nhận diện


class ConfirmResponse(BaseModel):
    file_id: str
    status: ImportStatus  # ready
    timetable: TimetableData
    issues: list[ImportIssue]
    stats: dict[str, int]


# --------------------------------------------------------------------------- #
# Tiện ích
# --------------------------------------------------------------------------- #
def _save_upload(upload: UploadFile, destination: Path) -> int:
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with destination.open("wb") as out:
            while chunk := upload.file.read(_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        413,
                        f"File vượt quá {settings.MAX_UPLOAD_MB} MB",
                    )
                out.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File rỗng")
    return size


def _preview_rows(frame: pd.DataFrame, header_row: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_index in range(header_row + 1, len(frame)):
        values = frame.iloc[row_index].tolist()
        if all(is_blank(v) for v in values):
            continue
        rows.append([normalize_text(v) for v in values])
        if len(rows) >= PREVIEW_ROWS:
            break
    return rows


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Không xóa được file %s", path)


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload file TKB và nhận gợi ý ánh xạ cột",
)
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Chỉ hỗ trợ file .xls, .xlsx, .xlsm, .csv",
        )

    file_id = uuid4().hex
    # Tên lưu trên đĩa do server tạo, không dùng tên người dùng gửi (tránh path traversal).
    destination = settings.UPLOAD_DIR / f"{file_id}{suffix}"
    size = _save_upload(file, destination)

    try:
        frames = read_spreadsheet(destination)
        sheet = select_sheet(frames)
        frame = frames[sheet]
        header_row = find_header_row(frame)
        suggested, confidence = suggest_mapping(frame, header_row)
        issues = validate_mapping(suggested, frame, header_row, sheet)
        headers = original_headers(frame, header_row)
        preview = _preview_rows(frame, header_row)
        missing = [f for f in REQUIRED_MAPPING_FIELDS if getattr(suggested, f) is None]

        crud.create_uploaded_file(
            db,
            file_id=file_id,
            original_name=original_name,
            stored_path=str(destination),
            size_bytes=size,
            sheet_name=sheet,
            header_row=header_row,
        )
    except ImportError as exc:
        _unlink(destination)
        logger.exception("Thiếu thư viện đọc file")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except ValueError as exc:
        _unlink(destination)
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        _unlink(destination)
        db.rollback()
        logger.exception("Không xử lý được file upload")
        raise HTTPException(
            422,
            "Không đọc được file. File có thể bị hỏng hoặc không đúng định dạng.",
        ) from exc

    return UploadResponse(
        file_id=file_id,
        status=ImportStatus.NEEDS_MAPPING if missing else ImportStatus.NEEDS_CONFIRMATION,
        sheet=sheet,
        sheets=list(frames),
        header_row=header_row,
        headers=headers,
        mapping=suggested.model_dump(),
        confidence=confidence,
        preview=preview,
        issues=issues,
    )


@router.post(
    "/upload/confirm",
    response_model=ConfirmResponse,
    summary="Xác nhận ánh xạ cột, chuẩn hóa và lưu thời khóa biểu",
)
def confirm_mapping(
    request: ConfirmRequest,
    db: Session = Depends(get_db),
) -> ConfirmResponse:
    record = crud.get_uploaded_file(db, request.file_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy file_id")

    path = Path(record.stored_path)
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, "File gốc không còn trên máy chủ")

    sheet_name = request.sheet_name or record.sheet_name
    header_row = request.header_row if request.header_row is not None else record.header_row

    try:
        result = import_timetable(
            path,
            sheet_name=sheet_name,
            mapping=request.mapping,
            confirmed_mapping=True,
            semester=request.semester,
            header_row=header_row,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    if result.status is not ImportStatus.READY or result.timetable is None:
        raise HTTPException(
            422,
            detail={
                "message": "Ánh xạ cột không hợp lệ hoặc không dựng được thời khóa biểu",
                "issues": [issue.model_dump() for issue in result.issues],
            },
        )

    crud.save_timetable(
        db,
        request.file_id,
        result.timetable,
        request.mapping,
        sheet_name=sheet_name,
        header_row=header_row,
    )
    return ConfirmResponse(
        file_id=request.file_id,
        status=result.status,
        timetable=result.timetable,
        issues=result.issues,
        stats=result.stats,
    )


@router.get(
    "/upload/{file_id}/timetable",
    response_model=TimetableData,
    summary="Đọc lại thời khóa biểu đã lưu",
)
def get_saved_timetable(file_id: str, db: Session = Depends(get_db)) -> TimetableData:
    record = crud.get_uploaded_file(db, file_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy file_id")
    if record.status != UPLOAD_STATUS_CONFIRMED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "File chưa được xác nhận ánh xạ cột"
        )
    timetable = crud.get_timetable(db, file_id)
    if timetable is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không có dữ liệu thời khóa biểu")
    return timetable


@router.delete(
    "/upload/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa file và dữ liệu đã lưu",
)
def delete_upload(file_id: str, db: Session = Depends(get_db)) -> None:
    stored_path = crud.delete_uploaded_file(db, file_id)
    if stored_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy file_id")
    _unlink(Path(stored_path))
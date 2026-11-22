"""Điều phối luồng đọc, ánh xạ, chuẩn hóa, kiểm tra và tổng hợp kết quả import thời khóa biểu."""

from collections import Counter
from pathlib import Path

from app.schemas.timetable import (
    ColumnMapping,
    ImportIssue,
    ImportStatus,
    TimetableImportResult,
)
from app.services.parser.grouping import frame_to_timetable
from app.services.parser.mapper import find_header_row, select_sheet, suggest_mapping
from app.services.parser.mapper import normalize_header
from app.services.parser.reader import read_spreadsheet
from app.services.parser.validate import (
    REQUIRED_MAPPING_FIELDS,
    get_preview,
    validate_mapping,
    validate_timetable,
)

MAX_ISSUES_PER_CODE = 50


def _has_errors(issues: list[ImportIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _cap_issues(
    issues: list[ImportIssue], sheet: str | None, per_code: int = MAX_ISSUES_PER_CODE
) -> list[ImportIssue]:
    """Giữ tối đa ``per_code`` cảnh báo mỗi loại, phần còn lại gộp thành một dòng tóm tắt."""
    seen: Counter[str] = Counter()
    kept: list[ImportIssue] = []
    for issue in issues:
        seen[issue.code] += 1
        if seen[issue.code] <= per_code:
            kept.append(issue)
    for code, total in seen.items():
        if total > per_code:
            kept.append(
                ImportIssue(
                    code=code,
                    message=f"... và {total - per_code} cảnh báo {code} khác chưa hiển thị",
                    sheet=sheet,
                    severity="info",
                )
            )
    return kept


def _confidence_for(
    effective: ColumnMapping,
    suggested: ColumnMapping,
    suggested_confidence: dict[str, float],
) -> dict[str, float]:
    """Cột do người dùng chọn khác gợi ý thì độ tin cậy là 1.0 (đã tự xác nhận)."""
    result: dict[str, float] = {}
    for field, value in effective.model_dump().items():
        if not value:
            continue
        same = normalize_header(value) == normalize_header(getattr(suggested, field) or "")
        result[field] = suggested_confidence.get(field, 1.0) if same else 1.0
    return result


def import_timetable(
    path: str | Path,
    *,
    sheet_name: str | int | None = None,
    mapping: ColumnMapping | dict[str, str | None] | None = None,
    confirmed_mapping: bool = False,
    semester: str | None = None,
    header_row: int | None = None,
) -> TimetableImportResult:
    """Import a spreadsheet through the normalized timetable schema.

    Luồng: không có mapping -> NEEDS_MAPPING / NEEDS_CONFIRMATION (kèm gợi ý);
    có mapping nhưng chưa xác nhận -> NEEDS_CONFIRMATION; có mapping và
    ``confirmed_mapping=True`` -> READY (kèm cảnh báo dữ liệu nếu có) hoặc FAILED.
    """

    frames = read_spreadsheet(path, sheet_name=sheet_name)
    selected_sheet = next(iter(frames)) if sheet_name is not None else select_sheet(frames)
    frame = frames[selected_sheet]
    if header_row is None:
        header_row = find_header_row(frame)
    elif not 0 <= header_row < len(frame):
        raise ValueError(f"header_row {header_row} nằm ngoài sheet ({len(frame)} dòng)")
    preview = get_preview(frame, header_row)

    suggested_mapping, suggested_confidence = suggest_mapping(frame, header_row)

    if mapping is None:
        missing = [
            field
            for field in REQUIRED_MAPPING_FIELDS
            if getattr(suggested_mapping, field) is None
        ]
        return TimetableImportResult(
            status=ImportStatus.NEEDS_MAPPING if missing else ImportStatus.NEEDS_CONFIRMATION,
            suggested_mapping=suggested_mapping,
            confidence=suggested_confidence,
            preview=preview,
            issues=validate_mapping(suggested_mapping, frame, header_row, selected_sheet),
        )

    effective_mapping = (
        mapping if isinstance(mapping, ColumnMapping) else ColumnMapping.model_validate(mapping)
    )
    confidence = _confidence_for(effective_mapping, suggested_mapping, suggested_confidence)
    mapping_issues = validate_mapping(effective_mapping, frame, header_row, selected_sheet)
    if _has_errors(mapping_issues):
        return TimetableImportResult(
            status=ImportStatus.FAILED,
            suggested_mapping=effective_mapping,
            confidence=confidence,
            preview=preview,
            issues=mapping_issues,
        )

    if not confirmed_mapping:
        return TimetableImportResult(
            status=ImportStatus.NEEDS_CONFIRMATION,
            suggested_mapping=effective_mapping,
            confidence=confidence,
            preview=preview,
            issues=mapping_issues,
        )

    try:
        timetable, normalize_issues = frame_to_timetable(
            frame,
            header_row,
            effective_mapping,
            semester=semester,
            sheet=selected_sheet,
        )
    except (ValueError, KeyError) as exc:
        return TimetableImportResult(
            status=ImportStatus.FAILED,
            suggested_mapping=effective_mapping,
            confidence=confidence,
            preview=preview,
            issues=[
                ImportIssue(
                    code="NORMALIZATION_ERROR",
                    message=str(exc),
                    sheet=selected_sheet,
                )
            ],
        )

    all_issues = mapping_issues + normalize_issues + validate_timetable(timetable, selected_sheet)
    meetings = [m for c in timetable.courses for s in c.sections for m in s.meetings]
    counts = Counter(issue.code for issue in all_issues)
    stats = {
        "courses": len(timetable.courses),
        "sections": sum(len(c.sections) for c in timetable.courses),
        "meetings": len(meetings),
        "unconfirmed_meetings": sum(1 for m in meetings if not m.schedule_confirmed),
        "skipped_rows": counts.get("SKIPPED_ROW", 0),
        "warnings": sum(1 for i in all_issues if i.severity == "warning"),
    }

    return TimetableImportResult(
        status=ImportStatus.READY,
        timetable=timetable,
        suggested_mapping=effective_mapping,
        confidence=confidence,
        preview=preview,
        issues=_cap_issues(all_issues, selected_sheet),
        stats=stats,
    )
"""Nhận diện dòng tiêu đề, chọn sheet phù hợp và gợi ý ánh xạ cột dữ liệu sang schema chuẩn."""

import re
from functools import lru_cache

import pandas as pd

from app.schemas.timetable import ColumnMapping
from app.services.parser.timeparse import fold_text, normalize_text


def normalize_header(value: object) -> str:
    """Chữ thường, bỏ dấu (kể cả đ), gọn khoảng trắng; ô trống/NaN -> ""."""
    return fold_text(value)


FIELD_RULES: dict[str, tuple[str, ...]] = {
    "course_id": (
        "ma hoc phan",
        "ma hp",
        "ma mon",
        "ma mon hoc",
        "course code",
        "course_id",
        "course id",
    ),
    "course_name": (
        "ten hoc phan",
        "ten mon",
        "ten mon hoc",
        "mon",
        "mon hoc",
        "course name",
        "subject",
    ),
    "section_id": (
        "ma lop hoc phan",
        "ma lop doc lap tren he thong euni",
        "ma lop",
        "ma lhp",
        "lop hoc phan",
        "class code",
        "section",
    ),
    "weekday": (
        "ngay hoc",
        "thu trong tuan",
        "thu",
        "weekday",
        "day",
    ),
    "time": (
        "tiet hoc",
        "tiet",
        "ca hoc",
        "ca",
        "period",
        "gio hoc",
        "time",
        "thoi gian",
    ),
    "location": (
        "dia diem",
        "phong hoc",
        "phong",
        "room",
        "location",
    ),
    "lecturer": (
        "giang vien",
        "gv",
        "lecturer",
        "instructor",
        "teacher",
    ),
    "component": (
        "lt/bt/th",
        "loai",
        "thanh phan",
        "lt th",
        "component",
    ),
    "delivery": (
        "hinh thuc",
        "hoc truc tuyen",
        "delivery",
        "online",
    ),
}

_MAX_HEADER_LENGTH = 80  # ô dài hơn mức này gần như chắc chắn là dữ liệu


@lru_cache(maxsize=None)
def _alias_regex(alias: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])")


def _row_headers(frame: pd.DataFrame, row_index: int) -> list[str]:
    return [normalize_header(value) for value in frame.iloc[row_index].tolist()]


def _assign_fields(headers: list[str]) -> dict[str, tuple[int, float]]:
    """Gán mỗi trường cho đúng một cột (và mỗi cột cho tối đa một trường).

    Khớp theo token nguyên vẹn nên "ca" không khớp "dia diem", "thu" không khớp
    "thuc hanh". Cặp (trường, cột) có điểm cao nhất được gán trước.
    """
    candidates: list[tuple[float, int, int, str, int]] = []
    for position, header in enumerate(headers):
        if not header or len(header) > _MAX_HEADER_LENGTH:
            continue
        for field, aliases in FIELD_RULES.items():
            best: tuple[float, int] | None = None
            for alias in aliases:
                if alias == header:
                    key = (1.0, len(alias))
                elif _alias_regex(alias).search(header):
                    key = (0.85, len(alias))
                else:
                    continue
                if best is None or key > best:
                    best = key
            if best is not None:
                candidates.append((best[0], best[1], -position, field, position))

    candidates.sort(reverse=True)
    assigned: dict[str, tuple[int, float]] = {}
    used_columns: set[int] = set()
    for score, _, _, field, position in candidates:
        if field in assigned or position in used_columns:
            continue
        assigned[field] = (position, score)
        used_columns.add(position)
    return assigned


def _row_score(headers: list[str]) -> float:
    return sum(score for _, score in _assign_fields(headers).values())


def find_header_row(frame: pd.DataFrame, max_rows: int = 30) -> int:
    best_row = 0
    best_score = -1.0
    for row_index in range(min(max_rows, len(frame))):
        score = _row_score(_row_headers(frame, row_index))
        if score > best_score:
            best_row, best_score = row_index, score
    return best_row


def suggest_mapping(
    frame: pd.DataFrame, header_row: int | None = None
) -> tuple[ColumnMapping, dict[str, float]]:
    if header_row is None:
        header_row = find_header_row(frame)

    headers = _row_headers(frame, header_row)
    mapping: dict[str, str | None] = {field: None for field in FIELD_RULES}
    confidence: dict[str, float] = {}
    for field, (position, score) in _assign_fields(headers).items():
        mapping[field] = normalize_text(frame.iloc[header_row, position])
        confidence[field] = score
    return ColumnMapping(**mapping), confidence


def select_sheet(frames: dict[str, pd.DataFrame]) -> str:
    if not frames:
        raise ValueError("Không có sheet nào để chọn")
    best_sheet = next(iter(frames))
    best_score = -1.0
    for name, frame in frames.items():
        if frame.empty:
            continue
        score = _row_score(_row_headers(frame, find_header_row(frame)))
        if score > best_score:
            best_sheet, best_score = name, score
    return best_sheet


def split_data_frame(frame: pd.DataFrame, header_row: int) -> pd.DataFrame:
    data = frame.iloc[header_row + 1 :].copy()
    data.columns = _row_headers(frame, header_row)
    return data.dropna(how="all")


def source_column_name(
    frame: pd.DataFrame, header_row: int, canonical: str
) -> str | None:
    mapping, _ = suggest_mapping(frame, header_row)
    return getattr(mapping, canonical)
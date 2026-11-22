"""Đọc và cắt biên dữ liệu thô từ các tệp CSV và Excel (.xls, .xlsx, .xlsm)."""

import codecs
import csv
import io
from pathlib import Path

import numpy as np
import pandas as pd

from app.services.parser.timeparse import is_blank


def _decode_csv(raw: bytes) -> str:
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1258", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _read_csv(source: Path) -> pd.DataFrame:
    text = _decode_csv(source.read_bytes())
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text, newline=""), dialect))
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        raise ValueError("File CSV rỗng")
    data = [
        [cell if cell.strip() else None for cell in row] + [None] * (width - len(row))
        for row in rows
    ]
    return pd.DataFrame(data, dtype=object)


def _trim(frame: pd.DataFrame) -> pd.DataFrame:
    """Cắt dòng/cột trống ở cuối. Không đổi vị trí dòng nên số dòng Excel vẫn đúng."""
    if frame.empty:
        return frame
    filled = frame.apply(lambda column: column.map(lambda v: not is_blank(v)))
    rows = np.flatnonzero(filled.any(axis=1).to_numpy())
    cols = np.flatnonzero(filled.any(axis=0).to_numpy())
    if len(rows) == 0:
        return frame.iloc[0:0]
    return frame.iloc[: rows[-1] + 1, : cols[-1] + 1]


def read_spreadsheet(
    path: str | Path,
    sheet_name: str | int | None = None,
) -> dict[str, pd.DataFrame]:
    """Đọc CSV/XLS/XLSX thành {tên sheet: DataFrame thô}, không giả định header.

    - Ô trống là NaN/None (xử lý thống nhất bằng ``is_blank``).
    - ``sheet_name`` có thể là tên hoặc chỉ số; khóa trả về luôn là tên sheet thật.
    - Sheet rỗng bị bỏ qua.
    """

    source = Path(path)
    suffix = source.suffix.lower()
    if not source.exists():
        raise FileNotFoundError(source)

    if suffix == ".csv":
        frame = _trim(_read_csv(source))
        if frame.empty:
            raise ValueError("Không tìm thấy dữ liệu trong file")
        return {"Sheet1": frame}

    if suffix not in {".xls", ".xlsx", ".xlsm"}:
        raise ValueError("Supported file types: .xls, .xlsx, .xlsm, .csv")

    try:
        workbook = pd.ExcelFile(source)
    except ImportError as exc:
        raise ImportError(
            f"Missing spreadsheet reader for {suffix}. Install openpyxl for XLSX "
            "and xlrd for legacy XLS."
        ) from exc

    with workbook:
        names = [str(name) for name in workbook.sheet_names]
        if sheet_name is None:
            targets = names
        elif isinstance(sheet_name, int):
            if not -len(names) <= sheet_name < len(names):
                raise ValueError(f"Không có sheet số {sheet_name}. Các sheet: {names}")
            targets = [names[sheet_name]]
        elif sheet_name in names:
            targets = [sheet_name]
        else:
            raise ValueError(f"Không có sheet '{sheet_name}'. Các sheet: {names}")

        result: dict[str, pd.DataFrame] = {}
        for name in targets:
            frame = _trim(workbook.parse(name, header=None, dtype=object))
            if not frame.empty:
                result[name] = frame

    if not result:
        raise ValueError("Không tìm thấy dữ liệu trong file")
    return result
"""Chuẩn hóa văn bản, thứ trong tuần và tiết/ca/giờ học từ ô Excel thô."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time

from app.schemas.timetable import TimeUnit, Weekday

MAX_PERIOD = 20
MAX_CA = 10
_SANITY_LIMIT = 100  # không bung khoảng lớn hơn mức này

_RANGE_SEP = r"(?:-|–|—|~|(?<![a-z])(?:den|toi|to)(?![a-z]))"
_NO_TIME = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "tba",
    "tbd",
    "online",
    "onl",
    "chua co",
    "thong bao",
    "thong bao sau",
}


# --------------------------------------------------------------------------- #
# Văn bản cơ bản
# --------------------------------------------------------------------------- #
def is_blank(value: object) -> bool:
    """True với None, NaN, NaT, pd.NA và chuỗi chỉ gồm khoảng trắng."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(value != value)  # NaN/NaT
    except (TypeError, ValueError):  # pd.NA
        return True


def normalize_text(value: object) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, datetime):
        text = value.isoformat(sep=" ")
    elif isinstance(value, date):
        text = value.isoformat()
    elif isinstance(value, time):
        text = value.strftime("%H:%M")
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))  # 7.0 -> "7"
    else:
        text = str(value)
    return re.sub(r"[\s\u200b\ufeff]+", " ", text).strip()


def fold_text(value: object) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (kể cả đ), gọn khoảng trắng."""
    text = unicodedata.normalize("NFD", normalize_text(value).lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d")


# --------------------------------------------------------------------------- #
# Đơn vị thời gian
# --------------------------------------------------------------------------- #
_PERIOD_RE = re.compile(r"(?<![a-z])(?:tiet|period)(?![a-z])")
# "ca" phải kiểm tra trên chữ còn dấu: bỏ dấu thì "cả"/"cá" cũng thành "ca".
_CA_RE = re.compile(r"(?<!\w)ca(?!\w)")
_GIO_RE = re.compile(r"(?<![a-z])gio(?![a-z])")
_CLOCK_RE = re.compile(r"(?<!\d)\d{1,2}\s*(?::|h(?![a-z])|gio)|(?<![a-z])gio(?![a-z])")


def _has_ca_word(value: object) -> bool:
    raw = unicodedata.normalize("NFC", normalize_text(value)).lower()
    return bool(_CA_RE.search(raw))


def parse_time_unit(value: object, hint: str | None = None) -> TimeUnit:
    """Nội dung ô được ưu tiên; tiêu đề cột (hint) chỉ dùng khi ô không nói rõ."""
    text = fold_text(value)
    if _PERIOD_RE.search(text):
        return TimeUnit.PERIOD
    if _has_ca_word(value):
        return TimeUnit.CA
    if _CLOCK_RE.search(text):
        return TimeUnit.CLOCK

    hint_text = fold_text(hint)
    if _PERIOD_RE.search(hint_text):
        return TimeUnit.PERIOD
    if _has_ca_word(hint):
        return TimeUnit.CA
    if _GIO_RE.search(hint_text):
        return TimeUnit.CLOCK
    return TimeUnit.PERIOD


# --------------------------------------------------------------------------- #
# Tiết / ca / giờ
# --------------------------------------------------------------------------- #
@dataclass
class ParsedTime:
    """Kết quả phân tích ô thời gian.

    ``warnings``/``errors`` là các mã (xem validate.py). Khi có lỗi nghiêm trọng
    (INVALID_TIME_RANGE, UNPARSEABLE_TIME) start/end để None.
    """

    start: int | None = None
    end: int | None = None
    unit: TimeUnit = TimeUnit.PERIOD
    periods: list[int] = field(default_factory=list)
    start_minute: int | None = None
    end_minute: int | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.start is None


_PERIOD_TOKEN = re.compile(rf"(\d+)(?:\s*{_RANGE_SEP}\s*(\d+))?")
_CLOCK_PIECE = re.compile(r"(\d{1,2})(?:\s*(?::|h|gio)\s*(\d{1,2})?)?")
_ISO_DATE_RE = re.compile(
    r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$"
)


def _fill_periods(numbers: set[int], unit: TimeUnit, result: ParsedTime) -> None:
    if not numbers:
        if not result.errors:
            result.errors.append("UNPARSEABLE_TIME")
        return
    periods = sorted(numbers)
    limit = MAX_CA if unit is TimeUnit.CA else MAX_PERIOD
    if periods[0] < 1 or periods[-1] > limit:
        result.errors.append("TIME_OUT_OF_RANGE")
    result.periods = periods
    result.start = periods[0]
    result.end = periods[-1]


def _parse_periods(text: str, unit: TimeUnit, result: ParsedTime) -> None:
    text = re.sub(r"(\d+)\.0+(?!\d)", r"\1", text)  # "7.0" -> "7"
    numbers: set[int] = set()
    for match in _PERIOD_TOKEN.finditer(text):
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) else first
        if last < first:
            result.errors.append("INVALID_TIME_RANGE")
            continue
        if last > _SANITY_LIMIT:
            numbers.update({first, last})
        else:
            numbers.update(range(first, last + 1))
    _fill_periods(numbers, unit, result)


def _clock_result(hour: int, minute: int) -> ParsedTime:
    total = hour * 60 + minute
    return ParsedTime(
        start=hour, end=hour, unit=TimeUnit.CLOCK, start_minute=total, end_minute=total
    )


def _parse_clock(text: str, result: ParsedTime) -> None:
    minutes: list[int] = []
    for piece in re.split(rf"\s*{_RANGE_SEP}\s*", text, maxsplit=1):
        match = _CLOCK_PIECE.search(piece)
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if hour > 23 or minute > 59:
            result.errors.append("TIME_OUT_OF_RANGE")
            return
        minutes.append(hour * 60 + minute)
    if not minutes:
        result.errors.append("UNPARSEABLE_TIME")
        return
    start_minute, end_minute = minutes[0], minutes[-1]
    if end_minute < start_minute:
        result.errors.append("INVALID_TIME_RANGE")
        return
    result.start_minute = start_minute
    result.end_minute = end_minute
    result.start = start_minute // 60
    result.end = end_minute // 60


def _from_converted_date(month: int, day: int, unit_hint: str | None) -> ParsedTime:
    """Excel đã đổi "1-3" thành ngày. Khôi phục lại khoảng tiết (nhỏ - lớn).

    Không phân biệt được "1-3" được hiểu là tháng-ngày hay ngày-tháng nên lấy
    min/max của hai số; luôn kèm cảnh báo DATE_CONVERTED để người dùng kiểm tra.
    """
    unit = parse_time_unit("", unit_hint)
    if unit is TimeUnit.CLOCK:
        unit = TimeUnit.PERIOD
    low, high = sorted((month, day))
    result = ParsedTime(unit=unit, warnings=["DATE_CONVERTED"])
    _fill_periods(set(range(low, high + 1)), unit, result)
    return result


def parse_time_range(value: object, unit_hint: str | None = None) -> ParsedTime:
    if isinstance(value, datetime):
        if value.year <= 1900 and (value.hour or value.minute):  # ô giờ của Excel
            return _clock_result(value.hour, value.minute)
        return _from_converted_date(value.month, value.day, unit_hint)
    if isinstance(value, date):
        return _from_converted_date(value.month, value.day, unit_hint)
    if isinstance(value, time):
        return _clock_result(value.hour, value.minute)

    text = normalize_text(value)
    iso = _ISO_DATE_RE.match(text)
    if iso:
        return _from_converted_date(int(iso.group(2)), int(iso.group(3)), unit_hint)

    folded = fold_text(text)
    unit = parse_time_unit(text, unit_hint)
    if folded in _NO_TIME or "thong bao" in folded:
        return ParsedTime(unit=unit)

    cleaned = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", folded)  # bỏ chú thích "(P.301)"
    result = ParsedTime(unit=unit)
    if unit is TimeUnit.CLOCK:
        _parse_clock(cleaned, result)
    else:
        _parse_periods(cleaned, unit, result)
    return result


# --------------------------------------------------------------------------- #
# Thứ trong tuần
# --------------------------------------------------------------------------- #
_NAME_TO_NUMBER = {"hai": 2, "ba": 3, "tu": 4, "nam": 5, "sau": 6, "bay": 7}
_LABELED = re.compile(
    r"(?P<cn>chu\s*nhat|(?<![a-z])cn(?![a-z]))"
    r"|thu\s*(?:(?P<d1>[2-8])(?!\d)|(?P<name>hai|ba|tu|nam|sau|bay)(?![a-z]))"
    r"|(?<![a-z])t\s*(?P<d2>[2-8])(?!\d)"
)
_BARE = re.compile(r"(?<!\d)([2-8])(?!\d)")
_RANGE_RE = re.compile(r"-|–|—|~|(?<![a-z])(?:den|toi)(?![a-z])")


def _prepare_weekday_text(value: object) -> str:
    text = re.sub(r"\([^)]*\)", " ", fold_text(value))
    # "thu 2, 4, 6" -> "thu 2, thu 4, thu 6"
    text = re.sub(
        r"thu\s*([2-8](?:\s*(?:,|;|/|&|\+|va)\s*[2-8])+)(?!\d)",
        lambda m: ", ".join(f"thu {n}" for n in re.findall(r"[2-8]", m.group(1))),
        text,
    )
    # "thu 2 - 4" -> "thu 2 - thu 4"
    return re.sub(rf"thu\s*([2-8])(\s*{_RANGE_SEP}\s*)(?=[2-8])", r"thu \1\2thu ", text)


def _token_number(match: re.Match[str]) -> int:
    if match.group("cn"):
        return 8
    if match.group("d1"):
        return int(match.group("d1"))
    if match.group("name"):
        return _NAME_TO_NUMBER[match.group("name")]
    return int(match.group("d2"))


def parse_weekdays(value: object) -> list[Weekday]:
    """Hỗ trợ "Thứ 2", "2", "T2", "CN", "Thứ 2, 4", "Thứ 2 đến Thứ 4", "2-4"."""
    text = _prepare_weekday_text(value)
    if not text or "thong bao" in text:
        return []

    labeled = list(_LABELED.finditer(text))
    if labeled:
        numbers = [_token_number(match) for match in labeled]
    else:
        numbers = [int(match.group(1)) for match in _BARE.finditer(text)]
    if not numbers:
        return []

    if len(numbers) == 2 and numbers[0] < numbers[1] and _RANGE_RE.search(text):
        numbers = list(range(numbers[0], numbers[1] + 1))

    unique = list(dict.fromkeys(numbers))
    return [Weekday(number) for number in unique]


def parse_weekday(value: object) -> Weekday | None:
    weekdays = parse_weekdays(value)
    return weekdays[0] if weekdays else None
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta


def parse_dt(value: str | None) -> datetime | None:
    """
    Parse yyyymmdd hoặc yyyymmddHHMM.
    Cho phép NGAY_SINH dạng yyyy00000000 / yyyy0000xxxx (tháng/ngày = 00).
    """
    if value is None:
        return None
    v = str(value).strip()
    if not v.isdigit():
        return None
    if len(v) == 8:
        return _parse_ymd(v, allow_zero_md=True)
    if len(v) == 12:
        dt = _parse_ymd(v[:8], allow_zero_md=True)
        if dt is None:
            return None
        hh, mm = int(v[8:10]), int(v[10:12])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        # tháng/ngày 00 → chỉ so sánh năm (giữ 01-01 tạm để order year-level)
        if v[4:8] == "0000":
            return datetime(int(v[:4]), 1, 1, hh, mm)
        return dt.replace(hour=hh, minute=mm)
    return None


def _parse_ymd(ymd: str, *, allow_zero_md: bool) -> datetime | None:
    if len(ymd) != 8 or not ymd.isdigit():
        return None
    y, m, d = int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])
    if not (1900 <= y <= 2100):
        return None
    if allow_zero_md and m == 0 and d == 0:
        return datetime(y, 1, 1)
    if allow_zero_md and m != 0 and d == 0:
        # chỉ có tháng — dùng ngày 1
        if not (1 <= m <= 12):
            return None
        return datetime(y, m, 1)
    if not (1 <= m <= 12):
        return None
    max_d = monthrange(y, m)[1]
    if not (1 <= d <= max_d):
        return None
    return datetime(y, m, d)


def valid_dt(value: str | None, *, expect_len: int | None = None) -> bool:
    if value is None:
        return False
    v = str(value).strip()
    if expect_len is not None and len(v) != expect_len:
        return False
    if len(v) == 8:
        return _parse_ymd(v, allow_zero_md=True) is not None
    if len(v) == 12:
        return parse_dt(v) is not None
    return False


def as_date(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, dt.day)


def days_inclusive(a: datetime, b: datetime) -> int:
    return (as_date(b) - as_date(a)).days + 1


def fmt(dt: datetime, length: int = 12) -> str:
    if length == 8:
        return dt.strftime("%Y%m%d")
    return dt.strftime("%Y%m%d%H%M")


def now_floor_minute() -> datetime:
    n = datetime.now()
    return n.replace(second=0, microsecond=0)


def within_range(
    value: datetime,
    start: datetime | None,
    end: datetime | None,
    *,
    by_date: bool = False,
) -> bool:
    """True nếu value nằm trong [start, end] (bỏ qua cạnh None)."""
    v = as_date(value) if by_date else value
    if start is not None:
        s = as_date(start) if by_date else start
        if v < s:
            return False
    if end is not None:
        e = as_date(end) if by_date else end
        if v > e:
            return False
    return True

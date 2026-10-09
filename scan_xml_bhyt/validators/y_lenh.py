from __future__ import annotations

from ..models import ValidationIssue
from .common import is_empty
from .timeutil import valid_dt


def _req(record: dict[str, str], field: str) -> str:
    return (record.get(field) or "").strip()


def _issue(
    *,
    file: str,
    loai: str,
    record_index: int,
    field: str,
    code: str,
    message: str,
    value: str = "",
) -> ValidationIssue:
    return ValidationIssue(
        file=file,
        severity="error",
        loai_hoso=loai,
        record_index=record_index,
        field=field,
        code=code,
        message=message,
        value=value,
    )


def _check_format(
    *,
    file: str,
    loai: str,
    record_index: int,
    field: str,
    value: str,
) -> list[ValidationIssue]:
    """Bắt buộc để schema; chỉ kiểm tra format khi có giá trị."""
    if is_empty(value):
        return []
    if not valid_dt(value, expect_len=12):
        return [
            _issue(
                file=file,
                loai=loai,
                record_index=record_index,
                field=field,
                code=f"{field}_FORMAT",
                message=f"{field} phải gồm 12 ký tự yyyymmddHHMM hợp lệ",
                value=value,
            )
        ]
    return []


def check_y_lenh_xml2(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    return _check_format(
        file=file,
        loai="XML2",
        record_index=record_index,
        field="NGAY_YL",
        value=_req(record, "NGAY_YL"),
    )


def check_y_lenh_xml3(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(
        _check_format(
            file=file,
            loai="XML3",
            record_index=record_index,
            field="NGAY_YL",
            value=_req(record, "NGAY_YL"),
        )
    )
    issues.extend(
        _check_format(
            file=file,
            loai="XML3",
            record_index=record_index,
            field="NGAY_TH_YL",
            value=_req(record, "NGAY_TH_YL"),
        )
    )
    return issues

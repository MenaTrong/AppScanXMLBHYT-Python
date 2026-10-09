from __future__ import annotations

import re

from ..models import ValidationIssue
from .common import is_empty

# GPHN/CCHN: 0020544/HCM-CCHN, 0009100/ĐNAI-CCHN, 4078/TNI-CCHN
RE_GPHN = re.compile(
    r"^\d{3,12}/[\wÀ-ỹĐđ]{1,15}-(CCHN|GPHN)$",
    re.IGNORECASE | re.UNICODE,
)
RE_THUC_HANH = re.compile(
    r"^(\d{3,12}/[\wÀ-ỹĐđ]{1,15}-(?:CCHN|GPHN))\.(\d{12})$",
    re.IGNORECASE | re.UNICODE,
)
RE_TX_HD = re.compile(
    r"^(\d{3,12}/[\wÀ-ỹĐđ]{1,15}-(?:CCHN|GPHN))\.(TX|HD)\.([0-9A-Za-z]{2,10})$",
    re.IGNORECASE | re.UNICODE,
)

# Portal/BHXH bắt buộc MA_BAC_SI trên các bảng này
REQUIRED_MA_BAC_SI = {"XML2", "XML3", "XML13", "XML14"}
# NGUOI_THUC_HIEN bắt buộc tuyệt đối
REQUIRED_NGUOI_THUC_HIEN = {"XML5"}

# Field dạng GPHN/CCHN — kiểm tra format khi có giá trị
GPHN_FIELDS_BY_LOAI: dict[str, tuple[str, ...]] = {
    "XML1": ("MA_TTDV",),
    "XML2": ("MA_BAC_SI",),
    "XML3": ("MA_BAC_SI", "NGUOI_THUC_HIEN"),
    "XML4": ("MA_BS_DOC_KQ",),
    "XML5": ("NGUOI_THUC_HIEN",),
    "XML6": ("MA_BAC_PHAC_DO", "MA_BAC_PHAC_DO_BD"),
    "XML7": ("MA_BS", "MA_TTDV"),
    "XML8": ("MA_TTDV",),
    "XML9": ("MA_TTDV",),
    "XML10": ("MA_BS", "MA_TTDV"),
    "XML11": ("MA_BS", "MA_TTDV"),
    "XML13": ("MA_BAC_SI", "MA_TTDV"),
    "XML14": ("MA_BAC_SI", "MA_TTDV"),
}


def _issue(
    *,
    file: str,
    loai: str,
    record_index: int,
    field: str,
    code: str,
    message: str,
    value: str,
    severity: str = "error",
) -> ValidationIssue:
    return ValidationIssue(
        file=file,
        severity=severity,
        loai_hoso=loai,
        record_index=record_index,
        field=field,
        code=code,
        message=message,
        value=value,
    )


def validate_one_gphn(token: str, field: str = "MA_BAC_SI") -> str | None:
    t = token.strip()
    if not t:
        return f"{field} rỗng"

    if RE_GPHN.match(t):
        return None

    m_th = RE_THUC_HANH.match(t)
    if m_th:
        cccd = m_th.group(2)
        if not cccd.startswith("0"):
            return (
                f"CCCD trong {field} nên bắt đầu bằng 0 (gặp {cccd})"
            )
        return None

    m_tx = RE_TX_HD.match(t)
    if m_tx:
        suffix = m_tx.group(3)
        kind = m_tx.group(2).upper()
        if re.fullmatch(r"\d{5}", suffix) or suffix == "00":
            return None
        if kind == "HD" and re.fullmatch(r"\d{2}XXX", suffix, re.IGNORECASE):
            return None
        if re.fullmatch(r"[0-9A-Za-z]{2,10}", suffix):
            return None
        return f"Hậu tố .{kind}.{suffix} không hợp lệ (cần mã CSKCB/tỉnh)"

    return (
        f"{field} không đúng định dạng GPHN/CCHN "
        f"(ví dụ 0020544/HCM-CCHN): {t}"
    )


def validate_gphn_value(value: str, field: str = "MA_BAC_SI") -> list[str]:
    errors: list[str] = []
    raw_parts = [p.strip() for p in value.split(";")]
    if any(not p for p in raw_parts):
        errors.append(f"{field} có đoạn rỗng giữa dấu ';'")
    tokens = [p for p in raw_parts if p]
    if not tokens:
        errors.append(f"{field} rỗng")
        return errors
    for tok in tokens:
        err = validate_one_gphn(tok, field=field)
        if err:
            errors.append(err)
    return errors


# backward-compatible aliases
validate_one_ma_bac_si = validate_one_gphn
validate_ma_bac_si_value = validate_gphn_value


def check_ma_bac_si(
    *,
    file: str,
    loai: str,
    record_index: int,
    record: dict[str, str],
) -> list[ValidationIssue]:
    """Chỉ kiểm tra định dạng GPHN. Bắt buộc để schema_3176 (SCHEMA_REQUIRED)."""
    if loai not in REQUIRED_MA_BAC_SI:
        return []

    value = (record.get("MA_BAC_SI") or "").strip()
    if is_empty(value):
        return []

    issues: list[ValidationIssue] = []
    for msg in validate_gphn_value(value, field="MA_BAC_SI"):
        issues.append(
            _issue(
                file=file,
                loai=loai,
                record_index=record_index,
                field="MA_BAC_SI",
                code="MA_BAC_SI_FORMAT",
                message=msg,
                value=value,
            )
        )
    return issues


def check_nguoi_thuc_hien(
    *,
    file: str,
    loai: str,
    record_index: int,
    record: dict[str, str],
    required: bool = False,
) -> list[ValidationIssue]:
    """Định dạng GPHN. Bắt buộc để schema (XML5 x / XML3 theo nhóm + notes K.*).

    `required=True` chỉ dùng khi schema chưa cover (fallback).
    """
    value = (record.get("NGUOI_THUC_HIEN") or "").strip()
    issues: list[ValidationIssue] = []

    if is_empty(value):
        if required:
            issues.append(
                _issue(
                    file=file,
                    loai=loai,
                    record_index=record_index,
                    field="NGUOI_THUC_HIEN",
                    code="NGUOI_THUC_HIEN_REQUIRED",
                    message=(
                        f"Trong thẻ Chi tiết thứ {record_index}, "
                        f"NGUOI_THUC_HIEN không được bỏ trống"
                    ),
                    value=value,
                )
            )
        return issues

    for msg in validate_gphn_value(value, field="NGUOI_THUC_HIEN"):
        issues.append(
            _issue(
                file=file,
                loai=loai,
                record_index=record_index,
                field="NGUOI_THUC_HIEN",
                code="NGUOI_THUC_HIEN_FORMAT",
                message=msg,
                value=value,
            )
        )
    return issues


def check_gphn_fields(
    *,
    file: str,
    loai: str,
    record_index: int,
    record: dict[str, str],
    skip_fields: set[str] | None = None,
) -> list[ValidationIssue]:
    """Kiểm tra định dạng GPHN/CCHN cho mọi field bác sĩ/người thực hiện khi có giá trị.

    Bỏ qua field đã xử lý riêng (MA_BAC_SI / NGUOI_THUC_HIEN) để tránh trùng.
    """
    fields = GPHN_FIELDS_BY_LOAI.get(loai, ())
    skip = skip_fields or set()
    issues: list[ValidationIssue] = []
    for field in fields:
        if field in skip:
            continue
        value = (record.get(field) or "").strip()
        if is_empty(value):
            continue
        for msg in validate_gphn_value(value, field=field):
            issues.append(
                _issue(
                    file=file,
                    loai=loai,
                    record_index=record_index,
                    field=field,
                    code=f"{field}_FORMAT",
                    message=msg,
                    value=value,
                )
            )
    return issues

from __future__ import annotations

import re

from ..models import FieldRule, ValidationIssue
from .timeutil import valid_dt

DATE8 = re.compile(r"^\d{8}$")
DATE12 = re.compile(r"^\d{12}$")
NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")

# Date-like field names (content format check when value present)
DATE12_FIELDS = {
    "NGAY_SINH",
    "NGAY_VAO",
    "NGAY_VAO_NOI_TRU",
    "NGAY_RA",
    "NGAY_TTOAN",
    "NGAY_YL",
    "NGAY_TH_YL",
    "NGAY_KQ",
    "NGAY_MIEN_CCT",
    "THOI_DIEM_DBLS",
    "THOIGIAN_DINHCHI",
    "NGAY_SINHCON",
    "NGAY_CONCHET",
    "NGAY_SINH_CON",
    "NGAY_BAT_DAU_XU_TRI",
    "NGAY_KET_THUC_XU_TRI",
    "NGAY_XN_TLVR",
    "NGAY_KQ_XN_TLVR",
    "NGAY_XN_PCR",
    "NGAY_KQ_XN_PCR",
    "NGAY_NHAN_TT_MANG_THAI",
    "NGAY_BAT_DAU_DT_CTX",
    "NGAY_CHUYEN_PHAC_DO",
}
DATE8_FIELDS = {
    "GT_THE_TU",
    "GT_THE_DEN",
    "NGAY_CT",
    "TU_NGAY",
    "DEN_NGAY",
    "NGAYSINH_NND",
    "NGAYCAP_CCCD_NND",
    "NGAY_HOP",
    "NGAY_CAP_CCCD",
    "NGAY_CHUNG_TU",
    "NGAY_DE_NGHI",
    "NGAYBD_DTRI_LAO",
    "NGAYKT_DTRI_LAO",
    "NGAY_HEN_KL",
    "NGAY_TAI_KHAM",
}


def is_empty(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def is_strict_required(required: str) -> bool:
    text = (required or "").strip().lower()
    return text in ("x", "x ", "bắt buộc", "bat buoc")


def valid_date8(value: str) -> bool:
    return valid_dt(value, expect_len=8)


def valid_date12(value: str) -> bool:
    return valid_dt(value, expect_len=12)


def valid_cccd(value: str) -> bool:
    """Basic SO_CCCD patterns from Excel notes (9/12 digits, passport-like)."""
    v = value.strip()
    if not v:
        return True
    if re.fullmatch(r"\d{9}", v) or re.fullmatch(r"\d{12}", v):
        return True
    # 8 uppercase letter + 7 digits; 1 letter + 8 digits; 2 letters + 7 digits
    if re.fullmatch(r"[A-Z]{8}\d{7}", v):
        return True
    if re.fullmatch(r"[A-Z]\d{8}", v):
        return True
    if re.fullmatch(r"[A-Z]{2}\d{7}", v):
        return True
    # passport / mixed up to 15
    if re.fullmatch(r"[A-Za-z0-9]{5,15}", v):
        return True
    return False


def check_field_value(
    *,
    file: str,
    loai: str,
    record_index: int,
    rule: FieldRule,
    value: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    code = rule.code
    val = "" if value is None else str(value)

    if is_empty(val):
        if is_strict_required(rule.required):
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso=loai,
                    record_index=record_index,
                    field=code,
                    code="REQUIRED",
                    message=f"Thiếu trường bắt buộc {code}",
                    value=val,
                )
            )
        return issues

    if rule.maxlen is not None and len(val) > rule.maxlen:
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso=loai,
                record_index=record_index,
                field=code,
                code="MAXLEN",
                message=f"{code} vượt kích thước tối đa {rule.maxlen} (hiện {len(val)})",
                value=val[:200],
            )
        )

    if rule.data_type == "Số" and not NUMERIC.match(val):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso=loai,
                record_index=record_index,
                field=code,
                code="TYPE",
                message=f"{code} phải là số theo schema",
                value=val[:200],
            )
        )

    if code == "GIOI_TINH" and val not in ("1", "2", "3"):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso=loai,
                record_index=record_index,
                field=code,
                code="ENUM",
                message="GIOI_TINH chỉ nhận 1 (Nam), 2 (Nữ), 3 (Chưa xác định)",
                value=val,
            )
        )

    if code == "SO_CCCD" and not valid_cccd(val):
        issues.append(
            ValidationIssue(
                file=file,
                severity="warning",
                loai_hoso=loai,
                record_index=record_index,
                field=code,
                code="CCCD_FORMAT",
                message="SO_CCCD không khớp định dạng thường gặp (9/12 số hoặc hộ chiếu)",
                value=val,
            )
        )

    # Date fields: accept 8 (yyyymmdd) or 12 (yyyymmddHHMM) depending on schema/name
    if code in DATE12_FIELDS or code in DATE8_FIELDS or code.startswith("NGAY_"):
        if len(val) == 12:
            if not valid_date12(val):
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="error",
                        loai_hoso=loai,
                        record_index=record_index,
                        field=code,
                        code="DATE12",
                        message=f"{code} không đúng định dạng yyyymmddHHMM",
                        value=val,
                    )
                )
        elif len(val) == 8:
            if code in DATE12_FIELDS and code not in DATE8_FIELDS:
                # strictly 12-char fields should not be 8
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="error",
                        loai_hoso=loai,
                        record_index=record_index,
                        field=code,
                        code="DATE12",
                        message=f"{code} phải gồm 12 ký tự yyyymmddHHMM",
                        value=val,
                    )
                )
            elif not valid_date8(val):
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="warning",
                        loai_hoso=loai,
                        record_index=record_index,
                        field=code,
                        code="DATE8",
                        message=f"{code} không đúng định dạng yyyymmdd",
                        value=val,
                    )
                )
        elif code in DATE12_FIELDS or code in DATE8_FIELDS:
            expect = "8 hoặc 12" if code in DATE8_FIELDS else "12"
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso=loai,
                    record_index=record_index,
                    field=code,
                    code="DATE_LEN",
                    message=f"{code} phải gồm {expect} ký tự ngày",
                    value=val,
                )
            )

    return issues

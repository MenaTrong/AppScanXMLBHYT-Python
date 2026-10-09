from __future__ import annotations

import re
from datetime import datetime

from ..models import ValidationIssue
from .common import is_empty

# Gói thầu: G1 .. G999 (không G0)
RE_GOI = re.compile(r"^G([1-9]\d{0,2})$", re.IGNORECASE)
# Nhóm thầu: N1 .. (không N0)
RE_NHOM = re.compile(r"^N([1-9]\d*)$", re.IGNORECASE)
# Năm 4 số
RE_NAM = re.compile(r"^(20\d{2})$")
# Gi.YY — nhiều nhà thầu cùng thuốc
RE_GI_YY = re.compile(r"^G([1-9]\d{0,2})\.(\d{1,2})$", re.IGNORECASE)
# Đơn vị áp thầu: 00 | mã tỉnh (2–3 số) | mã CSKCB (5 số)
RE_DON_VI = re.compile(r"^(00|\d{2,3}|\d{5})$")
# Số QĐ.Mã đơn vị (VTYT áp thầu)
RE_QD_DONVI = re.compile(r"^(.+)\.(\d{2,5}|00)$")


def _issue(
    *,
    file: str,
    loai: str,
    record_index: int,
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
        field="TT_THAU",
        code=code,
        message=message,
        value=value,
    )


def _check_year(nam: str) -> str | None:
    if not RE_NAM.match(nam):
        return f"Năm thầu không hợp lệ ({nam}), cần YYYY (20xx)"
    year = int(nam)
    max_year = datetime.now().year + 1
    if year > max_year:
        return f"Năm thầu {nam} vượt quá năm hiện tại + 1 ({max_year})"
    if year < 2000:
        return f"Năm thầu {nam} quá nhỏ"
    return None


def _check_goi(goi: str) -> str | None:
    if not RE_GOI.match(goi):
        return f"Mã gói thầu không hợp lệ ({goi}), phải G1–G999 (không được G0)"
    return None


def _check_nhom(nhom: str) -> str | None:
    if not RE_NHOM.match(nhom):
        return f"Mã nhóm thầu không hợp lệ ({nhom}), phải N1, N2, … (không được N0)"
    return None


def validate_tt_thau_thuoc(value: str) -> list[str]:
    """
    XML2 TT_THAU formats:
      1) QĐ;Gi;Ni;YYYY;ĐơnVị
      2) QĐ;YYYY                    (tự bào chế)
      3) QĐ;Gi;Ni;YYYY
      4) QĐ;Gi;Ni;YYYY;Gi.YY        (nhiều nhà thầu)
    """
    parts = [p.strip() for p in value.split(";")]
    if len(parts) < 2 or any(not p for p in parts):
        return ["TT_THAU thuốc thiếu phần hoặc có đoạn rỗng (cách nhau bằng ;)"]

    qd = parts[0]
    if len(qd) < 2:
        return ["Số quyết định thầu thuốc quá ngắn"]

    # Format 2: QĐ;YYYY
    if len(parts) == 2:
        err = _check_year(parts[1])
        return [err] if err else []

    # Format 3 / 1 / 4: need Gi, Ni, YYYY at minimum
    if len(parts) < 4:
        return [
            "TT_THAU thuốc không khớp định dạng "
            "(QĐ;Gi;Ni;YYYY[;ĐơnVị|Gi.YY] hoặc QĐ;YYYY)"
        ]

    errors: list[str] = []
    for err in (_check_goi(parts[1]), _check_nhom(parts[2]), _check_year(parts[3])):
        if err:
            errors.append(err)

    if len(parts) == 4:
        return errors

    if len(parts) == 5:
        tail = parts[4]
        if RE_GI_YY.match(tail):
            return errors
        if RE_DON_VI.match(tail):
            return errors
        errors.append(
            f"Phần cuối TT_THAU thuốc không hợp lệ ({tail}): "
            "cần mã đơn vị (00 / tỉnh / CSKCB) hoặc Gi.YY"
        )
        return errors

    errors.append(
        f"TT_THAU thuốc có {len(parts)} phần; tối đa 5 phần theo quy định"
    )
    return errors


def validate_tt_thau_vtyt(value: str) -> list[str]:
    """
    XML3 TT_THAU formats:
      1) QĐ;Gi;Ni;YYYY
      2) QĐ.MãĐV;Gi;Ni;YYYY     (áp thầu)
      3) QĐ;YYYY                (tự sản xuất)
      4) QĐ.MãĐV;Gi;YYYY        (kế hoạch cũ)
    """
    parts = [p.strip() for p in value.split(";")]
    if len(parts) < 2 or any(not p for p in parts):
        return ["TT_THAU VTYT thiếu phần hoặc có đoạn rỗng (cách nhau bằng ;)"]

    first = parts[0]
    if len(first) < 2:
        return ["Số quyết định thầu VTYT quá ngắn"]

    # Format 3: QĐ;YYYY
    if len(parts) == 2:
        err = _check_year(parts[1])
        return [err] if err else []

    # Format 4: QĐ.MãĐV;Gi;YYYY
    if len(parts) == 3:
        errors: list[str] = []
        if not RE_QD_DONVI.match(first):
            errors.append(
                f"Định dạng áp thầu/cũ cần SốQĐ.MãĐơnVị ở phần đầu (gặp {first})"
            )
        for err in (_check_goi(parts[1]), _check_year(parts[2])):
            if err:
                errors.append(err)
        return errors

    # Format 1 hoặc 2: ...;Gi;Ni;YYYY
    if len(parts) == 4:
        errors = []
        for err in (_check_goi(parts[1]), _check_nhom(parts[2]), _check_year(parts[3])):
            if err:
                errors.append(err)
        # Nếu phần đầu có dạng QĐ.MãĐV thì OK (áp thầu); không bắt buộc
        return errors

    return [
        f"TT_THAU VTYT có {len(parts)} phần; "
        "hợp lệ: QĐ;YYYY | QĐ;Gi;Ni;YYYY | QĐ.MãĐV;Gi;Ni;YYYY | QĐ.MãĐV;Gi;YYYY"
    ]


def check_tt_thau_xml2(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """Format only — bắt buộc xử lý qua required_eval (trừ nhóm 7,17)."""
    issues: list[ValidationIssue] = []
    tt = (record.get("TT_THAU") or "").strip()
    if is_empty(tt):
        return issues
    for msg in validate_tt_thau_thuoc(tt):
        issues.append(
            _issue(
                file=file,
                loai="XML2",
                record_index=record_index,
                code="TT_THAU_FORMAT",
                message=msg,
                value=tt,
            )
        )
    return issues


def check_tt_thau_xml3(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """Format only — bắt buộc MA_NHOM=10 qua required_eval."""
    issues: list[ValidationIssue] = []
    ma_nhom = (record.get("MA_NHOM") or "").strip()
    tt = (record.get("TT_THAU") or "").strip()
    has_vtyt = not is_empty(record.get("MA_VAT_TU") or "")

    if is_empty(tt):
        return issues

    if not has_vtyt and ma_nhom != "10":
        issues.append(
            _issue(
                file=file,
                loai="XML3",
                record_index=record_index,
                code="TT_THAU_UNEXPECTED",
                message="TT_THAU thường chỉ dùng cho VTYT (MA_NHOM=10); kiểm tra lại",
                value=tt,
                severity="warning",
            )
        )

    for msg in validate_tt_thau_vtyt(tt):
        issues.append(
            _issue(
                file=file,
                loai="XML3",
                record_index=record_index,
                code="TT_THAU_FORMAT",
                message=msg,
                value=tt,
            )
        )
    return issues

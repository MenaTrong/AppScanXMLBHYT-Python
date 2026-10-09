from __future__ import annotations

import re

from ..models import ValidationIssue
from .common import is_empty


def _req(record: dict[str, str], field: str) -> str:
    return (record.get(field) or "").strip()


def check_conditional_xml1(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    loai = "XML1"

    def err(field: str, code: str, msg: str) -> None:
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso=loai,
                record_index=record_index,
                field=field,
                code=code,
                message=msg,
                value=_req(record, field),
            )
        )

    ma_loai = _req(record, "MA_LOAI_KCB")
    # normalize 3 / 03
    if ma_loai in ("3", "03") and is_empty(_req(record, "LY_DO_VNT")):
        err("LY_DO_VNT", "COND_LY_DO_VNT", "Bắt buộc LY_DO_VNT khi MA_LOAI_KCB = 03")

    ma_loai_rv = _req(record, "MA_LOAI_RV")
    if ma_loai_rv in ("2", "5") and is_empty(_req(record, "MA_NOI_DEN")):
        err(
            "MA_NOI_DEN",
            "COND_MA_NOI_DEN",
            "Bắt buộc MA_NOI_DEN khi MA_LOAI_RV = 2 hoặc 5",
        )

    if _req(record, "MA_DOITUONG_KCB") == "8":
        tong = _req(record, "T_TONGCHI_BV") or _req(record, "T_TONGCHI_BH")
        try:
            if tong and float(tong) <= 0:
                err(
                    "T_TONGCHI_BV",
                    "COND_DOITUONG_8",
                    "Khi MA_DOITUONG_KCB = 8 thì tổng chi phí phải > 0",
                )
        except ValueError:
            pass

    ngay_tai = _req(record, "NGAY_TAI_KHAM")
    # Presence of NGAY_TAI_KHAM is checked at cross-file level for XML14

    ma_dinh_chi = _req(record, "MA_DINH_CHI_THAI")
    if ma_dinh_chi == "1":
        for f in ("NGUYENNHAN_DINHCHI", "THOIGIAN_DINHCHI", "TUOI_THAI"):
            # These are more on XML7; ignore if absent on XML1
            if f in record and is_empty(_req(record, f)):
                err(f, "COND_DINH_CHI", f"Bắt buộc {f} khi MA_DINH_CHI_THAI = 1")

    return issues


def check_conditional_xml4(
    *,
    file: str,
    record_index: int,
    record: dict[str, str],
    ma_nhom_by_dv: dict[str, str] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not is_empty(_req(record, "GIA_TRI")) and is_empty(_req(record, "NGAY_KQ")):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="XML4",
                record_index=record_index,
                field="NGAY_KQ",
                code="COND_NGAY_KQ",
                message="Bắt buộc NGAY_KQ khi GIA_TRI có dữ liệu",
                value="",
            )
        )
    # TEN_CHI_SO: schema required=x → SCHEMA_REQUIRED
    # KET_LUAN: schema notes "Bắt buộc nếu MA_NHOM (Bảng 3) = 2"
    # QĐ 3176: nếu đã có GIA_TRI (XN) thì được để trống KET_LUAN
    ma_dv = _req(record, "MA_DICH_VU")
    ma_nhom = (ma_nhom_by_dv or {}).get(ma_dv, "")
    if (
        ma_nhom == "2"
        and is_empty(_req(record, "GIA_TRI"))
        and is_empty(_req(record, "KET_LUAN"))
    ):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="XML4",
                record_index=record_index,
                field="KET_LUAN",
                code="COND_KET_LUAN",
                message=(
                    "Bắt buộc KET_LUAN khi dịch vụ XML3 có MA_NHOM = 2 "
                    f"(MA_DICH_VU={ma_dv})"
                ),
                value="",
            )
        )
    return issues


def check_conditional_xml7(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if _req(record, "MA_DINH_CHI_THAI") == "1":
        for f, code in (
            ("NGUYENNHAN_DINHCHI", "COND_DINH_CHI"),
            ("THOIGIAN_DINHCHI", "COND_DINH_CHI"),
            ("TUOI_THAI", "COND_DINH_CHI"),
        ):
            if is_empty(_req(record, f)):
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="error",
                        loai_hoso="XML7",
                        record_index=record_index,
                        field=f,
                        code=code,
                        message=f"Bắt buộc {f} khi MA_DINH_CHI_THAI = 1",
                        value="",
                    )
                )
    return issues


def check_conditional_checkin(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """Check-in: one of MA_DICH_VU / MA_THUOC / MA_VAT_TU should be present."""
    issues: list[ValidationIssue] = []
    dv = _req(record, "MA_DICH_VU")
    thuoc = _req(record, "MA_THUOC")
    vt = _req(record, "MA_VAT_TU")
    filled = [x for x in (dv, thuoc, vt) if x]
    if not filled:
        issues.append(
            ValidationIssue(
                file=file,
                severity="warning",
                loai_hoso="CHECKIN",
                record_index=record_index,
                field="MA_DICH_VU",
                code="COND_CHECKIN_ITEM",
                message="Check-in nên có một trong MA_DICH_VU / MA_THUOC / MA_VAT_TU",
                value="",
            )
        )

    if not is_empty(dv) and is_empty(_req(record, "TEN_DICH_VU")):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="CHECKIN",
                record_index=record_index,
                field="TEN_DICH_VU",
                code="COND_TEN_DV",
                message="Bắt buộc TEN_DICH_VU khi có MA_DICH_VU",
                value="",
            )
        )
    if not is_empty(thuoc) and is_empty(_req(record, "TEN_THUOC")):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="CHECKIN",
                record_index=record_index,
                field="TEN_THUOC",
                code="COND_TEN_THUOC",
                message="Bắt buộc TEN_THUOC khi có MA_THUOC",
                value="",
            )
        )
    if not is_empty(vt) and is_empty(_req(record, "TEN_VAT_TU")):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="CHECKIN",
                record_index=record_index,
                field="TEN_VAT_TU",
                code="COND_TEN_VT",
                message="Bắt buộc TEN_VAT_TU khi có MA_VAT_TU",
                value="",
            )
        )

    if _req(record, "MA_LOAI_KCB") in ("3", "03") and is_empty(
        _req(record, "LY_DO_VNT")
    ):
        # only if NGAY_VAO_NOI_TRU present per some notes
        if not is_empty(_req(record, "NGAY_VAO_NOI_TRU")):
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso="CHECKIN",
                    record_index=record_index,
                    field="LY_DO_VNT",
                    code="COND_LY_DO_VNT",
                    message="Bắt buộc LY_DO_VNT khi có NGAY_VAO_NOI_TRU",
                    value="",
                )
            )
    return issues


def check_conditional_xml3(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if _req(record, "MA_NHOM") == "12" and is_empty(_req(record, "MA_XANG_DAU")):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="XML3",
                record_index=record_index,
                field="MA_XANG_DAU",
                code="COND_XANG_DAU",
                message="Bắt buộc MA_XANG_DAU khi MA_NHOM = 12",
                value="",
            )
        )
    return issues


def check_conditional_xml6(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """HIV/AIDS — điều kiện Excel không parse được (KHAC) + cặp ngày."""
    issues: list[ValidationIssue] = []
    phac = _req(record, "MA_PHAC_DO_DIEU_TRI").upper()
    if phac == "KHAC" and is_empty(_req(record, "MA_BAC_PHAC_DO")):
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="XML6",
                record_index=record_index,
                field="MA_BAC_PHAC_DO",
                code="COND_MA_BAC_PHAC_DO",
                message="Bắt buộc MA_BAC_PHAC_DO khi MA_PHAC_DO_DIEU_TRI = KHAC",
                value="",
            )
        )
    return issues


def check_conditional_xml11(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """Đình chỉ thai trên giấy nghỉ BHXH."""
    issues: list[ValidationIssue] = []
    ma = _req(record, "MA_DINH_CHI_THAI")
    if ma and ma not in ("0", "00"):
        for f in ("NGUYENNHAN_DINHCHI", "TUOI_THAI"):
            if is_empty(_req(record, f)):
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="error",
                        loai_hoso="XML11",
                        record_index=record_index,
                        field=f,
                        code="COND_DINH_CHI",
                        message=f"Bắt buộc {f} khi MA_DINH_CHI_THAI = {ma}",
                        value="",
                    )
                )
    return issues


def parse_required_condition(required: str) -> tuple[str, str, set[str]] | None:
    """
    Parse simple patterns like:
      Bắt buộc nếu MA_LOAI_RV = 2;5
      bắt buộc khi MA_DINH_CHI_THAI =1
      Bắt buộc MA_NHOM =1,2,3,8,18
    Returns (field, op, values) or None.
    """
    text = (required or "").strip()
    if not text or text.lower() in ("x",):
        return None
    m = re.search(
        r"(?:nếu|khi|if)\s+([A-Z0-9_]+)\s*=\s*([0-9A-Za-z_;,\s]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"bắt buộc\s+([A-Z0-9_]+)\s*=\s*([0-9A-Za-z_;,\s]+)",
            text,
            flags=re.IGNORECASE,
        )
    if not m:
        return None
    field = m.group(1).upper()
    raw_vals = m.group(2)
    values = {v.strip() for v in re.split(r"[;,\s]+", raw_vals) if v.strip()}
    extra = set()
    for v in values:
        if v.isdigit() and len(v) == 1:
            extra.add(v.zfill(2))
        if v.isdigit() and len(v) == 2 and v.startswith("0"):
            extra.add(str(int(v)))
    values |= extra
    return field, "=", values


def check_required_expression(
    *,
    file: str,
    loai: str,
    record_index: int,
    field_code: str,
    required: str,
    record: dict[str, str],
) -> list[ValidationIssue]:
    parsed = parse_required_condition(required)
    if not parsed:
        return []
    dep_field, _, values = parsed
    dep_val = _req(record, dep_field)
    if dep_val in values and is_empty(_req(record, field_code)):
        return [
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso=loai,
                record_index=record_index,
                field=field_code,
                code="COND_REQUIRED",
                message=f"Bắt buộc {field_code} khi {dep_field} thuộc {sorted(values)}",
                value="",
            )
        ]
    return []

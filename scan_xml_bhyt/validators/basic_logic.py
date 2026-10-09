from __future__ import annotations

from ..models import ValidationIssue
from .common import is_empty


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


def check_basic_xml1(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """Logic không thuộc thời gian (thời gian xử lý ở time_logic)."""
    issues: list[ValidationIssue] = []

    ma_kt = _req(record, "MA_BENH_KT")
    if ma_kt:
        codes = [c.strip() for c in ma_kt.split(";") if c.strip()]
        if len(codes) > 12:
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field="MA_BENH_KT",
                    code="MA_BENH_KT_MAX",
                    message=f"MA_BENH_KT tối đa 12 mã (hiện {len(codes)})",
                    value=ma_kt[:200],
                )
            )

    ma_yhct = _req(record, "MA_BENH_YHCT")
    if ma_yhct:
        codes = [c.strip() for c in ma_yhct.split(";") if c.strip()]
        if len(codes) > 13:
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field="MA_BENH_YHCT",
                    code="MA_BENH_YHCT_MAX",
                    message=f"MA_BENH_YHCT tối đa 13 mã (hiện {len(codes)})",
                    value=ma_yhct[:200],
                )
            )

    return issues


def check_basic_xml3(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ma_nhom = _req(record, "MA_NHOM")
    ma_dv = _req(record, "MA_DICH_VU")
    ma_vt = _req(record, "MA_VAT_TU")
    ten_dv = _req(record, "TEN_DICH_VU")
    ten_vt = _req(record, "TEN_VAT_TU")

    # Phải có DV hoặc VTYT
    if is_empty(ma_dv) and is_empty(ma_vt):
        issues.append(
            _issue(
                file=file,
                loai="XML3",
                record_index=record_index,
                field="MA_DICH_VU",
                code="XML3_DV_OR_VT",
                message="XML3 phải có MA_DICH_VU hoặc MA_VAT_TU",
            )
        )
    if ma_dv and is_empty(ten_dv):
        issues.append(
            _issue(
                file=file,
                loai="XML3",
                record_index=record_index,
                field="TEN_DICH_VU",
                code="TEN_DICH_VU_REQUIRED",
                message="Bắt buộc TEN_DICH_VU khi có MA_DICH_VU",
            )
        )
    if ma_vt and is_empty(ten_vt):
        issues.append(
            _issue(
                file=file,
                loai="XML3",
                record_index=record_index,
                field="TEN_VAT_TU",
                code="TEN_VAT_TU_REQUIRED",
                message="Bắt buộc TEN_VAT_TU khi có MA_VAT_TU",
            )
        )

    # NGUOI_THUC_HIEN / NGAY_TH_YL: schema + notes K.* (required_eval)
    issues.extend(_check_money_line(file, "XML3", record_index, record))
    return issues


def check_basic_xml2(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if is_empty(_req(record, "MA_THUOC")):
        issues.append(
            _issue(
                file=file,
                loai="XML2",
                record_index=record_index,
                field="MA_THUOC",
                code="MA_THUOC_REQUIRED",
                message="Bắt buộc MA_THUOC trên XML2",
            )
        )
    if _req(record, "MA_THUOC") and is_empty(_req(record, "TEN_THUOC")):
        issues.append(
            _issue(
                file=file,
                loai="XML2",
                record_index=record_index,
                field="TEN_THUOC",
                code="TEN_THUOC_REQUIRED",
                message="Bắt buộc TEN_THUOC khi có MA_THUOC",
            )
        )
    issues.extend(_check_money_line(file, "XML2", record_index, record))
    return issues


def _don_gia_field(loai: str, record: dict[str, str]) -> tuple[str, str]:
    """XML2 dùng DON_GIA; XML3 dùng DON_GIA_BH (fallback lẫn nhau)."""
    if loai == "XML2":
        primary, fallback = "DON_GIA", "DON_GIA_BH"
    else:
        primary, fallback = "DON_GIA_BH", "DON_GIA"
    if _req(record, primary):
        return primary, _req(record, primary)
    if _req(record, fallback):
        return fallback, _req(record, fallback)
    return primary, ""


def _check_money_line(
    file: str, loai: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    """SO_LUONG * đơn giá ≈ THANH_TIEN_BH (sai số 1đ)."""
    issues: list[ValidationIssue] = []
    dg_field, dg_raw = _don_gia_field(loai, record)
    try:
        sl = float(_req(record, "SO_LUONG"))
        dg = float(dg_raw)
        tt = float(_req(record, "THANH_TIEN_BH"))
    except ValueError:
        return issues
    expected = sl * dg
    if abs(expected - tt) > 1.0:
        issues.append(
            _issue(
                file=file,
                loai=loai,
                record_index=record_index,
                field="THANH_TIEN_BH",
                code="MONEY_LINE",
                message=(
                    f"THANH_TIEN_BH ({tt}) khác SO_LUONG*{dg_field} ({expected})"
                ),
                value=str(tt),
                severity="warning",
            )
        )
    return issues


def sum_thanh_tien(
    records: list[dict[str, str]], field: str = "THANH_TIEN_BH"
) -> float | None:
    total = 0.0
    any_val = False
    for rec in records:
        raw = _req(rec, field)
        if not raw:
            continue
        try:
            total += float(raw)
            any_val = True
        except ValueError:
            return None
    return total if any_val else 0.0


def dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple] = set()
    out: list[ValidationIssue] = []
    for i in issues:
        key = (
            i.file,
            i.hoso_index,
            i.loai_hoso,
            i.record_index,
            i.field,
            i.code,
            i.message,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out

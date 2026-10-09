from __future__ import annotations

from ..models import ValidationIssue
from ..parser import ParsedHoSo
from .basic_logic import sum_thanh_tien
from .common import is_empty

# XML8 chỉ có khi MA_LOAI_KCB thuộc tập này (ghi chú Excel bảng 8)
XML8_LOAI_KCB = {"03", "04", "06", "09", "3", "4", "6", "9"}


def check_cross_file(hoso: ParsedHoSo) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    file = hoso.path

    if not hoso.ma_cskcb:
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="ENVELOPE",
                record_index=0,
                field="MACSKCB",
                code="ENV_MACSKCB",
                message="Thiếu MACSKCB trong THONGTINDONVI",
            )
        )

    if not hoso.has_signature:
        issues.append(
            ValidationIssue(
                file=file,
                severity="warning",
                loai_hoso="ENVELOPE",
                record_index=0,
                field="CHUKYDONVI",
                code="ENV_SIGNATURE",
                message="Không thấy khối chữ ký CHUKYDONVI/Signature",
            )
        )

    loai_set = {f.loai_hoso for f in hoso.files}
    if "XML1" not in loai_set:
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="ENVELOPE",
                record_index=0,
                field="XML1",
                code="ENV_XML1",
                message="Hồ sơ thiếu XML1 (Tổng hợp)",
            )
        )

    # Collect MA_LK + records per type
    ma_lk_by_loai: dict[str, set[str]] = {}
    records_by_loai: dict[str, list[dict[str, str]]] = {}
    xml1_records: list[dict[str, str]] = []
    for decoded in hoso.files:
        malks: set[str] = set()
        recs = list(decoded.records)
        records_by_loai.setdefault(decoded.loai_hoso, []).extend(recs)
        for rec in recs:
            ml = (rec.get("MA_LK") or "").strip()
            if ml:
                malks.add(ml)
            if decoded.loai_hoso == "XML1":
                xml1_records.append(rec)
        ma_lk_by_loai[decoded.loai_hoso] = malks

    xml1_malks = ma_lk_by_loai.get("XML1", set())
    if len(xml1_malks) > 1:
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="XML1",
                record_index=0,
                field="MA_LK",
                code="CROSS_MA_LK_MULTI",
                message=f"XML1 có nhiều MA_LK khác nhau: {sorted(xml1_malks)}",
            )
        )

    primary_lk = next(iter(xml1_malks), "")
    for loai, malks in ma_lk_by_loai.items():
        if loai == "XML1" or not malks:
            continue
        if primary_lk and any(m != primary_lk for m in malks):
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso=loai,
                    record_index=0,
                    field="MA_LK",
                    code="CROSS_MA_LK",
                    message=(
                        f"{loai} có MA_LK không khớp XML1 "
                        f"(XML1={primary_lk}, {loai}={sorted(malks)})"
                    ),
                )
            )

    for rec in xml1_records:
        ngay_tai = (rec.get("NGAY_TAI_KHAM") or "").strip()
        if ngay_tai and "XML14" not in loai_set:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso="XML1",
                    record_index=0,
                    field="NGAY_TAI_KHAM",
                    code="CROSS_XML14",
                    message="Có NGAY_TAI_KHAM nhưng thiếu XML14 (Giấy hẹn khám lại)",
                    value=ngay_tai,
                )
            )

        ma_loai_rv = (rec.get("MA_LOAI_RV") or "").strip()
        if ma_loai_rv in ("2", "5") and "XML13" not in loai_set:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="warning",
                    loai_hoso="XML1",
                    record_index=0,
                    field="MA_LOAI_RV",
                    code="CROSS_XML13",
                    message="MA_LOAI_RV = 2/5 (chuyển tuyến) nhưng không có XML13",
                    value=ma_loai_rv,
                )
            )

        ma_loai_kcb = (rec.get("MA_LOAI_KCB") or "").strip()
        if ma_loai_kcb in ("3", "03") and "XML7" not in loai_set:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="warning",
                    loai_hoso="XML1",
                    record_index=0,
                    field="MA_LOAI_KCB",
                    code="CROSS_XML7",
                    message="Nội trú (MA_LOAI_KCB=03) thường cần XML7 giấy ra viện",
                    value=ma_loai_kcb,
                )
            )

        # XML8 chỉ khi MA_LOAI_KCB ∈ 03,04,06,09
        if ma_loai_kcb in XML8_LOAI_KCB and "XML8" not in loai_set:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="warning",
                    loai_hoso="XML1",
                    record_index=0,
                    field="MA_LOAI_KCB",
                    code="CROSS_XML8",
                    message=(
                        f"MA_LOAI_KCB={ma_loai_kcb} thường kèm XML8 "
                        "(Tóm tắt HSBA)"
                    ),
                    value=ma_loai_kcb,
                )
            )
        if "XML8" in loai_set and ma_loai_kcb and ma_loai_kcb not in XML8_LOAI_KCB:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="warning",
                    loai_hoso="XML8",
                    record_index=0,
                    field="MA_LOAI_KCB",
                    code="CROSS_XML8_UNEXPECTED",
                    message=(
                        f"Có XML8 nhưng MA_LOAI_KCB={ma_loai_kcb} "
                        "không thuộc 03/04/06/09"
                    ),
                    value=ma_loai_kcb,
                )
            )

        # XML9 bắt buộc nếu CAN_NANG_CON có dữ liệu
        can_nang_con = (rec.get("CAN_NANG_CON") or "").strip()
        if can_nang_con and "XML9" not in loai_set:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso="XML1",
                    record_index=0,
                    field="CAN_NANG_CON",
                    code="CROSS_XML9",
                    message=(
                        "Có CAN_NANG_CON nhưng thiếu XML9 (Giấy chứng sinh)"
                    ),
                    value=can_nang_con,
                )
            )

    # Cơ bản: T_* trên XML1 phải là số; công thức T_BHTT; đối chiếu tổng XML2/XML3
    for idx, rec in enumerate(xml1_records, start=1):
        for money_field in (
            "T_THUOC",
            "T_VTYT",
            "T_TONGCHI_BV",
            "T_TONGCHI_BH",
            "T_BNTT",
            "T_BNCCT",
            "T_BHTT",
            "T_NGUONKHAC",
        ):
            val = (rec.get(money_field) or "").strip()
            if is_empty(val):
                continue
            try:
                float(val)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="error",
                        loai_hoso="XML1",
                        record_index=idx,
                        field=money_field,
                        code="MONEY_TYPE",
                        message=f"{money_field} không phải số hợp lệ",
                        value=val,
                    )
                )

        try:
            tong_bh = float(rec.get("T_TONGCHI_BH") or "")
            bncct = float(rec.get("T_BNCCT") or "")
            bhtt = float(rec.get("T_BHTT") or "")
            expected = tong_bh - bncct
            if abs(expected - bhtt) > 1.0:
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="warning",
                        loai_hoso="XML1",
                        record_index=idx,
                        field="T_BHTT",
                        code="MONEY_FORMULA",
                        message=(
                            f"T_BHTT ({bhtt}) khác T_TONGCHI_BH - T_BNCCT ({expected})"
                        ),
                        value=str(bhtt),
                    )
                )
        except ValueError:
            pass

        # Đối chiếu tổng dòng chi tiết ↔ XML1 (sai số 1đ)
        xml2_recs = records_by_loai.get("XML2") or []
        t_thuoc_raw = (rec.get("T_THUOC") or "").strip()
        if xml2_recs and t_thuoc_raw:
            try:
                t_thuoc = float(t_thuoc_raw)
                s2 = sum_thanh_tien(xml2_recs)
                if s2 is not None and abs(s2 - t_thuoc) > 1.0:
                    issues.append(
                        ValidationIssue(
                            file=file,
                            severity="warning",
                            loai_hoso="XML1",
                            record_index=idx,
                            field="T_THUOC",
                            code="MONEY_SUM_MISMATCH",
                            message=(
                                f"T_THUOC ({t_thuoc}) khác tổng "
                                f"XML2.THANH_TIEN_BH ({s2})"
                            ),
                            value=t_thuoc_raw,
                        )
                    )
            except ValueError:
                pass

        # T_VTYT chỉ đối chiếu dòng XML3 có MA_VAT_TU
        xml3_vt = [
            r
            for r in (records_by_loai.get("XML3") or [])
            if (r.get("MA_VAT_TU") or "").strip()
        ]
        t_vtyt_raw = (rec.get("T_VTYT") or "").strip()
        if xml3_vt and t_vtyt_raw:
            try:
                t_vtyt = float(t_vtyt_raw)
                s3 = sum_thanh_tien(xml3_vt)
                if s3 is not None and abs(s3 - t_vtyt) > 1.0:
                    issues.append(
                        ValidationIssue(
                            file=file,
                            severity="warning",
                            loai_hoso="XML1",
                            record_index=idx,
                            field="T_VTYT",
                            code="MONEY_SUM_MISMATCH",
                            message=(
                                f"T_VTYT ({t_vtyt}) khác tổng "
                                f"XML3(VTYT).THANH_TIEN_BH ({s3})"
                            ),
                            value=t_vtyt_raw,
                        )
                    )
            except ValueError:
                pass

    return issues

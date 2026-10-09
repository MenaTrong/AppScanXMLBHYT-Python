from __future__ import annotations

from dataclasses import dataclass

from ..models import ValidationIssue
from .common import is_empty
from .timeutil import (
    days_inclusive,
    now_floor_minute,
    parse_dt,
    valid_dt,
    within_range,
)


@dataclass
class EpisodeBounds:
    """Khoảng điều trị từ XML1."""

    ngay_vao: str = ""
    ngay_ra: str = ""
    ngay_vao_nt: str = ""
    ngay_ttoan: str = ""

    @property
    def vao(self):
        return parse_dt(self.ngay_vao)

    @property
    def ra(self):
        return parse_dt(self.ngay_ra)

    @property
    def vao_nt(self):
        return parse_dt(self.ngay_vao_nt)


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


def _order(
    *,
    file: str,
    loai: str,
    record_index: int,
    earlier_field: str,
    earlier_val: str,
    later_field: str,
    later_val: str,
    code: str,
    allow_equal: bool = True,
) -> ValidationIssue | None:
    a, b = parse_dt(earlier_val), parse_dt(later_val)
    if not a or not b:
        return None
    if allow_equal and b < a:
        return _issue(
            file=file,
            loai=loai,
            record_index=record_index,
            field=later_field,
            code=code,
            message=f"{later_field} ({later_val}) phải >= {earlier_field} ({earlier_val})",
            value=later_val,
        )
    if not allow_equal and b <= a:
        return _issue(
            file=file,
            loai=loai,
            record_index=record_index,
            field=later_field,
            code=code,
            message=f"{later_field} ({later_val}) phải > {earlier_field} ({earlier_val})",
            value=later_val,
        )
    return None


def _not_future(
    *,
    file: str,
    loai: str,
    record_index: int,
    field: str,
    value: str,
    grace_minutes: int = 0,
) -> ValidationIssue | None:
    dt = parse_dt(value)
    if not dt:
        return None
    limit = now_floor_minute()
    if grace_minutes:
        from datetime import timedelta

        limit = limit + timedelta(minutes=grace_minutes)
    if dt > limit:
        return _issue(
            file=file,
            loai=loai,
            record_index=record_index,
            field=field,
            code="TIME_FUTURE",
            message=f"{field} ({value}) không được lớn hơn thời điểm hiện tại",
            value=value,
        )
    return None


def _in_episode(
    *,
    file: str,
    loai: str,
    record_index: int,
    field: str,
    value: str,
    bounds: EpisodeBounds | None,
    by_date: bool = False,
) -> ValidationIssue | None:
    if not bounds or not bounds.vao or not bounds.ra:
        return None
    dt = parse_dt(value)
    if not dt:
        return None
    if not within_range(dt, bounds.vao, bounds.ra, by_date=by_date):
        return _issue(
            file=file,
            loai=loai,
            record_index=record_index,
            field=field,
            code="TIME_OUT_OF_EPISODE",
            message=(
                f"{field} ({value}) phải nằm trong khoảng điều trị "
                f"[{bounds.ngay_vao} → {bounds.ngay_ra}]"
            ),
            value=value,
        )
    return None


def extract_episode_bounds(xml1_record: dict[str, str] | None) -> EpisodeBounds | None:
    if not xml1_record:
        return None
    return EpisodeBounds(
        ngay_vao=_req(xml1_record, "NGAY_VAO"),
        ngay_ra=_req(xml1_record, "NGAY_RA"),
        ngay_vao_nt=_req(xml1_record, "NGAY_VAO_NOI_TRU"),
        ngay_ttoan=_req(xml1_record, "NGAY_TTOAN"),
    )


def check_time_xml1(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ngay_vao = _req(record, "NGAY_VAO")
    ngay_ra = _req(record, "NGAY_RA")
    ngay_nt = _req(record, "NGAY_VAO_NOI_TRU")
    ngay_tt = _req(record, "NGAY_TTOAN")
    gt_tu = _req(record, "GT_THE_TU")
    gt_den = _req(record, "GT_THE_DEN")
    ngay_tai = _req(record, "NGAY_TAI_KHAM")
    so_ngay = _req(record, "SO_NGAY_DTRI")
    ma_loai = _req(record, "MA_LOAI_KCB")

    for field, val, expect in (
        ("NGAY_VAO", ngay_vao, 12),
        ("NGAY_RA", ngay_ra, 12),
    ):
        if val and not valid_dt(val, expect_len=expect):
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field=field,
                    code="TIME_FORMAT",
                    message=f"{field} không hợp lệ (cần yyyymmddHHMM, ngày lịch đúng)",
                    value=val,
                )
            )

    iss = _order(
        file=file,
        loai="XML1",
        record_index=record_index,
        earlier_field="NGAY_VAO",
        earlier_val=ngay_vao,
        later_field="NGAY_RA",
        later_val=ngay_ra,
        code="TIME_ORDER",
    )
    if iss:
        issues.append(iss)

    if ngay_nt:
        if not valid_dt(ngay_nt, expect_len=12):
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field="NGAY_VAO_NOI_TRU",
                    code="TIME_FORMAT",
                    message="NGAY_VAO_NOI_TRU không hợp lệ (yyyymmddHHMM)",
                    value=ngay_nt,
                )
            )
        else:
            for earlier_f, earlier_v, later_f, later_v in (
                ("NGAY_VAO", ngay_vao, "NGAY_VAO_NOI_TRU", ngay_nt),
                ("NGAY_VAO_NOI_TRU", ngay_nt, "NGAY_RA", ngay_ra),
            ):
                iss = _order(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    earlier_field=earlier_f,
                    earlier_val=earlier_v,
                    later_field=later_f,
                    later_val=later_v,
                    code="TIME_ORDER",
                )
                if iss:
                    issues.append(iss)

    if gt_tu and gt_den:
        iss = _order(
            file=file,
            loai="XML1",
            record_index=record_index,
            earlier_field="GT_THE_TU",
            earlier_val=gt_tu,
            later_field="GT_THE_DEN",
            later_val=gt_den,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)

    # Thẻ còn hiệu lực tại thời điểm vào viện (theo ngày)
    if gt_tu and ngay_vao:
        a, b = parse_dt(gt_tu), parse_dt(ngay_vao)
        if a and b and b.date() < a.date():
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field="GT_THE_TU",
                    code="TIME_CARD",
                    message=(
                        f"NGAY_VAO ({ngay_vao}) trước GT_THE_TU ({gt_tu}) — "
                        "thẻ chưa có hiệu lực"
                    ),
                    value=gt_tu,
                )
            )
    if gt_den and ngay_vao:
        a, b = parse_dt(gt_den), parse_dt(ngay_vao)
        if a and b and b.date() > a.date():
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field="GT_THE_DEN",
                    code="TIME_CARD",
                    message=(
                        f"NGAY_VAO ({ngay_vao}) sau GT_THE_DEN ({gt_den}) — "
                        "thẻ hết hiệu lực"
                    ),
                    value=gt_den,
                )
            )

    if ngay_tt:
        iss = _not_future(
            file=file,
            loai="XML1",
            record_index=record_index,
            field="NGAY_TTOAN",
            value=ngay_tt,
            grace_minutes=5,
        )
        if iss:
            issues.append(iss)
        # Thanh toán không trước khi vào
        iss = _order(
            file=file,
            loai="XML1",
            record_index=record_index,
            earlier_field="NGAY_VAO",
            earlier_val=ngay_vao,
            later_field="NGAY_TTOAN",
            later_val=ngay_tt,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)

    for field in ("NGAY_VAO", "NGAY_RA"):
        val = _req(record, field)
        if val:
            iss = _not_future(
                file=file,
                loai="XML1",
                record_index=record_index,
                field=field,
                value=val,
                grace_minutes=5,
            )
            if iss:
                issues.append(iss)

    # Hẹn tái khám / khám lại sau khi ra
    if ngay_tai and ngay_ra:
        # NGAY_TAI_KHAM có thể 8 hoặc 12
        a, b = parse_dt(ngay_ra), parse_dt(ngay_tai)
        if a and b and b.date() < a.date():
            issues.append(
                _issue(
                    file=file,
                    loai="XML1",
                    record_index=record_index,
                    field="NGAY_TAI_KHAM",
                    code="TIME_ORDER",
                    message=(
                        f"NGAY_TAI_KHAM ({ngay_tai}) phải >= ngày NGAY_RA ({ngay_ra})"
                    ),
                    value=ngay_tai,
                )
            )

    # SO_NGAY_DTRI (chỉ tính khi VAO ≤ RA)
    if so_ngay and ngay_vao and ngay_ra:
        dv, dr = parse_dt(ngay_vao), parse_dt(ngay_ra)
        if dv and dr and dr >= dv:
            try:
                actual = int(float(so_ngay))
            except ValueError:
                actual = None
            if actual is not None:
                expected = days_inclusive(dv, dr)
                if ma_loai in ("1", "01", "7", "07", "9", "09"):
                    if actual != 0:
                        issues.append(
                            _issue(
                                file=file,
                                loai="XML1",
                                record_index=record_index,
                                field="SO_NGAY_DTRI",
                                code="SO_NGAY_DTRI",
                                message=(
                                    f"MA_LOAI_KCB={ma_loai}: SO_NGAY_DTRI phải = 0 "
                                    f"(hiện {actual})"
                                ),
                                value=so_ngay,
                                severity="warning",
                            )
                        )
                elif actual != expected:
                    issues.append(
                        _issue(
                            file=file,
                            loai="XML1",
                            record_index=record_index,
                            field="SO_NGAY_DTRI",
                            code="SO_NGAY_DTRI",
                            message=(
                                f"SO_NGAY_DTRI={actual} khác NGAY_RA−NGAY_VAO+1={expected}"
                            ),
                            value=so_ngay,
                            severity="warning" if abs(actual - expected) <= 1 else "error",
                        )
                    )
    return issues


def check_time_xml2(
    *,
    file: str,
    record_index: int,
    record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ngay_yl = _req(record, "NGAY_YL")
    ngay_th = _req(record, "NGAY_TH_YL")

    for field, val in (("NGAY_YL", ngay_yl), ("NGAY_TH_YL", ngay_th)):
        if not val:
            continue
        if not valid_dt(val, expect_len=12):
            issues.append(
                _issue(
                    file=file,
                    loai="XML2",
                    record_index=record_index,
                    field=field,
                    code="TIME_FORMAT",
                    message=f"{field} không hợp lệ (yyyymmddHHMM, ngày lịch đúng)",
                    value=val,
                )
            )
            continue
        iss = _not_future(
            file=file,
            loai="XML2",
            record_index=record_index,
            field=field,
            value=val,
            grace_minutes=5,
        )
        if iss:
            issues.append(iss)
        iss = _in_episode(
            file=file,
            loai="XML2",
            record_index=record_index,
            field=field,
            value=val,
            bounds=bounds,
            by_date=False,
        )
        if iss:
            issues.append(iss)

    if ngay_yl and ngay_th:
        iss = _order(
            file=file,
            loai="XML2",
            record_index=record_index,
            earlier_field="NGAY_YL",
            earlier_val=ngay_yl,
            later_field="NGAY_TH_YL",
            later_val=ngay_th,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)
    return issues


def check_time_xml3(
    *,
    file: str,
    record_index: int,
    record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ngay_yl = _req(record, "NGAY_YL")
    ngay_th = _req(record, "NGAY_TH_YL")
    ngay_kq = _req(record, "NGAY_KQ")
    ma_nhom = _req(record, "MA_NHOM")

    for field, val in (
        ("NGAY_YL", ngay_yl),
        ("NGAY_TH_YL", ngay_th),
        ("NGAY_KQ", ngay_kq),
    ):
        if not val:
            continue
        if not valid_dt(val, expect_len=12):
            issues.append(
                _issue(
                    file=file,
                    loai="XML3",
                    record_index=record_index,
                    field=field,
                    code="TIME_FORMAT",
                    message=f"{field} không hợp lệ (yyyymmddHHMM, ngày lịch đúng)",
                    value=val,
                )
            )
            continue
        # YL / TH_YL phải trong đợt điều trị
        if field in ("NGAY_YL", "NGAY_TH_YL"):
            iss = _in_episode(
                file=file,
                loai="XML3",
                record_index=record_index,
                field=field,
                value=val,
                bounds=bounds,
                by_date=False,
            )
            if iss:
                issues.append(iss)
            iss = _not_future(
                file=file,
                loai="XML3",
                record_index=record_index,
                field=field,
                value=val,
                grace_minutes=5,
            )
            if iss:
                issues.append(iss)

    if ngay_yl and ngay_th:
        iss = _order(
            file=file,
            loai="XML3",
            record_index=record_index,
            earlier_field="NGAY_YL",
            earlier_val=ngay_yl,
            later_field="NGAY_TH_YL",
            later_val=ngay_th,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)

    if ngay_kq:
        # >= NGAY_YL
        if ngay_yl:
            iss = _order(
                file=file,
                loai="XML3",
                record_index=record_index,
                earlier_field="NGAY_YL",
                earlier_val=ngay_yl,
                later_field="NGAY_KQ",
                later_val=ngay_kq,
                code="TIME_ORDER",
            )
            if iss:
                issues.append(iss)
        # >= NGAY_TH_YL nếu có
        if ngay_th:
            iss = _order(
                file=file,
                loai="XML3",
                record_index=record_index,
                earlier_field="NGAY_TH_YL",
                earlier_val=ngay_th,
                later_field="NGAY_KQ",
                later_val=ngay_kq,
                code="TIME_ORDER",
            )
            if iss:
                issues.append(iss)
        # <= hiện tại (3176 cho phép KQ sau ra viện với XN)
        iss = _not_future(
            file=file,
            loai="XML3",
            record_index=record_index,
            field="NGAY_KQ",
            value=ngay_kq,
            grace_minutes=5,
        )
        if iss:
            issues.append(iss)
        # Nếu KQ trước NGAY_VAO → lỗi
        if bounds and bounds.vao:
            dt = parse_dt(ngay_kq)
            if dt and dt < bounds.vao:
                issues.append(
                    _issue(
                        file=file,
                        loai="XML3",
                        record_index=record_index,
                        field="NGAY_KQ",
                        code="TIME_OUT_OF_EPISODE",
                        message=(
                            f"NGAY_KQ ({ngay_kq}) trước NGAY_VAO ({bounds.ngay_vao})"
                        ),
                        value=ngay_kq,
                    )
                )
        # Giường: TH_YL là bắt đầu, KQ là kết thúc trong ngày
        if ma_nhom in ("14", "15", "16") and ngay_th and ngay_kq:
            # chỉ cảnh báo nếu khác ngày nhiều
            pass
    return issues


def check_time_xml4(
    *,
    file: str,
    record_index: int,
    record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ngay_kq = _req(record, "NGAY_KQ")
    if not ngay_kq:
        return issues
    if not valid_dt(ngay_kq, expect_len=12):
        issues.append(
            _issue(
                file=file,
                loai="XML4",
                record_index=record_index,
                field="NGAY_KQ",
                code="TIME_FORMAT",
                message="NGAY_KQ không hợp lệ (yyyymmddHHMM)",
                value=ngay_kq,
            )
        )
        return issues
    iss = _not_future(
        file=file,
        loai="XML4",
        record_index=record_index,
        field="NGAY_KQ",
        value=ngay_kq,
        grace_minutes=5,
    )
    if iss:
        issues.append(iss)
    if bounds and bounds.vao:
        dt = parse_dt(ngay_kq)
        if dt and dt < bounds.vao:
            issues.append(
                _issue(
                    file=file,
                    loai="XML4",
                    record_index=record_index,
                    field="NGAY_KQ",
                    code="TIME_OUT_OF_EPISODE",
                    message=f"NGAY_KQ ({ngay_kq}) trước NGAY_VAO ({bounds.ngay_vao})",
                    value=ngay_kq,
                )
            )
    return issues


def check_time_xml7_xml8(
    *, file: str, loai: str, record_index: int, record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ngay_vao = _req(record, "NGAY_VAO")
    ngay_ra = _req(record, "NGAY_RA")
    ngay_ct = _req(record, "NGAY_CT")

    if ngay_vao and ngay_ra:
        iss = _order(
            file=file,
            loai=loai,
            record_index=record_index,
            earlier_field="NGAY_VAO",
            earlier_val=ngay_vao,
            later_field="NGAY_RA",
            later_val=ngay_ra,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)

    # Khớp XML1 nếu có
    if bounds:
        for field, val, expected in (
            ("NGAY_VAO", ngay_vao, bounds.ngay_vao),
            ("NGAY_RA", ngay_ra, bounds.ngay_ra),
        ):
            if val and expected and val != expected:
                issues.append(
                    _issue(
                        file=file,
                        loai=loai,
                        record_index=record_index,
                        field=field,
                        code="TIME_MISMATCH_XML1",
                        message=(
                            f"{loai}.{field} ({val}) khác XML1.{field} ({expected})"
                        ),
                        value=val,
                        severity="warning",
                    )
                )

    if ngay_ct and ngay_ra:
        a, b = parse_dt(ngay_ra), parse_dt(ngay_ct)
        if a and b and b.date() < a.date():
            issues.append(
                _issue(
                    file=file,
                    loai=loai,
                    record_index=record_index,
                    field="NGAY_CT",
                    code="TIME_ORDER",
                    message=f"NGAY_CT ({ngay_ct}) phải >= ngày NGAY_RA ({ngay_ra})",
                    value=ngay_ct,
                )
            )
    return issues


def check_time_range_fields(
    *,
    file: str,
    loai: str,
    record_index: int,
    record: dict[str, str],
    start_field: str = "TU_NGAY",
    end_field: str = "DEN_NGAY",
    days_field: str | None = "SO_NGAY",
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    tu = _req(record, start_field)
    den = _req(record, end_field)
    if tu and den:
        iss = _order(
            file=file,
            loai=loai,
            record_index=record_index,
            earlier_field=start_field,
            earlier_val=tu,
            later_field=end_field,
            later_val=den,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)
        if days_field:
            so = _req(record, days_field)
            a, b = parse_dt(tu), parse_dt(den)
            if so and a and b:
                try:
                    actual = int(float(so))
                    expected = days_inclusive(a, b)
                    if actual != expected:
                        issues.append(
                            _issue(
                                file=file,
                                loai=loai,
                                record_index=record_index,
                                field=days_field,
                                code="SO_NGAY_CALC",
                                message=(
                                    f"{days_field}={actual} khác "
                                    f"{end_field}−{start_field}+1={expected}"
                                ),
                                value=so,
                            )
                        )
                except ValueError:
                    pass
    return issues


def check_time_xml14(
    *, file: str, record_index: int, record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    hen = _req(record, "NGAY_HEN_KL")
    ngay_ra = _req(record, "NGAY_RA") or (bounds.ngay_ra if bounds else "")
    if hen and not valid_dt(hen):
        issues.append(
            _issue(
                file=file,
                loai="XML14",
                record_index=record_index,
                field="NGAY_HEN_KL",
                code="TIME_FORMAT",
                message="NGAY_HEN_KL không hợp lệ (yyyymmdd hoặc yyyymmddHHMM)",
                value=hen,
            )
        )
    elif hen and ngay_ra:
        a, b = parse_dt(ngay_ra), parse_dt(hen)
        if a and b and b.date() < a.date():
            issues.append(
                _issue(
                    file=file,
                    loai="XML14",
                    record_index=record_index,
                    field="NGAY_HEN_KL",
                    code="TIME_ORDER",
                    message=(
                        f"NGAY_HEN_KL ({hen}) phải >= ngày ra viện ({ngay_ra})"
                    ),
                    value=hen,
                )
            )
    # Khớp NGAY_VAO/NGAY_RA với XML1 nếu có
    if bounds:
        for field, expected in (
            ("NGAY_VAO", bounds.ngay_vao),
            ("NGAY_RA", bounds.ngay_ra),
        ):
            val = _req(record, field)
            if val and expected and val != expected:
                issues.append(
                    _issue(
                        file=file,
                        loai="XML14",
                        record_index=record_index,
                        field=field,
                        code="TIME_MISMATCH_XML1",
                        message=(
                            f"XML14.{field} ({val}) khác XML1.{field} ({expected})"
                        ),
                        value=val,
                        severity="warning",
                    )
                )
    return issues


def check_time_xml5(
    *,
    file: str,
    record_index: int,
    record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    """THOI_DIEM_DBLS nằm trong đợt điều trị, không ở tương lai."""
    issues: list[ValidationIssue] = []
    val = _req(record, "THOI_DIEM_DBLS")
    if not val:
        return issues
    if not valid_dt(val, expect_len=12) and not valid_dt(val):
        issues.append(
            _issue(
                file=file,
                loai="XML5",
                record_index=record_index,
                field="THOI_DIEM_DBLS",
                code="TIME_FORMAT",
                message="THOI_DIEM_DBLS không hợp lệ (yyyymmddHHMM)",
                value=val,
            )
        )
        return issues
    iss = _not_future(
        file=file,
        loai="XML5",
        record_index=record_index,
        field="THOI_DIEM_DBLS",
        value=val,
        grace_minutes=5,
    )
    if iss:
        issues.append(iss)
    iss = _in_episode(
        file=file,
        loai="XML5",
        record_index=record_index,
        field="THOI_DIEM_DBLS",
        value=val,
        bounds=bounds,
        by_date=False,
    )
    if iss:
        issues.append(iss)
    return issues


def check_time_order_pairs(
    *,
    file: str,
    loai: str,
    record_index: int,
    record: dict[str, str],
    pairs: list[tuple[str, str]],
) -> list[ValidationIssue]:
    """Kiểm tra cặp ngày earlier <= later khi cả hai có giá trị."""
    issues: list[ValidationIssue] = []
    for earlier_f, later_f in pairs:
        earlier_v, later_v = _req(record, earlier_f), _req(record, later_f)
        if not earlier_v or not later_v:
            continue
        iss = _order(
            file=file,
            loai=loai,
            record_index=record_index,
            earlier_field=earlier_f,
            earlier_val=earlier_v,
            later_field=later_f,
            later_val=later_v,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)
    return issues


def check_time_xml6(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    return check_time_order_pairs(
        file=file,
        loai="XML6",
        record_index=record_index,
        record=record,
        pairs=[
            ("NGAY_XN_TLVR", "NGAY_KQ_XN_TLVR"),
            ("NGAY_XN_PCR", "NGAY_KQ_XN_PCR"),
            ("NGAY_BAT_DAU_XU_TRI", "NGAY_KET_THUC_XU_TRI"),
            ("NGAYBD_DTRI_LAO", "NGAYKT_DTRI_LAO"),
        ],
    )


def check_time_xml9(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sinh = _req(record, "NGAY_SINH_CON")
    ct = _req(record, "NGAY_CT")
    if sinh and ct:
        iss = _order(
            file=file,
            loai="XML9",
            record_index=record_index,
            earlier_field="NGAY_SINH_CON",
            earlier_val=sinh,
            later_field="NGAY_CT",
            later_val=ct,
            code="TIME_ORDER",
        )
        if iss:
            issues.append(iss)
    return issues


def check_time_xml12(
    *, file: str, record_index: int, record: dict[str, str]
) -> list[ValidationIssue]:
    return check_time_order_pairs(
        file=file,
        loai="XML12",
        record_index=record_index,
        record=record,
        pairs=[
            ("NGAY_CAP_CCCD", "NGAY_HOP"),
            ("NGAY_CHUNG_TU", "NGAY_DE_NGHI"),
            ("NGAY_HOP", "NGAY_DE_NGHI"),
        ],
    )


def check_time_xml13(
    *,
    file: str,
    record_index: int,
    record: dict[str, str],
    bounds: EpisodeBounds | None = None,
) -> list[ValidationIssue]:
    issues = check_time_xml7_xml8(
        file=file,
        loai="XML13",
        record_index=record_index,
        record=record,
        bounds=bounds,
    )
    return issues

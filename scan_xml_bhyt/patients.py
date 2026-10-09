from __future__ import annotations

from dataclasses import dataclass, field

from .models import ValidationIssue
from .parser import ParsedHoSo

GENDER = {"1": "Nam", "2": "Nữ", "3": "Chưa xác định"}


@dataclass
class PatientView:
    file: str
    hoso_index: int
    ma_bn: str = ""
    ho_ten: str = ""
    ngay_sinh: str = ""
    gioi_tinh: str = ""
    so_cccd: str = ""
    ma_the: str = ""
    ma_lk: str = ""
    ngay_vao: str = ""
    ngay_ra: str = ""
    ma_benh: str = ""
    chan_doan: str = ""
    error_count: int = 0
    warning_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.error_count:
            return "Lỗi"
        if self.warning_count:
            return "Cảnh báo"
        return "Đạt"

    def error_summary(self, limit: int = 8) -> str:
        errors = [i for i in self.issues if i.severity == "error"]
        if not errors:
            return ""
        parts = []
        for issue in errors[:limit]:
            loc = issue.loai_hoso
            if issue.field:
                loc += f".{issue.field}"
            parts.append(f"{loc}: {issue.message}")
        extra = len(errors) - limit
        if extra > 0:
            parts.append(f"... và {extra} lỗi khác")
        return " | ".join(parts)


def format_date(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) < 8:
        return (value or "").strip()
    year, month, day = digits[:4], digits[4:6], digits[6:8]
    if month == "00" and day == "00":
        return year
    if month == "00":
        return year
    return f"{day}/{month}/{year}"


def format_datetime(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    date = format_date(value)
    if len(digits) < 12 or not date:
        return date
    hour, minute = digits[8:10], digits[10:12]
    if hour == "00" and minute == "00":
        return date
    return f"{date} {hour}:{minute}"


def _xml1_record(hoso: ParsedHoSo, hoso_index: int) -> dict[str, str]:
    for decoded in hoso.files:
        if decoded.hoso_index != hoso_index or decoded.loai_hoso != "XML1":
            continue
        if decoded.records:
            return decoded.records[0]
    return {}


def build_patients(hoso: ParsedHoSo, issues: list[ValidationIssue]) -> list[PatientView]:
    indexes = {decoded.hoso_index for decoded in hoso.files}
    indexes.update(issue.hoso_index for issue in issues if issue.hoso_index)
    if not indexes:
        indexes.add(1)

    envelope = [issue for issue in issues if not issue.hoso_index]
    by_index: dict[int, list[ValidationIssue]] = {}
    for issue in issues:
        if issue.hoso_index:
            by_index.setdefault(issue.hoso_index, []).append(issue)

    patients: list[PatientView] = []
    for pos, index in enumerate(sorted(indexes)):
        rec = _xml1_record(hoso, index)
        gender = (rec.get("GIOI_TINH") or "").strip()
        own = list(by_index.get(index, []))
        if pos == 0 and envelope:
            own = envelope + own
        patients.append(
            PatientView(
                file=hoso.path,
                hoso_index=index,
                ma_bn=(rec.get("MA_BN") or "").strip(),
                ho_ten=(rec.get("HO_TEN") or "").strip(),
                ngay_sinh=format_date(rec.get("NGAY_SINH") or ""),
                gioi_tinh=GENDER.get(gender, gender),
                so_cccd=(rec.get("SO_CCCD") or "").strip(),
                ma_the=(rec.get("MA_THE_BHYT") or "").strip(),
                ma_lk=(rec.get("MA_LK") or "").strip(),
                ngay_vao=format_datetime(rec.get("NGAY_VAO") or ""),
                ngay_ra=format_datetime(rec.get("NGAY_RA") or ""),
                ma_benh=(rec.get("MA_BENH_CHINH") or "").strip(),
                chan_doan=(rec.get("CHAN_DOAN_RV") or rec.get("CHAN_DOAN_VAO") or "").strip(),
                error_count=sum(1 for issue in own if issue.severity == "error"),
                warning_count=sum(1 for issue in own if issue.severity == "warning"),
                issues=own,
            )
        )
        for issue in patients[-1].issues:
            issue.ma_lk = patients[-1].ma_lk
    return patients

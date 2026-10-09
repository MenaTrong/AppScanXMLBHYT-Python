from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .models import ValidationIssue
from .patients import PatientView

HEADERS_VI = [
    ("ma_lk", "Mã LK"),
    ("file", "File"),
    ("severity", "Mức độ"),
    ("loai_hoso", "Loại hồ sơ"),
    ("record_index", "Dòng/STT"),
    ("field", "Chỉ tiêu"),
    ("code", "Mã lỗi"),
    ("message", "Nội dung"),
    ("value", "Giá trị"),
]


def write_csv(issues: list[ValidationIssue], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [key for key, _ in HEADERS_VI]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for issue in issues:
            writer.writerow(issue.to_row())


PATIENT_HEADERS = [
    "Mã BN",
    "Họ tên",
    "Ngày sinh",
    "Giới tính",
    "CCCD",
    "Mã thẻ BHYT",
    "Mã LK",
    "Ngày vào",
    "Ngày ra",
    "Mã bệnh",
    "Chẩn đoán",
    "Số lỗi",
    "Số cảnh báo",
    "Kết quả",
    "Tóm tắt lỗi",
    "File",
]


def _write_patient_sheet(wb, patients: list[PatientView], header_font, header_fill, err_fill, warn_fill) -> None:
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter

    ws = wb.active
    ws.title = "Benh_nhan"
    for col, title in enumerate(PATIENT_HEADERS, start=1):
        cell = ws.cell(1, col, title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for row, patient in enumerate(patients, start=2):
        values = [
            patient.ma_bn,
            patient.ho_ten,
            patient.ngay_sinh,
            patient.gioi_tinh,
            patient.so_cccd,
            patient.ma_the,
            patient.ma_lk,
            patient.ngay_vao,
            patient.ngay_ra,
            patient.ma_benh,
            patient.chan_doan,
            patient.error_count,
            patient.warning_count,
            patient.status,
            patient.error_summary(),
            Path(patient.file).name,
        ]
        fill = err_fill if patient.error_count else warn_fill if patient.warning_count else None
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row, col, value)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if fill is not None:
                cell.fill = fill

    widths = [16, 28, 14, 12, 16, 20, 16, 18, 18, 12, 36, 10, 14, 12, 70, 42]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    last = max(1, len(patients) + 1)
    ws.auto_filter.ref = f"A1:P{last}"
    ws.freeze_panes = "A2"


def write_excel(
    issues: list[ValidationIssue],
    path: Path,
    *,
    scanned_files: int | None = None,
    ok_files: int | None = None,
    patients: list[PatientView] | None = None,
) -> None:
    """Xuất báo cáo Excel: sheet Benh_nhan + Tong_hop + Chi_tiet."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    path.parent.mkdir(parents=True, exist_ok=True)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    err_fill = PatternFill("solid", fgColor="FCE4EC")
    warn_fill = PatternFill("solid", fgColor="FFF8E1")

    wb = Workbook()
    _write_patient_sheet(wb, patients or [], header_font, header_fill, err_fill, warn_fill)

    # --- Sheet tổng hợp ---
    ws_sum = wb.create_sheet("Tong_hop")
    by_sev = Counter(i.severity for i in issues)
    by_file_err = Counter(Path(i.file).name for i in issues if i.severity == "error")
    by_file_warn = Counter(Path(i.file).name for i in issues if i.severity == "warning")
    by_code = Counter(i.code for i in issues if i.severity == "error")

    ws_sum["A1"] = "Báo cáo quét lỗi XML BHYT (QĐ 3176)"
    ws_sum["A1"].font = Font(bold=True, size=14)
    ws_sum.merge_cells("A1:B1")
    ws_sum["A2"] = "Thời gian"
    ws_sum["B2"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws_sum["A3"] = "Tổng file quét"
    ws_sum["B3"] = scanned_files if scanned_files is not None else ""
    ws_sum["A4"] = "File đạt"
    ws_sum["B4"] = ok_files if ok_files is not None else ""
    ws_sum["A5"] = "Tổng lỗi (error)"
    ws_sum["B5"] = by_sev.get("error", 0)
    ws_sum["A6"] = "Tổng cảnh báo (warning)"
    ws_sum["B6"] = by_sev.get("warning", 0)

    ws_sum["A8"] = "File"
    ws_sum["B8"] = "Số error"
    ws_sum["C8"] = "Số warning"
    for col in range(1, 4):
        cell = ws_sum.cell(8, col)
        cell.font = header_font
        cell.fill = header_fill

    file_names = sorted(set(by_file_err) | set(by_file_warn))
    row = 9
    for name in file_names:
        ws_sum.cell(row, 1, name)
        ws_sum.cell(row, 2, by_file_err.get(name, 0))
        ws_sum.cell(row, 3, by_file_warn.get(name, 0))
        if by_file_err.get(name, 0):
            ws_sum.cell(row, 2).fill = err_fill
        row += 1

    row += 1
    ws_sum.cell(row, 1, "Mã lỗi")
    ws_sum.cell(row, 2, "Số lần")
    for col in range(1, 3):
        cell = ws_sum.cell(row, col)
        cell.font = header_font
        cell.fill = header_fill
    row += 1
    for code, count in by_code.most_common():
        ws_sum.cell(row, 1, code)
        ws_sum.cell(row, 2, count)
        row += 1

    ws_sum.column_dimensions["A"].width = 55
    ws_sum.column_dimensions["B"].width = 14
    ws_sum.column_dimensions["C"].width = 14

    # --- Sheet chi tiết ---
    ws = wb.create_sheet("Chi_tiet")
    for col, (_, title) in enumerate(HEADERS_VI, start=1):
        cell = ws.cell(1, col, title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for r_idx, issue in enumerate(issues, start=2):
        data = issue.to_row()
        for c_idx, (key, _) in enumerate(HEADERS_VI, start=1):
            val = data.get(key, "")
            if key == "file":
                val = Path(str(val)).name
            cell = ws.cell(r_idx, c_idx, val)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if issue.severity == "error":
                cell.fill = err_fill
            elif issue.severity == "warning":
                cell.fill = warn_fill

    widths = [18, 40, 12, 12, 10, 18, 18, 60, 30]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    last_col = get_column_letter(len(HEADERS_VI))
    ws.auto_filter.ref = f"A1:{last_col}{max(1, len(issues) + 1)}"
    ws.freeze_panes = "A2"
    wb.move_sheet(ws, offset=-wb.sheetnames.index("Chi_tiet"))
    wb.active = ws

    wb.save(path)


def write_json(issues: list[ValidationIssue], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([i.to_row() for i in issues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def summarize(issues: list[ValidationIssue]) -> str:
    by_sev = Counter(i.severity for i in issues)
    by_file = Counter(Path(i.file).name for i in issues if i.severity == "error")
    lines = [
        f"Tổng issue: {len(issues)} "
        f"(error={by_sev.get('error', 0)}, warning={by_sev.get('warning', 0)})",
    ]
    if by_file:
        lines.append("File có lỗi:")
        for name, count in by_file.most_common(20):
            lines.append(f"  - {name}: {count} error(s)")
    return "\n".join(lines)


def default_report_stem() -> str:
    return datetime.now().strftime("scan_%Y%m%d_%H%M%S")

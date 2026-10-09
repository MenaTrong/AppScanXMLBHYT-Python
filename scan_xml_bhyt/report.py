from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .models import ValidationIssue

HEADERS_VI = [
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


def write_excel(
    issues: list[ValidationIssue],
    path: Path,
    *,
    scanned_files: int | None = None,
    ok_files: int | None = None,
) -> None:
    """Xuất báo cáo Excel: sheet Tong_hop + sheet Chi_tiet."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # --- Sheet tổng hợp ---
    ws_sum = wb.active
    ws_sum.title = "Tong_hop"
    by_sev = Counter(i.severity for i in issues)
    by_file_err = Counter(Path(i.file).name for i in issues if i.severity == "error")
    by_file_warn = Counter(Path(i.file).name for i in issues if i.severity == "warning")
    by_code = Counter(i.code for i in issues if i.severity == "error")

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    err_fill = PatternFill("solid", fgColor="FCE4EC")
    warn_fill = PatternFill("solid", fgColor="FFF8E1")

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

    widths = [40, 12, 12, 10, 18, 18, 60, 30]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.auto_filter.ref = f"A1:H{max(1, len(issues) + 1)}"
    ws.freeze_panes = "A2"

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

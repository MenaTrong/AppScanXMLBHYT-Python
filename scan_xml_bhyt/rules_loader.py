from __future__ import annotations

import json
import re
from pathlib import Path

from .models import FieldRule

SHEET_MAP = {
    "Bang Check-in": "CHECKIN",
    "Bang 1_Tong hop": "XML1",
    "Bang 2_Thuoc ": "XML2",
    "Bang 3_DVKT, VTYT": "XML3",
    "Bang 4_Dich vu CLS": "XML4",
    "Bang 5_Dien bien lam sang": "XML5",
    "Bang 6_HIV.AIDS": "XML6",
    " Bang 7_Giay ra vien": "XML7",
    "Bang 8 _Tom tat HSBA": "XML8",
    "Bang 9_Giay chung sinh": "XML9",
    "Bang 10_Giay nghi duong thai": "XML10",
    "Bang 11_Giay nghi huong BHXH": "XML11",
    "bang 12_ du lieu giam dinh y kh": "XML12",
    "Bang 13_Giay chuyen tuyen BHYT": "XML13",
    "Bang 14_Giay hen kham lai": "XML14",
    "Bang 15_Lao": "XML15",
}


def _parse_maxlen(value) -> int | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("", "n", "none", "null"):
        return None
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _detect_overrides(notes: list[str]) -> tuple[str | None, int | None, bool]:
    """
    Detect type/maxlen overrides and 'drop required' from 3176 notes.
    Returns (dtype, maxlen, drop_required).
    Ignores SQL-style notes to avoid false maxlen (e.g. '2 ký tự đầu').
    """
    filtered = [
        n
        for n in notes
        if "select " not in n.lower() and "nằm trong list" not in n.lower()
    ]
    text = " ".join(filtered).lower().replace("sạng", "dạng")
    drop_required = "bỏ bắt buộc" in text

    dtype: str | None = None
    maxlen: int | None = None

    to_string = any(
        phrase in text
        for phrase in (
            "dạng chuỗi",
            "thành dạng chuỗi",
            "sang dạng chuỗi",
            "thành chuỗi",
            "sang chuỗi",
            "đổi từ dạng số sang dạng chuỗi",
            "đổi kiểu dữ liệu thành chuỗi",
            "đổi kiểu dữ liêu thành chuỗi",
            "chuyển từ dạng số thành dạng chuỗi",
            "chuyển từ dạng số về dạng chuỗi",
            "chuyển từ số thành chuỗi",
            "chuyển đổi từ dạng số thành chuỗi",
        )
    )
    to_number = any(
        phrase in text
        for phrase in (
            "chuyển thành dạng số",
            "đổi thành dạng số",
            "thành dạng số",
        )
    ) and "chuỗi" not in text
    if to_string:
        dtype = "Chuỗi"
    elif to_number:
        dtype = "Số"

    # Only explicit size-change phrases (avoid CCCD format examples like "8 ký tự bắt đầu")
    size_patterns = [
        r"kích thước tối đa[^\d]{0,40}(\d+)",
        r"kích thước[^\d]{0,20}(?:tối đa|max)[^\d]{0,20}(\d+)",
        r"chuyển từ\s+\d+\s+xuống\s+(\d+)",
        r"xuống\s+(\d+)(?:\s|$)",
        r"(?:ký tự max|số ký tự max)\s*(?:là\s*)?(\d+)",
        r"max\s+(\d+)\s*ký tự",
        r"tối đa\s+(\d+)\s*ký tự",
        r"dạng chuỗi[^\d]{0,40}(?:kích thước\s+)?(?:là\s+|tối đa\s+)?(\d+)",
        r"(\d+)\s*ký tự số định dạng",
        r"gồm\s*0?(\d+)\s*ký tự\s+theo định dạng",
        r"gồm\s*0?(\d+)\s*ký tự(?:\s|,|\.|$)",
    ]
    for pat in size_patterns:
        match = re.search(pat, text)
        if match:
            maxlen = int(match.group(1))
            break

    return dtype, maxlen, drop_required


def _normalize_type(raw: str) -> str:
    text = (raw or "").strip().lower()
    if "số" in text or text in ("number", "int", "numeric"):
        return "Số"
    return "Chuỗi"


def load_rules_from_excel(excel_path: Path | str) -> dict[str, list[FieldRule]]:
    from openpyxl import load_workbook

    excel_path = Path(excel_path)
    wb = load_workbook(excel_path, data_only=True)
    schema: dict[str, list[FieldRule]] = {}

    for sheet_name, xml_code in SHEET_MAP.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        fields: list[FieldRule] = []
        for row in range(2, ws.max_row + 1):
            code = ws.cell(row, 2).value
            if not code:
                continue
            code = str(code).strip()
            dtype = _normalize_type(str(ws.cell(row, 3).value or ""))
            maxlen = _parse_maxlen(ws.cell(row, 4).value)
            required_raw = ws.cell(row, 6).value
            required = str(required_raw).strip() if required_raw else ""

            notes: list[str] = []
            for col in range(8, ws.max_column + 1):
                header = ws.cell(1, col).value or ""
                value = ws.cell(row, col).value
                header_s = str(header)
                if not value:
                    continue
                # Skip SQL check columns for override text
                if "sql" in header_s.lower():
                    continue
                if (
                    "3176" in header_s
                    or "Sửa đổi" in header_s
                    or "Note" in header_s
                    or "Nội dung sửa" in header_s
                ):
                    notes.append(str(value).strip())

            odtype, omaxlen, drop_required = _detect_overrides(notes)
            if odtype:
                dtype = odtype
            if omaxlen is not None:
                maxlen = omaxlen
            if drop_required:
                required = ""

            fields.append(
                FieldRule(
                    code=code,
                    data_type=dtype,
                    maxlen=maxlen,
                    required=required,
                    notes=notes[:3],
                )
            )
        schema[xml_code] = fields
    return schema


def schema_to_jsonable(schema: dict[str, list[FieldRule]]) -> dict:
    return {
        code: [
            {
                "code": f.code,
                "type": f.data_type,
                "maxlen": f.maxlen,
                "required": f.required,
                "notes": f.notes,
            }
            for f in fields
        ]
        for code, fields in schema.items()
    }


def schema_from_jsonable(data: dict) -> dict[str, list[FieldRule]]:
    out: dict[str, list[FieldRule]] = {}
    for code, fields in data.items():
        out[code] = [
            FieldRule(
                code=f["code"],
                data_type=f.get("type", "Chuỗi"),
                maxlen=f.get("maxlen"),
                required=f.get("required", ""),
                notes=list(f.get("notes") or []),
            )
            for f in fields
        ]
    return out


def load_or_build_schema(
    excel_path: Path | str | None = None,
    cache_path: Path | str | None = None,
    force_rebuild: bool = False,
) -> dict[str, list[FieldRule]]:
    base = Path(__file__).resolve().parent.parent
    cache = Path(cache_path) if cache_path else base / "rules" / "schema_3176.json"
    excel = (
        Path(excel_path)
        if excel_path
        else base / "Validate CTN QĐ 3176_20250906.xlsx"
    )

    if cache.exists() and not force_rebuild:
        if not excel.exists() or cache.stat().st_mtime >= excel.stat().st_mtime:
            return schema_from_jsonable(json.loads(cache.read_text(encoding="utf-8")))

    if not excel.exists():
        if cache.exists():
            return schema_from_jsonable(json.loads(cache.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"Không tìm thấy Excel rule: {excel}")

    schema = load_rules_from_excel(excel)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(schema_to_jsonable(schema), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return schema

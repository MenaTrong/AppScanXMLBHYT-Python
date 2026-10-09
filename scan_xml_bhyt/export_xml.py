from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .parser import ParsedHoSo, parse_file


def _pretty_xml(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        root = ET.fromstring(text)
        ET.indent(root, space="  ")
        body = ET.tostring(root, encoding="unicode")
        if not body.lstrip().startswith("<?xml"):
            return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
        return body + ("\n" if not body.endswith("\n") else "")
    except ET.ParseError:
        return text if text.endswith("\n") else text + "\n"


def export_pre_base64(
    hoso: ParsedHoSo,
    out_dir: Path | str = "XML_pre_Base64",
) -> Path:
    """
    Xuất từng FILEHOSO đã decode base64 ra thư mục để đọc rõ.
    Cấu trúc: XML_pre_Base64/<tên_file_gốc>/XML1.xml, XML2.xml, ...
    """
    out_root = Path(out_dir)
    stem = Path(hoso.path).stem
    dest = out_root / stem
    dest.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for decoded in hoso.files:
        loai = decoded.loai_hoso or "UNKNOWN"
        n = counts.get(loai, 0) + 1
        counts[loai] = n
        name = f"{loai}.xml" if n == 1 else f"{loai}_{n}.xml"
        path = dest / name
        path.write_text(_pretty_xml(decoded.raw_xml), encoding="utf-8")

    return dest


def export_path_pre_base64(
    path: Path | str,
    out_dir: Path | str = "XML_pre_Base64",
) -> Path:
    return export_pre_base64(parse_file(path), out_dir=out_dir)

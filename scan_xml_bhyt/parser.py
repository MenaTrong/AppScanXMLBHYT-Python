from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


# Known list-item tags for multi-row XML payloads
LIST_ITEM_TAGS = {
    "CHI_TIET_THUOC",
    "CHI_TIET_DVKT",
    "CHI_TIET_CLS",
    "CHI_TIET_DIEN_BIEN_BENH",
    "CHI_TIET_HIV",
    "CHI_TIET_GIAY_CHUNG_SINH",
    "CHI_TIET_LAO",
}


# Fallback tên thẻ chi tiết theo LOAIHOSO khi không suy ra được từ XML
DEFAULT_ITEM_TAG = {
    "XML2": "CHI_TIET_THUOC",
    "XML3": "CHI_TIET_DVKT",
    "XML4": "CHI_TIET_CLS",
    "XML5": "CHI_TIET_DIEN_BIEN_BENH",
    "XML6": "CHI_TIET_HIV",
    "XML9": "CHI_TIET_GIAY_CHUNG_SINH",
    "XML15": "CHI_TIET_LAO",
}


@dataclass
class DecodedFile:
    loai_hoso: str
    root_tag: str
    records: list[dict[str, str]]
    raw_xml: str = ""
    item_tag: str = ""  # ví dụ CHI_TIET_THUOC
    hoso_index: int = 1


@dataclass
class ParsedHoSo:
    path: str
    ma_cskcb: str = ""
    ngay_lap: str = ""
    so_luong_hoso: int | None = None
    has_signature: bool = False
    files: list[DecodedFile] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _element_to_dict(el: ET.Element) -> dict[str, str]:
    """Map direct child tags -> text (empty string if self-closing/empty)."""
    data: dict[str, str] = {}
    for child in list(el):
        key = _local(child.tag)
        if list(child):
            continue
        data[key] = _text(child)
    return data


def _extract_records(root: ET.Element) -> tuple[list[dict[str, str]], str]:
    """Extract flat field records + tên thẻ chi tiết từ XML payload."""
    for tag in LIST_ITEM_TAGS:
        items = [el for el in root.iter() if _local(el.tag) == tag]
        if items:
            return [_element_to_dict(el) for el in items], tag

    best: list[ET.Element] = []
    best_tag = ""
    for el in root.iter():
        children = list(el)
        if len(children) < 1:
            continue
        tags = {_local(c.tag) for c in children}
        if len(tags) != 1:
            continue
        sample = children[0]
        fields = [c for c in list(sample) if not list(c)]
        if len(fields) >= 3 and len(children) > len(best):
            best = children
            best_tag = next(iter(tags))
    if best:
        return [_element_to_dict(el) for el in best], best_tag

    flat = _element_to_dict(root)
    if flat:
        return [flat], _local(root.tag)
    return [], ""


def _decode_noidung(b64_text: str) -> tuple[str | None, str | None]:
    if not b64_text or not b64_text.strip():
        return None, "NOIDUNGFILE rỗng"
    cleaned = re.sub(r"\s+", "", b64_text.strip())
    try:
        raw = base64.b64decode(cleaned, validate=False)
    except Exception as exc:  # noqa: BLE001
        return None, f"Base64 không hợp lệ: {exc}"
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return None, "Không decode được nội dung XML (encoding)"


def _find_filehoso(hoso: ET.Element) -> list[ET.Element]:
    direct = [c for c in list(hoso) if _local(c.tag) == "FILEHOSO"]
    if direct:
        return direct
    return [el for el in hoso.findall(".//FILEHOSO")]


def parse_file(path: Path | str) -> ParsedHoSo:
    path = Path(path)
    result = ParsedHoSo(path=str(path))
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as exc:
        result.parse_errors.append(f"XML envelope không parse được: {exc}")
        return result
    except OSError as exc:
        result.parse_errors.append(f"Không đọc được file: {exc}")
        return result

    if _local(root.tag) != "GIAMDINHHS":
        result.parse_errors.append(
            f"Root không phải GIAMDINHHS (gặp {_local(root.tag)})"
        )

    donvi = root.find("THONGTINDONVI")
    if donvi is None:
        donvi = root.find(".//THONGTINDONVI")
    if donvi is not None:
        result.ma_cskcb = _text(donvi.find("MACSKCB"))

    thongtin = root.find("THONGTINHOSO")
    if thongtin is None:
        thongtin = root.find(".//THONGTINHOSO")
    if thongtin is not None:
        result.ngay_lap = _text(thongtin.find("NGAYLAP"))
        sluong = _text(thongtin.find("SOLUONGHOSO"))
        if sluong.isdigit():
            result.so_luong_hoso = int(sluong)

    result.has_signature = (
        root.find(".//CHUKYDONVI") is not None
        or root.find(".//Signature") is not None
    )

    hoso_list = [el for el in root.iter() if _local(el.tag) == "HOSO"]
    # Prefer HOSO under DANHSACHHOSO
    nested = root.findall(".//DANHSACHHOSO/HOSO")
    if nested:
        hoso_list = nested

    if result.so_luong_hoso is not None and result.so_luong_hoso != len(hoso_list):
        result.parse_errors.append(
            f"SOLUONGHOSO={result.so_luong_hoso} nhưng có {len(hoso_list)} thẻ HOSO"
        )

    if not hoso_list:
        hoso_list = [root]

    seen_filehoso: set[int] = set()
    for hoso_index, hoso in enumerate(hoso_list, start=1):
        for fh in _find_filehoso(hoso):
            fid = id(fh)
            if fid in seen_filehoso:
                continue
            seen_filehoso.add(fid)

            loai = _text(fh.find("LOAIHOSO")).upper()
            noidung_el = fh.find("NOIDUNGFILE")
            noidung = _text(noidung_el)
            if not loai:
                result.parse_errors.append("FILEHOSO thiếu LOAIHOSO")
                continue
            xml_text, err = _decode_noidung(noidung)
            if err:
                result.parse_errors.append(f"{loai}: {err}")
                continue
            assert xml_text is not None
            try:
                inner = ET.fromstring(xml_text)
            except ET.ParseError as exc:
                result.parse_errors.append(f"{loai}: XML con lỗi — {exc}")
                continue
            records, item_tag = _extract_records(inner)
            if not item_tag:
                item_tag = DEFAULT_ITEM_TAG.get(loai, _local(inner.tag))
            result.files.append(
                DecodedFile(
                    loai_hoso=loai,
                    root_tag=_local(inner.tag),
                    records=records,
                    raw_xml=xml_text,
                    item_tag=item_tag,
                    hoso_index=hoso_index,
                )
            )

    if not result.files and not result.parse_errors:
        result.parse_errors.append("Không tìm thấy FILEHOSO/NOIDUNGFILE nào")

    return result


def collect_xml_paths(target: Path | str) -> list[Path]:
    target = Path(target)
    if target.is_file():
        return [target]
    if not target.is_dir():
        return []
    return sorted(p for p in target.rglob("*.xml") if p.is_file())

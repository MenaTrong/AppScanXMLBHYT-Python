from __future__ import annotations

import re

from .common import is_empty

# Chuẩn hóa required text từ schema_3176.json / Excel → True/False/None


def _val(record: dict[str, str], field: str) -> str:
    return (record.get(field) or "").strip()


def _expand_nums(values: set[str]) -> set[str]:
    extra: set[str] = set()
    for v in values:
        if v.isdigit() and len(v) == 1:
            extra.add(v.zfill(2))
        if v.isdigit() and len(v) == 2 and v.startswith("0"):
            extra.add(str(int(v)))
    return values | extra


def _split_values(raw: str) -> set[str]:
    parts = {v.strip() for v in re.split(r"[;,\s]+", raw.strip()) if v.strip()}
    return _expand_nums(parts)


def _notes_text(notes: list[str] | None) -> str:
    return " ".join(notes or []).lower()


def _is_k_cls(record: dict[str, str]) -> bool:
    """DVKT chuyển CLS / chuyển giao: mã K.xxxxx."""
    ma = _val(record, "MA_DICH_VU").upper()
    return bool(ma.startswith("K."))


def _alias_4210_required(low: str, field_code: str) -> bool | None:
    """
    'Như QĐ 4210' / 'Giữ nguyên như 4210' ≈ bắt buộc theo 4210.
    Ngoại lệ XOR DV/VT trên XML3 — để basic_logic xử lý.
    """
    aliases = (
        "như qđ 4210",
        "như qd 4210",
        "giữ nguyên như 4210",
        "giữ nguyên như qd 4210",
        "giữ nguyên như qđ 4210",
    )
    if low not in aliases and not any(low.startswith(a) for a in aliases):
        return None
    xor = {
        "MA_DICH_VU",
        "MA_VAT_TU",
        "TEN_DICH_VU",
        "TEN_VAT_TU",
    }
    if field_code in xor:
        return None
    return True


def evaluate_required(
    required: str,
    record: dict[str, str],
    *,
    field_code: str = "",
    notes: list[str] | None = None,
) -> bool | None:
    """
    Trả về:
      True  → trường đang bắt buộc với bản ghi này (theo schema)
      False → không bắt buộc
      None  → không parse được (để rule custom khác xử lý)
    """
    text = (required or "").strip()
    if not text:
        return False

    low = text.lower().strip()
    notes_low = _notes_text(notes)

    # Note schema: K.XXXXX / chuyển CLS → không bắt buộc field này
    if (
        notes_low
        and _is_k_cls(record)
        and "không bắt buộc" in notes_low
        and (
            "k.xxxxx" in notes_low
            or "mã k." in notes_low
            or "mã dịch vụ là mã k" in notes_low
            or "dvkt chuyển giao" in notes_low
            or "chuyển xét nghiệm" in notes_low
        )
    ):
        return False

    if low in ("x", "bắt buộc", "bat buoc"):
        return True

    alias = _alias_4210_required(low, field_code)
    if alias is not None:
        return alias

    # Bỏ qua ghi chú không phải rule (đã xử lý alias ở trên)
    if low.startswith("giữ nguyên") or low.startswith("như qđ") or low.startswith("như qd"):
        return None

    # "không bắt buộc khi FIELD = 0 còn lại là bắt buộc"
    m = re.search(
        r"không bắt buộc khi\s+([A-Z0-9_]+)\s*=\s*([0-9A-Za-z]+).*còn lại.*bắt buộc",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        field, val = m.group(1).upper(), m.group(2).strip()
        return _val(record, field) != val

    # "Bắt buộc trừ mã nhóm 7,17"
    m = re.search(
        r"trừ\s+(?:mã\s+)?nhóm\s*([0-9,;\s]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m and "bắt buộc" in low:
        excluded = _split_values(m.group(1))
        return _val(record, "MA_NHOM") not in excluded

    # "Bắt buộc khi trường GIA_TRI có dữ liệu"
    m = re.search(r"khi\s+trường\s+([A-Z0-9_]+)\s+có dữ liệu", text, re.I)
    if m:
        return not is_empty(_val(record, m.group(1).upper()))

    # "chỉ bắt buộc khi FIELD not null"
    m = re.search(
        r"khi\s+([A-Z0-9_]+)\s+not\s+null",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return not is_empty(_val(record, m.group(1).upper()))

    # "khi A và B = null"
    m = re.search(
        r"khi\s+([A-Z0-9_]+)\s+(?:và|and)\s+([A-Z0-9_]+)\s*=\s*null",
        text.replace("  ", " "),
        flags=re.IGNORECASE,
    )
    if m:
        a, b = m.group(1).upper(), m.group(2).upper()
        return is_empty(_val(record, a)) and is_empty(_val(record, b))

    # "bắt buộc trong trường hợp FIELD = KHAC"
    m = re.search(
        r"trường hợp\s+([A-Z0-9_]+)\s*=\s*([0-9A-Za-z_]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m and "bắt buộc" in low:
        field = m.group(1).upper()
        expect = m.group(2).strip().upper()
        return _val(record, field).upper() == expect

    # "Bắt buộc khi/nếu FIELD = v1;v2" hoặc "bắt buộc FIELD = v1,v2"
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
    if m:
        field = m.group(1).upper()
        values = _split_values(m.group(2))
        return _val(record, field) in values

    # "khi FIELD là mã 1"
    m = re.search(
        r"khi\s+([A-Z0-9_]+)\s+là\s+mã\s*([0-9]*)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        field = m.group(1).upper()
        code = m.group(2).strip()
        val = _val(record, field)
        if code:
            return val == code or val == code.zfill(2)
        return not is_empty(val) and val not in ("0", "00")

    return None


def check_required_smart(
    *,
    file: str,
    loai: str,
    record_index: int,
    field_code: str,
    required: str,
    record: dict[str, str],
    value: str,
    notes: list[str] | None = None,
    item_tag: str = "",
) -> list:
    from ..models import ValidationIssue

    state = evaluate_required(
        required, record, field_code=field_code, notes=notes
    )
    if state is True and is_empty(value):
        req_hint = (required or "").strip()
        if len(req_hint) > 80:
            req_hint = req_hint[:77] + "..."
        tag = (item_tag or "").strip()
        if tag:
            where = f"Trong thẻ <{tag}> thứ {record_index}"
        else:
            where = f"Trong thẻ chi tiết thứ {record_index}"
        msg = f"{where}, {field_code} không được bỏ trống"
        if req_hint and req_hint.lower() not in ("x", "bắt buộc"):
            msg = f"{msg} (schema: {req_hint})"
        return [
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso=loai,
                record_index=record_index,
                field=field_code,
                code="SCHEMA_REQUIRED",
                message=msg,
                value="",
            )
        ]
    return []

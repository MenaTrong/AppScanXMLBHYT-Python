from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldRule:
    code: str
    data_type: str  # Chuỗi | Số
    maxlen: int | None
    required: str  # raw text from Excel ("x", conditional, ...)
    notes: list[str] = field(default_factory=list)


@dataclass
class ValidationIssue:
    file: str
    severity: str  # error | warning
    loai_hoso: str
    record_index: int
    field: str
    code: str
    message: str
    value: str = ""
    hoso_index: int = 0
    ma_lk: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "ma_lk": self.ma_lk,
            "file": self.file,
            "severity": self.severity,
            "loai_hoso": self.loai_hoso,
            "record_index": self.record_index,
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "value": self.value,
        }

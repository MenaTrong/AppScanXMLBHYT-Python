from __future__ import annotations

from pathlib import Path

from ..models import FieldRule, ValidationIssue
from ..parser import ParsedHoSo, parse_file
from .basic_logic import dedupe_issues
from .required_eval import check_required_smart


def validate_hoso(
    hoso: ParsedHoSo,
    schema: dict[str, list[FieldRule]],
) -> list[ValidationIssue]:
    """Chỉ bắt field bắt buộc theo schema_3176 (cột required + notes ngoại lệ)."""
    issues: list[ValidationIssue] = []
    file = hoso.path

    for msg in hoso.parse_errors:
        issues.append(
            ValidationIssue(
                file=file,
                severity="error",
                loai_hoso="ENVELOPE",
                record_index=0,
                field="",
                code="PARSE",
                message=msg,
            )
        )

    for decoded in hoso.files:
        loai = decoded.loai_hoso
        rules = schema.get(loai)
        if not rules:
            if loai not in schema:
                issues.append(
                    ValidationIssue(
                        file=file,
                        severity="warning",
                        loai_hoso=loai,
                        record_index=0,
                        field="LOAIHOSO",
                        code="UNKNOWN_LOAI",
                        message=f"Không có schema cho {loai}",
                    )
                )
            continue

        if not decoded.records:
            issues.append(
                ValidationIssue(
                    file=file,
                    severity="error",
                    loai_hoso=loai,
                    record_index=0,
                    field="",
                    code="NO_RECORD",
                    message=f"{loai}: không trích được bản ghi chỉ tiêu",
                )
            )
            continue

        item_tag = decoded.item_tag or ""
        for idx, record in enumerate(decoded.records, start=1):
            for rule in rules:
                # Bỏ qua field không có rule bắt buộc trong schema
                if not (rule.required or "").strip():
                    continue
                value = record.get(rule.code, "")
                if value is None:
                    value = ""
                issues.extend(
                    check_required_smart(
                        file=file,
                        loai=loai,
                        record_index=idx,
                        field_code=rule.code,
                        required=rule.required,
                        record=record,
                        value=value,
                        notes=rule.notes,
                        item_tag=item_tag,
                    )
                )

    return dedupe_issues(issues)


def validate_path(
    path: Path | str,
    schema: dict[str, list[FieldRule]],
) -> tuple[ParsedHoSo, list[ValidationIssue]]:
    hoso = parse_file(path)
    return hoso, validate_hoso(hoso, schema)

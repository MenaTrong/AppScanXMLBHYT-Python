from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .export_xml import export_pre_base64
from .parser import collect_xml_paths
from .report import (
    default_report_stem,
    summarize,
    write_csv,
    write_excel,
    write_json,
)
from .rules_loader import load_or_build_schema
from .validators.engine import validate_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scan_xml_bhyt",
        description=(
            "Quét lỗi hồ sơ XML BHYT (GIAMDINHHS) theo chuẩn QĐ 3176 "
            "trước khi gửi cổng gdbhyt.baohiemxahoi.gov.vn"
        ),
    )
    p.add_argument(
        "path",
        nargs="?",
        default="XML_Standard",
        help="File XML hoặc thư mục chứa XML (mặc định: XML_Standard)",
    )
    p.add_argument(
        "--excel",
        default=None,
        help="File Excel Validate CTN QĐ 3176 (mặc định: tìm trong thư mục dự án)",
    )
    p.add_argument(
        "--schema-cache",
        default=None,
        help="Đường dẫn cache schema JSON (mặc định: rules/schema_3176.json)",
    )
    p.add_argument(
        "--rebuild-schema",
        action="store_true",
        help="Bắt buộc đọc lại Excel và ghi cache schema",
    )
    p.add_argument(
        "--out",
        default="reports",
        help="Thư mục xuất báo cáo (mặc định: reports)",
    )
    p.add_argument(
        "--error-dir",
        default="XML_Error",
        help="Thư mục copy file có lỗi (mặc định: XML_Error)",
    )
    p.add_argument(
        "--copy-error",
        action="store_true",
        default=True,
        help="Copy file có error sang --error-dir (mặc định: bật)",
    )
    p.add_argument(
        "--no-copy-error",
        action="store_true",
        help="Không copy file lỗi",
    )
    p.add_argument(
        "--csv",
        action="store_true",
        help="Xuất thêm báo cáo CSV (mặc định chỉ Excel)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Xuất thêm báo cáo JSON",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Chỉ in tóm tắt",
    )
    p.add_argument(
        "--pre-base64",
        default="XML_pre_Base64",
        help=(
            "Thư mục xuất XML đã giải mã base64 "
            "(mặc định: XML_pre_Base64). Để trống '' để tắt."
        ),
    )
    p.add_argument(
        "--no-pre-base64",
        action="store_true",
        help="Không xuất XML_pre_Base64",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.path)
    if not target.exists():
        print(f"Không tìm thấy đường dẫn: {target}", file=sys.stderr)
        return 2

    try:
        schema = load_or_build_schema(
            excel_path=args.excel,
            cache_path=args.schema_cache,
            force_rebuild=args.rebuild_schema,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Lỗi tải schema: {exc}", file=sys.stderr)
        return 2

    paths = collect_xml_paths(target)
    if not paths:
        print(f"Không có file .xml nào tại {target}", file=sys.stderr)
        return 2

    print(f"Đang quét {len(paths)} file XML (schema: {len(schema)} bảng)...")

    all_issues = []
    files_with_errors: set[Path] = set()
    ok_count = 0
    dump_pre = not args.no_pre_base64 and bool(str(args.pre_base64 or "").strip())
    pre_dir = Path(args.pre_base64) if dump_pre else None
    dumped = 0

    for path in paths:
        hoso, issues = validate_path(path, schema)
        if pre_dir is not None:
            dest = export_pre_base64(hoso, out_dir=pre_dir)
            dumped += 1
            if not args.quiet:
                n_files = len(hoso.files)
                print(f"[DUMP] {path.name} → {dest}/ ({n_files} XML)")
        errors = [i for i in issues if i.severity == "error"]
        all_issues.extend(issues)
        if errors:
            files_with_errors.add(path)
            if not args.quiet:
                print(f"\n[FAIL] {path.name} — {len(errors)} error(s)")
                for issue in errors[:15]:
                    loc = f"{issue.loai_hoso}"
                    if issue.record_index:
                        loc += f"#{issue.record_index}"
                    if issue.field:
                        loc += f".{issue.field}"
                    print(f"  - [{issue.code}] {loc}: {issue.message}")
                if len(errors) > 15:
                    print(f"  ... và {len(errors) - 15} lỗi khác")
        else:
            ok_count += 1
            warn_n = sum(1 for i in issues if i.severity == "warning")
            if not args.quiet:
                suffix = f" ({warn_n} warning)" if warn_n else ""
                print(f"[OK]   {path.name}{suffix}")

    out_dir = Path(args.out)
    stem = default_report_stem()
    xlsx_path = out_dir / f"{stem}.xlsx"
    write_excel(
        all_issues,
        xlsx_path,
        scanned_files=len(paths),
        ok_files=ok_count,
    )
    if args.csv:
        write_csv(all_issues, out_dir / f"{stem}.csv")
    if args.json:
        write_json(all_issues, out_dir / f"{stem}.json")

    copy_error = args.copy_error and not args.no_copy_error
    copied = 0
    if copy_error and files_with_errors:
        err_dir = Path(args.error_dir).resolve()
        err_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(files_with_errors):
            dest = err_dir / path.name
            # Bỏ qua nếu đang quét chính thư mục XML_Error (src == dest)
            try:
                if path.resolve() == dest.resolve():
                    continue
            except OSError:
                pass
            shutil.copy2(path, dest)
            copied += 1

    print("\n" + summarize(all_issues))
    print(f"Pass: {ok_count}/{len(paths)}")
    print(f"Báo cáo Excel: {xlsx_path}")
    if copy_error and copied:
        print(f"Đã copy {copied} file lỗi → {args.error_dir}/")
    if pre_dir is not None and dumped:
        print(f"XML trước base64: {pre_dir}/ ({dumped} hồ sơ)")

    return 1 if files_with_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

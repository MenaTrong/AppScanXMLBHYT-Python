from __future__ import annotations

import os
import shutil
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .export_xml import export_pre_base64
from .models import ValidationIssue
from .parser import collect_xml_paths
from .paths import app_dir
from .patients import PatientView, build_patients
from .report import default_report_stem, summarize, write_excel
from .rules_loader import load_or_build_schema
from .validators.engine import validate_path


@dataclass
class ScanResult:
    files: int = 0
    ok_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    patients: list[PatientView] = field(default_factory=list)
    xlsx_path: Path | None = None
    error_dir: Path | None = None
    copied: int = 0
    pre_dir: Path | None = None
    dumped: int = 0


def run_scan(
    target: Path,
    *,
    out_dir: Path,
    copy_error: bool,
    dump_pre: bool,
    on_progress=None,
) -> ScanResult:
    schema = load_or_build_schema()
    paths = collect_xml_paths(target)
    if not paths:
        raise FileNotFoundError(f"Không có file .xml nào tại {target}")

    result = ScanResult(files=len(paths))
    files_with_errors: set[Path] = set()
    pre_dir = out_dir / "XML_pre_Base64" if dump_pre else None

    for index, path in enumerate(paths, start=1):
        if on_progress:
            on_progress(index, len(paths), path.name)
        hoso, issues = validate_path(path, schema)
        result.patients.extend(build_patients(hoso, issues))
        if pre_dir is not None:
            export_pre_base64(hoso, out_dir=pre_dir)
            result.dumped += 1
        result.issues.extend(issues)
        if any(issue.severity == "error" for issue in issues):
            files_with_errors.add(path)
        else:
            result.ok_count += 1

    xlsx_path = out_dir / "reports" / f"{default_report_stem()}.xlsx"
    write_excel(
        result.issues,
        xlsx_path,
        scanned_files=len(paths),
        ok_files=result.ok_count,
        patients=result.patients,
    )
    result.xlsx_path = xlsx_path

    if copy_error and files_with_errors:
        err_dir = (out_dir / "XML_Error").resolve()
        err_dir.mkdir(parents=True, exist_ok=True)
        result.error_dir = err_dir
        for path in sorted(files_with_errors):
            dest = err_dir / path.name
            try:
                if path.resolve() == dest.resolve():
                    continue
            except OSError:
                pass
            shutil.copy2(path, dest)
            result.copied += 1

    if pre_dir is not None and result.dumped:
        result.pre_dir = pre_dir
    return result


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Scan XML BHYT — QĐ 3176  v{__version__}")
        self.geometry("1280x720")
        self.minsize(980, 560)
        self._worker: threading.Thread | None = None
        self._result: ScanResult | None = None
        self._issues: list[ValidationIssue] = []

        self.path_var = tk.StringVar()
        self.out_var = tk.StringVar(value=str(app_dir()))
        self.copy_var = tk.BooleanVar(value=True)
        self.pre_var = tk.BooleanVar(value=True)
        self.filter_var = tk.StringVar(value="Tất cả")
        self.status_var = tk.StringVar(
            value="Chọn file hoặc thư mục XML rồi bấm Quét. Mỗi dòng là một lỗi, kèm mã LK."
        )

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        head = ttk.Label(
            root,
            text="Quét lỗi hồ sơ XML BHYT trước khi gửi cổng giám định",
            font=("Segoe UI", 12, "bold"),
        )
        head.grid(row=0, column=0, sticky="w", **pad)

        form = ttk.LabelFrame(root, text="Nguồn và kết quả", padding=8)
        form.grid(row=1, column=0, sticky="ew", **pad)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="XML").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.path_var).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        btns = ttk.Frame(form)
        btns.grid(row=0, column=2, sticky="e")
        ttk.Button(btns, text="Chọn file", command=self._pick_file).pack(
            side="left", padx=2
        )
        ttk.Button(btns, text="Chọn thư mục", command=self._pick_dir).pack(
            side="left", padx=2
        )

        ttk.Label(form, text="Lưu tại").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(form, textvariable=self.out_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(8, 0)
        )
        ttk.Button(form, text="Chọn thư mục", command=self._pick_out).grid(
            row=1, column=2, sticky="e", pady=(8, 0)
        )

        opts = ttk.Frame(form)
        opts.grid(row=2, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            opts, text="Copy file lỗi vào XML_Error", variable=self.copy_var
        ).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(
            opts,
            text="Xuất XML đã giải mã (XML_pre_Base64)",
            variable=self.pre_var,
        ).pack(side="left")

        actions = ttk.Frame(root)
        actions.grid(row=2, column=0, sticky="ew", **pad)
        self.scan_btn = ttk.Button(actions, text="Quét", command=self._start_scan)
        self.scan_btn.pack(side="left")
        ttk.Button(actions, text="Quản lý rule", command=self._open_rules).pack(
            side="left", padx=(6, 0)
        )
        ttk.Label(actions, textvariable=self.status_var).pack(
            side="left", padx=12, fill="x", expand=True
        )
        ttk.Label(actions, text="Lọc").pack(side="left")
        filt = ttk.Combobox(
            actions,
            textvariable=self.filter_var,
            values=("Tất cả", "Lỗi", "Cảnh báo"),
            width=12,
            state="readonly",
        )
        filt.pack(side="left", padx=6)
        filt.bind("<<ComboboxSelected>>", lambda _e: self._fill_tree())
        self.open_report_btn = ttk.Button(
            actions, text="Mở Excel", command=self._open_report, state="disabled"
        )
        self.open_report_btn.pack(side="left", padx=2)
        self.open_error_btn = ttk.Button(
            actions, text="Mở XML_Error", command=self._open_errors, state="disabled"
        )
        self.open_error_btn.pack(side="left", padx=2)

        table = ttk.Frame(root)
        table.grid(row=3, column=0, sticky="nsew", **pad)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        cols = ("ma_lk", "file", "severity", "loai", "stt", "field", "code", "message")
        self.tree = ttk.Treeview(table, columns=cols, show="headings")
        headings = {
            "ma_lk": ("Mã LK", 140),
            "file": ("File", 220),
            "severity": ("Mức", 70),
            "loai": ("Loại", 70),
            "stt": ("STT", 50),
            "field": ("Chỉ tiêu", 120),
            "code": ("Mã lỗi", 140),
            "message": ("Nội dung", 420),
        }
        for key, (title, width) in headings.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w", stretch=(key == "message"))
        self.tree.tag_configure("error", foreground="#9B1C1C")
        self.tree.tag_configure("warning", foreground="#8A5A00")
        self.tree.bind("<Double-1>", self._show_issue)

        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        self.summary = tk.Text(root, height=6, wrap="word", font=("Segoe UI", 9))
        self.summary.grid(row=4, column=0, sticky="ew", **pad)
        self.summary.configure(state="disabled")

    def _pick_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn file XML",
            filetypes=[("XML", "*.xml"), ("Tất cả", "*.*")],
        )
        if path:
            self.path_var.set(path)
            self._suggest_out(Path(path))

    def _pick_dir(self) -> None:
        path = filedialog.askdirectory(title="Chọn thư mục chứa XML")
        if path:
            self.path_var.set(path)
            self._suggest_out(Path(path))

    def _pick_out(self) -> None:
        path = filedialog.askdirectory(title="Thư mục lưu báo cáo")
        if path:
            self.out_var.set(path)

    def _suggest_out(self, selected: Path) -> None:
        parent = selected.parent if selected.is_file() else selected.parent
        if parent and str(parent) not in ("", "."):
            self.out_var.set(str(parent))

    def _set_summary(self, text: str) -> None:
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def _start_scan(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        raw = self.path_var.get().strip()
        if not raw:
            messagebox.showwarning("Thiếu đường dẫn", "Hãy chọn file hoặc thư mục XML.")
            return
        target = Path(raw)
        if not target.exists():
            messagebox.showerror("Không tìm thấy", f"Không tìm thấy:\n{target}")
            return
        out_dir = Path(self.out_var.get().strip() or str(app_dir()))
        self.scan_btn.configure(state="disabled")
        self.open_report_btn.configure(state="disabled")
        self.open_error_btn.configure(state="disabled")
        self._issues = []
        self._fill_tree()
        self._set_summary("")
        self.status_var.set("Đang tải schema và quét...")

        def progress(index: int, total: int, name: str) -> None:
            self.after(0, lambda: self.status_var.set(f"Đang quét {index}/{total}: {name}"))

        def work() -> None:
            try:
                result = run_scan(
                    target,
                    out_dir=out_dir,
                    copy_error=self.copy_var.get(),
                    dump_pre=self.pre_var.get(),
                    on_progress=progress,
                )
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._scan_failed(exc))
                return
            self.after(0, lambda: self._scan_done(result))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _scan_failed(self, exc: Exception) -> None:
        self.scan_btn.configure(state="normal")
        self.status_var.set("Quét thất bại.")
        messagebox.showerror("Lỗi", str(exc))

    def _scan_done(self, result: ScanResult) -> None:
        self._result = result
        self._issues = result.issues
        self._fill_tree()
        errors = sum(1 for issue in result.issues if issue.severity == "error")
        self.status_var.set(
            f"Xong: {errors} lỗi / {len(result.issues)} dòng, {len(result.patients)} bệnh nhân."
        )
        lines = [summarize(result.issues), f"Pass: {result.ok_count}/{result.files}"]
        if result.xlsx_path:
            lines.append(f"Báo cáo Excel: {result.xlsx_path}")
        if result.copied and result.error_dir:
            lines.append(f"Đã copy {result.copied} file lỗi → {result.error_dir}")
        if result.pre_dir:
            lines.append(f"XML trước base64: {result.pre_dir} ({result.dumped} hồ sơ)")
        self._set_summary("\n".join(lines))
        self.scan_btn.configure(state="normal")
        if result.xlsx_path and result.xlsx_path.exists():
            self.open_report_btn.configure(state="normal")
        if result.error_dir and result.copied:
            self.open_error_btn.configure(state="normal")

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        mode = self.filter_var.get()
        for index, issue in enumerate(self._issues):
            if mode == "Lỗi" and issue.severity != "error":
                continue
            if mode == "Cảnh báo" and issue.severity != "warning":
                continue
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                tags=(issue.severity,),
                values=(
                    issue.ma_lk,
                    Path(issue.file).name,
                    issue.severity,
                    issue.loai_hoso,
                    issue.record_index or "",
                    issue.field,
                    issue.code,
                    issue.message,
                ),
            )

    def _show_issue(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        try:
            issue = self._issues[int(selected[0])]
        except (ValueError, IndexError):
            return
        loc = issue.loai_hoso
        if issue.record_index:
            loc += f"#{issue.record_index}"
        if issue.field:
            loc += f".{issue.field}"
        messagebox.showinfo(
            "Chi tiết lỗi",
            "\n".join(
                [
                    f"Mã LK: {issue.ma_lk}",
                    f"File: {Path(issue.file).name}",
                    f"Mức: {issue.severity}",
                    f"Vị trí: {loc}",
                    f"Mã lỗi: {issue.code}",
                    "",
                    issue.message,
                ]
            ),
        )

    def _open_rules(self) -> None:
        from .rules_editor import RulesEditor

        RulesEditor(self)

    def _open_report(self) -> None:
        if self._result and self._result.xlsx_path:
            os.startfile(self._result.xlsx_path)  # noqa: S606

    def _open_errors(self) -> None:
        if self._result and self._result.error_dir:
            os.startfile(self._result.error_dir)  # noqa: S606

    def _on_close(self) -> None:
        self.destroy()


def main() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    style_root = App()
    style = ttk.Style(style_root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style_root.mainloop()


if __name__ == "__main__":
    main()

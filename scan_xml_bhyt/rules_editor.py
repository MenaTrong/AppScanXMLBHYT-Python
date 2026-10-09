from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .models import FieldRule
from .rules_loader import load_editable_schema, save_editable_schema, writable_schema_path


class RulesEditor(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("Quản lý rule — schema 3176")
        self.geometry("980x560")
        self.minsize(820, 460)
        self.schema = load_editable_schema()
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value=str(writable_schema_path()))
        self._build()
        self._fill_tables()
        self.transient(master)
        self.grab_set()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(root, text="Bảng").grid(row=0, column=0, sticky="w")
        search = ttk.Frame(root)
        search.grid(row=0, column=1, sticky="ew")
        ttk.Label(search, text="Tìm chỉ tiêu").pack(side="left")
        entry = ttk.Entry(search, textvariable=self.search_var, width=28)
        entry.pack(side="left", padx=6)
        entry.bind("<KeyRelease>", lambda _e: self._fill_rules())

        tables = ttk.Frame(root)
        tables.grid(row=1, column=0, sticky="ns", padx=(0, 8), pady=6)
        self.table_list = tk.Listbox(tables, width=16, exportselection=False)
        table_scroll = ttk.Scrollbar(tables, command=self.table_list.yview)
        self.table_list.configure(yscrollcommand=table_scroll.set)
        self.table_list.pack(side="left", fill="y")
        table_scroll.pack(side="left", fill="y")
        self.table_list.bind("<<ListboxSelect>>", lambda _e: self._fill_rules())

        table_btns = ttk.Frame(root)
        table_btns.grid(row=2, column=0, sticky="w")
        ttk.Button(table_btns, text="Thêm bảng", command=self._add_table).pack(side="left")
        ttk.Button(table_btns, text="Xóa bảng", command=self._delete_table).pack(
            side="left", padx=4
        )

        cols = ("code", "type", "maxlen", "required", "notes")
        self.tree = ttk.Treeview(root, columns=cols, show="headings")
        headings = {
            "code": ("Chỉ tiêu", 140),
            "type": ("Kiểu", 70),
            "maxlen": ("Max", 60),
            "required": ("Bắt buộc", 220),
            "notes": ("Ghi chú", 360),
        }
        for key, (title, width) in headings.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w", stretch=(key in ("required", "notes")))
        yscroll = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=1, column=1, sticky="nsew", pady=6)
        yscroll.grid(row=1, column=2, sticky="ns", pady=6)
        self.tree.bind("<Double-1>", lambda _e: self._edit_rule())

        rule_btns = ttk.Frame(root)
        rule_btns.grid(row=2, column=1, sticky="w")
        ttk.Button(rule_btns, text="Thêm rule", command=self._add_rule).pack(side="left")
        ttk.Button(rule_btns, text="Sửa", command=self._edit_rule).pack(side="left", padx=4)
        ttk.Button(rule_btns, text="Xóa", command=self._delete_rule).pack(side="left")
        ttk.Label(root, textvariable=self.status_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

    def _current_table(self) -> str | None:
        selected = self.table_list.curselection()
        if not selected:
            return None
        return self.table_list.get(selected[0])

    def _fill_tables(self, select: str | None = None) -> None:
        self.table_list.delete(0, "end")
        names = list(self.schema)
        for name in names:
            self.table_list.insert("end", name)
        if not names:
            self._fill_rules()
            return
        index = names.index(select) if select in names else 0
        self.table_list.selection_set(index)
        self.table_list.activate(index)
        self._fill_rules()

    def _fill_rules(self) -> None:
        self.tree.delete(*self.tree.get_children())
        table = self._current_table()
        if not table:
            return
        query = self.search_var.get().strip().lower()
        for index, rule in enumerate(self.schema.get(table, [])):
            if query and query not in rule.code.lower() and query not in rule.required.lower():
                continue
            note = " ".join(rule.notes).replace("\n", " ")
            if len(note) > 80:
                note = note[:77] + "..."
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    rule.code,
                    rule.data_type,
                    "" if rule.maxlen is None else rule.maxlen,
                    rule.required,
                    note,
                ),
            )

    def _selected_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            return None
        try:
            return int(selected[0])
        except ValueError:
            return None

    def _persist(self, message: str) -> None:
        path = save_editable_schema(self.schema)
        self.status_var.set(f"{message} — {path}")

    def _add_table(self) -> None:
        name = _ask_text(self, "Thêm bảng", "Tên bảng (ví dụ XML16)")
        if name is None:
            return
        code = name.strip().upper()
        if not code:
            return
        if code in self.schema:
            messagebox.showwarning("Trùng bảng", f"Đã có bảng {code}.", parent=self)
            return
        self.schema[code] = []
        self._persist(f"Đã thêm bảng {code}")
        self._fill_tables(code)

    def _delete_table(self) -> None:
        table = self._current_table()
        if not table:
            return
        count = len(self.schema.get(table, []))
        if not messagebox.askyesno(
            "Xóa bảng",
            f"Xóa bảng {table} và {count} rule?",
            parent=self,
        ):
            return
        self.schema.pop(table, None)
        self._persist(f"Đã xóa bảng {table}")
        self._fill_tables()

    def _add_rule(self) -> None:
        table = self._current_table()
        if not table:
            messagebox.showwarning("Chưa chọn bảng", "Hãy chọn một bảng trước.", parent=self)
            return
        rule = _rule_dialog(self, f"Thêm rule — {table}", None)
        if rule is None:
            return
        codes = {item.code for item in self.schema[table]}
        if rule.code in codes:
            messagebox.showwarning("Trùng chỉ tiêu", f"{table} đã có {rule.code}.", parent=self)
            return
        self.schema[table].append(rule)
        self._persist(f"Đã thêm {table}.{rule.code}")
        self._fill_rules()
        self.tree.selection_set(str(len(self.schema[table]) - 1))

    def _edit_rule(self) -> None:
        table = self._current_table()
        index = self._selected_index()
        if table is None or index is None:
            return
        current = self.schema[table][index]
        rule = _rule_dialog(self, f"Sửa rule — {table}.{current.code}", current)
        if rule is None:
            return
        codes = {item.code for i, item in enumerate(self.schema[table]) if i != index}
        if rule.code in codes:
            messagebox.showwarning("Trùng chỉ tiêu", f"{table} đã có {rule.code}.", parent=self)
            return
        self.schema[table][index] = rule
        self._persist(f"Đã sửa {table}.{rule.code}")
        self._fill_rules()
        self.tree.selection_set(str(index))

    def _delete_rule(self) -> None:
        table = self._current_table()
        index = self._selected_index()
        if table is None or index is None:
            return
        rule = self.schema[table][index]
        if not messagebox.askyesno(
            "Xóa rule",
            f"Xóa {table}.{rule.code}?",
            parent=self,
        ):
            return
        del self.schema[table][index]
        self._persist(f"Đã xóa {table}.{rule.code}")
        self._fill_rules()


def _ask_text(parent: tk.Misc, title: str, label: str) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    win.resizable(False, False)
    value = tk.StringVar()
    result: dict[str, str | None] = {"value": None}

    ttk.Label(win, text=label).grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
    entry = ttk.Entry(win, textvariable=value, width=32)
    entry.grid(row=1, column=0, padx=10, sticky="ew")
    entry.focus_set()

    def ok() -> None:
        result["value"] = value.get()
        win.destroy()

    def cancel() -> None:
        win.destroy()

    buttons = ttk.Frame(win)
    buttons.grid(row=2, column=0, padx=10, pady=10, sticky="e")
    ttk.Button(buttons, text="Lưu", command=ok).pack(side="left")
    ttk.Button(buttons, text="Hủy", command=cancel).pack(side="left", padx=(6, 0))
    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: cancel())
    parent.wait_window(win)
    return result["value"]


def _rule_dialog(parent: tk.Misc, title: str, initial: FieldRule | None) -> FieldRule | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    win.geometry("520x420")

    code = tk.StringVar(value="" if initial is None else initial.code)
    dtype = tk.StringVar(value="Chuỗi" if initial is None else initial.data_type or "Chuỗi")
    maxlen = tk.StringVar(
        value="" if initial is None or initial.maxlen is None else str(initial.maxlen)
    )
    required = tk.StringVar(value="" if initial is None else initial.required)
    result: dict[str, FieldRule | None] = {"rule": None}

    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    ttk.Label(form, text="Chỉ tiêu").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Entry(form, textvariable=code).grid(row=0, column=1, sticky="ew", pady=4)
    ttk.Label(form, text="Kiểu").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Combobox(
        form, textvariable=dtype, values=("Chuỗi", "Số"), state="readonly", width=12
    ).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(form, text="Max length").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Entry(form, textvariable=maxlen).grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Label(form, text="Bắt buộc").grid(row=3, column=0, sticky="w", pady=4)
    ttk.Entry(form, textvariable=required).grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Label(
        form,
        text="x = bắt buộc. Để trống = không bắt buộc. Có thể ghi điều kiện.",
    ).grid(row=4, column=1, sticky="w")
    ttk.Label(form, text="Ghi chú").grid(row=5, column=0, sticky="nw", pady=4)
    notes = tk.Text(form, height=10, wrap="word")
    notes.grid(row=5, column=1, sticky="nsew", pady=4)
    form.rowconfigure(5, weight=1)
    if initial and initial.notes:
        notes.insert("1.0", "\n\n".join(initial.notes))

    def ok() -> None:
        field_code = code.get().strip().upper()
        if not field_code:
            messagebox.showwarning("Thiếu chỉ tiêu", "Nhập mã chỉ tiêu.", parent=win)
            return
        raw_len = maxlen.get().strip()
        parsed_len: int | None
        if not raw_len:
            parsed_len = None
        else:
            try:
                parsed_len = int(raw_len)
            except ValueError:
                messagebox.showwarning("Max length", "Max length phải là số nguyên.", parent=win)
                return
            if parsed_len < 0:
                messagebox.showwarning("Max length", "Max length không được âm.", parent=win)
                return
        kind = dtype.get().strip() or "Chuỗi"
        if kind not in ("Chuỗi", "Số"):
            kind = "Chuỗi"
        note_text = notes.get("1.0", "end").strip()
        note_list = [part.strip() for part in note_text.split("\n\n") if part.strip()]
        result["rule"] = FieldRule(
            code=field_code,
            data_type=kind,
            maxlen=parsed_len,
            required=required.get().strip(),
            notes=note_list,
        )
        win.destroy()

    buttons = ttk.Frame(form)
    buttons.grid(row=6, column=1, sticky="e", pady=(8, 0))
    ttk.Button(buttons, text="Lưu", command=ok).pack(side="left")
    ttk.Button(buttons, text="Hủy", command=win.destroy).pack(side="left", padx=(6, 0))
    win.bind("<Escape>", lambda _e: win.destroy())
    parent.wait_window(win)
    return result["rule"]

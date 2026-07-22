from __future__ import annotations

import json
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox, ttk
from typing import Any

from app.controller import check_product_url
from checker.config import load_json_config
from scraper.product_scraper import is_valid_url


MAX_WORKERS = 3


class ProductCheckerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.severity_styles = load_json_config("severity_styles.json")
        self.title("ABK Product Checker")
        self.geometry("1220x780")
        self.minsize(980, 640)
        self.configure(bg="#101010")

        self.results: list[dict[str, Any]] = []
        self.selected_index: int | None = None
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="No products checked yet.")

        self._build_styles()
        self._build_layout()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#101010")
        style.configure("Panel.TFrame", background="#1b1b1b", relief="solid", borderwidth=1)
        style.configure("Header.TFrame", background="#050505")
        style.configure("Header.TLabel", background="#050505", foreground="#00ff88", font=("Segoe UI", 18, "bold"))
        style.configure("SubHeader.TLabel", background="#050505", foreground="#efe9dc", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#101010", foreground="#f4f7f3", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#1b1b1b", foreground="#00ff88", font=("Segoe UI", 9, "bold"))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Accent.TButton", background="#00ff88", foreground="#050505")
        style.configure("TNotebook", background="#101010", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(16, 8))
        style.configure("Treeview", background="#080808", foreground="#f4f7f3", fieldbackground="#080808", rowheight=30)
        style.configure("Treeview.Heading", background="#050505", foreground="#00ff88", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#143d2b")])

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Header.TFrame", padding=(20, 14))
        header.pack(fill="x")
        ttk.Label(header, text="ABK LISTING PROCESSOR", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="PRODUCT CHECKER APP", style="SubHeader.TLabel").pack(anchor="w", pady=(3, 0))

        input_panel = ttk.Frame(root, style="Panel.TFrame", padding=14)
        input_panel.pack(fill="x", padx=18, pady=(16, 10))
        ttk.Label(input_panel, text="CHECK PRODUCT URLS", style="Panel.TLabel").pack(anchor="w")

        input_row = ttk.Frame(input_panel, style="Panel.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.url_text = tk.Text(
            input_row,
            height=5,
            wrap="word",
            bg="#101010",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
            padx=10,
            pady=8,
        )
        self.url_text.pack(side="left", fill="x", expand=True)
        self.check_button = ttk.Button(input_row, text="CHECK", command=self.start_check, style="Accent.TButton")
        self.check_button.pack(side="left", fill="y", padx=(10, 0))

        summary_row = ttk.Frame(root, style="Root.TFrame")
        summary_row.pack(fill="x", padx=18, pady=(0, 10))
        ttk.Label(summary_row, textvariable=self.summary_var).pack(side="left")
        ttk.Label(summary_row, textvariable=self.status_var).pack(side="right")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        self.checker_tab = ttk.Frame(self.notebook, padding=10, style="Root.TFrame")
        self.log_tab = ttk.Frame(self.notebook, padding=10, style="Root.TFrame")
        self.notebook.add(self.checker_tab, text="CHECKER")
        self.notebook.add(self.log_tab, text="LOG")

        self._build_checker_tab()
        self._build_log_tab()

    def _build_checker_tab(self) -> None:
        self.result_tree = ttk.Treeview(
            self.checker_tab,
            columns=("url", "sku", "issues", "evaluation"),
            show="headings",
            height=8,
        )
        self.result_tree.heading("url", text="URL")
        self.result_tree.heading("sku", text="SKU")
        self.result_tree.heading("issues", text="Issues")
        self.result_tree.heading("evaluation", text="Evaluation")
        self.result_tree.column("url", width=650, anchor="w")
        self.result_tree.column("sku", width=260, anchor="w")
        self.result_tree.column("issues", width=80, anchor="center")
        self.result_tree.column("evaluation", width=110, anchor="center")
        self.result_tree.pack(fill="x")
        self.result_tree.bind("<<TreeviewSelect>>", self._on_result_select)

        self.result_tree.tag_configure("pass", foreground="#00ff88")
        self.result_tree.tag_configure("fail", foreground="#ff5b5b")
        self.result_tree.tag_configure("checking", foreground="#facc15")

        detail_frame = ttk.Frame(self.checker_tab, style="Root.TFrame")
        detail_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.detail_text = tk.Text(
            detail_frame,
            wrap="word",
            bg="#050505",
            fg="#f4f7f3",
            insertbackground="#ffffff",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
            padx=12,
            pady=12,
        )
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")

        self.detail_text.tag_configure("PASS", foreground="#00ff88", font=("Segoe UI", 15, "bold"))
        self.detail_text.tag_configure("FAIL", foreground="#ff5b5b", font=("Segoe UI", 15, "bold"))
        self.detail_text.tag_configure("heading", foreground="#00ff88", font=("Segoe UI", 11, "bold"))
        for severity, colors in self.severity_styles.items():
            self.detail_text.tag_configure(severity, foreground=colors["fg"], background=colors["bg"], font=("Segoe UI", 9, "bold"))
        self._set_detail_text("Paste product URLs and press CHECK.")

    def _build_log_tab(self) -> None:
        self.log_text = tk.Text(
            self.log_tab,
            wrap="none",
            font=("Consolas", 10),
            bg="#050505",
            fg="#e5e7eb",
            insertbackground="#ffffff",
            relief="solid",
            borderwidth=1,
            padx=12,
            pady=12,
        )
        y_scroll = ttk.Scrollbar(self.log_tab, orient="vertical", command=self.log_text.yview)
        x_scroll = ttk.Scrollbar(self.log_tab, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.log_tab.rowconfigure(0, weight=1)
        self.log_tab.columnconfigure(0, weight=1)
        self._set_log_text("No product data loaded.")

    def start_check(self) -> None:
        urls = self._parse_urls()
        if not urls:
            messagebox.showerror("Invalid URL", "Please paste at least one product URL.")
            return

        invalid = [url for url in urls if not is_valid_url(url)]
        if invalid:
            messagebox.showerror("Invalid URL", f"Invalid URL:\n{invalid[0]}")
            return

        self.results = [{"url": url, "status": "pending", "product": None, "issues": [], "error": None} for url in urls]
        self.selected_index = None
        self.check_button.configure(state="disabled")
        self.status_var.set("Checking products...")
        self.summary_var.set(f"0/{len(urls)} completed")
        self._render_result_table()
        self._set_detail_text("Checking, please wait...")
        self._set_log_text("")

        thread = threading.Thread(target=self._batch_worker, daemon=True)
        thread.start()

    def _parse_urls(self) -> list[str]:
        raw = self.url_text.get("1.0", "end")
        urls = [line.strip() for line in raw.splitlines() if line.strip()]
        return list(dict.fromkeys(urls))

    def _batch_worker(self) -> None:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(self.results) or 1)) as executor:
            future_map = {}
            for index, item in enumerate(self.results):
                self.after(0, lambda i=index: self._mark_checking(i))
                future = executor.submit(check_product_url, item["url"])
                future_map[future] = index

            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    product_data, issues = future.result()
                    payload = {"status": "done", "product": product_data, "issues": issues, "error": None}
                except Exception as exc:
                    payload = {"status": "error", "product": None, "issues": [], "error": str(exc)}
                self.after(0, lambda i=index, p=payload: self._update_result(i, p))

        self.after(0, self._finish_batch)

    def _mark_checking(self, index: int) -> None:
        if index < len(self.results):
            self.results[index]["status"] = "checking"
            self._render_result_table()

    def _update_result(self, index: int, payload: dict[str, Any]) -> None:
        self.results[index].update(payload)
        self._render_result_table()
        self._update_summary()
        if self.selected_index is None:
            self._select_row(index)

    def _finish_batch(self) -> None:
        self._update_summary()
        self.status_var.set("Completed")
        self.check_button.configure(state="normal")

    def _update_summary(self) -> None:
        completed = sum(1 for item in self.results if item["status"] in {"done", "error"})
        failed = sum(1 for item in self.results if self._evaluation(item) == "FAIL")
        passed = completed - failed
        issues = sum(self._issue_count(item) for item in self.results)
        self.summary_var.set(f"{completed}/{len(self.results)} completed | PASS {passed} | FAIL {failed} | Issues {issues}")

    def _render_result_table(self) -> None:
        self.result_tree.delete(*self.result_tree.get_children())
        for index, item in enumerate(self.results):
            product = item.get("product") or {}
            evaluation = self._evaluation(item)
            tag = "checking" if evaluation == "CHECKING" else evaluation.lower()
            self.result_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(item["url"], product.get("sku") or "-", self._issue_count(item), evaluation),
                tags=(tag,),
            )

    def _on_result_select(self, _event: Any) -> None:
        selected = self.result_tree.selection()
        if selected:
            self._select_row(int(selected[0]))

    def _select_row(self, index: int) -> None:
        self.selected_index = index
        if self.result_tree.exists(str(index)):
            self.result_tree.selection_set(str(index))
            self.result_tree.focus(str(index))
        self._render_detail(index)

    def _render_detail(self, index: int) -> None:
        item = self.results[index]
        product = item.get("product") or {}
        issues = item.get("issues") or []
        error = item.get("error")
        evaluation = self._evaluation(item)

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", f"{product.get('sku') or 'No SKU'} - {evaluation}\n", "PASS" if evaluation == "PASS" else "FAIL")
        self.detail_text.insert("end", f"URL: {item['url']}\n\n", "heading")

        if error:
            self.detail_text.insert("end", f"Fetch error:\n{error}\n")
        elif not issues:
            self.detail_text.insert("end", "PASS", "PASS")
            self.detail_text.insert("end", "\nNo issues were found by the current test cases.\n")
        else:
            for issue_index, issue in enumerate(issues, start=1):
                severity = issue.get("severity", "NOTICE")
                self.detail_text.insert("end", f"{severity}\n", severity)
                self.detail_text.insert("end", f"{issue_index}. [{issue.get('code', 'NO_CODE')}] {issue.get('title', 'Unnamed issue')}\n")
                self.detail_text.insert("end", f"Test case: {issue.get('case_name', '')}\n")
                self.detail_text.insert("end", f"Found: {issue.get('found', '')}\n")
                self.detail_text.insert("end", f"Expected: {issue.get('expected', '')}\n")
                self.detail_text.insert("end", f"Explanation: {issue.get('explanation', issue.get('detail', ''))}\n\n")

        self.detail_text.configure(state="disabled")
        self._set_log_text(json.dumps(item, ensure_ascii=False, indent=2))

    def _evaluation(self, item: dict[str, Any]) -> str:
        if item.get("status") in {"pending", "checking"}:
            return "CHECKING"
        if item.get("status") == "error":
            return "FAIL"
        return "FAIL" if item.get("issues") else "PASS"

    def _issue_count(self, item: dict[str, Any]) -> int:
        if item.get("status") == "error":
            return 1
        return len(item.get("issues") or [])

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", text)
        self.detail_text.configure(state="disabled")

    def _set_log_text(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", text)
        self.log_text.configure(state="disabled")


def main() -> None:
    app = ProductCheckerApp()
    app.mainloop()

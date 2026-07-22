from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from app.controller import check_product_url
from checker.config import load_json_config
from scraper.product_scraper import is_valid_url


class ProductCheckerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.severity_styles = load_json_config("severity_styles.json")
        self.title("ABK Product Checker")
        self.geometry("1080x720")
        self.minsize(900, 620)
        self.configure(bg="#f4f6f8")

        self.url_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready to check a product.")
        self.last_product_data: dict[str, Any] | None = None

        self._build_styles()
        self._build_layout()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("Header.TFrame", background="#111827")
        style.configure("Header.TLabel", background="#111827", foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.TLabel", background="#111827", foreground="#d1d5db", font=("Segoe UI", 10))
        style.configure("TLabel", background="#f4f6f8", foreground="#111827", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("TNotebook", background="#f4f6f8", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(16, 8))

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(18, 14))
        header.pack(fill="x")

        ttk.Label(header, text="ABK Product Checker", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Enter a product URL to extract data and display validation results.",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        input_frame = ttk.Frame(self, padding=(18, 14))
        input_frame.pack(fill="x")

        ttk.Label(input_frame, text="URL LINK").pack(anchor="w")
        row = ttk.Frame(input_frame)
        row.pack(fill="x", pady=(6, 0))

        self.url_entry = ttk.Entry(row, textvariable=self.url_var, font=("Segoe UI", 10))
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda _event: self.start_check())

        self.check_button = ttk.Button(row, text="CHECK", command=self.start_check)
        self.check_button.pack(side="left", padx=(10, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self.checker_tab = ttk.Frame(self.notebook, padding=12)
        self.log_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.checker_tab, text="CHECKER")
        self.notebook.add(self.log_tab, text="LOG")

        self._build_checker_tab()
        self._build_log_tab()

        status_bar = ttk.Frame(self, padding=(18, 8))
        status_bar.pack(fill="x")
        ttk.Label(status_bar, textvariable=self.status_var).pack(anchor="w")

    def _build_checker_tab(self) -> None:
        legend = ttk.Frame(self.checker_tab)
        legend.pack(fill="x", pady=(0, 10))

        for severity, colors in self.severity_styles.items():
            label = tk.Label(
                legend,
                text=severity,
                bg=colors["bg"],
                fg=colors["fg"],
                font=("Segoe UI", 9, "bold"),
                padx=10,
                pady=4,
            )
            label.pack(side="left", padx=(0, 8))

        self.checker_text = tk.Text(
            self.checker_tab,
            wrap="word",
            font=("Segoe UI", 11),
            bg="#ffffff",
            fg="#111827",
            relief="solid",
            borderwidth=1,
            padx=12,
            pady=12,
        )
        self.checker_text.pack(fill="both", expand=True)
        self.checker_text.configure(state="disabled")

        self.checker_text.tag_configure("PASS", foreground="#15803d", font=("Segoe UI", 16, "bold"))
        for severity, colors in self.severity_styles.items():
            self.checker_text.tag_configure(
                severity,
                foreground=colors["fg"],
                background=colors["bg"],
                font=("Segoe UI", 10, "bold"),
                spacing1=6,
                spacing3=6,
            )

    def _build_log_tab(self) -> None:
        self.log_text = tk.Text(
            self.log_tab,
            wrap="none",
            font=("Consolas", 10),
            bg="#0f172a",
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

    def start_check(self) -> None:
        url = self.url_var.get().strip()
        if not is_valid_url(url):
            messagebox.showerror("Invalid URL", "Please enter a link that starts with http:// or https://")
            return

        self.check_button.configure(state="disabled")
        self.status_var.set("Loading product data...")
        self._set_checker_text("Checking, please wait...\n")
        self._set_log_text("")

        thread = threading.Thread(target=self._check_worker, args=(url,), daemon=True)
        thread.start()

    def _check_worker(self, url: str) -> None:
        try:
            product_data, issues = check_product_url(url)
        except Exception as exc:
            self.after(0, lambda: self._show_error(exc))
            return

        self.after(0, lambda: self._show_result(product_data, issues))

    def _show_result(self, product_data: dict[str, Any], issues: list[dict[str, str]]) -> None:
        self.last_product_data = product_data
        self._render_checker(issues)
        self._set_log_text(json.dumps(product_data, ensure_ascii=False, indent=2))
        self.status_var.set("Product check completed.")
        self.check_button.configure(state="normal")

    def _show_error(self, exc: Exception) -> None:
        self._set_checker_text(f"Product check failed:\n{exc}")
        self._set_log_text("")
        self.status_var.set("Check failed.")
        self.check_button.configure(state="normal")

    def _render_checker(self, issues: list[dict[str, str]]) -> None:
        self.checker_text.configure(state="normal")
        self.checker_text.delete("1.0", "end")

        if not issues:
            self.checker_text.insert("end", "PASS", "PASS")
            self.checker_text.insert("end", "\nNo issues were found by the current test cases.")
        else:
            for index, issue in enumerate(issues, start=1):
                severity = issue.get("severity", "NOTICE")
                code = issue.get("code", "NO_CODE")
                case_name = issue.get("case_name", "Unnamed test case")
                title = issue.get("title", "Unnamed issue")
                found = issue.get("found", "")
                expected = issue.get("expected", "")
                explanation = issue.get("explanation", issue.get("detail", ""))

                self.checker_text.insert("end", f"{severity}\n", severity)
                self.checker_text.insert("end", f"{index}. [{code}] {title}\n")
                self.checker_text.insert("end", f"   Test case: {case_name}\n")
                if found:
                    self.checker_text.insert("end", f"   Found: {found}\n")
                if expected:
                    self.checker_text.insert("end", f"   Expected: {expected}\n")
                if explanation:
                    self.checker_text.insert("end", f"   Explanation: {explanation}\n")
                self.checker_text.insert("end", "\n")

        self.checker_text.configure(state="disabled")

    def _set_checker_text(self, text: str) -> None:
        self.checker_text.configure(state="normal")
        self.checker_text.delete("1.0", "end")
        self.checker_text.insert("end", text)
        self.checker_text.configure(state="disabled")

    def _set_log_text(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", text)
        self.log_text.configure(state="disabled")


def main() -> None:
    app = ProductCheckerApp()
    app.mainloop()

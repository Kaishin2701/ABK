from __future__ import annotations

import csv
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import requests
import tkinter as tk
from bs4 import BeautifulSoup
from PIL import Image, ImageTk

from app.controller import check_product_url
from checker.config import load_json_config, project_path
from scraper.product_scraper import is_valid_url

MAX_PRODUCT_WORKERS = 3
MAX_LINK_WORKERS = 8
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class ABKToolApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ABK Tool App")
        self.geometry("1420x820")
        self.minsize(1120, 680)
        self.configure(bg="#101010")
        self.severity_styles = load_json_config("severity_styles.json")
        self.product_results: list[dict[str, Any]] = []
        self.selected_product_index: int | None = None
        self.link_rows: list[dict[str, Any]] = []
        self.stop_link_check = threading.Event()
        self.tool_frames: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.watermark_images: list[Path] = []
        self.watermark_file: Path | None = self._default_watermark()
        self.logo_image: ImageTk.PhotoImage | None = None
        self.status_var = tk.StringVar(value="READY")
        self.page_title_var = tk.StringVar(value="PRODUCT CHECKER")
        self._build_styles()
        self._build_layout()
        self.show_tool("product")

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#101010")
        style.configure("Sidebar.TFrame", background="#050505")
        style.configure("Panel.TFrame", background="#1b1b1b", relief="solid", borderwidth=1)
        style.configure("Tool.TFrame", background="#101010")
        style.configure("Header.TLabel", background="#101010", foreground="#00ff88", font=("Segoe UI", 18, "bold"))
        style.configure("SubHeader.TLabel", background="#101010", foreground="#fff7e6", font=("Segoe UI", 10, "bold"))
        style.configure("Panel.TLabel", background="#1b1b1b", foreground="#00ff88", font=("Segoe UI", 9, "bold"))
        style.configure("TLabel", background="#101010", foreground="#f4f7f3", font=("Segoe UI", 10))
        style.configure("Sidebar.TLabel", background="#050505", foreground="#00ff88", font=("Segoe UI", 12, "bold"))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.configure("Accent.TButton", background="#00ff88", foreground="#050505")
        style.configure("Danger.TButton", background="#2c2c2c", foreground="#ff5b5b")
        style.configure("TNotebook", background="#101010", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(16, 8))
        style.configure("Treeview", background="#080808", foreground="#f4f7f3", fieldbackground="#080808", rowheight=30)
        style.configure("Treeview.Heading", background="#050505", foreground="#00ff88", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#143d2b")])

    def _build_layout(self) -> None:
        shell = ttk.Frame(self, style="Root.TFrame")
        shell.pack(fill="both", expand=True)
        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", width=180, padding=(14, 18))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)
        main = ttk.Frame(shell, style="Root.TFrame")
        main.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(main, style="Root.TFrame", padding=(18, 14))
        header.pack(fill="x")
        left = ttk.Frame(header, style="Root.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="ABK LISTING PROCESSOR", style="Header.TLabel").pack(anchor="w")
        ttk.Label(left, textvariable=self.page_title_var, style="SubHeader.TLabel").pack(anchor="w", pady=(3, 0))
        tk.Label(header, textvariable=self.status_var, bg="#050505", fg="#00ff88", font=("Segoe UI", 9, "bold"), width=14, relief="solid", bd=1, padx=12, pady=8).pack(side="right")
        self.content = ttk.Frame(main, style="Root.TFrame")
        self.content.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self._build_product_checker()
        self._build_watermark()
        self._build_link_checker()
        self._build_html_cleaner()
        self._build_sku_generator()

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        logo = project_path("static/assets/logo.png")
        if logo.exists():
            try:
                image = Image.open(logo)
                image.thumbnail((72, 72))
                self.logo_image = ImageTk.PhotoImage(image)
                tk.Label(parent, image=self.logo_image, bg="#050505").pack(pady=(0, 12))
            except Exception:
                pass
        ttk.Label(parent, text="ABK TOOL", style="Sidebar.TLabel").pack(pady=(0, 24))
        for key, label in [("product", "Product Checker"), ("watermark", "Auto Watermark"), ("link", "Link Checker"), ("html", "HTML Cleaner"), ("sku", "SKU Generator")]:
            button = tk.Button(parent, text=label, command=lambda tool=key: self.show_tool(tool), anchor="w", bg="#000000", fg="#fff7e6", activebackground="#00ff88", activeforeground="#050505", relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=12)
            button.pack(fill="x", pady=(0, 10))
            self.nav_buttons[key] = button
        ttk.Label(parent, text="Ver 3.0 App", background="#050505", foreground="#d7ccba").pack(side="bottom")

    def _make_tool_frame(self, key: str) -> ttk.Frame:
        frame = ttk.Frame(self.content, style="Tool.TFrame")
        self.tool_frames[key] = frame
        return frame

    def show_tool(self, key: str) -> None:
        for frame in self.tool_frames.values():
            frame.pack_forget()
        self.tool_frames[key].pack(fill="both", expand=True)
        for nav_key, button in self.nav_buttons.items():
            active = nav_key == key
            button.configure(bg="#00ff88" if active else "#000000", fg="#050505" if active else "#fff7e6")
        titles = {"product": "PRODUCT CHECKER", "watermark": "AUTO WATERMARK", "link": "LINK CHECKER", "html": "HTML CLEANER", "sku": "SKU GENERATOR"}
        self.page_title_var.set(titles[key])
        self.status_var.set("READY")

    def _panel(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        frame.pack(fill="x", pady=(0, 12))
        ttk.Label(frame, text=title, style="Panel.TLabel").pack(anchor="w", pady=(0, 8))
        return frame

    def _text(self, parent: ttk.Frame, height: int = 5, mono: bool = False) -> tk.Text:
        return tk.Text(parent, height=height, wrap="word", bg="#101010", fg="#ffffff", insertbackground="#ffffff", relief="solid", borderwidth=1, padx=10, pady=8, font=("Consolas", 10) if mono else ("Segoe UI", 10))

    def _build_product_checker(self) -> None:
        frame = self._make_tool_frame("product")
        panel = self._panel(frame, "CHECK PRODUCT URLS")
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x")
        self.product_input = self._text(row, height=5)
        self.product_input.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="CHECK", command=self.start_product_check, style="Accent.TButton").pack(side="left", fill="y", padx=(10, 0))
        summary = ttk.Frame(frame, style="Root.TFrame")
        summary.pack(fill="x", pady=(0, 12))
        self.product_summary_vars = {"result": tk.StringVar(value="Waiting"), "issues": tk.StringVar(value="0"), "sku": tk.StringVar(value="-"), "reviews": tk.StringVar(value="-")}
        for label, var in [("RESULT", "result"), ("ISSUES", "issues"), ("SKU", "sku"), ("REVIEWS", "reviews")]:
            card = ttk.Frame(summary, style="Panel.TFrame", padding=12)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            ttk.Label(card, text=label, style="Panel.TLabel").pack(anchor="w")
            tk.Label(card, textvariable=self.product_summary_vars[var], bg="#000000", fg="#00ff88", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(8, 0))
        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)
        checker = ttk.Frame(notebook, style="Root.TFrame", padding=10)
        log = ttk.Frame(notebook, style="Root.TFrame", padding=10)
        notebook.add(checker, text="CHECKER")
        notebook.add(log, text="LOG")
        self.product_table = ttk.Treeview(checker, columns=("url", "sku", "issues", "evaluation"), show="headings", height=8)
        for col, title, width in [("url", "URL", 760), ("sku", "SKU", 260), ("issues", "Issues", 80), ("evaluation", "Evaluation", 110)]:
            self.product_table.heading(col, text=title)
            self.product_table.column(col, width=width, anchor="w" if col in {"url", "sku"} else "center")
        self.product_table.pack(fill="x")
        self.product_table.bind("<<TreeviewSelect>>", self._on_product_select)
        self.product_table.tag_configure("pass", foreground="#00ff88")
        self.product_table.tag_configure("fail", foreground="#ff5b5b")
        self.product_table.tag_configure("checking", foreground="#facc15")
        self.product_detail = self._text(checker, height=16)
        self.product_detail.pack(fill="both", expand=True, pady=(10, 0))
        self.product_detail.tag_configure("PASS", foreground="#00ff88", font=("Segoe UI", 15, "bold"))
        self.product_detail.tag_configure("FAIL", foreground="#ff5b5b", font=("Segoe UI", 15, "bold"))
        self.product_detail.tag_configure("heading", foreground="#00ff88", font=("Segoe UI", 11, "bold"))
        for severity, colors in self.severity_styles.items():
            self.product_detail.tag_configure(severity, foreground=colors["fg"], background=colors["bg"], font=("Segoe UI", 9, "bold"))
        self.product_log = self._text(log, height=24, mono=True)
        self.product_log.pack(fill="both", expand=True)
        self._set_text(self.product_detail, "Paste product URLs and press CHECK.", disabled=True)
        self._set_text(self.product_log, "No product data loaded.", disabled=True)

    def start_product_check(self) -> None:
        urls = self._extract_lines(self.product_input.get("1.0", "end"))
        invalid = [url for url in urls if not is_valid_url(url)]
        if not urls:
            messagebox.showerror("Invalid URL", "Please paste at least one product URL.")
            return
        if invalid:
            messagebox.showerror("Invalid URL", f"Invalid URL:\n{invalid[0]}")
            return
        self.product_results = [{"url": url, "status": "pending", "product": None, "issues": [], "error": None} for url in urls]
        self.selected_product_index = None
        self._render_product_table()
        self._set_text(self.product_detail, "Checking, please wait...", disabled=True)
        self._set_text(self.product_log, "", disabled=True)
        self.status_var.set("CHECKING")
        threading.Thread(target=self._product_worker, daemon=True).start()

    def _product_worker(self) -> None:
        with ThreadPoolExecutor(max_workers=min(MAX_PRODUCT_WORKERS, len(self.product_results) or 1)) as executor:
            futures = {}
            for index, item in enumerate(self.product_results):
                self.after(0, lambda i=index: self._mark_product(i, "checking"))
                futures[executor.submit(check_product_url, item["url"])] = index
            for future in as_completed(futures):
                index = futures[future]
                try:
                    product, issues = future.result()
                    payload = {"status": "done", "product": product, "issues": issues, "error": None}
                except Exception as exc:
                    payload = {"status": "error", "product": None, "issues": [], "error": str(exc)}
                self.after(0, lambda i=index, p=payload: self._update_product(i, p))
        self.after(0, lambda: self.status_var.set("COMPLETE"))

    def _mark_product(self, index: int, status: str) -> None:
        self.product_results[index]["status"] = status
        self._render_product_table()
        self._update_product_summary()

    def _update_product(self, index: int, payload: dict[str, Any]) -> None:
        self.product_results[index].update(payload)
        self._render_product_table()
        self._update_product_summary()
        if self.selected_product_index is None:
            self._select_product(index)
    def _render_product_table(self) -> None:
        self.product_table.delete(*self.product_table.get_children())
        for index, item in enumerate(self.product_results):
            product = item.get("product") or {}
            evaluation = self._product_eval(item)
            self.product_table.insert("", "end", iid=str(index), values=(item["url"], product.get("sku") or ("Checking..." if evaluation == "CHECKING" else "-"), self._product_issue_count(item), evaluation), tags=(evaluation.lower(),))

    def _on_product_select(self, _event: Any) -> None:
        selection = self.product_table.selection()
        if selection:
            self._select_product(int(selection[0]))

    def _select_product(self, index: int) -> None:
        self.selected_product_index = index
        if self.product_table.exists(str(index)):
            self.product_table.selection_set(str(index))
        self._render_product_detail(index)

    def _render_product_detail(self, index: int) -> None:
        item = self.product_results[index]
        product = item.get("product") or {}
        issues = item.get("issues") or []
        evaluation = self._product_eval(item)
        self.product_detail.configure(state="normal")
        self.product_detail.delete("1.0", "end")
        self.product_detail.insert("end", f"{product.get('sku') or 'No SKU'} - {evaluation}\n", "PASS" if evaluation == "PASS" else "FAIL")
        self.product_detail.insert("end", f"URL: {item['url']}\n\n", "heading")
        if item.get("error"):
            self.product_detail.insert("end", f"Fetch error:\n{item['error']}\n")
        elif not issues and evaluation != "CHECKING":
            self.product_detail.insert("end", "PASS", "PASS")
            self.product_detail.insert("end", "\nNo issues were found by the current test cases.\n")
        else:
            for issue_index, issue in enumerate(issues, start=1):
                severity = issue.get("severity", "NOTICE")
                self.product_detail.insert("end", f"{severity}\n", severity)
                self.product_detail.insert("end", f"{issue_index}. [{issue.get('code', 'NO_CODE')}] {issue.get('title', 'Unnamed issue')}\n")
                self.product_detail.insert("end", f"Test case: {issue.get('case_name', '')}\n")
                self.product_detail.insert("end", f"Found: {issue.get('found', '')}\n")
                self.product_detail.insert("end", f"Expected: {issue.get('expected', '')}\n")
                self.product_detail.insert("end", f"Explanation: {issue.get('explanation', issue.get('detail', ''))}\n\n")
        self.product_detail.configure(state="disabled")
        self._set_text(self.product_log, json.dumps(item, ensure_ascii=False, indent=2), disabled=True)

    def _update_product_summary(self) -> None:
        completed = [item for item in self.product_results if item["status"] in {"done", "error"}]
        failed = [item for item in self.product_results if self._product_eval(item) == "FAIL"]
        total_issues = sum(self._product_issue_count(item) for item in self.product_results if item["status"] in {"done", "error"})
        self.product_summary_vars["result"].set(f"{len(completed)}/{len(self.product_results)}" if completed else "Waiting")
        self.product_summary_vars["issues"].set(str(total_issues))
        if len(self.product_results) == 1:
            product = self.product_results[0].get("product") or {}
            self.product_summary_vars["sku"].set(product.get("sku") or "-")
            self.product_summary_vars["reviews"].set(str(product.get("review_count", "-")))
        else:
            self.product_summary_vars["sku"].set(f"{len(failed)} Fail")
            self.product_summary_vars["reviews"].set(f"{len(completed) - len(failed)} Pass")

    def _product_eval(self, item: dict[str, Any]) -> str:
        if item.get("status") in {"pending", "checking"}:
            return "CHECKING"
        if item.get("status") == "error":
            return "FAIL"
        return "FAIL" if item.get("issues") else "PASS"

    def _product_issue_count(self, item: dict[str, Any]) -> int:
        return 1 if item.get("status") == "error" else len(item.get("issues") or [])

    def _build_watermark(self) -> None:
        frame = self._make_tool_frame("watermark")
        panel = self._panel(frame, "IMAGE GALLERY")
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="Select Images", command=self.select_watermark_images, style="Accent.TButton").pack(side="left")
        ttk.Button(row, text="Clear Gallery", command=self.clear_watermark_images).pack(side="left", padx=(8, 0))
        self.watermark_gallery_var = tk.StringVar(value="No images selected.")
        ttk.Label(panel, textvariable=self.watermark_gallery_var, style="Panel.TLabel").pack(anchor="w", pady=(10, 0))
        settings = self._panel(frame, "WATERMARK SETTINGS")
        wm_row = ttk.Frame(settings, style="Panel.TFrame")
        wm_row.pack(fill="x", pady=(0, 8))
        self.watermark_path_var = tk.StringVar(value=str(self.watermark_file) if self.watermark_file else "No watermark selected.")
        ttk.Label(wm_row, textvariable=self.watermark_path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(wm_row, text="Select Logo", command=self.select_watermark_file).pack(side="left", padx=(8, 0))
        controls = ttk.Frame(settings, style="Panel.TFrame")
        controls.pack(fill="x")
        ttk.Label(controls, text="Mode:", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.watermark_mode = tk.StringVar(value="Fullscreen")
        ttk.Combobox(controls, textvariable=self.watermark_mode, values=["Fullscreen", "Bottom-right", "Tile"], state="readonly", width=18).grid(row=0, column=1, sticky="w")
        ttk.Label(controls, text="Rename:", style="Panel.TLabel").grid(row=0, column=2, sticky="w", padx=(20, 6))
        self.watermark_rename = tk.StringVar(value="{default name}")
        ttk.Entry(controls, textvariable=self.watermark_rename, width=36).grid(row=0, column=3, sticky="ew")
        controls.columnconfigure(3, weight=1)
        self.watermark_quality = tk.IntVar(value=85)
        self.watermark_opacity = tk.IntVar(value=100)
        ttk.Label(controls, text="Quality:", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Scale(controls, from_=1, to=100, variable=self.watermark_quality, orient="horizontal").grid(row=1, column=1, sticky="ew", pady=(10, 0))
        ttk.Label(controls, text="Opacity:", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Scale(controls, from_=0, to=100, variable=self.watermark_opacity, orient="horizontal").grid(row=2, column=1, sticky="ew", pady=(6, 0))
        self.watermark_log = self._text(frame, height=15, mono=True)
        self.watermark_log.pack(fill="both", expand=True, pady=(0, 12))
        ttk.Button(frame, text="START PROCESSING", command=self.start_watermark_process, style="Accent.TButton").pack(fill="x")

    def select_watermark_images(self) -> None:
        files = filedialog.askopenfilenames(title="Select images", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")])
        self.watermark_images.extend(Path(file) for file in files if Path(file).suffix.lower() in IMAGE_TYPES)
        self._update_watermark_gallery()
        self._tool_log(self.watermark_log, f"Added {len(files)} image(s).")

    def clear_watermark_images(self) -> None:
        self.watermark_images = []
        self._update_watermark_gallery()
        self._tool_log(self.watermark_log, "Cleared image gallery.")

    def select_watermark_file(self) -> None:
        file = filedialog.askopenfilename(title="Select watermark", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")])
        if file:
            self.watermark_file = Path(file)
            self.watermark_path_var.set(str(self.watermark_file))
            self._tool_log(self.watermark_log, f"Loaded watermark: {self.watermark_file.name}")

    def start_watermark_process(self) -> None:
        if not self.watermark_images:
            messagebox.showerror("No images", "Please select at least one image.")
            return
        output_dir = filedialog.askdirectory(title="Select output folder")
        if not output_dir:
            return
        self.status_var.set("PROCESSING")
        self._set_text(self.watermark_log, "")
        threading.Thread(target=self._watermark_worker, args=(Path(output_dir),), daemon=True).start()
    def _watermark_worker(self, output_dir: Path) -> None:
        processed = 0
        for image_path in self.watermark_images:
            try:
                output = self._process_one_image(image_path, output_dir)
                processed += 1
                self.after(0, lambda msg=f"OK: {image_path.name} -> {output.name}": self._tool_log(self.watermark_log, msg))
            except Exception as exc:
                self.after(0, lambda msg=f"Error: {image_path.name} - {exc}": self._tool_log(self.watermark_log, msg))
        self.after(0, lambda: self._tool_log(self.watermark_log, f"Done. Processed {processed}/{len(self.watermark_images)} image(s)."))
        self.after(0, lambda: self.status_var.set("COMPLETE"))

    def _process_one_image(self, image_path: Path, output_dir: Path) -> Path:
        image = Image.open(image_path).convert("RGBA")
        if self.watermark_file and self.watermark_file.exists():
            watermark = Image.open(self.watermark_file).convert("RGBA")
            overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
            alpha = max(0, min(100, self.watermark_opacity.get())) / 100
            mode = self.watermark_mode.get()
            if mode == "Fullscreen":
                mark = watermark.resize(image.size)
                overlay.alpha_composite(mark)
            elif mode == "Bottom-right":
                mark_w = max(int(image.width * 0.2), 50)
                mark_h = int(mark_w * watermark.height / watermark.width)
                mark = watermark.resize((mark_w, mark_h))
                overlay.alpha_composite(mark, (image.width - mark_w - 20, image.height - mark_h - 20))
            else:
                mark_w = max(int(image.width * 0.25), 50)
                mark_h = int(mark_w * watermark.height / watermark.width)
                mark = watermark.resize((mark_w, mark_h))
                for x in range(0, image.width + mark_w, mark_w + 50):
                    for y in range(0, image.height + mark_h, mark_h + 50):
                        overlay.alpha_composite(mark, (x, y))
            if alpha < 1:
                overlay.putalpha(overlay.getchannel("A").point(lambda value: int(value * alpha)))
            image = Image.alpha_composite(image, overlay)
        base_name = self.watermark_rename.get().replace("{default name}", image_path.stem)
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", base_name).strip() or image_path.stem
        output = output_dir / f"{safe_name}.webp"
        quality = max(1, min(100, self.watermark_quality.get()))
        image.convert("RGB").save(output, "WEBP", quality=quality)
        return output

    def _update_watermark_gallery(self) -> None:
        if not self.watermark_images:
            self.watermark_gallery_var.set("No images selected.")
        else:
            self.watermark_gallery_var.set(f"{len(self.watermark_images)} image(s): " + ", ".join(path.name for path in self.watermark_images[:5]))

    def _default_watermark(self) -> Path | None:
        path = project_path("static/watermark/RFS.jpg")
        return path if path.exists() else None

    def _build_link_checker(self) -> None:
        frame = self._make_tool_frame("link")
        panel = self._panel(frame, "CHECK LINKS")
        self.link_input = self._text(panel, height=8)
        self.link_input.pack(fill="x")
        controls = ttk.Frame(panel, style="Panel.TFrame")
        controls.pack(fill="x", pady=(10, 0))
        self.link_filter = tk.StringVar(value="Show All")
        ttk.Combobox(controls, textvariable=self.link_filter, values=["Show All", "Live (200)", "Dead (404)", "Error"], state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="CHECK LINKS", command=self.start_link_check, style="Accent.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="STOP", command=self.stop_link_check.set, style="Danger.TButton").pack(side="left", padx=(8, 0))
        self.link_filter.trace_add("write", lambda *_args: self._render_link_table())
        self.link_stats_var = tk.StringVar(value="Live: 0 | Dead: 0 | Error: 0")
        ttk.Label(panel, textvariable=self.link_stats_var).pack(anchor="e", pady=(8, 0))
        self.link_table = ttk.Treeview(frame, columns=("status", "url", "message"), show="headings", height=18)
        for col, title, width in [("status", "Status", 100), ("url", "URL", 760), ("message", "Message", 420)]:
            self.link_table.heading(col, text=title)
            self.link_table.column(col, width=width, anchor="w")
        self.link_table.pack(fill="both", expand=True)
        self.link_table.tag_configure("live", foreground="#00ff88")
        self.link_table.tag_configure("dead", foreground="#ff5b5b")
        self.link_table.tag_configure("error", foreground="#38bdf8")

    def start_link_check(self) -> None:
        urls = re.findall(r"https?://[^\s<>'\"]+", self.link_input.get("1.0", "end"))
        urls = list(dict.fromkeys(urls))
        if not urls:
            messagebox.showerror("No URLs", "No URLs found.")
            return
        self.link_rows = [{"status": "...", "url": url, "message": "Checking...", "kind": "error"} for url in urls]
        self.stop_link_check.clear()
        self.status_var.set("CHECKING")
        self._render_link_table()
        threading.Thread(target=self._link_worker, args=(urls,), daemon=True).start()

    def _link_worker(self, urls: list[str]) -> None:
        def check(url: str) -> dict[str, Any]:
            if self.stop_link_check.is_set():
                return {"status": "STOP", "url": url, "message": "Stopped", "kind": "error"}
            headers = {"User-Agent": "ABK-Tool-LinkChecker/1.0"}
            try:
                response = requests.head(url, headers=headers, allow_redirects=True, timeout=12)
                if response.status_code in {403, 405}:
                    response = requests.get(url, headers=headers, allow_redirects=True, timeout=12, stream=True)
                kind = "live" if 200 <= response.status_code < 400 else "dead" if response.status_code == 404 else "error"
                return {"status": response.status_code, "url": url, "message": response.reason or "Checked", "kind": kind}
            except requests.RequestException as exc:
                return {"status": "ERR", "url": url, "message": str(exc), "kind": "error"}
        with ThreadPoolExecutor(max_workers=min(MAX_LINK_WORKERS, len(urls))) as executor:
            futures = {executor.submit(check, url): index for index, url in enumerate(urls)}
            for future in as_completed(futures):
                index = futures[future]
                if index < len(self.link_rows):
                    self.link_rows[index] = future.result()
                    self.after(0, self._render_link_table)
        self.after(0, lambda: self.status_var.set("COMPLETE"))

    def _render_link_table(self) -> None:
        self.link_table.delete(*self.link_table.get_children())
        filter_value = self.link_filter.get()
        stats = {"live": 0, "dead": 0, "error": 0}
        for row in self.link_rows:
            kind = row.get("kind", "error")
            if kind in stats:
                stats[kind] += 1
            show = filter_value == "Show All" or (filter_value == "Live (200)" and kind == "live") or (filter_value == "Dead (404)" and kind == "dead") or (filter_value == "Error" and kind == "error")
            if show:
                self.link_table.insert("", "end", values=(row["status"], row["url"], row["message"]), tags=(kind,))
        self.link_stats_var.set(f"Live: {stats['live']} | Dead: {stats['dead']} | Error: {stats['error']}")

    def _build_html_cleaner(self) -> None:
        frame = self._make_tool_frame("html")
        top = ttk.Frame(frame, style="Root.TFrame")
        top.pack(fill="both", expand=True)
        left = self._panel(top, "INPUT HTML")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = self._panel(top, "CLEANED HTML")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.html_input = self._text(left, height=24, mono=True)
        self.html_input.pack(fill="both", expand=True)
        self.html_output = self._text(right, height=24, mono=True)
        self.html_output.pack(fill="both", expand=True)
        controls = ttk.Frame(frame, style="Root.TFrame")
        controls.pack(fill="x")
        ttk.Button(controls, text="CLEAN HTML", command=self.clean_html, style="Accent.TButton").pack(side="left")
        ttk.Button(controls, text="COPY RESULT", command=self.copy_html_result).pack(side="left", padx=(8, 0))

    def clean_html(self) -> None:
        raw = self.html_input.get("1.0", "end")
        if not raw.strip():
            messagebox.showerror("No HTML", "Please paste HTML into the input box.")
            return
        soup = BeautifulSoup(raw, "html.parser")
        root = soup.body or soup
        for tag in root.select("div, section, article, header, footer, aside, main, nav"):
            tag.unwrap()
        allowed_attrs = {"style", "href", "target", "src", "alt", "width", "height", "colspan", "rowspan"}
        for tag in root.find_all(True):
            for attr in list(tag.attrs):
                if attr not in allowed_attrs:
                    del tag.attrs[attr]
        for span in root.find_all("span"):
            if not span.attrs:
                span.unwrap()
        for tag in root.select("p, h1, h2, h3, h4, h5, h6, li, ul, ol, blockquote"):
            if not tag.get_text(strip=True) and not tag.select_one("img, br, hr, iframe"):
                tag.decompose()
        cleaned = root.decode_contents().strip() if getattr(root, "name", None) == "body" else str(root).strip()
        self._set_text(self.html_output, cleaned)
        self.status_var.set("COMPLETE")

    def copy_html_result(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.html_output.get("1.0", "end").strip())
        self.status_var.set("COPIED")
    def _build_sku_generator(self) -> None:
        frame = self._make_tool_frame("sku")
        panel = self._panel(frame, "SKU BASE CODE")
        self.sku_base = tk.StringVar()
        entry = ttk.Entry(panel, textvariable=self.sku_base, font=("Segoe UI", 11))
        entry.pack(fill="x")
        entry.bind("<Return>", lambda _event: self.generate_skus())
        controls = ttk.Frame(panel, style="Panel.TFrame")
        controls.pack(fill="x", pady=(10, 0))
        ttk.Button(controls, text="GENERATE", command=self.generate_skus, style="Accent.TButton").pack(side="left")
        ttk.Button(controls, text="COPY ALL", command=self.copy_skus).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="EXPORT CSV", command=self.export_skus).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="CLEAR", command=self.clear_skus).pack(side="left", padx=(8, 0))
        self.sku_info = tk.StringVar(value="Supported patterns: AD, KD, or ADK/KD.")
        ttk.Label(panel, textvariable=self.sku_info).pack(anchor="w", pady=(8, 0))
        self.sku_output = self._text(frame, height=24, mono=True)
        self.sku_output.pack(fill="both", expand=True)

    def generate_skus(self) -> None:
        base = self.sku_base.get().strip()
        variants = self._sku_variants(base)
        self._set_text(self.sku_output, "\n".join(variants))
        self.sku_info.set(f"Generated {len(variants)} SKU variant(s)." if variants else "No variants generated. Use AD, KD, or ADK/KD in the base SKU.")

    def copy_skus(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.sku_output.get("1.0", "end").strip())
        self.status_var.set("COPIED")

    def export_skus(self) -> None:
        rows = [line for line in self.sku_output.get("1.0", "end").splitlines() if line.strip()]
        if not rows:
            return
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="sku_variants.csv")
        if not file:
            return
        with open(file, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["SKU"])
            for row in rows:
                writer.writerow([row])
        self.status_var.set("EXPORTED")

    def clear_skus(self) -> None:
        self.sku_base.set("")
        self._set_text(self.sku_output, "")
        self.sku_info.set("Supported patterns: AD, KD, or ADK/KD.")

    def _sku_variants(self, base: str) -> list[str]:
        kids_sizes = ["16", "18", "20", "22", "24", "26", "28"]
        kids_labels = ["(3-4 yrs)", "(4-5 yrs)", "(5-6 yrs)", "(7-8 yrs)", "(8-9 yrs)", "(10-11 yrs)", "(12-13 yrs)"]
        adult_sizes = ["S", "M", "L", "XL", "XXL"]
        variants: list[str] = []
        if "ADK/KD" in base:
            variants.extend(f"{base}_{size} {kids_labels[index]}" for index, size in enumerate(kids_sizes))
            variants.extend(f"{base}_{size}" for size in adult_sizes)
        elif "KD" in base:
            variants.extend(f"{base}_{size} {kids_labels[index]}" for index, size in enumerate(kids_sizes))
        elif "AD" in base:
            variants.extend(f"{base}_{size}" for size in adult_sizes)
        return variants

    def _extract_lines(self, raw: str) -> list[str]:
        return list(dict.fromkeys(line.strip() for line in raw.splitlines() if line.strip()))

    def _set_text(self, widget: tk.Text, value: str, disabled: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", value)
        if disabled:
            widget.configure(state="disabled")

    def _tool_log(self, widget: tk.Text, message: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        widget.see("end")
        widget.configure(state="disabled")


def main() -> None:
    app = ABKToolApp()
    app.mainloop()



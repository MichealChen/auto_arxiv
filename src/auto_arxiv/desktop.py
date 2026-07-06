from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from shutil import copyfile
from urllib.request import Request, urlopen
import calendar
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .config import AppConfig, load_config
from .store import (
    load_daily_recommendations,
    load_history,
    load_latest_recommendations,
    load_reading_list,
    load_user_state,
    update_user_state,
)
from .workflow import generate_recommendations, generate_recommendations_for_date


APP_TITLE = "auto_arxiv"
ARXIV_CATEGORIES = (
    "astro-ph.CO", "astro-ph.EP", "astro-ph.GA", "astro-ph.HE", "astro-ph.IM", "astro-ph.SR",
    "cond-mat.dis-nn", "cond-mat.mes-hall", "cond-mat.mtrl-sci", "cond-mat.other",
    "cond-mat.quant-gas", "cond-mat.soft", "cond-mat.stat-mech", "cond-mat.str-el", "cond-mat.supr-con",
    "cs.AI", "cs.AR", "cs.CC", "cs.CE", "cs.CG", "cs.CL", "cs.CR", "cs.CV", "cs.CY",
    "cs.DB", "cs.DC", "cs.DL", "cs.DM", "cs.DS", "cs.ET", "cs.FL", "cs.GL", "cs.GR",
    "cs.GT", "cs.HC", "cs.IR", "cs.IT", "cs.LG", "cs.LO", "cs.MA", "cs.MM", "cs.MS",
    "cs.NA", "cs.NE", "cs.NI", "cs.OH", "cs.OS", "cs.PF", "cs.PL", "cs.RO", "cs.SC", "cs.SD", "cs.SE", "cs.SI", "cs.SY",
    "eess.AS", "eess.IV", "eess.SP", "eess.SY",
    "gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th", "math-ph", "nlin.AO", "nlin.CD",
    "physics.app-ph", "physics.atom-ph", "physics.bio-ph", "physics.chem-ph", "physics.comp-ph",
    "physics.data-an", "physics.flu-dyn", "physics.gen-ph", "physics.ins-det", "physics.optics",
    "quant-ph", "stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH",
)


class DesktopApp:
    def __init__(self, root: tk.Tk, app_dir: Path, resource_dir: Path) -> None:
        self.root = root
        self.app_dir = app_dir
        self.resource_dir = resource_dir
        self.config_path = app_dir / "config.toml"
        self.profiles_path = app_dir / "profiles.json"
        self.config: AppConfig | None = None
        self.payload: dict | None = None
        self.selected_paper: dict | None = None
        self.user_state = {"schema_version": 1, "papers": {}}
        self.profiles = {"active": "", "profiles": {}}

        self.status_var = tk.StringVar(value="正在启动...")
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.range_start_var = tk.StringVar(value=date.today().isoformat())
        self.range_end_var = tk.StringVar(value=date.today().isoformat())
        self.search_var = tk.StringVar(value="")
        self.profile_var = tk.StringVar(value="")
        self.profile_name_var = tk.StringVar()
        self.categories_var = tk.StringVar()
        self.days_back_var = tk.StringVar()
        self.max_results_var = tk.StringVar()
        self.limit_var = tk.StringVar()
        self.min_score_var = tk.StringVar()
        self.followed_authors_var = tk.StringVar()
        self.calendar_popup = None
        self.calendar_anchor = None
        self.active_settings_dialog = None
        self.category_editor = None
        self.keyword_editor = None
        self.exclude_editor = None
        self.author_editor = None

        self.root.title(APP_TITLE)
        self.root.geometry("1280x800")
        self.root.minsize(1040, 680)
        self._ensure_config()
        self._ensure_profiles()
        self._activate_profile_config()
        self.config = load_config(self.config_path)
        self.user_state = load_user_state(self.config.output.data_directory)
        self._build_ui()
        self._load_initial_data()

    def _build_ui(self) -> None:
        self._configure_style()
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.root.configure(bg="#f6f8fb")
        header = ttk.Frame(self.root, padding=(18, 14), style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(header, text="auto_arxiv 每日文献推荐", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, textvariable=self.status_var, foreground="#1d4ed8").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        notebook = ttk.Notebook(self.root, style="App.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.notebook = notebook

        self.recommend_tab = ttk.Frame(notebook, padding=10)
        self.reading_tab = ttk.Frame(notebook, padding=10)
        self.history_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.recommend_tab, text="推荐")
        notebook.add(self.reading_tab, text="待读列表")
        notebook.add(self.history_tab, text="历史记录")

        self._build_recommend_tab()
        self._build_reading_tab()
        self._build_history_tab()
        self._build_account_bar()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#f6f8fb", foreground="#0f172a")
        style.configure("App.TFrame", background="#f6f8fb")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TNotebook", background="#f6f8fb", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), font=("Segoe UI", 10))
        style.configure(
            "Treeview",
            rowheight=30,
            font=("Segoe UI", 10),
            background="#ffffff",
            fieldbackground="#ffffff",
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#eef2ff")
        style.configure("TButton", padding=(10, 6))
        style.configure("Accent.TButton", padding=(12, 6), background="#2563eb", foreground="#ffffff")
        style.configure("TLabelframe", background="#f6f8fb", bordercolor="#dbe3ef")
        style.configure("TLabelframe.Label", background="#f6f8fb", foreground="#334155", font=("Segoe UI", 10, "bold"))

    def _build_recommend_tab(self) -> None:
        tab = self.recommend_tab
        tab.grid_rowconfigure(2, weight=1)
        tab.grid_columnconfigure(0, weight=3)
        tab.grid_columnconfigure(1, weight=2)

        controls = ttk.Frame(tab, padding=(10, 10), style="Card.TFrame")
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="日期").pack(side=tk.LEFT)
        self.date_entry = ttk.Entry(controls, textvariable=self.date_var, width=14)
        self.date_entry.pack(side=tk.LEFT, padx=(6, 8))
        self.date_entry.bind("<Button-1>", self.open_calendar)
        ttk.Button(controls, text="生成该日期推荐", command=self.load_selected_date).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="生成今日推荐", command=self.refresh_today).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(controls, text="时间范围").pack(side=tk.LEFT, padx=(18, 4))
        self.range_start_entry = ttk.Entry(controls, textvariable=self.range_start_var, width=12)
        self.range_start_entry.pack(side=tk.LEFT)
        self.range_start_entry.bind("<Button-1>", lambda event: self.open_calendar_for(self.range_start_var, self.range_start_entry))
        ttk.Label(controls, text="至").pack(side=tk.LEFT, padx=4)
        self.range_end_entry = ttk.Entry(controls, textvariable=self.range_end_var, width=12)
        self.range_end_entry.pack(side=tk.LEFT)
        self.range_end_entry.bind("<Button-1>", lambda event: self.open_calendar_for(self.range_end_var, self.range_end_entry))
        ttk.Button(controls, text="生成范围推荐", command=self.generate_range).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(controls, text="在当前列表中筛选").pack(side=tk.LEFT, padx=(18, 4))
        search_entry = ttk.Entry(controls, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<KeyRelease>", lambda _event: self.render_papers())

        self.summary_var = tk.StringVar(value="暂无推荐数据")
        ttk.Label(tab, textvariable=self.summary_var).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        columns = ("rank", "score", "published", "title")
        self.paper_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        self.paper_tree.heading("rank", text="#")
        self.paper_tree.heading("score", text="分数")
        self.paper_tree.heading("published", text="发布日期")
        self.paper_tree.heading("title", text="标题")
        self.paper_tree.column("rank", width=48, anchor="center", stretch=False)
        self.paper_tree.column("score", width=70, anchor="center", stretch=False)
        self.paper_tree.column("published", width=100, anchor="center", stretch=False)
        self.paper_tree.column("title", width=520)
        self.paper_tree.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        self.paper_tree.bind("<<TreeviewSelect>>", self.on_paper_selected)

        detail_frame = ttk.Frame(tab, padding=12, style="Card.TFrame")
        detail_frame.grid(row=2, column=1, sticky="nsew")
        detail_frame.grid_rowconfigure(4, weight=1)
        detail_frame.grid_columnconfigure(0, weight=1)

        self.detail_title_var = tk.StringVar(value="请选择一篇论文")
        self.detail_meta_var = tk.StringVar(value="")
        title_label = ttk.Label(
            detail_frame,
            textvariable=self.detail_title_var,
            font=("Segoe UI", 12, "bold"),
            wraplength=520,
            justify="left",
        )
        title_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(detail_frame, textvariable=self.detail_meta_var, wraplength=520, justify="left").grid(
            row=1, column=0, sticky="ew"
        )
        self.reason_var = tk.StringVar(value="")
        reason_box = ttk.LabelFrame(detail_frame, text="为什么推荐")
        reason_box.grid(row=2, column=0, sticky="ew", pady=(8, 8))
        ttk.Label(reason_box, textvariable=self.reason_var, wraplength=500, justify="left").pack(
            fill=tk.X, padx=8, pady=6
        )

        abstract_box = ttk.LabelFrame(detail_frame, text="摘要")
        abstract_box.grid(row=4, column=0, sticky="nsew")
        abstract_box.grid_rowconfigure(0, weight=1)
        abstract_box.grid_columnconfigure(0, weight=1)
        self.abstract_text = tk.Text(
            abstract_box,
            wrap="word",
            height=18,
            font=("Segoe UI", 10),
            padx=14,
            pady=12,
            relief="flat",
            background="#ffffff",
            foreground="#111827",
        )
        self.abstract_text.grid(row=0, column=0, sticky="nsew")
        abstract_scroll = ttk.Scrollbar(abstract_box, orient="vertical", command=self.abstract_text.yview)
        abstract_scroll.grid(row=0, column=1, sticky="ns")
        self.abstract_text.configure(yscrollcommand=abstract_scroll.set, state="disabled")

        actions = ttk.Frame(tab)
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="加入/移出待读列表", command=self.toggle_reading_list).pack(side=tk.LEFT)
        ttk.Button(actions, text="标记已读/未读", command=self.toggle_read).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="下载 PDF", command=self.download_selected_pdf).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="复制 arXiv 链接", command=self.copy_selected_link).pack(side=tk.LEFT, padx=(8, 0))

    def _build_reading_tab(self) -> None:
        tab = self.reading_tab
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(top, text="刷新待读列表", command=self.render_reading_list).pack(side=tk.LEFT)
        ttk.Button(top, text="从待读列表移除", command=self.remove_from_reading_list).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top, text="下载选中 PDF", command=self.download_reading_pdf).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top, text="保存笔记", command=self.save_reading_note).pack(side=tk.LEFT, padx=(8, 0))

        pane = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        pane.grid(row=1, column=0, sticky="nsew")

        columns = ("updated", "title")
        list_frame = ttk.Frame(pane)
        pane.add(list_frame, weight=2)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        self.reading_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.reading_tree.heading("updated", text="更新日期")
        self.reading_tree.heading("title", text="标题")
        self.reading_tree.column("updated", width=120, anchor="center", stretch=False)
        self.reading_tree.column("title", width=780)
        self.reading_tree.grid(row=0, column=0, sticky="nsew")
        self.reading_tree.bind("<<TreeviewSelect>>", self.on_reading_selected)

        note_frame = ttk.Frame(pane)
        pane.add(note_frame, weight=2)
        note_frame.grid_rowconfigure(1, weight=1)
        note_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(note_frame, text="阅读笔记", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.note_text = tk.Text(note_frame, height=12, wrap="word", font=("Segoe UI", 10), padx=10, pady=8)
        self.note_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    def _build_history_tab(self) -> None:
        tab = self.history_tab
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(top, text="刷新历史记录", command=self.render_history).pack(side=tk.LEFT)
        ttk.Button(top, text="加载选中日期", command=self.load_history_selection).pack(side=tk.LEFT, padx=(8, 0))

        columns = ("date", "selected", "matched", "profile")
        self.history_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        for column, text, width in (
            ("date", "日期", 130),
            ("selected", "推荐", 80),
            ("matched", "匹配", 80),
            ("profile", "Profile", 300),
        ):
            self.history_tree.heading(column, text=text)
            self.history_tree.column(column, width=width, stretch=column == "profile")
        self.history_tree.grid(row=1, column=0, sticky="nsew")

    def _build_account_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        bar.grid(row=2, column=0, sticky="ew")
        ttk.Label(bar, text="账户").pack(side=tk.LEFT)
        self.profile_combo = ttk.Combobox(bar, textvariable=self.profile_var, state="readonly", width=22)
        self.profile_combo.pack(side=tk.LEFT, padx=(6, 8))
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _event: self.switch_profile())
        ttk.Button(bar, text="账户设置", command=self.open_profile_settings).pack(side=tk.LEFT)
        ttk.Button(bar, text="新建账户", command=self.create_profile).pack(side=tk.LEFT, padx=(8, 0))
        self.refresh_profile_options()
        self.load_config_into_form()

    def open_profile_settings(self) -> None:
        if self.active_settings_dialog is not None and self.active_settings_dialog.winfo_exists():
            self.active_settings_dialog.focus_force()
            return
        dialog = tk.Toplevel(self.root)
        self.active_settings_dialog = dialog
        dialog.title("账户设置")
        dialog.geometry("900x760")
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", self._close_settings_dialog)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        dialog.grid_rowconfigure(2, weight=1)
        dialog.grid_rowconfigure(3, weight=1)
        dialog.grid_rowconfigure(4, weight=1)

        form = ttk.LabelFrame(dialog, text="基础参数", padding=10)
        form.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)
        rows = [
            ("Profile 名称", self.profile_name_var),
            ("days_back", self.days_back_var),
            ("max_results", self.max_results_var),
            ("limit", self.limit_var),
            ("min_score", self.min_score_var),
        ]
        for index, (label, var) in enumerate(rows):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(form, text=label).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=5)
            entry_width = 14 if label != "Profile 名称" else 28
            ttk.Entry(form, textvariable=var, width=entry_width).grid(
                row=row,
                column=column + 1,
                sticky="ew",
                padx=(0, 18),
                pady=5,
            )

        profile = self._active_profile()
        self.category_editor = TokenEditor(
            dialog,
            title="arXiv 分类",
            initial=profile.get("categories", []),
            choices=ARXIV_CATEGORIES,
        )
        self.category_editor.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        self.keyword_editor = TokenEditor(dialog, title="兴趣关键词", initial=profile.get("keywords", []))
        self.keyword_editor.grid(row=2, column=0, sticky="nsew", padx=12, pady=8)
        self.exclude_editor = TokenEditor(dialog, title="排除关键词", initial=profile.get("exclude_keywords", []))
        self.exclude_editor.grid(row=3, column=0, sticky="nsew", padx=12, pady=8)
        self.author_editor = TokenEditor(dialog, title="关注作者", initial=profile.get("followed_authors", []))
        self.author_editor.grid(row=4, column=0, sticky="nsew", padx=12, pady=8)

        buttons = ttk.Frame(dialog, padding=(12, 8))
        buttons.grid(row=5, column=0, sticky="ew")
        ttk.Button(buttons, text="保存当前账户档案", command=self.save_config).pack(side=tk.LEFT)
        ttk.Button(buttons, text="删除账户", command=self.delete_profile).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="打开数据目录", command=self.open_data_dir).pack(side=tk.LEFT, padx=(8, 0))

    def _close_settings_dialog(self) -> None:
        if self.active_settings_dialog is not None and self.active_settings_dialog.winfo_exists():
            self.active_settings_dialog.destroy()
        self.active_settings_dialog = None
        self.category_editor = None
        self.keyword_editor = None
        self.exclude_editor = None
        self.author_editor = None

    def _load_initial_data(self) -> None:
        try:
            assert self.config is not None
            latest_path = self.config.output.data_directory / "recommendations.json"
            if latest_path.exists():
                self.payload = load_latest_recommendations(self.config.output.data_directory)
                self.date_var.set(self.payload.get("date", date.today().isoformat()))
                self.status_var.set("已加载最近一次推荐。")
                self.render_all()
            else:
                self.refresh_today()
        except Exception as exc:
            self.status_var.set(f"加载失败：{exc}")

    def load_selected_date(self) -> None:
        try:
            target = datetime.strptime(self.date_var.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror(APP_TITLE, "日期格式应为 YYYY-MM-DD。")
            return
        self._run_background(lambda: self._load_or_generate_date(target), "正在生成该日期推荐...")

    def refresh_today(self) -> None:
        self.date_var.set(date.today().isoformat())
        self._run_background(self._generate_today, "正在生成今日推荐...")

    def open_calendar(self, _event=None) -> None:
        self.open_calendar_for(self.date_var, self.date_entry)

    def open_calendar_for(self, variable: tk.StringVar, anchor: tk.Widget) -> None:
        if self.calendar_popup is not None and self.calendar_popup.exists():
            if self.calendar_anchor is anchor:
                self.calendar_popup.close()
                return
            self.calendar_popup.close()
        try:
            current = datetime.strptime(variable.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            current = date.today()
        self.calendar_anchor = anchor
        self.calendar_popup = CalendarPopup(
            self.root,
            current,
            lambda selected: self._set_calendar_var(variable, selected),
            anchor=anchor,
            on_close=self._clear_calendar_popup,
        )

    def _clear_calendar_popup(self) -> None:
        self.calendar_popup = None
        self.calendar_anchor = None

    def _set_calendar_date(self, selected: date) -> None:
        self.date_var.set(selected.isoformat())

    def _set_calendar_var(self, variable: tk.StringVar, selected: date) -> None:
        variable.set(selected.isoformat())

    def _generate_today(self) -> str:
        self.config = load_config(self.config_path)
        result = generate_recommendations(self.config)
        self.payload = load_latest_recommendations(self.config.output.data_directory)
        return f"刷新完成：抓取 {result.fetched_count} 篇，推荐 {result.selected_count} 篇。"

    def _load_or_generate_date(self, target: date) -> str:
        assert self.config is not None
        self.config = load_config(self.config_path)
        result = generate_recommendations_for_date(self.config, target)
        self.payload = load_daily_recommendations(self.config.output.data_directory, target.isoformat())
        return f"已生成 {target.isoformat()} 推荐：抓取 {result.fetched_count} 篇，推荐 {result.selected_count} 篇。"

    def generate_range(self) -> None:
        try:
            start = datetime.strptime(self.range_start_var.get().strip(), "%Y-%m-%d").date()
            end = datetime.strptime(self.range_end_var.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror(APP_TITLE, "时间范围格式应为 YYYY-MM-DD。")
            return
        if start > end:
            messagebox.showerror(APP_TITLE, "开始日期不能晚于结束日期。")
            return
        if end > date.today():
            messagebox.showerror(APP_TITLE, "结束日期不能晚于今天。")
            return
        self._run_background(lambda: self._generate_range(start, end), "正在生成时间范围推荐...")

    def _generate_range(self, start: date, end: date) -> str:
        assert self.config is not None
        self.config = load_config(self.config_path)
        current = start
        all_papers = []
        fetched = matched = selected = 0
        while current <= end:
            result = generate_recommendations_for_date(self.config, current)
            payload = load_daily_recommendations(self.config.output.data_directory, current.isoformat())
            for paper in payload.get("papers", []):
                paper = dict(paper)
                paper["source_date"] = current.isoformat()
                all_papers.append(paper)
            fetched += result.fetched_count
            matched += result.ranked_count
            selected += result.selected_count
            current += timedelta(days=1)
        self.payload = {
            "date": f"{start.isoformat()} 至 {end.isoformat()}",
            "stats": {"fetched": fetched, "matched": matched, "selected": selected},
            "papers": all_papers,
        }
        return f"范围推荐完成：{start.isoformat()} 至 {end.isoformat()}，共推荐 {selected} 篇。"

    def render_all(self) -> None:
        self.user_state = load_user_state(self.config.output.data_directory) if self.config else self.user_state
        self.render_papers()
        self.render_history()
        self.render_reading_list()

    def render_papers(self) -> None:
        self.paper_tree.delete(*self.paper_tree.get_children())
        self.selected_paper = None
        self.clear_detail()
        if not self.payload:
            self.summary_var.set("暂无推荐数据")
            return

        stats = self.payload.get("stats", {})
        self.summary_var.set(
            f"日期 {self.payload.get('date')} · 抓取 {stats.get('fetched', 0)} 篇 · "
            f"匹配 {stats.get('matched', 0)} 篇 · 推荐 {stats.get('selected', 0)} 篇"
        )
        query = self.search_var.get().strip().lower()
        for paper in self._filtered_papers(query):
            published = _date_part(paper.get("published", ""))
            title = _state_prefix(self._paper_state(paper.get("arxiv_id", ""))) + paper.get("title", "")
            self.paper_tree.insert(
                "",
                tk.END,
                iid=paper["arxiv_id"],
                values=(paper.get("rank", ""), f"{paper.get('score', 0):.1f}", published, title),
            )

    def render_history(self) -> None:
        self.history_tree.delete(*self.history_tree.get_children())
        if not self.config:
            return
        history = load_history(self.config.output.data_directory)
        for item in history.get("dates", []):
            self.history_tree.insert(
                "",
                tk.END,
                iid=item["date"],
                values=(item.get("date"), item.get("selected"), item.get("matched"), item.get("profile")),
            )

    def render_reading_list(self) -> None:
        self.reading_tree.delete(*self.reading_tree.get_children())
        if not self.config:
            return
        for paper in load_reading_list(self.config.output.data_directory):
            self.reading_tree.insert(
                "",
                tk.END,
                iid=paper["arxiv_id"],
                values=(_date_part(paper.get("updated", "")), paper.get("title", "")),
            )

    def on_reading_selected(self, _event=None) -> None:
        if not self.config:
            return
        selection = self.reading_tree.selection()
        if not selection:
            return
        arxiv_id = selection[0]
        paper = next(
            (item for item in load_reading_list(self.config.output.data_directory) if item["arxiv_id"] == arxiv_id),
            None,
        )
        if not paper:
            return
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", paper.get("user_state", {}).get("note", ""))
        self.status_var.set(f"已加载待读论文笔记：{paper.get('title', '')[:60]}")

    def on_paper_selected(self, _event=None) -> None:
        selection = self.paper_tree.selection()
        if not selection or not self.payload:
            return
        arxiv_id = selection[0]
        self.selected_paper = next(
            (paper for paper in self.payload.get("papers", []) if paper.get("arxiv_id") == arxiv_id),
            None,
        )
        self.render_detail(self.selected_paper)

    def render_detail(self, paper: dict | None) -> None:
        self.clear_detail()
        if not paper:
            return
        self.detail_title_var.set(paper.get("title", ""))
        self.detail_meta_var.set(
            "\n".join(
                [
                    f"作者：{', '.join(paper.get('authors', [])) or 'N/A'}",
                    f"分区/分类：{', '.join(paper.get('categories', [])) or 'N/A'}",
                ]
            )
        )
        reason = next(iter(paper.get("recommendation_reasons", [])), "")
        self.reason_var.set(reason.replace("\n", " ").strip() or "暂无推荐理由")
        self.abstract_text.configure(state="normal")
        self.abstract_text.delete("1.0", tk.END)
        _render_markdown_text(self.abstract_text, _abstract_markdown(paper))
        self.abstract_text.configure(state="disabled")

    def clear_detail(self) -> None:
        self.detail_title_var.set("请选择一篇论文")
        self.detail_meta_var.set("")
        self.reason_var.set("")
        self.abstract_text.configure(state="normal")
        self.abstract_text.delete("1.0", tk.END)
        self.abstract_text.configure(state="disabled")

    def toggle_reading_list(self) -> None:
        self._toggle_selected_state("reading_list")

    def toggle_read(self) -> None:
        self._toggle_selected_state("read")

    def _toggle_selected_state(self, field: str) -> None:
        if not self.config or not self.selected_paper:
            messagebox.showinfo(APP_TITLE, "请先选择一篇论文。")
            return
        arxiv_id = self.selected_paper["arxiv_id"]
        current = self._paper_state(arxiv_id)
        self.user_state = update_user_state(
            self.config.output.data_directory,
            arxiv_id,
            {field: not current.get(field, False)},
        )
        self.render_all()
        self.render_detail(self.selected_paper)

    def remove_from_reading_list(self) -> None:
        if not self.config:
            return
        selection = self.reading_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "请先选择待读列表中的论文。")
            return
        self.user_state = update_user_state(
            self.config.output.data_directory,
            selection[0],
            {"reading_list": False},
        )
        self.render_reading_list()
        self.render_papers()

    def download_selected_pdf(self) -> None:
        if not self.selected_paper:
            messagebox.showinfo(APP_TITLE, "请先选择一篇论文。")
            return
        self._download_pdf(self.selected_paper)

    def download_reading_pdf(self) -> None:
        if not self.config:
            return
        selection = self.reading_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "请先选择待读列表中的论文。")
            return
        paper = next(
            (item for item in load_reading_list(self.config.output.data_directory) if item["arxiv_id"] == selection[0]),
            None,
        )
        if paper:
            self._download_pdf(paper)

    def _download_pdf(self, paper: dict) -> None:
        if not self.config:
            return
        pdf_url = paper.get("pdf_url")
        if not pdf_url:
            messagebox.showerror(APP_TITLE, "这篇论文没有 PDF 链接。")
            return

        def run() -> str:
            path = self._ensure_pdf_file(paper)
            return f"PDF 已下载：{path}"

        self._run_background(run, "正在下载 PDF...")

    def _ensure_pdf_file(self, paper: dict) -> Path:
        assert self.config is not None
        pdf_url = paper.get("pdf_url")
        if not pdf_url:
            raise ValueError("这篇论文没有 PDF 链接。")
        self.config.output.download_directory.mkdir(parents=True, exist_ok=True)
        path = self.config.output.download_directory / f"{paper['arxiv_id'].replace('/', '_')}.pdf"
        if not path.exists():
            request = Request(pdf_url, headers={"User-Agent": "auto-arxiv/0.1"})
            with urlopen(request, timeout=60) as response:
                path.write_bytes(response.read())
        return path

    def save_reading_note(self) -> None:
        if not self.config:
            return
        selection = self.reading_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "请先选择待读列表中的论文。")
            return
        self.user_state = update_user_state(
            self.config.output.data_directory,
            selection[0],
            {"note": self.note_text.get("1.0", tk.END).strip()},
        )
        self.status_var.set("笔记已保存。")

    def copy_selected_link(self) -> None:
        if not self.selected_paper:
            messagebox.showinfo(APP_TITLE, "请先选择一篇论文。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.selected_paper.get("abs_url", ""))
        self.status_var.set("arXiv 链接已复制到剪贴板。")

    def load_history_selection(self) -> None:
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "请先选择一个历史日期。")
            return
        self.date_var.set(selection[0])
        self.load_selected_date()
        self.notebook.select(self.recommend_tab)

    def load_config_into_form(self) -> None:
        self.config = load_config(self.config_path)
        config = self.config
        active = self.profiles.get("active") or config.profile.name
        self.profile_var.set(active)
        self.profile_name_var.set(config.profile.name)
        self.categories_var.set(", ".join(config.profile.categories))
        self.days_back_var.set(str(config.search.days_back))
        self.max_results_var.set(str(config.search.max_results))
        self.limit_var.set(str(config.output.limit))
        self.min_score_var.set(str(config.output.min_score))
        self.followed_authors_var.set(", ".join(config.profile.followed_authors))
        if editor := self._editor("category_editor"):
            editor.set_values(config.profile.categories)
        if editor := self._editor("keyword_editor"):
            editor.set_values(config.profile.keywords)
        if editor := self._editor("exclude_editor"):
            editor.set_values(config.profile.exclude_keywords)
        if editor := self._editor("author_editor"):
            editor.set_values(config.profile.followed_authors)
        if hasattr(self, "keywords_text"):
            self.keywords_text.delete("1.0", tk.END)
            self.keywords_text.insert("1.0", "\n".join(config.profile.keywords))
        if hasattr(self, "exclude_text"):
            self.exclude_text.delete("1.0", tk.END)
            self.exclude_text.insert("1.0", "\n".join(config.profile.exclude_keywords))
        self.status_var.set("配置已加载。")

    def save_config(self) -> None:
        try:
            profile_name = self.profile_name_var.get().strip() or self.profile_var.get().strip()
            if not profile_name:
                profile_name = "My Research Radar"
            text = _render_config_text(
                name=profile_name,
                categories=self._categories_from_form(),
                keywords=self._keywords_from_form(),
                exclude_keywords=self._exclude_from_form(),
                followed_authors=self._followed_authors_from_form(),
                days_back=int(self.days_back_var.get()),
                max_results=int(self.max_results_var.get()),
                limit=int(self.limit_var.get()),
                min_score=float(self.min_score_var.get()),
            )
            self.config_path.write_text(text, encoding="utf-8")
            self.config = load_config(self.config_path)
            self.profiles.setdefault("profiles", {})[profile_name] = self._form_to_profile(profile_name)
            self.profiles["active"] = profile_name
            self._write_profiles()
            self.refresh_profile_options()
            self.profile_var.set(profile_name)
            self.status_var.set("配置已保存。")
            self._close_settings_dialog()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"保存配置失败：\n{exc}")

    def refresh_profile_options(self) -> None:
        names = sorted(self.profiles.get("profiles", {}).keys())
        self.profile_combo.configure(values=names)
        active = self.profiles.get("active")
        if active in names:
            self.profile_var.set(active)
        elif names:
            self.profile_var.set(names[0])

    def switch_profile(self) -> None:
        name = self.profile_var.get()
        profile = self.profiles.get("profiles", {}).get(name)
        if not profile:
            return
        self._profile_to_form(profile)
        self.config_path.write_text(_profile_to_config_text(profile), encoding="utf-8")
        self.config = load_config(self.config_path)
        self.user_state = load_user_state(self.config.output.data_directory)
        self.profiles["active"] = name
        self._write_profiles()
        self.status_var.set(f"已切换到账户：{name}")
        self._load_initial_data()

    def create_profile(self) -> None:
        name = simpledialog.askstring(APP_TITLE, "请输入新账户/Profile 名称：", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.profiles.get("profiles", {}):
            messagebox.showerror(APP_TITLE, "这个账户名称已经存在。")
            return
        profile = self._active_profile().copy()
        profile["name"] = name
        self.profiles.setdefault("profiles", {})[name] = profile
        self.profiles["active"] = name
        self._write_profiles()
        self.refresh_profile_options()
        self._profile_to_form(profile)
        self.status_var.set(f"已新建账户：{name}")

    def delete_profile(self) -> None:
        name = self.profile_var.get()
        profiles = self.profiles.get("profiles", {})
        if not name or name not in profiles:
            return
        if len(profiles) <= 1:
            messagebox.showinfo(APP_TITLE, "至少需要保留一个账户。")
            return
        if not messagebox.askyesno(APP_TITLE, f"确定删除账户 {name} 吗？"):
            return
        profiles.pop(name)
        self.profiles["active"] = sorted(profiles.keys())[0]
        self._write_profiles()
        self.refresh_profile_options()
        self.switch_profile()

    def _form_to_profile(self, name: str) -> dict:
        return {
            "name": name,
            "categories": self._categories_from_form(),
            "keywords": self._keywords_from_form(),
            "exclude_keywords": self._exclude_from_form(),
            "followed_authors": self._followed_authors_from_form(),
            "days_back": int(self.days_back_var.get()),
            "max_results": int(self.max_results_var.get()),
            "limit": int(self.limit_var.get()),
            "min_score": float(self.min_score_var.get()),
        }

    def _profile_to_form(self, profile: dict) -> None:
        self.profile_name_var.set(str(profile.get("name", "")))
        self.categories_var.set(", ".join(profile.get("categories", [])))
        self.days_back_var.set(str(profile.get("days_back", 2)))
        self.max_results_var.set(str(profile.get("max_results", 100)))
        self.limit_var.set(str(profile.get("limit", 10)))
        self.min_score_var.set(str(profile.get("min_score", 2.0)))
        self.followed_authors_var.set(", ".join(profile.get("followed_authors", [])))
        if editor := self._editor("category_editor"):
            editor.set_values(profile.get("categories", []))
        if editor := self._editor("keyword_editor"):
            editor.set_values(profile.get("keywords", []))
        if editor := self._editor("exclude_editor"):
            editor.set_values(profile.get("exclude_keywords", []))
        if editor := self._editor("author_editor"):
            editor.set_values(profile.get("followed_authors", []))
        if hasattr(self, "keywords_text"):
            self.keywords_text.delete("1.0", tk.END)
            self.keywords_text.insert("1.0", "\n".join(profile.get("keywords", [])))
        if hasattr(self, "exclude_text"):
            self.exclude_text.delete("1.0", tk.END)
            self.exclude_text.insert("1.0", "\n".join(profile.get("exclude_keywords", [])))

    def open_data_dir(self) -> None:
        if not self.config:
            return
        self.config.output.data_directory.mkdir(parents=True, exist_ok=True)
        os.startfile(self.config.output.data_directory)

    def _filtered_papers(self, query: str) -> list[dict]:
        papers = list(self.payload.get("papers", []) if self.payload else [])
        if not query:
            return papers
        result = []
        for paper in papers:
            text = " ".join(
                [
                    paper.get("title", ""),
                    paper.get("abstract", ""),
                    " ".join(paper.get("authors", [])),
                    " ".join(paper.get("categories", [])),
                    " ".join(paper.get("matched_keywords", [])),
                ]
            ).lower()
            if query in text:
                result.append(paper)
        return result

    def _paper_state(self, arxiv_id: str) -> dict:
        return self.user_state.get("papers", {}).get(arxiv_id, {})

    def _run_background(self, job, start_message: str) -> None:
        self.status_var.set(start_message)

        def run() -> None:
            try:
                message = job()
                self.root.after(0, lambda: self._finish_background(message))
            except Exception as exc:
                self.root.after(0, lambda exc=exc: self._fail_background(exc))

        threading.Thread(target=run, daemon=True).start()

    def _finish_background(self, message: str) -> None:
        self.status_var.set(message)
        self.render_all()

    def _fail_background(self, exc: Exception) -> None:
        self.status_var.set(f"操作失败：{exc}")
        messagebox.showerror(APP_TITLE, f"操作失败：\n{exc}")

    def _ensure_config(self) -> None:
        if self.config_path.exists():
            return
        source = self.resource_dir / "config.example.toml"
        if not source.exists():
            raise FileNotFoundError("缺少 config.example.toml，无法创建默认配置。")
        copyfile(source, self.config_path)

    def _ensure_profiles(self) -> None:
        if self.profiles_path.exists():
            self.profiles = json.loads(self.profiles_path.read_text(encoding="utf-8"))
            return
        config = load_config(self.config_path)
        profile = {
            "name": config.profile.name,
            "categories": list(config.profile.categories),
            "keywords": list(config.profile.keywords),
            "exclude_keywords": list(config.profile.exclude_keywords),
            "followed_authors": list(config.profile.followed_authors),
            "days_back": config.search.days_back,
            "max_results": config.search.max_results,
            "limit": config.output.limit,
            "min_score": config.output.min_score,
        }
        self.profiles = {
            "schema_version": 1,
            "active": config.profile.name,
            "profiles": {config.profile.name: profile},
        }
        self._write_profiles()

    def _active_profile(self) -> dict:
        profiles = self.profiles.get("profiles", {})
        name = self.profile_var.get() or self.profiles.get("active", "")
        if name in profiles:
            return profiles[name]
        if profiles:
            return next(iter(profiles.values()))
        return {}

    def _activate_profile_config(self) -> None:
        profile = self._active_profile()
        if profile:
            self.config_path.write_text(_profile_to_config_text(profile), encoding="utf-8")

    def _categories_from_form(self) -> list[str]:
        if editor := self._editor("category_editor"):
            return editor.get_values()
        return _split_values(self.categories_var.get())

    def _keywords_from_form(self) -> list[str]:
        if editor := self._editor("keyword_editor"):
            return editor.get_values()
        if hasattr(self, "keywords_text"):
            return _text_lines(self.keywords_text)
        return list(self._active_profile().get("keywords", []))

    def _exclude_from_form(self) -> list[str]:
        if editor := self._editor("exclude_editor"):
            return editor.get_values()
        if hasattr(self, "exclude_text"):
            return _text_lines(self.exclude_text)
        return list(self._active_profile().get("exclude_keywords", []))

    def _followed_authors_from_form(self) -> list[str]:
        if editor := self._editor("author_editor"):
            return editor.get_values()
        return _split_values(self.followed_authors_var.get())

    def _editor(self, attr: str):
        editor = getattr(self, attr, None)
        if editor is None:
            return None
        try:
            return editor if editor.winfo_exists() else None
        except tk.TclError:
            return None

    def _write_profiles(self) -> None:
        self.profiles_path.write_text(
            json.dumps(self.profiles, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class TokenEditor(ttk.LabelFrame):
    def __init__(self, parent, title: str, initial: list[str] | tuple[str, ...], choices=None) -> None:
        super().__init__(parent, text=title, padding=8)
        self.choices = tuple(choices or ())
        self.value_var = tk.StringVar()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        input_row = ttk.Frame(self)
        input_row.grid(row=0, column=0, sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)
        if self.choices:
            self.input = ttk.Combobox(
                input_row,
                textvariable=self.value_var,
                values=self.choices,
                state="readonly",
                height=12,
            )
        else:
            self.input = ttk.Entry(input_row, textvariable=self.value_var)
            self.input.bind("<Return>", lambda _event: self.add_value())
        self.input.grid(row=0, column=0, sticky="ew")
        ttk.Button(input_row, text="添加", command=self.add_value).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(input_row, text="移除选中", command=self.remove_selected).grid(row=0, column=2, padx=(8, 0))

        self.listbox = tk.Listbox(
            self,
            height=4,
            activestyle="none",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#dbe3ef",
            selectbackground="#2563eb",
            selectforeground="#ffffff",
        )
        self.listbox.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.set_values(initial)

    def add_value(self) -> None:
        value = self.value_var.get().strip()
        if not value:
            return
        if self.choices and value not in self.choices:
            return
        values = self.get_values()
        if value not in values:
            self.listbox.insert(tk.END, value)
        self.value_var.set("")

    def remove_selected(self) -> None:
        for index in reversed(self.listbox.curselection()):
            self.listbox.delete(index)

    def get_values(self) -> list[str]:
        return [self.listbox.get(index) for index in range(self.listbox.size())]

    def set_values(self, values) -> None:
        self.listbox.delete(0, tk.END)
        allowed = set(self.choices)
        for value in values:
            value = str(value).strip()
            if not value:
                continue
            if self.choices and value not in allowed:
                continue
            if value not in self.get_values():
                self.listbox.insert(tk.END, value)


class CalendarPopup:
    def __init__(self, parent: tk.Tk, current: date, callback, anchor=None, on_close=None) -> None:
        self.callback = callback
        self.on_close = on_close
        self.closed = False
        today = date.today()
        current = min(current, today)
        self.today = today
        self.year = current.year
        self.month = current.month
        self.window = tk.Toplevel(parent)
        self.window.title("选择日期")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda _event: self.close())
        self.header_var = tk.StringVar()
        self.body = ttk.Frame(self.window, padding=10)
        self.body.pack(fill=tk.BOTH, expand=True)
        self._render()
        if anchor is not None:
            self.window.update_idletasks()
            x = anchor.winfo_rootx()
            y = anchor.winfo_rooty() + anchor.winfo_height() + 4
            self.window.geometry(f"+{x}+{y}")
        self.window.focus_force()

    def exists(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def _render(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        top = ttk.Frame(self.body)
        top.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 8))
        ttk.Button(top, text="<", width=4, command=self._prev_month).pack(side=tk.LEFT)
        self.header_var.set(f"{self.year}-{self.month:02d}")
        ttk.Label(top, textvariable=self.header_var, font=("Segoe UI", 11, "bold")).pack(
            side=tk.LEFT, expand=True
        )
        next_button = ttk.Button(top, text=">", width=4, command=self._next_month)
        next_button.pack(side=tk.RIGHT)
        if (self.year, self.month) >= (self.today.year, self.today.month):
            next_button.state(["disabled"])

        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        for column, label in enumerate(weekdays):
            ttk.Label(self.body, text=label, anchor="center").grid(row=1, column=column, padx=2, pady=2)

        month = calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        for row, week in enumerate(month, start=2):
            for column, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.body, text="").grid(row=row, column=column, padx=2, pady=2)
                    continue
                button = ttk.Button(
                    self.body,
                    text=str(day),
                    width=4,
                    command=lambda day=day: self._select(day),
                )
                button.grid(row=row, column=column, padx=2, pady=2)
                if date(self.year, self.month, day) > self.today:
                    button.state(["disabled"])

    def _prev_month(self) -> None:
        if self.month == 1:
            self.year -= 1
            self.month = 12
        else:
            self.month -= 1
        self._render()

    def _next_month(self) -> None:
        if self.month == 12:
            self.year += 1
            self.month = 1
        else:
            self.month += 1
        self._render()

    def _select(self, day: int) -> None:
        self.callback(date(self.year, self.month, day))
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.window.winfo_exists():
                self.window.grab_release()
                self.window.destroy()
        finally:
            if self.on_close is not None:
                self.on_close()


def main() -> int:
    app_dir = _app_dir()
    resource_dir = _resource_dir()
    root = tk.Tk()
    DesktopApp(root=root, app_dir=app_dir, resource_dir=resource_dir)
    root.mainloop()
    return 0


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path.cwd()


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def _text_lines(widget: tk.Text) -> list[str]:
    return [line.strip() for line in widget.get("1.0", tk.END).splitlines() if line.strip()]


def _render_config_text(
    *,
    name: str,
    categories: list[str],
    keywords: list[str],
    exclude_keywords: list[str],
    followed_authors: list[str],
    days_back: int,
    max_results: int,
    limit: int,
    min_score: float,
) -> str:
    profile_slug = _slugify(name)
    return "\n".join(
        [
            "[profile]",
            f'name = "{_escape_toml(name)}"',
            f"categories = {_toml_array(categories)}",
            "keywords = [",
            *[f'  "{_escape_toml(item)}",' for item in keywords],
            "]",
            "exclude_keywords = [",
            *[f'  "{_escape_toml(item)}",' for item in exclude_keywords],
            "]",
            "followed_authors = [",
            *[f'  "{_escape_toml(item)}",' for item in followed_authors],
            "]",
            "",
            "[search]",
            f"days_back = {max(1, days_back)}",
            f"max_results = {max(1, max_results)}",
            "",
            "[output]",
            f"limit = {max(1, limit)}",
            f"min_score = {min_score}",
            f'directory = "recommendations/{profile_slug}"',
            f'data_directory = "data/{profile_slug}"',
            f'download_directory = "downloads/{profile_slug}"',
            "",
        ]
    )


def _profile_to_config_text(profile: dict) -> str:
    return _render_config_text(
        name=str(profile.get("name", "My Research Radar")),
        categories=list(profile.get("categories", [])),
        keywords=list(profile.get("keywords", [])),
        exclude_keywords=list(profile.get("exclude_keywords", [])),
        followed_authors=list(profile.get("followed_authors", [])),
        days_back=int(profile.get("days_back", 2)),
        max_results=int(profile.get("max_results", 100)),
        limit=int(profile.get("limit", 10)),
        min_score=float(profile.get("min_score", 2.0)),
    )


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(f'"{_escape_toml(value)}"' for value in values) + "]"


def _escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    slug = "_".join(part for part in slug.split("_") if part)
    return slug or "profile"


def _abstract_markdown(paper: dict) -> str:
    return "\n\n".join(
        [
            "### Abstract",
            paper.get("abstract", ""),
        ]
    )


def _render_markdown_text(widget: tk.Text, markdown_text: str) -> None:
    widget.tag_configure("h3", font=("Segoe UI", 12, "bold"), spacing3=8)
    widget.tag_configure("p", font=("Segoe UI", 10), spacing1=4, spacing3=10, lmargin1=6, lmargin2=6)
    widget.tag_configure("bullet", font=("Segoe UI", 10), spacing3=6, lmargin1=22, lmargin2=34)
    for block in markdown_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("### "):
            widget.insert(tk.END, block.removeprefix("### ") + "\n", "h3")
        elif block.startswith("- ") or block.startswith("• "):
            for line in block.splitlines():
                widget.insert(tk.END, "• " + line.lstrip("-• ").strip() + "\n", "bullet")
        else:
            widget.insert(tk.END, block + "\n\n", "p")


def _date_part(value: str) -> str:
    return value[:10] if value else ""


def _state_prefix(state: dict) -> str:
    labels = []
    if state.get("reading_list"):
        labels.append("[待读]")
    if state.get("read"):
        labels.append("[已读]")
    return "".join(labels) + (" " if labels else "")


def _state_text(state: dict) -> str:
    labels = []
    if state.get("reading_list"):
        labels.append("待读")
    if state.get("read"):
        labels.append("已读")
    if state.get("ignored"):
        labels.append("忽略")
    return ", ".join(labels) if labels else "未标记"


if __name__ == "__main__":
    raise SystemExit(main())

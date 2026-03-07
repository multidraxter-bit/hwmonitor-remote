#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from tkinter import ttk


DEFAULT_URL = "ssh://loofi@192.168.1.3"
DEFAULT_SSH_SCRIPT = r"C:\Users\loofi\hwremote-monitor\lhm-snapshot.ps1"
CONFIG_PATH = os.path.expanduser("~/.config/hwremote-monitor.json")
CATEGORY_VALUES = ("all", "temperature", "load", "cooling", "power", "clock", "storage")
SEVERITY_FILTER_VALUES = ("all", "active", "critical", "warn")
APP_ICON_NAME = "hwremote-monitor"
SOURCE_FILTER_VALUES = ("all", "LibreHardwareMonitorLib", "HWiNFO")
COMPACT_NOISE_HINTS = (
    "bus clock",
    "core utility",
    "core ratio",
    "effective clock",
    "uncore ratio",
    "video engine load",
    "receiver error",
    "replay",
    "bad dllp",
    "bad tlp",
    "lcrc",
    "nak",
    "unsupported request",
    "correctable error",
    "non-fatal error",
    "fatal error",
    "lane error",
    "t0 effective clock",
    "t1 effective clock",
)


@dataclass
class SensorRow:
    kind: str
    name: str
    path: str
    indent: int
    sensor_type: str = ""
    unit: str = ""
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    category: str = "other"
    severity: str = "normal"


@dataclass
class FavoriteRow:
    label: str
    sensor: str
    value: str
    path: str
    severity: str = "normal"
    is_pinned: bool = False


@dataclass
class InsightRow:
    label: str
    value: str
    detail: str
    path: str
    severity: str = "normal"


@dataclass
class AlertEvent:
    timestamp: str
    path: str
    name: str
    severity: str
    value_text: str
    status: str = "new"


class SensorApp:
    _SEVERITY_ORDER: dict[str, int] = {"normal": 0, "cool": 0, "warn": 1, "critical": 2}

    def __init__(self, root: tk.Tk, url: str, interval_ms: int) -> None:
        self.root = root
        self.url_var = tk.StringVar(value=url)
        self.source_preset_var = tk.StringVar(value=url)
        self.interval_var = tk.IntVar(value=interval_ms)
        self.wallboard_mode_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Waiting for first refresh")
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.category_var = tk.StringVar(value="all")
        self.severity_filter_var = tk.StringVar(value="all")
        self.source_var = tk.StringVar(value="all")
        self.hardware_var = tk.StringVar(value="all")
        self.compact_mode_var = tk.BooleanVar(value=True)
        self.hw_group_var = tk.BooleanVar(value=False)
        self.refresh_job = None
        self.current_payload: dict = {}
        self.current_rows: list[SensorRow] = []
        self.summary_value_vars: dict[str, tk.StringVar] = {}
        self.summary_detail_vars: dict[str, tk.StringVar] = {}
        self.summary_bar_canvases: dict[str, tk.Canvas] = {}
        self.favorite_rows: list[FavoriteRow] = []
        self.active_alert_rows: list[InsightRow] = []
        self.top_mover_rows: list[InsightRow] = []
        self.alert_history: list[AlertEvent] = []
        self.cpu_core_rows: list[tuple[str, str]] = []
        self.favorite_paths: set[str] = set()
        self.source_presets: list[str] = [url]
        self.muted_paths: set[str] = set()
        self.threshold_overrides: dict[str, dict[str, float]] = {}
        self.favorite_item_paths: dict[str, str] = {}
        self.alert_item_paths: dict[str, str] = {}
        self.mover_item_paths: dict[str, str] = {}
        self.alert_log_item_indexes: dict[str, int] = {}
        self.history: dict[str, list[float]] = {}
        self.alert_states: dict[str, str] = {}
        self.item_paths: dict[str, str] = {}
        self.item_nodes: dict[str, dict] = {}
        self.open_paths: set[str] = set()
        self.selected_path: str | None = None
        self.visible_sensor_count = 0
        self.visible_group_count = 0
        self._app_icon_image = None
        self.wallboard_job = None
        self.wallboard_rotate_index = 0
        self.detail_name_var = tk.StringVar(value="No sensor selected")
        self.detail_meta_var = tk.StringVar(value="")
        self.detail_status_var = tk.StringVar(value="")
        self.detail_value_var = tk.StringVar(value="")
        self.detail_range_var = tk.StringVar(value="")
        self.detail_stats_var = tk.StringVar(value="")
        self.detail_threshold_var = tk.StringVar(value="")
        self.detail_history_var = tk.StringVar(value="")
        self.detail_chart_canvas = None
        self.hint_var = tk.StringVar(value=self._default_hint_text())
        self.header_source_var = tk.StringVar(value="Waiting for data")
        self.header_snapshot_var = tk.StringVar(value="No snapshot yet")
        self.header_filter_var = tk.StringVar(value="Filters: all sensors")
        self.header_alert_var = tk.StringVar(value="Alerts: none")
        self.wallboard_title_var = tk.StringVar(value="Wallboard Off")
        self.wallboard_detail_var = tk.StringVar(value="Toggle wallboard mode for passive monitoring")
        self._banner_dismissed = False
        self.problem_paths: list[str] = []
        self.scope_buttons: dict[str, ttk.Button] = {}
        self.active_scope: str = "all"
        self.ssh_script_path_var = tk.StringVar(value=DEFAULT_SSH_SCRIPT)
        self.ssh_extra_args_var = tk.StringVar(value="")
        self._load_saved_state()

        self._build_ui()
        self.root.after(250, self.refresh)

    def _build_ui(self) -> None:
        self.root.title("HWMonitor Remote")
        self.root.geometry("1540x930")
        self.root.minsize(1180, 720)
        self.root.configure(bg="#11161c")
        self.root.option_add("*tearOff", False)
        self._set_app_icon()

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#11161c"
        panel = "#181f27"
        card = "#1d252e"
        edge = "#27313c"
        text = "#e6edf3"
        muted = "#8b9bae"
        green = "#37c871"
        amber = "#ffb020"
        red = "#ff5d5d"

        style.configure(".", background=bg, foreground=text, fieldbackground=panel)
        style.configure("App.TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Card.TFrame", background=card)
        style.configure("Title.TLabel", background=panel, foreground=text, font=("DejaVu Sans", 13, "bold"))
        style.configure("Muted.TLabel", background=panel, foreground=muted, font=("DejaVu Sans", 10))
        style.configure("CardTitle.TLabel", background=card, foreground=muted, font=("DejaVu Sans", 10, "bold"))
        style.configure("CardValue.TLabel", background=card, foreground=text, font=("DejaVu Sans", 17, "bold"))
        style.configure("CardDetail.TLabel", background=card, foreground=muted, font=("DejaVu Sans", 10))
        style.configure("Section.TLabel", background=panel, foreground=text, font=("DejaVu Sans", 11, "bold"))
        style.configure("Treeview", background=panel, foreground=text, fieldbackground=panel, rowheight=23, borderwidth=0, font=("DejaVu Sans Mono", 10))
        style.configure("Treeview.Heading", background=card, foreground=text, relief="flat", font=("DejaVu Sans", 10, "bold"))
        style.map("Treeview", background=[("selected", "#2a3642")], foreground=[("selected", text)])
        style.configure("TEntry", fieldbackground=card, foreground=text, insertcolor=text, bordercolor=edge)
        style.configure("TCombobox", fieldbackground=card, foreground=text, arrowcolor=text)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", card)],
            background=[("readonly", card)],
            foreground=[("readonly", text)],
            selectforeground=[("readonly", text)],
            selectbackground=[("readonly", "#24303b")],
        )
        style.configure("TButton", background=card, foreground=text, bordercolor=edge)
        style.map("TButton", background=[("active", "#24303b")])
        style.configure("Scope.TButton", background=card, foreground=muted, bordercolor=edge)
        style.configure("Scope.Active.TButton", background="#1a5e8c", foreground=text, bordercolor="#2a8fc7")
        style.map("Scope.Active.TButton", background=[("active", "#1a6fa8")])
        style.configure("TCheckbutton", background=panel, foreground=text)
        style.configure("Overview.TNotebook", background=panel, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("Overview.TNotebook.Tab", background=card, foreground=muted, padding=(10, 6), font=("DejaVu Sans", 10, "bold"))
        style.map("Overview.TNotebook.Tab", background=[("selected", "#24303b")], foreground=[("selected", text)])

        outer = ttk.Frame(self.root, style="App.TFrame", padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        header.pack(fill="x")

        left_header = ttk.Frame(header, style="Panel.TFrame")
        left_header.pack(side="left", fill="x", expand=True)
        ttk.Label(left_header, text="HWMonitor Remote", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left_header, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        controls = ttk.Frame(header, style="Panel.TFrame")
        controls.pack(side="right")
        ttk.Label(controls, text="Source", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.source_entry = ttk.Entry(controls, textvariable=self.url_var, width=38)
        self.source_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        ttk.Button(controls, text="Refresh", command=self.refresh).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(controls, text="Wallboard", command=self._toggle_wallboard_mode).grid(row=0, column=6, padx=(10, 0))
        ttk.Checkbutton(controls, text="Auto", variable=self.auto_refresh_var, command=self._toggle_auto).grid(row=0, column=3, padx=(0, 8))
        ttk.Label(controls, text="Interval", style="Muted.TLabel").grid(row=0, column=4, sticky="e")
        interval_box = ttk.Combobox(controls, width=8, state="readonly", textvariable=self.interval_var, values=(1000, 2000, 3000, 5000, 10000))
        interval_box.grid(row=0, column=5, padx=(6, 0))
        interval_box.bind("<<ComboboxSelected>>", lambda _event: self._reschedule())
        ttk.Label(controls, text="Preset", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.preset_box = ttk.Combobox(controls, width=38, state="readonly", textvariable=self.source_preset_var)
        self.preset_box.grid(row=1, column=1, sticky="ew", padx=(6, 8), pady=(8, 0))
        self.preset_box.bind("<<ComboboxSelected>>", self._apply_selected_preset)
        ttk.Button(controls, text="Use", command=self._apply_selected_preset).grid(row=1, column=2, padx=(0, 8), pady=(8, 0))
        ttk.Button(controls, text="Save Preset", command=self._save_current_preset).grid(row=1, column=3, padx=(0, 8), pady=(8, 0))
        controls.columnconfigure(1, weight=1)

        telemetry_bar = ttk.Frame(outer, style="Panel.TFrame", padding=8)
        telemetry_bar.pack(fill="x", pady=(8, 0))
        telemetry_specs = (
            ("Source Health", self.header_source_var),
            ("Snapshot", self.header_snapshot_var),
            ("Focus", self.header_filter_var),
            ("Alerts", self.header_alert_var),
        )
        for index, (title, variable) in enumerate(telemetry_specs):
            cell = ttk.Frame(telemetry_bar, style="Card.TFrame", padding=10)
            cell.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0))
            telemetry_bar.columnconfigure(index, weight=1)
            ttk.Label(cell, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(cell, textvariable=variable, style="CardDetail.TLabel", wraplength=280, justify="left").pack(anchor="w", pady=(4, 0))

        self.alert_banner = tk.Frame(outer, bg="#7c2020", padx=10, pady=6)
        # Not packed by default — only shown when alerts exist

        self.alert_text_var = tk.StringVar()
        alert_label = tk.Label(
            self.alert_banner,
            textvariable=self.alert_text_var,
            bg="#7c2020",
            fg="#ffffff",
            font=("DejaVu Sans", 10, "bold"),
            anchor="w",
        )
        alert_label.pack(side="left", fill="x", expand=True)

        self.alert_action_button = tk.Button(
            self.alert_banner,
            text="Show",
            bg="#7c2020",
            fg="#ffffff",
            relief="flat",
            font=("DejaVu Sans", 10, "bold"),
            command=self._show_problem_sensors,
        )
        self.alert_action_button.pack(side="right", padx=(8, 4))

        alert_dismiss = tk.Button(
            self.alert_banner,
            text="x",
            bg="#7c2020",
            fg="#ffffff",
            relief="flat",
            font=("DejaVu Sans", 10),
            command=self._dismiss_alert_banner,
        )
        alert_dismiss.pack(side="right")

        self.wallboard_frame = ttk.Frame(outer, style="Card.TFrame", padding=12)
        ttk.Label(self.wallboard_frame, textvariable=self.wallboard_title_var, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.wallboard_frame, textvariable=self.wallboard_detail_var, style="CardDetail.TLabel").pack(anchor="w", pady=(4, 0))

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(10, 0))

        overview = ttk.Frame(body, style="Panel.TFrame", padding=10)
        explorer = ttk.Frame(body, style="Panel.TFrame", padding=10)
        body.add(overview, weight=1)
        body.add(explorer, weight=4)
        self.body = body

        summary_grid = ttk.Frame(overview, style="Panel.TFrame")
        summary_grid.pack(fill="x")
        summary_specs = ("CPU", "GPU", "Cooling", "Drive")
        for idx, title in enumerate(summary_specs):
            card_frame = ttk.Frame(summary_grid, style="Card.TFrame", padding=10)
            row = idx // 2
            col = idx % 2
            card_frame.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0), pady=(0, 6))
            summary_grid.columnconfigure(col, weight=1)
            ttk.Label(card_frame, text=title, style="CardTitle.TLabel").pack(anchor="w")
            value_var = tk.StringVar(value="--")
            detail_var = tk.StringVar(value="")
            ttk.Label(card_frame, textvariable=value_var, style="CardValue.TLabel").pack(anchor="w", pady=(4, 0))
            ttk.Label(card_frame, textvariable=detail_var, style="CardDetail.TLabel").pack(anchor="w", pady=(4, 0))
            self.summary_value_vars[title] = value_var
            self.summary_detail_vars[title] = detail_var
            bar_canvas = tk.Canvas(card_frame, height=6, bg="#27313c", highlightthickness=0, bd=0)
            bar_canvas.pack(fill="x", pady=(6, 0))
            self.summary_bar_canvases[title] = bar_canvas
            bar_canvas.bind("<Configure>", lambda _e, n=title: self._redraw_summary_bar(n, None))

        insights_tabs = ttk.Notebook(overview, style="Overview.TNotebook")
        insights_tabs.pack(fill="both", expand=True, pady=(8, 0))

        fav_frame = ttk.Frame(insights_tabs, style="Card.TFrame", padding=8)
        self.favorites_tree = ttk.Treeview(fav_frame, columns=("sensor", "value", "state"), show="headings", height=8)
        self.favorites_tree.heading("sensor", text="Sensor", command=lambda: self._sort_table(self.favorites_tree, "sensor", numeric=False))
        self.favorites_tree.heading("value", text="Value", command=lambda: self._sort_table(self.favorites_tree, "value", numeric=True))
        self.favorites_tree.heading("state", text="State", command=lambda: self._sort_table(self.favorites_tree, "state", numeric=False))
        self.favorites_tree.column("sensor", width=180, anchor="w")
        self.favorites_tree.column("value", width=85, anchor="e")
        self.favorites_tree.column("state", width=70, anchor="center")
        self.favorites_tree.tag_configure("warn", foreground=amber)
        self.favorites_tree.tag_configure("critical", foreground=red)
        self.favorites_tree.tag_configure("cool", foreground=green)
        self.favorites_tree.pack(fill="x")
        self.favorites_tree.bind("<Double-1>", self._focus_selected_favorite)
        self.favorites_tree.bind("<Return>", self._focus_selected_favorite)
        self.favorites_tree.bind("<Delete>", self._remove_selected_favorite_pin)
        self.favorites_tree.bind("<Button-3>", self._show_favorite_context_menu)

        alert_frame = ttk.Frame(insights_tabs, style="Card.TFrame", padding=8)
        self.alerts_tree = ttk.Treeview(alert_frame, columns=("sensor", "value", "state"), show="headings", height=6)
        self.alerts_tree.heading("sensor", text="Sensor", command=lambda: self._sort_table(self.alerts_tree, "sensor", numeric=False))
        self.alerts_tree.heading("value", text="Value", command=lambda: self._sort_table(self.alerts_tree, "value", numeric=True))
        self.alerts_tree.heading("state", text="State", command=lambda: self._sort_table(self.alerts_tree, "state", numeric=False))
        self.alerts_tree.column("sensor", width=170, anchor="w")
        self.alerts_tree.column("value", width=85, anchor="e")
        self.alerts_tree.column("state", width=82, anchor="center")
        self.alerts_tree.tag_configure("warn", foreground=amber)
        self.alerts_tree.tag_configure("critical", foreground=red)
        self.alerts_tree.pack(fill="x")
        self.alerts_tree.bind("<Double-1>", self._focus_selected_alert)
        self.alerts_tree.bind("<Return>", self._focus_selected_alert)

        movers_frame = ttk.Frame(insights_tabs, style="Card.TFrame", padding=8)
        self.movers_tree = ttk.Treeview(movers_frame, columns=("sensor", "delta", "latest"), show="headings", height=6)
        self.movers_tree.heading("sensor", text="Sensor", command=lambda: self._sort_table(self.movers_tree, "sensor", numeric=False))
        self.movers_tree.heading("delta", text="Delta", command=lambda: self._sort_table(self.movers_tree, "delta", numeric=True))
        self.movers_tree.heading("latest", text="Latest", command=lambda: self._sort_table(self.movers_tree, "latest", numeric=True))
        self.movers_tree.column("sensor", width=170, anchor="w")
        self.movers_tree.column("delta", width=85, anchor="e")
        self.movers_tree.column("latest", width=85, anchor="e")
        self.movers_tree.tag_configure("warn", foreground=amber)
        self.movers_tree.tag_configure("critical", foreground=red)
        self.movers_tree.tag_configure("cool", foreground=green)
        self.movers_tree.pack(fill="x")
        self.movers_tree.bind("<Double-1>", self._focus_selected_mover)
        self.movers_tree.bind("<Return>", self._focus_selected_mover)

        alert_log_frame = ttk.Frame(insights_tabs, style="Card.TFrame", padding=8)
        alert_log_actions = ttk.Frame(alert_log_frame, style="Card.TFrame")
        alert_log_actions.pack(fill="x", pady=(0, 8))
        ttk.Button(alert_log_actions, text="Acknowledge", command=self._ack_selected_alert_event).pack(side="left")
        ttk.Button(alert_log_actions, text="Clear Log", command=self._clear_alert_history).pack(side="left", padx=(6, 0))
        self.alert_log_tree = ttk.Treeview(alert_log_frame, columns=("time", "sensor", "value", "state", "status"), show="headings", height=10)
        self.alert_log_tree.heading("time", text="Time", command=lambda: self._sort_table(self.alert_log_tree, "time", numeric=False))
        self.alert_log_tree.heading("sensor", text="Sensor", command=lambda: self._sort_table(self.alert_log_tree, "sensor", numeric=False))
        self.alert_log_tree.heading("value", text="Value", command=lambda: self._sort_table(self.alert_log_tree, "value", numeric=True))
        self.alert_log_tree.heading("state", text="State", command=lambda: self._sort_table(self.alert_log_tree, "state", numeric=False))
        self.alert_log_tree.heading("status", text="Status", command=lambda: self._sort_table(self.alert_log_tree, "status", numeric=False))
        self.alert_log_tree.column("time", width=90, anchor="w")
        self.alert_log_tree.column("sensor", width=160, anchor="w")
        self.alert_log_tree.column("value", width=80, anchor="e")
        self.alert_log_tree.column("state", width=75, anchor="center")
        self.alert_log_tree.column("status", width=95, anchor="center")
        self.alert_log_tree.tag_configure("warn", foreground=amber)
        self.alert_log_tree.tag_configure("critical", foreground=red)
        self.alert_log_tree.pack(fill="both", expand=True)
        self.alert_log_tree.bind("<Double-1>", self._focus_selected_alert_event)
        self.alert_log_tree.bind("<Return>", self._focus_selected_alert_event)

        cores_frame = ttk.Frame(insights_tabs, style="Card.TFrame", padding=8)
        self.cores_tree = ttk.Treeview(cores_frame, columns=("temp",), show="headings", height=8)
        self.cores_tree.heading("temp", text="Temp", command=lambda: self._sort_table(self.cores_tree, "temp", numeric=True))
        self.cores_tree.column("#0", width=0, stretch=False)
        self.cores_tree.column("temp", width=100, anchor="e")
        self.cores_tree.pack(fill="both", expand=True)
        insights_tabs.add(fav_frame, text="Pinned")
        insights_tabs.add(alert_frame, text="Alerts")
        insights_tabs.add(movers_frame, text="Movers")
        insights_tabs.add(alert_log_frame, text="Alert Log")
        insights_tabs.add(cores_frame, text="CPU Cores")

        filter_bar = ttk.Frame(explorer, style="Panel.TFrame")
        filter_bar.pack(fill="x")
        ttk.Label(filter_bar, text="Explore", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.search_entry = ttk.Entry(filter_bar, textvariable=self.search_var, width=34)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._rebuild_tree())
        for _scope_key, _scope_label, _col in (("all", "All", 2), ("active", "Alerts", 3), ("hwinfo", "HWiNFO", 4), ("native", "Native", 5)):
            _pad = (0, 6) if _scope_key != "native" else (0, 12)
            _style = "Scope.Active.TButton" if _scope_key == "all" else "Scope.TButton"
            _btn = ttk.Button(filter_bar, text=_scope_label, style=_style, command=lambda s=_scope_key: self._apply_quick_scope(s))
            _btn.grid(row=0, column=_col, padx=_pad)
            self.scope_buttons[_scope_key] = _btn
        self.count_label = ttk.Label(filter_bar, text="0 sensors", style="Muted.TLabel")
        self.count_label.grid(row=0, column=6, sticky="e")
        ttk.Label(filter_bar, text="Category", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        category_box = ttk.Combobox(filter_bar, width=12, state="readonly", textvariable=self.category_var, values=CATEGORY_VALUES)
        category_box.grid(row=1, column=1, sticky="w", padx=(6, 8), pady=(8, 0))
        category_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        ttk.Label(filter_bar, text="Severity", style="Muted.TLabel").grid(row=1, column=2, sticky="e", padx=(10, 0), pady=(8, 0))
        severity_box = ttk.Combobox(filter_bar, width=10, state="readonly", textvariable=self.severity_filter_var, values=SEVERITY_FILTER_VALUES)
        severity_box.grid(row=1, column=3, padx=(6, 0), pady=(8, 0))
        severity_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        ttk.Label(filter_bar, text="Source", style="Muted.TLabel").grid(row=1, column=4, sticky="e", padx=(10, 0), pady=(8, 0))
        self.source_box = ttk.Combobox(filter_bar, width=18, state="readonly", textvariable=self.source_var, values=SOURCE_FILTER_VALUES)
        self.source_box.grid(row=1, column=5, padx=(6, 0), pady=(8, 0))
        self.source_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        ttk.Label(filter_bar, text="Hardware", style="Muted.TLabel").grid(row=1, column=6, sticky="e", padx=(10, 0), pady=(8, 0))
        self.hardware_box = ttk.Combobox(filter_bar, width=22, state="readonly", textvariable=self.hardware_var, values=("all",))
        self.hardware_box.grid(row=1, column=7, padx=(6, 6), pady=(8, 0))
        self.hardware_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        ttk.Checkbutton(filter_bar, text="Compact", variable=self.compact_mode_var, command=self._rebuild_tree).grid(row=1, column=8, padx=(0, 8), pady=(8, 0))
        by_hw_cb = ttk.Checkbutton(filter_bar, text="By HW", variable=self.hw_group_var, command=self._rebuild_tree)
        by_hw_cb.grid(row=1, column=9, padx=(0, 8), pady=(8, 0))
        ttk.Button(filter_bar, text="Expand", command=lambda: self._set_all_open(True)).grid(row=1, column=10, padx=(6, 6), pady=(8, 0))
        ttk.Button(filter_bar, text="Collapse", command=lambda: self._set_all_open(False)).grid(row=1, column=11, padx=(0, 6), pady=(8, 0))
        ttk.Button(filter_bar, text="Reset", command=self._reset_filters).grid(row=1, column=12, padx=(0, 10), pady=(8, 0))
        ttk.Button(filter_bar, text="Export CSV", command=self._export_csv).grid(row=1, column=13, padx=(0, 10), pady=(8, 0))
        filter_bar.columnconfigure(1, weight=1)
        filter_bar.columnconfigure(6, weight=1)
        ttk.Label(explorer, textvariable=self.hint_var, style="Muted.TLabel").pack(anchor="w", pady=(2, 8))

        self.tree_frame = ttk.Frame(explorer, style="Card.TFrame", padding=6)
        self.tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(self.tree_frame, columns=("value", "delta", "min", "max"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Sensor", command=lambda: self._sort_main_tree("#0", numeric=False))
        self.tree.heading("value", text="Value", command=lambda: self._sort_main_tree("value", numeric=True))
        self.tree.heading("delta", text="Delta", command=lambda: self._sort_main_tree("delta", numeric=True))
        self.tree.heading("min", text="Min", command=lambda: self._sort_main_tree("min", numeric=True))
        self.tree.heading("max", text="Max", command=lambda: self._sort_main_tree("max", numeric=True))
        self.tree.column("#0", width=560, anchor="w")
        self.tree.column("value", width=120, anchor="e")
        self.tree.column("delta", width=120, anchor="e")
        self.tree.column("min", width=110, anchor="e")
        self.tree.column("max", width=110, anchor="e")
        self.tree.tag_configure("hardware", foreground="#d9e2ec", font=("DejaVu Sans", 10, "bold"))
        self.tree.tag_configure("group", foreground="#a9b8c7", font=("DejaVu Sans", 10, "bold"))
        self.tree.tag_configure("sensor", foreground=text)
        self.tree.tag_configure("favorite", foreground="#7fd4ff", font=("DejaVu Sans Mono", 10, "bold"))
        self.tree.tag_configure("muted", foreground=muted)
        self.tree.tag_configure("warn", foreground=amber)
        self.tree.tag_configure("critical", foreground=red)
        self.tree.tag_configure("cool", foreground=green)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._show_tree_context_menu)
        yscroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree_frame.rowconfigure(0, weight=1)
        self.tree_frame.columnconfigure(0, weight=1)

        self.detail_frame = ttk.Frame(explorer, style="Card.TFrame", padding=8)
        self.detail_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(self.detail_frame, text="Selected Sensor", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.detail_frame, textvariable=self.detail_name_var, style="Title.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_value_var, style="CardValue.TLabel").grid(row=1, column=1, sticky="e", padx=(20, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_meta_var, style="Muted.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_status_var, style="CardDetail.TLabel").grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_range_var, style="CardDetail.TLabel").grid(row=3, column=1, sticky="e", padx=(20, 0), pady=(4, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_stats_var, style="CardDetail.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_threshold_var, style="CardDetail.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_history_var, style="Muted.TLabel").grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.detail_chart_canvas = tk.Canvas(
            self.detail_frame,
            width=420,
            height=120,
            bg="#141b22",
            highlightthickness=1,
            highlightbackground="#27313c",
            bd=0,
        )
        self.detail_chart_canvas.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions = ttk.Frame(self.detail_frame, style="Card.TFrame")
        actions.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.detail_pin_button = ttk.Button(actions, text="Pin", command=self._toggle_selected_favorite)
        self.detail_pin_button.pack(side="left")
        self.detail_mute_button = ttk.Button(actions, text="Mute Alert", command=self._toggle_selected_mute)
        self.detail_mute_button.pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Warn = Current", command=self._set_warn_threshold_from_selected).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Critical = Current", command=self._set_critical_threshold_from_selected).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Clear Thresholds", command=self._clear_selected_thresholds).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Copy Path", command=self._copy_selected_path).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Copy Value", command=self._copy_selected_value).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Focus Hardware", command=self._focus_selected_hardware).pack(side="left", padx=(6, 0))
        self.detail_frame.columnconfigure(0, weight=1)

        self.tree_menu = tk.Menu(self.root, tearoff=False)
        self.tree_menu.add_command(label="Pin / Unpin Sensor", command=self._toggle_selected_favorite)
        self.tree_menu.add_command(label="Mute / Unmute Alert", command=self._toggle_selected_mute)
        self.tree_menu.add_command(label="Set Warn Threshold = Current", command=self._set_warn_threshold_from_selected)
        self.tree_menu.add_command(label="Set Critical Threshold = Current", command=self._set_critical_threshold_from_selected)
        self.tree_menu.add_command(label="Clear Custom Thresholds", command=self._clear_selected_thresholds)
        self.tree_menu.add_command(label="Copy Sensor Path", command=self._copy_selected_path)
        self.tree_menu.add_command(label="Copy Sensor Value", command=self._copy_selected_value)
        self.tree_menu.add_command(label="Filter To Hardware", command=self._focus_selected_hardware)
        self.tree_menu.add_command(label="Search Sensor Name", command=self._search_selected_name)

        self.favorite_menu = tk.Menu(self.root, tearoff=False)
        self.favorite_menu.add_command(label="Open Favorite in Tree", command=self._focus_selected_favorite)
        self.favorite_menu.add_command(label="Pin / Unpin Favorite", command=self._on_favorite_activate)
        self.favorite_menu.add_command(label="Remove Saved Pin", command=self._remove_selected_favorite_pin)
        self.favorite_menu.add_command(label="Copy Favorite Path", command=self._copy_selected_favorite_path)

        self.root.bind("<F5>", lambda _event: self.refresh())
        self.root.bind("<Control-r>", lambda _event: self.refresh())
        self.root.bind("<Control-f>", self._focus_search)
        self.root.bind("<Control-l>", self._focus_source)
        self.root.bind("<Control-s>", lambda _event: self._save_current_preset())
        self.root.bind("<Control-c>", self._copy_selected_value)
        self.root.bind("<F11>", lambda _event: self._toggle_wallboard_mode())
        self.root.bind("<Escape>", self._handle_escape)
        self.root.bind("<p>", lambda _event: self._toggle_selected_favorite())

        self._update_source_presets_ui()
        self.root.after(150, self._set_initial_layout)

    def _set_app_icon(self) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        png_path = os.path.join(base_dir, "assets", "icons", f"{APP_ICON_NAME}.png")
        ico_path = os.path.join(base_dir, "assets", "icons", f"{APP_ICON_NAME}.ico")

        if os.name == "nt" and os.path.exists(ico_path):
            try:
                self.root.iconbitmap(default=ico_path)
            except tk.TclError as exc:
                print(f"Warning: failed to load Windows app icon {ico_path}: {exc}", file=sys.stderr)

        for candidate in (png_path, os.path.join(base_dir, "logo.png")):
            if not os.path.exists(candidate):
                continue
            try:
                self._app_icon_image = tk.PhotoImage(file=candidate)
                self.root.iconphoto(True, self._app_icon_image)
                return
            except (tk.TclError, OSError) as exc:
                print(f"Warning: failed to load app icon {candidate}: {exc}", file=sys.stderr)
                return

        print(f"Warning: no app icon asset found near {png_path}", file=sys.stderr)

    def _toggle_auto(self) -> None:
        self._reschedule()

    def _update_source_presets_ui(self) -> None:
        unique_presets = []
        seen: set[str] = set()
        for value in [self.url_var.get(), *self.source_presets]:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_presets.append(normalized)
        self.source_presets = unique_presets
        self.preset_box.configure(values=tuple(self.source_presets))
        if self.source_preset_var.get() not in self.source_presets:
            self.source_preset_var.set(self.url_var.get())

    def _apply_selected_preset(self, _event=None) -> None:
        preset = self.source_preset_var.get().strip()
        if not preset:
            return
        self.url_var.set(preset)
        self.status_var.set(f"Source preset selected: {preset}")
        self._persist_config()

    def _save_current_preset(self) -> str:
        preset = self.url_var.get().strip()
        if not preset:
            self.status_var.set("No source URL to save as a preset")
            return "break"
        if preset not in self.source_presets:
            self.source_presets.append(preset)
        self.source_preset_var.set(preset)
        self._update_source_presets_ui()
        self._persist_config()
        self.status_var.set(f"Saved source preset: {preset}")
        return "break"

    def _refresh_scope_buttons(self, active_scope: str) -> None:
        self.active_scope = active_scope
        for scope, btn in self.scope_buttons.items():
            btn.configure(style=SensorApp._scope_button_style_name(scope, active_scope))

    def _apply_quick_scope(self, scope: str) -> None:
        if scope == "all":
            self.search_var.set("")
            self.category_var.set("all")
            self.severity_filter_var.set("all")
            self.source_var.set("all")
            self.hardware_var.set("all")
            self.compact_mode_var.set(True)
        elif scope == "active":
            self.search_var.set("")
            self.severity_filter_var.set("active")
            self.source_var.set("all")
            self.hardware_var.set("all")
            self.compact_mode_var.set(True)
        elif scope == "hwinfo":
            self.search_var.set("")
            self.source_var.set("HWiNFO")
            self.hardware_var.set("all")
            self.compact_mode_var.set(True)
        elif scope == "native":
            self.search_var.set("")
            self.source_var.set("LibreHardwareMonitorLib")
            self.hardware_var.set("all")
            self.compact_mode_var.set(True)
        self._refresh_scope_buttons(scope)
        self._rebuild_tree()

    def _toggle_wallboard_mode(self) -> str:
        self.wallboard_mode_var.set(not self.wallboard_mode_var.get())
        self._apply_wallboard_mode()
        self._persist_config()
        return "break"

    def _apply_wallboard_mode(self) -> None:
        enabled = self.wallboard_mode_var.get()
        try:
            self.root.attributes("-fullscreen", enabled)
        except tk.TclError:
            pass
        if enabled:
            self.wallboard_frame.pack(fill="x", pady=(10, 0), before=self.body)
            self._set_all_open(False)
            self._render_wallboard()
            self._schedule_wallboard_rotation()
            self.status_var.set("Wallboard mode enabled")
        else:
            self.wallboard_frame.pack_forget()
            if self.wallboard_job is not None:
                self.root.after_cancel(self.wallboard_job)
                self.wallboard_job = None
            self.status_var.set("Wallboard mode disabled")

    def _schedule_wallboard_rotation(self) -> None:
        if self.wallboard_job is not None:
            self.root.after_cancel(self.wallboard_job)
            self.wallboard_job = None
        if self.wallboard_mode_var.get():
            self.wallboard_job = self.root.after(5000, self._rotate_wallboard_focus)

    def _rotate_wallboard_focus(self) -> None:
        if not self.wallboard_mode_var.get():
            return
        if self.problem_paths:
            path = self.problem_paths[self.wallboard_rotate_index % len(self.problem_paths)]
            self.wallboard_rotate_index += 1
            self._focus_path(path)
        self._render_wallboard()
        self._schedule_wallboard_rotation()

    def _render_wallboard(self) -> None:
        critical_count, warn_count = SensorApp._alert_counts(self.current_rows)
        if not self.wallboard_mode_var.get():
            self.wallboard_title_var.set("Wallboard Off")
            self.wallboard_detail_var.set("Toggle wallboard mode for passive monitoring")
            return
        focus_path = ""
        if self.problem_paths:
            focus_path = self.problem_paths[(max(self.wallboard_rotate_index - 1, 0)) % len(self.problem_paths)]
        title, detail = SensorApp._wallboard_texts(
            critical_count,
            warn_count,
            focus_path,
            self.visible_sensor_count,
        )
        self.wallboard_title_var.set(title)
        self.wallboard_detail_var.set(detail)

    def _refresh_header_summary(self) -> None:
        payload_sources = self.current_payload.get("sources", [])
        if isinstance(payload_sources, list) and payload_sources:
            source_text = ", ".join(str(source) for source in payload_sources[:3])
            if len(payload_sources) > 3:
                source_text += f" +{len(payload_sources) - 3}"
        else:
            source_text = "Waiting for source metadata"
        self.header_source_var.set(f"{source_text}  |  interval {self.interval_var.get()} ms")

        generated = self.current_payload.get("generatedAt")
        self.header_snapshot_var.set(f"{generated}" if generated else "No snapshot yet")

        filter_bits = []
        if self.search_var.get().strip():
            filter_bits.append(f"search={self.search_var.get().strip()}")
        if self.source_var.get() != "all":
            filter_bits.append(f"source={self.source_var.get()}")
        if self.hardware_var.get() != "all":
            filter_bits.append(f"hardware={self.hardware_var.get()}")
        if self.severity_filter_var.get() != "all":
            filter_bits.append(f"severity={self.severity_filter_var.get()}")
        if self.category_var.get() != "all":
            filter_bits.append(f"category={self.category_var.get()}")
        if self.compact_mode_var.get():
            filter_bits.append("compact")
        if not filter_bits:
            filter_bits.append("all sensors")
        self.header_filter_var.set(
            f"{', '.join(filter_bits)}  |  visible {self.visible_sensor_count} sensors / {self.visible_group_count} groups"
        )

        critical_count, warn_count = SensorApp._alert_counts(self.current_rows)
        if critical_count or warn_count:
            alert_bits = []
            if critical_count:
                alert_bits.append(f"{critical_count} critical")
            if warn_count:
                alert_bits.append(f"{warn_count} warning")
            self.header_alert_var.set(" / ".join(alert_bits))
        else:
            self.header_alert_var.set("No active alerts")

    @staticmethod
    def _wallboard_texts(critical_count: int, warn_count: int, focus_path: str, sensor_count: int) -> tuple[str, str]:
        if focus_path:
            title = f"Critical {critical_count}  |  Warn {warn_count}  |  Focus {focus_path.split('/')[-1]}"
            detail = f"Auto-rotating problem sensors every 5s  |  Current path: {focus_path}"
            return title, detail
        return (
            "System Stable",
            f"No active warning thresholds breached  |  Monitoring {sensor_count} sensors",
        )

    def _thresholds_for_path(self, path: str, sensor_type: str) -> dict[str, float] | None:
        if not path:
            return None
        overrides = self.threshold_overrides.get(path)
        if overrides:
            return overrides
        return SensorApp._default_thresholds(sensor_type)

    def _effective_severity(self, path: str, sensor_type: str, value: float | None) -> str:
        thresholds = self._thresholds_for_path(path, sensor_type)
        if value is None or not thresholds:
            return "normal"
        warn_at = thresholds.get("warn")
        critical_at = thresholds.get("critical")
        if critical_at is not None and value >= critical_at:
            return "critical"
        if warn_at is not None and value >= warn_at:
            return "warn"
        if sensor_type in {"Temperature", "Load", "Control", "Power"}:
            return "cool"
        return "normal"

    def _apply_effective_states(self, rows: list[SensorRow]) -> None:
        for row in rows:
            if row.kind != "sensor":
                continue
            row.severity = self._effective_severity(row.path, row.sensor_type, row.value)

    def _selected_sensor_payload(self) -> tuple[str, dict] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        item_id = selection[0]
        path = self.item_paths.get(item_id, "")
        node = self.item_nodes.get(item_id, {})
        if not path or node.get("kind") != "sensor":
            return None
        return path, node

    def _toggle_selected_mute(self) -> None:
        selected = self._selected_sensor_payload()
        if not selected:
            return
        path, _node = selected
        if path in self.muted_paths:
            self.muted_paths.remove(path)
            self.status_var.set(f"Unmuted alert for {path}")
        else:
            self.muted_paths.add(path)
            self.status_var.set(f"Muted alert for {path}")
        self._persist_config()
        self._apply_effective_states(self.current_rows)
        self._update_overview(self.current_rows)
        self._rebuild_tree()
        self._on_tree_select()

    def _set_warn_threshold_from_selected(self) -> None:
        self._set_threshold_from_selected("warn")

    def _set_critical_threshold_from_selected(self) -> None:
        self._set_threshold_from_selected("critical")

    def _set_threshold_from_selected(self, level: str) -> None:
        selected = self._selected_sensor_payload()
        if not selected:
            return
        path, node = selected
        value = node.get("value")
        sensor_type = node.get("type", "")
        if value is None or sensor_type not in {"Temperature", "Load", "Control", "Power"}:
            self.status_var.set("Threshold overrides are only available for numeric temp/load/power sensors")
            return
        overrides = dict(self.threshold_overrides.get(path, SensorApp._default_thresholds(sensor_type) or {}))
        overrides[level] = float(value)
        if overrides.get("warn", 0) > overrides.get("critical", 0):
            if level == "warn":
                overrides["critical"] = overrides["warn"]
            else:
                overrides["warn"] = overrides["critical"]
        self.threshold_overrides[path] = overrides
        self.status_var.set(f"Set {level} threshold for {path} to {self._format_value(value, node.get('unit', ''))}")
        self._persist_config()
        self._apply_effective_states(self.current_rows)
        self._update_overview(self.current_rows)
        self._rebuild_tree()
        self._on_tree_select()

    def _clear_selected_thresholds(self) -> None:
        selected = self._selected_sensor_payload()
        if not selected:
            return
        path, _node = selected
        if path in self.threshold_overrides:
            del self.threshold_overrides[path]
            self.status_var.set(f"Cleared custom thresholds for {path}")
            self._persist_config()
            self._apply_effective_states(self.current_rows)
            self._update_overview(self.current_rows)
            self._rebuild_tree()
            self._on_tree_select()

    def _reschedule(self) -> None:
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
            self.refresh_job = None
        if self.auto_refresh_var.get():
            self.refresh_job = self.root.after(self.interval_var.get(), self.refresh)

    def refresh(self) -> None:
        self.status_var.set(f"Refreshing {self.url_var.get()} ...")
        self._persist_config()
        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()

    def _fetch_data(self) -> None:
        started = time.time()
        try:
            if self.url_var.get().startswith("ssh://"):
                payload = self._fetch_over_ssh(self.url_var.get())
            else:
                request = urllib.request.Request(self.url_var.get(), headers={"User-Agent": "hwremote-monitor/1.0"})
                with urllib.request.urlopen(request, timeout=6) as response:
                    payload = json.load(response)
            elapsed = int((time.time() - started) * 1000)
            self.root.after(0, lambda: self._apply_data(payload, elapsed))
        except urllib.error.URLError as exc:
            self.root.after(0, lambda: self._set_error(f"Refresh failed: {exc}"))
        except Exception as exc:
            self.root.after(0, lambda: self._set_error(f"Refresh failed: {exc}"))

    def _set_error(self, message: str) -> None:
        self.status_var.set(message)
        self.hint_var.set("Last refresh failed  |  Check source host, SSH, and Windows sensor script  |  Esc clears filters")
        self._reschedule()

    @staticmethod
    def _fetch_over_ssh(url: str) -> dict:
        target = url[len("ssh://") :]
        remote_script = r"C:\Users\loofi\hwremote-monitor\lhm-snapshot.ps1"
        cmd = [
            "ssh",
            "-F",
            "/dev/null",
            target,
            f"powershell -NoProfile -ExecutionPolicy Bypass -File {remote_script}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)
        return json.loads(result.stdout)

    def _apply_data(self, payload: dict, elapsed_ms: int) -> None:
        self.current_payload = payload
        self.current_rows = self._flatten_rows(payload)
        self._apply_effective_states(self.current_rows)
        new_alerts, self.alert_states = self._compute_alerts_static(self.current_rows, self.alert_states)
        self._record_alert_events(new_alerts)
        self._update_source_choices(payload)
        self._update_hardware_choices(payload)
        self._update_overview(self.current_rows)
        self._rebuild_tree()
        self._refresh_header_summary()
        self._update_alert_banner(self.current_rows)
        self._render_wallboard()
        generated = payload.get("generatedAt", "unknown time")
        self.status_var.set(f"Updated in {elapsed_ms} ms, snapshot {generated}")
        self.hint_var.set(self._default_hint_text())
        self._reschedule()

    def _dismiss_alert_banner(self) -> None:
        self._banner_dismissed = True
        self.alert_banner.pack_forget()

    def _update_alert_banner(self, rows: list[SensorRow]) -> None:
        breached = [
            row for row in rows
            if row.kind == "sensor"
            and row.value is not None
            and row.path not in self.muted_paths
            and row.severity in ("warn", "critical")
        ]
        breached.sort(
            key=lambda row: (
                SensorApp._SEVERITY_ORDER.get(row.severity, 0),
                row.value or 0,
            ),
            reverse=True,
        )
        self.problem_paths = [row.path for row in breached]
        if not breached:
            self.alert_banner.pack_forget()
            self._banner_dismissed = False
            return

        if self._banner_dismissed:
            return

        critical_count, warn_count = SensorApp._alert_counts(breached)
        summary_bits = []
        if critical_count:
            summary_bits.append(f"{critical_count} critical")
        if warn_count:
            summary_bits.append(f"{warn_count} warning")

        parts = [
            f"{self._display_label(row.name, row.severity)} {self._format_value(row.value, row.unit)}"
            for row in breached[:5]
        ]
        if len(breached) > 5:
            parts.append(f"+{len(breached) - 5} more")

        has_critical = any(
            r.severity == "critical" for r in breached
        )
        color = "#7c2020" if has_critical else "#7c5c00"
        self.alert_banner.configure(bg=color)
        for widget in self.alert_banner.winfo_children():
            try:
                widget.configure(bg=color)
            except tk.TclError:
                pass

        summary_prefix = " / ".join(summary_bits)
        self.alert_text_var.set(f"  ALERTS: {summary_prefix}  |  " + "  |  ".join(parts))
        self.alert_banner.pack(fill="x", pady=(4, 0), before=self.body)

    def _set_initial_layout(self) -> None:
        try:
            total_width = max(self.root.winfo_width(), 1540)
            self.body.sashpos(0, int(total_width * 0.30))
        except tk.TclError:
            pass
        self._on_tree_select()
        self._apply_wallboard_mode()

    def _redraw_summary_bar(self, name: str, row: SensorRow | None) -> None:
        canvas = self.summary_bar_canvases.get(name)
        if canvas is None:
            return
        canvas.delete("all")
        w = canvas.winfo_width()
        if w <= 1:
            return  # not yet laid out — will be redrawn by <Configure> binding
        h = int(canvas.cget("height"))
        canvas.create_rectangle(0, 0, w, h, fill="#27313c", outline="")
        if row is None or row.value is None:
            return
        fill = SensorApp._bar_fill(row.value, row.sensor_type)
        color = SensorApp._bar_color(row.severity)
        bar_w = max(int(w * fill), 0)
        if bar_w > 0:
            canvas.create_rectangle(0, 0, bar_w, h, fill=color, outline="")

    def _update_overview(self, rows: list[SensorRow]) -> None:
        self._update_history(rows)
        cpu_temp = self._best_row(
            rows,
            hardware_hints=("intel", "amd", "cpu", "ryzen"),
            sensor_hints=("package", "cpu package", "core max"),
            sensor_type="Temperature",
            exclude_hints=("distance to tjmax", "critical temperature", "package/ring critical", "throttling", "yes/no", "nvidia", "radeon", "arc", "gpu"),
        )
        cpu_load = self._best_row(
            rows,
            hardware_hints=("intel", "amd", "cpu", "ryzen"),
            sensor_hints=("cpu total", "total"),
            sensor_type="Load",
            exclude_hints=("nvidia", "radeon", "arc", "gpu"),
        )
        gpu_temp = self._best_row(
            rows,
            hardware_hints=("nvidia", "radeon", "arc", "gpu"),
            sensor_hints=("hot spot", "hotspot", "gpu core", "core"),
            sensor_type="Temperature",
        )
        gpu_load = self._best_row(
            rows,
            hardware_hints=("nvidia", "radeon", "arc", "gpu"),
            sensor_hints=("gpu core", "d3d 3d", "core"),
            sensor_type="Load",
            allow_zero=False,
        )
        cooling = self._best_row(
            rows,
            hardware_hints=("asus", "motherboard", "board", "cpu"),
            sensor_hints=("cpu fan", "aio", "pump", "cha fan", "fan"),
            sensor_type="Fan",
            allow_zero=False,
        )
        drive_temp = self._best_row(
            rows,
            hardware_hints=("ssd", "nvme", "samsung", "wd", "kingston", "crucial"),
            sensor_hints=("composite temperature", "temperature #1", "assembly", "temperature"),
            sensor_type="Temperature",
            exclude_hints=("critical temperature", "warning temperature"),
        )
        summaries = {
            "CPU": cpu_temp or cpu_load,
            "GPU": gpu_temp,
            "Cooling": cooling,
            "Drive": drive_temp,
        }
        for name, row in summaries.items():
            if row:
                self.summary_value_vars[name].set(self._value_text(row))
                source_name = self._source_for_path(row.path)
                detail = f"{row.name}  |  {SensorApp._severity_text(row.severity)}  |  {source_name}  |  {self._history_text(row.path)}"
                if name == "GPU" and gpu_load:
                    detail += f"  |  Load {self._value_text(gpu_load)}"
                self.summary_detail_vars[name].set(detail)
                self._redraw_summary_bar(name, row)
            else:
                self.summary_value_vars[name].set("--")
                self.summary_detail_vars[name].set("No sensor")
                self._redraw_summary_bar(name, None)

        favorites = self._favorite_rows(rows)
        self.favorite_rows = favorites
        self.favorites_tree.delete(*self.favorites_tree.get_children())
        self.favorite_item_paths.clear()
        for favorite in favorites:
            item_id = self.favorites_tree.insert(
                "",
                "end",
                values=(
                    f"{self._display_label(favorite.label, favorite.severity, favorite.is_pinned)}: {favorite.sensor}",
                    favorite.value,
                    SensorApp._severity_text(favorite.severity),
                ),
                tags=(favorite.severity,) if favorite.severity in {"warn", "critical", "cool"} else (),
            )
            self.favorite_item_paths[item_id] = favorite.path

        alert_rows = self._active_alert_rows_from_rows(rows)
        self.active_alert_rows = alert_rows
        self.alerts_tree.delete(*self.alerts_tree.get_children())
        self.alert_item_paths.clear()
        for alert in alert_rows:
            item_id = self.alerts_tree.insert(
                "",
                "end",
                values=(alert.label, alert.value, alert.detail),
                tags=(alert.severity,) if alert.severity in {"warn", "critical"} else (),
            )
            self.alert_item_paths[item_id] = alert.path

        mover_rows = self._top_mover_rows(rows)
        self.top_mover_rows = mover_rows
        self.movers_tree.delete(*self.movers_tree.get_children())
        self.mover_item_paths.clear()
        for mover in mover_rows:
            item_id = self.movers_tree.insert(
                "",
                "end",
                values=(mover.label, mover.detail, mover.value),
                tags=(mover.severity,) if mover.severity in {"warn", "critical", "cool"} else (),
            )
            self.mover_item_paths[item_id] = mover.path

        self.alert_log_tree.delete(*self.alert_log_tree.get_children())
        self.alert_log_item_indexes.clear()
        for index, event in enumerate(self.alert_history):
            item_id = self.alert_log_tree.insert(
                "",
                "end",
                values=(event.timestamp, event.name, event.value_text, SensorApp._severity_text(event.severity), event.status.title()),
                tags=(event.severity,) if event.severity in {"warn", "critical"} else (),
            )
            self.alert_log_item_indexes[item_id] = index

        cores = self._cpu_core_rows(rows)
        self.cpu_core_rows = cores
        self.cores_tree.delete(*self.cores_tree.get_children())
        self.cores_tree["columns"] = ("core", "temp")
        self.cores_tree.heading("core", text="Core")
        self.cores_tree.heading("temp", text="Temp")
        self.cores_tree.column("core", width=180, anchor="w")
        self.cores_tree.column("temp", width=80, anchor="e")
        for core_name, temp in cores:
            self.cores_tree.insert("", "end", values=(core_name, temp))

    def _rebuild_tree(self) -> None:
        current_selection = self.tree.selection()
        if current_selection:
            self.selected_path = self.item_paths.get(current_selection[0])
        self._capture_open_paths()
        self.tree.delete(*self.tree.get_children())
        self.item_paths.clear()
        self.item_nodes.clear()
        self.visible_sensor_count = 0
        self.visible_group_count = 0
        if not self.current_payload:
            self.count_label.configure(text="0 sensors")
            self._refresh_header_summary()
            return
        if self.hw_group_var.get():
            self._insert_hw_group_tree()
        else:
            search = self.search_var.get().strip().lower()
            category = self.category_var.get() or "all"
            self._insert_tree_node("", self.current_payload, search, category, 0, "")
        self.count_label.configure(text=self._count_label_text())
        self._refresh_header_summary()
        self._restore_selection()
        self._persist_config()

    def _insert_hw_group_tree(self) -> None:
        """Insert only hardware-level nodes into the tree (no groups or sensors)."""
        for child in self.current_payload.get("children", []):
            if child.get("kind") != "hardware":
                continue
            name = child.get("name", "Unknown")
            item = self.tree.insert("", "end", text=name, values=("", "", "", ""), tags=("hardware",))
            self.item_paths[item] = name
            self.item_nodes[item] = child
            self.visible_group_count += 1

    def _drill_into_selected_hardware(self) -> None:
        """When in HW group mode, drill into the selected hardware node."""
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        node = self.item_nodes.get(item_id, {})
        if node.get("kind") != "hardware":
            return
        self.hardware_var.set(node.get("name", "all"))
        self.hw_group_var.set(False)
        self._rebuild_tree()

    def _on_tree_double_click(self, _event=None) -> None:
        if self.hw_group_var.get():
            self._drill_into_selected_hardware()
        else:
            self._toggle_selected_favorite()

    def _capture_open_paths(self) -> None:
        paths: set[str] = set()

        def walk(item_id: str) -> None:
            path = self.item_paths.get(item_id)
            if path and self.tree.item(item_id, "open"):
                paths.add(path)
            for child in self.tree.get_children(item_id):
                walk(child)

        for top in self.tree.get_children():
            walk(top)
        self.open_paths = paths

    def _node_visible(self, node: dict, search: str, category: str, path: str = "") -> bool:
        kind = node.get("kind", "sensor")
        name = node.get("name", "Unknown")
        node_type = node.get("type", "")
        current_path = f"{path}/{name}".strip("/")
        path_blob = f"{current_path} {node_type}".lower()
        hardware_filter = self.hardware_var.get()
        severity_filter = self.severity_filter_var.get()
        source_filter = self.source_var.get()

        matches_search = not search or search in path_blob
        matches_category = True
        if kind == "sensor" and category != "all":
            matches_category = self._category_for_type(node_type) == category
        matches_severity = True
        if kind == "sensor" and severity_filter != "all":
            matches_severity = self._matches_severity_filter(self._effective_severity(current_path, node_type, node.get("value")), severity_filter)
        matches_hardware = True
        if hardware_filter != "all" and kind != "machine":
            matches_hardware = hardware_filter.lower() in path_blob
        matches_source = True
        if source_filter != "all" and kind != "machine":
            matches_source = self._source_for_path(current_path) == source_filter
        compact_visible = True
        if kind == "sensor" and self.compact_mode_var.get() and not search:
            compact_visible = not self._is_compact_noise(current_path, name, node_type)
        if kind == "machine":
            return any(self._node_visible(child, search, category, current_path) for child in node.get("children", []))
        if matches_search and matches_category and matches_severity and matches_hardware and matches_source and compact_visible:
            return True
        return any(self._node_visible(child, search, category, current_path) for child in node.get("children", []))

    def _should_open_by_default(self, node: dict, path: str, depth: int) -> bool:
        if path in self.open_paths:
            return True
        kind = node.get("kind", "sensor")
        name = node.get("name", "")
        if kind == "hardware":
            return True
        if kind == "group" and name in {"Temperatures", "Loads", "Fans", "Powers"}:
            return True
        return depth <= 1

    def _insert_tree_node(self, parent: str, node: dict, search: str, category: str, depth: int, path: str) -> bool:
        if not self._node_visible(node, search, category, path):
            return False

        kind = node.get("kind", "sensor")
        name = node.get("name", "Unknown")
        current_path = f"{path}/{name}".strip("/")

        if kind == "machine":
            for child in node.get("children", []):
                self._insert_tree_node(parent, child, search, category, 0, current_path)
            return True

        tags = [kind.lower()]
        severity = self._severity(node)
        if severity in ("warn", "critical", "cool"):
            tags.append(severity)
        if kind == "sensor" and current_path in self.favorite_paths:
            tags.append("favorite")
        if kind == "sensor" and current_path in self.muted_paths:
            tags.append("muted")

        label = name
        values = ("", "", "", "")
        if kind == "sensor":
            label = self._display_label(name, severity, current_path in self.favorite_paths)
            values = (
                self._format_value(node.get("value"), node.get("unit")),
                self._delta_text(self.history.get(current_path, []), node.get("unit", "")),
                self._format_value(node.get("min"), node.get("unit")),
                self._format_value(node.get("max"), node.get("unit")),
            )

        item = self.tree.insert(parent, "end", text=("   " * depth) + label, values=values, tags=tuple(tags))
        self.item_paths[item] = current_path
        self.item_nodes[item] = node
        if kind == "sensor":
            self.visible_sensor_count += 1
        else:
            self.visible_group_count += 1
        self.tree.item(item, open=self._should_open_by_default(node, current_path, depth))
        for child in node.get("children", []):
            self._insert_tree_node(item, child, search, category, depth + 1, current_path)
        return True

    def _set_all_open(self, open_state: bool) -> None:
        def walk(item_id: str) -> None:
            self.tree.item(item_id, open=open_state)
            for child in self.tree.get_children(item_id):
                walk(child)

        for top in self.tree.get_children():
            walk(top)
        self._capture_open_paths()

    def _reset_filters(self) -> None:
        self.search_var.set("")
        self.category_var.set("all")
        self.severity_filter_var.set("all")
        self.source_var.set("all")
        self.hardware_var.set("all")
        self.compact_mode_var.set(True)
        self.hw_group_var.set(False)
        self._refresh_scope_buttons("all")
        self._rebuild_tree()

    def _handle_escape(self, _event=None) -> str:
        if self.wallboard_mode_var.get():
            self.wallboard_mode_var.set(False)
            self._apply_wallboard_mode()
            self._persist_config()
            return "break"
        if (
            self.search_var.get().strip()
            or self.category_var.get() != "all"
            or self.severity_filter_var.get() != "all"
            or self.source_var.get() != "all"
            or self.hardware_var.get() != "all"
            or not self.compact_mode_var.get()
        ):
            self._reset_filters()
            return "break"
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
            self.selected_path = None
            self._on_tree_select()
        return "break"

    def _sort_table(self, tree: ttk.Treeview, column: str, numeric: bool = False) -> None:
        descending = getattr(tree, "_descending", False)
        last_column = getattr(tree, "_sort_column", None)
        if last_column != column:
            descending = False

        def key_for(item_id: str):
            value = tree.set(item_id, column)
            if numeric:
                token = "".join(ch for ch in value if ch.isdigit() or ch in ".-")
                try:
                    return float(token)
                except ValueError:
                    return float("-inf")
            return value.lower()

        items = list(tree.get_children(""))
        items.sort(key=key_for, reverse=descending)
        for index, item_id in enumerate(items):
            tree.move(item_id, "", index)

        tree._sort_column = column
        tree._descending = not descending

    def _sort_main_tree(self, column: str, numeric: bool = False) -> None:
        descending = getattr(self.tree, "_descending", False)
        last_column = getattr(self.tree, "_sort_column", None)
        if last_column != column:
            descending = False

        def sort_children(parent: str) -> None:
            items = list(self.tree.get_children(parent))
            items.sort(key=lambda item_id: self._main_tree_sort_key(item_id, column, numeric), reverse=descending)
            for index, item_id in enumerate(items):
                self.tree.move(item_id, parent, index)
                sort_children(item_id)

        sort_children("")
        self.tree._sort_column = column
        self.tree._descending = not descending

    def _main_tree_sort_key(self, item_id: str, column: str, numeric: bool):
        node = self.item_nodes.get(item_id, {})
        kind_rank = {"hardware": 0, "group": 1, "sensor": 2}.get(node.get("kind", "sensor"), 3)
        if column == "#0":
            return (kind_rank, self.tree.item(item_id, "text").lower())
        value = self.tree.set(item_id, column)
        if numeric:
            token = "".join(ch for ch in value if ch.isdigit() or ch in ".-")
            try:
                parsed = float(token)
            except ValueError:
                parsed = float("-inf")
            return (kind_rank, parsed)
        return (kind_rank, value.lower())

    def _restore_selection(self) -> None:
        if not self.selected_path:
            self._on_tree_select()
            return
        for item_id, path in self.item_paths.items():
            if path == self.selected_path:
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                self.tree.see(item_id)
                self._on_tree_select()
                return
        self._on_tree_select()  # path not found in rebuilt tree

    def _show_tree_context_menu(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self._on_tree_select()
        self.tree_menu.tk_popup(event.x_root, event.y_root)

    def _show_favorite_context_menu(self, event) -> None:
        item_id = self.favorites_tree.identify_row(event.y)
        if not item_id:
            return
        self.favorites_tree.selection_set(item_id)
        self.favorite_menu.tk_popup(event.x_root, event.y_root)

    def _copy_text(self, value: str) -> None:
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.status_var.set(f"Copied: {value}")

    def _copy_selected_path(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self._copy_text(self.item_paths.get(selection[0], ""))

    def _copy_selected_value(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        node = self.item_nodes.get(selection[0], {})
        if node.get("kind") == "sensor":
            self._copy_text(self._format_value(node.get("value"), node.get("unit", "")))

    def _copy_selected_favorite_path(self) -> None:
        selection = self.favorites_tree.selection()
        if not selection:
            return
        self._copy_text(self.favorite_item_paths.get(selection[0], ""))

    def _select_tree_path(self, path: str) -> bool:
        for item_id, item_path in self.item_paths.items():
            if item_path != path:
                continue
            parent_id = self.tree.parent(item_id)
            while parent_id:
                self.tree.item(parent_id, open=True)
                parent_id = self.tree.parent(parent_id)
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self.tree.see(item_id)
            self._capture_open_paths()
            self._on_tree_select()
            return True
        return False

    def _focus_path(self, path: str, *, reset_filters_if_needed: bool = True) -> bool:
        if not path:
            return False
        if self._select_tree_path(path):
            return True
        if not reset_filters_if_needed:
            return False
        parts = path.split("/")
        self.search_var.set("")
        self.category_var.set("all")
        self.severity_filter_var.set("all")
        self.source_var.set("all")
        if len(parts) >= 2:
            self.hardware_var.set(parts[1])
        else:
            self.hardware_var.set("all")
        self.compact_mode_var.set(True)
        self._rebuild_tree()
        return self._select_tree_path(path)

    def _focus_selected_hardware(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        path = self.item_paths.get(selection[0], "")
        parts = path.split("/")
        if len(parts) >= 2:
            self.hardware_var.set(parts[1])
            self._rebuild_tree()

    def _search_selected_name(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        node = self.item_nodes.get(selection[0], {})
        name = node.get("name", "")
        if name:
            self.search_var.set(name)
            self._rebuild_tree()

    def _focus_search(self, _event=None) -> str:
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")
        return "break"

    def _focus_source(self, _event=None) -> str:
        self.source_entry.focus_set()
        self.source_entry.selection_range(0, "end")
        return "break"

    def _focus_selected_favorite(self, _event=None) -> None:
        selection = self.favorites_tree.selection()
        if not selection:
            return
        path = self.favorite_item_paths.get(selection[0], "")
        if self._focus_path(path):
            self.status_var.set(f"Focused {path}")
        else:
            self.status_var.set(f"Unable to focus {path}")

    def _focus_selected_alert(self, _event=None) -> None:
        selection = self.alerts_tree.selection()
        if not selection:
            return
        path = self.alert_item_paths.get(selection[0], "")
        if self._focus_path(path):
            self.status_var.set(f"Focused alert {path}")

    def _focus_selected_mover(self, _event=None) -> None:
        selection = self.movers_tree.selection()
        if not selection:
            return
        path = self.mover_item_paths.get(selection[0], "")
        if self._focus_path(path):
            self.status_var.set(f"Focused changing sensor {path}")

    def _focus_selected_alert_event(self, _event=None) -> None:
        selection = self.alert_log_tree.selection()
        if not selection:
            return
        index = self.alert_log_item_indexes.get(selection[0])
        if index is None or index >= len(self.alert_history):
            return
        path = self.alert_history[index].path
        if self._focus_path(path):
            self.status_var.set(f"Focused alert log sensor {path}")

    def _ack_selected_alert_event(self) -> None:
        selection = self.alert_log_tree.selection()
        if not selection:
            return
        changed = 0
        for item_id in selection:
            index = self.alert_log_item_indexes.get(item_id)
            if index is None or index >= len(self.alert_history):
                continue
            if self.alert_history[index].status != "acknowledged":
                self.alert_history[index].status = "acknowledged"
                changed += 1
        if changed:
            self.status_var.set(f"Acknowledged {changed} alert event(s)")
            self._persist_config()
            self._update_overview(self.current_rows)

    def _clear_alert_history(self) -> None:
        self.alert_history = []
        self.status_var.set("Cleared alert history")
        self._persist_config()
        self._update_overview(self.current_rows)

    def _remove_selected_favorite_pin(self, _event=None) -> None:
        selection = self.favorites_tree.selection()
        if not selection:
            return
        path = self.favorite_item_paths.get(selection[0], "")
        if path not in self.favorite_paths:
            self.status_var.set("Selected row is a smart favorite, not a saved pin")
            return
        self.favorite_paths.remove(path)
        self._persist_config()
        self._update_overview(self.current_rows)
        self._rebuild_tree()

    def _show_problem_sensors(self) -> None:
        if not self.problem_paths:
            return
        self.search_var.set("")
        self.category_var.set("all")
        self.severity_filter_var.set("active")
        self.source_var.set("all")
        self.hardware_var.set("all")
        self.compact_mode_var.set(True)
        self._rebuild_tree()
        for path in self.problem_paths:
            if self._focus_path(path, reset_filters_if_needed=False):
                self.status_var.set(f"Focused problem sensor {path}")
                return

    def _export_csv(self) -> None:
        import csv
        import datetime

        rows = self.current_rows
        if not rows:
            self.status_var.set("No data to export")
            return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.expanduser(f"~/hwremote-snapshot-{timestamp}.csv")
        sensor_rows = [r for r in rows if r.kind == "sensor" and r.value is not None]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["path", "name", "type", "value", "unit", "min", "max", "severity"])
                for r in sensor_rows:
                    writer.writerow([r.path, r.name, r.sensor_type, r.value, r.unit, r.min_value, r.max_value, r.severity])
            self.status_var.set(f"Exported {len(sensor_rows)} sensors to {path}")
        except OSError as exc:
            self.status_var.set(f"Export failed: {exc}")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            self.detail_name_var.set("No sensor selected")
            self.detail_meta_var.set("Pick a sensor from the tree, alert list, or movers panel")
            self.detail_status_var.set("No active selection")
            self.detail_value_var.set("--")
            self.detail_range_var.set("Min --   Max --")
            self.detail_stats_var.set("Session avg --  |  spread --  |  samples 0")
            self.detail_threshold_var.set("Thresholds: select a sensor to inspect alert behavior")
            self.detail_history_var.set("Trend unavailable until a sensor is selected")
            self._draw_empty_detail_chart("Select a sensor to see recent history")
            self.detail_pin_button.configure(text="Pin")
            self.detail_mute_button.configure(text="Mute Alert")
            return

        item_id = selection[0]
        node = self.item_nodes.get(item_id, {})
        kind = node.get("kind", "sensor")
        name = node.get("name", "Unknown")
        node_type = node.get("type", kind.title())
        unit = node.get("unit", "")
        path = self.item_paths.get(item_id, "")
        self.selected_path = path

        self.detail_name_var.set(name)
        self.detail_meta_var.set(f"{node_type}  |  {path}")
        if kind == "sensor":
            value_text = self._format_value(node.get("value"), unit) or "--"
            min_text = self._format_value(node.get("min"), unit) or "--"
            max_text = self._format_value(node.get("max"), unit) or "--"
            severity = self._effective_severity(path, node_type, node.get("value"))
            pin_state = "Pinned" if path in self.favorite_paths else "Not pinned"
            mute_state = "Muted" if path in self.muted_paths else "Live alerts"
            self.detail_value_var.set(value_text)
            self.detail_status_var.set(
                f"{SensorApp._severity_text(severity)}  |  {SensorApp._delta_text(self.history.get(path, []), unit)}  |  {pin_state}  |  {mute_state}"
            )
            self.detail_range_var.set(f"Min {min_text}   Max {max_text}")
            self.detail_stats_var.set(self._detail_stats_text(path, unit, node.get("value"), node.get("min"), node.get("max")))
            self.detail_threshold_var.set(self._threshold_text(path, node_type, node.get("value"), unit))
            self.detail_history_var.set(f"Trend {self._history_text(path)}")
            self._draw_detail_chart(path, node_type, unit)
            self.detail_pin_button.configure(text="Unpin" if path in self.favorite_paths else "Pin")
            self.detail_mute_button.configure(text="Unmute Alert" if path in self.muted_paths else "Mute Alert")
        else:
            child_count = len(node.get("children", []))
            self.detail_status_var.set("Group selection")
            self.detail_value_var.set(f"{child_count} items")
            self.detail_range_var.set("Min --   Max --")
            self.detail_stats_var.set("Select a sensor under this group for live stats and history")
            self.detail_threshold_var.set("Thresholds apply to sensor rows, not hardware/group nodes")
            self.detail_history_var.set("Trend unavailable for grouped nodes")
            self._draw_empty_detail_chart("Select a sensor to see recent history")
            self.detail_pin_button.configure(text="Pin")
            self.detail_mute_button.configure(text="Mute Alert")

    def _on_favorite_activate(self, _event=None) -> None:
        selection = self.favorites_tree.selection()
        if not selection:
            return
        path = self.favorite_item_paths.get(selection[0])
        if not path:
            return
        if path in self.favorite_paths:
            self.favorite_paths.remove(path)
        else:
            self.favorite_paths.add(path)
        self._persist_config()
        self._update_overview(self.current_rows)
        self._rebuild_tree()

    def _toggle_selected_favorite(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        path = self.item_paths.get(selection[0])
        node = self.item_nodes.get(selection[0], {})
        if not path or node.get("kind") != "sensor":
            return
        if path in self.favorite_paths:
            self.favorite_paths.remove(path)
        else:
            self.favorite_paths.add(path)
        self._persist_config()
        self._update_overview(self.current_rows)
        self._rebuild_tree()
        self._on_tree_select()

    def _update_hardware_choices(self, payload: dict) -> None:
        hardware_names = ["all"]
        for child in payload.get("children", []):
            if child.get("kind") == "hardware":
                hardware_names.append(child.get("name", "Unknown"))
        self.hardware_box.configure(values=tuple(hardware_names))
        if self.hardware_var.get() not in hardware_names:
            self.hardware_var.set("all")

    def _update_source_choices(self, payload: dict) -> None:
        source_names = ["all"]
        payload_sources = payload.get("sources", [])
        if isinstance(payload_sources, list):
            for source in payload_sources:
                if isinstance(source, str) and source not in source_names:
                    source_names.append(source)
        for child in payload.get("children", []):
            name = child.get("name", "")
            if isinstance(name, str) and name and name not in source_names and name in SOURCE_FILTER_VALUES:
                source_names.append(name)
        self.source_box.configure(values=tuple(source_names))
        if self.source_var.get() not in source_names:
            self.source_var.set("all")

    def _update_history(self, rows: list[SensorRow]) -> None:
        current_paths: set[str] = set()
        for row in rows:
            if row.kind != "sensor" or row.value is None:
                continue
            current_paths.add(row.path)
            samples = self.history.setdefault(row.path, [])
            samples.append(float(row.value))
            if len(samples) > 24:
                del samples[:-24]
        stale_paths = [path for path in self.history if path not in current_paths]
        for path in stale_paths:
            del self.history[path]

    def _history_text(self, path: str) -> str:
        samples = self.history.get(path, [])
        if not samples:
            return "no trend"
        return self._sparkline(samples)

    @staticmethod
    def _sparkline(samples: list[float]) -> str:
        chars = "▁▂▃▄▅▆▇█"
        if len(samples) == 1:
            return chars[-1]
        low = min(samples)
        high = max(samples)
        if high <= low:
            return chars[len(chars) // 2] * min(len(samples), 12)
        recent = samples[-12:]
        pieces = []
        scale = (len(chars) - 1) / (high - low)
        for value in recent:
            index = int((value - low) * scale)
            index = max(0, min(index, len(chars) - 1))
            pieces.append(chars[index])
        return "".join(pieces)

    def _load_saved_state(self) -> None:
        data = self._load_config_data()
        favorites = data.get("favorite_paths", [])
        self.favorite_paths = {path for path in favorites if isinstance(path, str)}
        muted = data.get("muted_paths", [])
        self.muted_paths = {path for path in muted if isinstance(path, str)}
        overrides = data.get("threshold_overrides", {})
        if isinstance(overrides, dict):
            cleaned_overrides: dict[str, dict[str, float]] = {}
            for path, values in overrides.items():
                if not isinstance(path, str) or not isinstance(values, dict):
                    continue
                warn_value = values.get("warn")
                critical_value = values.get("critical")
                numeric_values = {}
                if isinstance(warn_value, (int, float)):
                    numeric_values["warn"] = float(warn_value)
                if isinstance(critical_value, (int, float)):
                    numeric_values["critical"] = float(critical_value)
                if numeric_values:
                    cleaned_overrides[path] = numeric_values
            self.threshold_overrides = cleaned_overrides
        alert_history = data.get("alert_history", [])
        if isinstance(alert_history, list):
            cleaned_history: list[AlertEvent] = []
            for item in alert_history:
                if not isinstance(item, dict):
                    continue
                timestamp = item.get("timestamp")
                path = item.get("path")
                name = item.get("name")
                severity = item.get("severity")
                value_text = item.get("value_text")
                status = item.get("status", "new")
                if all(isinstance(v, str) and v for v in (timestamp, path, name, severity, value_text)):
                    cleaned_history.append(
                        AlertEvent(
                            timestamp=timestamp,
                            path=path,
                            name=name,
                            severity=severity,
                            value_text=value_text,
                            status=status if isinstance(status, str) else "new",
                        )
                    )
            self.alert_history = cleaned_history[:200]
        presets = data.get("source_presets", [])
        if isinstance(presets, list):
            cleaned = [value for value in presets if isinstance(value, str) and value.strip()]
            if cleaned:
                self.source_presets = cleaned
        category = data.get("category_filter", "all")
        if isinstance(category, str):
            self.category_var.set(category)
        severity = data.get("severity_filter", "all")
        if isinstance(severity, str):
            self.severity_filter_var.set(severity)
        source = data.get("source_filter", "all")
        if isinstance(source, str):
            self.source_var.set(source)
        hardware = data.get("hardware_filter", "all")
        if isinstance(hardware, str):
            self.hardware_var.set(hardware)
        compact_mode = data.get("compact_mode", True)
        if isinstance(compact_mode, bool):
            self.compact_mode_var.set(compact_mode)
        selected_preset = data.get("selected_preset", self.url_var.get())
        if isinstance(selected_preset, str) and selected_preset.strip():
            self.source_preset_var.set(selected_preset)
        wallboard_mode = data.get("wallboard_mode", False)
        if isinstance(wallboard_mode, bool):
            self.wallboard_mode_var.set(wallboard_mode)
        ssh_script = data.get("ssh_script_path", DEFAULT_SSH_SCRIPT)
        if isinstance(ssh_script, str) and ssh_script.strip():
            self.ssh_script_path_var.set(ssh_script)
        ssh_extra = data.get("ssh_extra_args", "")
        if isinstance(ssh_extra, str):
            self.ssh_extra_args_var.set(ssh_extra)

    @staticmethod
    def _load_config_data() -> dict:
        if not os.path.exists(CONFIG_PATH):
            return {}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _flatten_rows(self, node: dict, depth: int = 0, path: str = "") -> list[SensorRow]:
        rows: list[SensorRow] = []
        kind = node.get("kind", "sensor")
        name = node.get("name", "Unknown")
        current_path = f"{path}/{name}".strip("/")
        if kind != "machine":
            sensor_type = node.get("type", "")
            rows.append(
                SensorRow(
                    kind=kind,
                    name=name,
                    path=current_path,
                    indent=depth,
                    sensor_type=sensor_type,
                    unit=node.get("unit", ""),
                    value=node.get("value"),
                    min_value=node.get("min"),
                    max_value=node.get("max"),
                    category=self._category_for_type(sensor_type),
                    severity=self._severity(node),
                )
            )
        for child in node.get("children", []):
            rows.extend(self._flatten_rows(child, depth + (0 if kind == "machine" else 1), current_path))
        return rows

    def _best_row(
        self,
        rows: list[SensorRow],
        hardware_hints: tuple[str, ...],
        sensor_hints: tuple[str, ...],
        sensor_type: str,
        *,
        exclude_hints: tuple[str, ...] = (),
        allow_zero: bool = True,
    ) -> SensorRow | None:
        best = None
        best_score = -10**9
        for row in rows:
            if row.kind != "sensor" or row.value is None:
                continue
            if not allow_zero and isinstance(row.value, (int, float)) and row.value == 0:
                continue
            if row.sensor_type != sensor_type:
                continue
            if not self._expected_unit_matches(sensor_type, row.unit):
                continue
            haystack = f"{row.path} {row.name}".lower()
            hardware_score = sum((len(hardware_hints) - index) * 8 for index, hint in enumerate(hardware_hints) if hint in haystack)
            sensor_score = sum((len(sensor_hints) - index) * 18 for index, hint in enumerate(sensor_hints) if hint in haystack)
            if hardware_hints and hardware_score == 0:
                continue
            if sensor_hints and sensor_score == 0:
                continue
            score = 100
            score += hardware_score
            score += sensor_score
            score += self._source_priority_for_path(row.path)
            score -= sum(35 for hint in exclude_hints if hint in haystack)
            if row.severity == "critical" and sensor_type == "Temperature":
                score -= 10
            if score > best_score:
                best = row
                best_score = score
        return best

    @staticmethod
    def _expected_unit_matches(sensor_type: str, unit: str) -> bool:
        expected_by_type = {
            "Temperature": ("C", "F"),
            "Load": ("%",),
            "Fan": ("RPM",),
            "Power": ("W",),
        }
        expected_units = expected_by_type.get(sensor_type)
        if not expected_units:
            return True
        normalized = (unit or "").strip()
        return normalized in expected_units

    def _favorite_candidates(self, rows: list[SensorRow]) -> list[tuple[str, SensorRow | None]]:
        return [
            (
                "CPU Package",
                self._best_row(
                    rows,
                    ("intel", "amd", "cpu", "ryzen"),
                    ("package", "cpu package", "core max"),
                    "Temperature",
                    exclude_hints=("distance to tjmax", "nvidia", "radeon", "arc", "gpu"),
                ),
            ),
            (
                "CPU Load",
                self._best_row(
                    rows,
                    ("intel", "amd", "cpu", "ryzen"),
                    ("total", "cpu total"),
                    "Load",
                    exclude_hints=("nvidia", "radeon", "arc", "gpu"),
                ),
            ),
            ("GPU Hotspot", self._best_row(rows, ("nvidia", "radeon", "arc", "gpu"), ("hot spot", "hotspot", "gpu core", "core"), "Temperature")),
            (
                "GPU Load",
                self._best_row(
                    rows,
                    ("nvidia", "radeon", "arc", "gpu"),
                    ("d3d 3d", "gpu core", "gpu memory", "core"),
                    "Load",
                    allow_zero=False,
                ),
            ),
            (
                "GPU Power",
                self._best_row(
                    rows,
                    ("nvidia", "radeon", "arc", "gpu"),
                    ("gpu package", "board power", "gpu power", "package"),
                    "Power",
                    allow_zero=False,
                ),
            ),
            (
                "CPU Fan",
                self._best_row(
                    rows,
                    ("asus", "motherboard", "board", "cpu"),
                    ("cpu fan", "aio", "pump", "cha fan", "fan"),
                    "Fan",
                    allow_zero=False,
                ),
            ),
            (
                "Drive Temp",
                self._best_row(
                    rows,
                    ("ssd", "nvme", "samsung", "wd", "kingston", "crucial"),
                    ("composite temperature", "temperature #1", "assembly", "temperature"),
                    "Temperature",
                    exclude_hints=("critical temperature", "warning temperature"),
                ),
            ),
        ]

    def _favorite_rows(self, rows: list[SensorRow]) -> list[FavoriteRow]:
        auto_candidates = self._favorite_candidates(rows)
        row_by_path = {row.path: row for row in rows if row.kind == "sensor"}
        out: list[FavoriteRow] = []
        seen: set[str] = set()
        for path in sorted(self.favorite_paths):
            row = row_by_path.get(path)
            if not row or row.path in seen:
                continue
            seen.add(row.path)
            out.append(
                FavoriteRow(
                    label=row.name,
                    sensor=row.path.split("/")[-2],
                    value=self._value_text(row),
                    path=row.path,
                    severity=row.severity,
                    is_pinned=True,
                )
            )
        for label, row in auto_candidates:
            if not row or row.path in seen:
                continue
            seen.add(row.path)
            out.append(
                FavoriteRow(
                    label=label,
                    sensor=row.name,
                    value=self._value_text(row),
                    path=row.path,
                    severity=row.severity,
                )
            )
        return out

    def _active_alert_rows_from_rows(self, rows: list[SensorRow]) -> list[InsightRow]:
        muted_paths = getattr(self, "muted_paths", set())
        alert_rows = [
            row
            for row in rows
            if row.kind == "sensor" and row.value is not None and row.path not in muted_paths and row.severity in {"warn", "critical"}
        ]
        alert_rows.sort(
            key=lambda row: (
                self._SEVERITY_ORDER.get(row.severity, 0),
                row.value if isinstance(row.value, (int, float)) else float("-inf"),
            ),
            reverse=True,
        )
        return [
            InsightRow(
                label=self._display_label(row.name, row.severity),
                value=self._value_text(row),
                detail=self._severity_text(row.severity),
                path=row.path,
                severity=row.severity,
            )
            for row in alert_rows[:10]
        ]

    def _record_alert_events(self, alerts: list[tuple[str, str, str, str]]) -> None:
        if not alerts:
            return
        now = datetime.now().strftime("%H:%M:%S")
        existing_open = {
            (event.path, event.severity): event
            for event in self.alert_history
            if event.status != "acknowledged"
        }
        for path, name, severity, value_text in alerts:
            previous = existing_open.get((path, severity))
            status = "new" if previous is None else "repeat"
            if previous and previous.value_text == value_text:
                continue
            self.alert_history.insert(
                0,
                AlertEvent(
                    timestamp=now,
                    path=path,
                    name=name,
                    severity=severity,
                    value_text=value_text,
                    status=status,
                ),
            )
        self.alert_history = self.alert_history[:200]
        self._persist_config()

    def _top_mover_rows(self, rows: list[SensorRow]) -> list[InsightRow]:
        favorite_paths = getattr(self, "favorite_paths", set())
        scored: list[tuple[float, InsightRow]] = []
        for row in rows:
            if row.kind != "sensor" or row.value is None:
                continue
            samples = self.history.get(row.path, [])
            if len(samples) < 2:
                continue
            delta = samples[-1] - samples[-2]
            magnitude = abs(delta)
            if magnitude < 0.1:
                continue
            scored.append(
                (
                    magnitude,
                    InsightRow(
                        label=self._display_label(row.name, row.severity, row.path in favorite_paths),
                        value=self._value_text(row),
                        detail=f"{'+' if delta > 0 else '-'}{self._format_value(magnitude, row.unit)}",
                        path=row.path,
                        severity=row.severity,
                    ),
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:10]]

    def _cpu_core_rows(self, rows: list[SensorRow]) -> list[tuple[str, str]]:
        core_rows = []
        for row in rows:
            if row.kind != "sensor" or row.sensor_type != "Temperature" or row.value is None:
                continue
            haystack = f"{row.path} {row.name}".lower()
            if "core" not in haystack:
                continue
            if "distance to tjmax" in haystack:
                continue
            if not any(token in haystack for token in ("intel", "amd", "cpu", "ryzen", "core")):
                continue
            core_rows.append((row.name, self._value_text(row), row.value))
        core_rows.sort(key=lambda item: item[2], reverse=True)
        return [(name, value) for name, value, _ in core_rows[:12]]

    def _detail_stats_text(self, path: str, unit: str, value, min_value, max_value) -> str:
        samples = self.history.get(path, [])
        if not samples:
            return "Session avg --  |  spread --  |  samples 0"
        avg = sum(samples) / len(samples)
        spread = max(samples) - min(samples)
        current_text = self._format_value(value, unit) or "--"
        min_text = self._format_value(min_value, unit) or self._format_value(min(samples), unit) or "--"
        max_text = self._format_value(max_value, unit) or self._format_value(max(samples), unit) or "--"
        avg_text = self._format_value(avg, unit) or "--"
        spread_text = self._format_value(spread, unit) or "--"
        return (
            f"Current {current_text}  |  Session avg {avg_text}  |  spread {spread_text}  |  "
            f"Range {min_text} -> {max_text}  |  samples {len(samples)}"
        )

    def _draw_empty_detail_chart(self, message: str) -> None:
        if self.detail_chart_canvas is None:
            return
        canvas = self.detail_chart_canvas
        canvas.delete("all")
        width = int(canvas.cget("width"))
        height = int(canvas.cget("height"))
        canvas.create_text(
            width / 2,
            height / 2,
            text=message,
            fill="#8b9bae",
            font=("DejaVu Sans", 10),
        )

    def _draw_detail_chart(self, path: str, sensor_type: str, unit: str) -> None:
        if self.detail_chart_canvas is None:
            return
        samples = self.history.get(path, [])
        canvas = self.detail_chart_canvas
        canvas.delete("all")
        width = int(canvas.cget("width"))
        height = int(canvas.cget("height"))
        pad = 10
        canvas.create_rectangle(0, 0, width, height, outline="", fill="#141b22")
        if len(samples) < 2:
            self._draw_empty_detail_chart("Need at least two samples for a chart")
            return

        thresholds = self._thresholds_for_path(path, sensor_type) or {}
        low = min(samples)
        high = max(samples)
        if thresholds:
            low = min(low, thresholds.get("warn", low), thresholds.get("critical", low))
            high = max(high, thresholds.get("warn", high), thresholds.get("critical", high))
        if high <= low:
            high = low + 1

        for value, color in (
            (thresholds.get("warn"), "#ffb020"),
            (thresholds.get("critical"), "#ff5d5d"),
        ):
            if value is None:
                continue
            y = self._scale_chart_y(value, low, high, height, pad)
            canvas.create_line(pad, y, width - pad, y, fill=color, dash=(4, 3))
            canvas.create_text(width - pad - 2, y - 2, text=self._format_value(value, unit), fill=color, anchor="se", font=("DejaVu Sans", 8))

        points = self._history_plot_points(samples, width, height, pad)
        if points:
            flattened = [coord for point in points for coord in point]
            canvas.create_line(*flattened, fill="#7fd4ff", width=2, smooth=True)
            last_x, last_y = points[-1]
            canvas.create_oval(last_x - 3, last_y - 3, last_x + 3, last_y + 3, fill="#7fd4ff", outline="")

        canvas.create_text(pad, pad - 2, text=self._format_value(high, unit), fill="#8b9bae", anchor="sw", font=("DejaVu Sans", 8))
        canvas.create_text(pad, height - pad + 2, text=self._format_value(low, unit), fill="#8b9bae", anchor="nw", font=("DejaVu Sans", 8))
        canvas.create_text(width - pad, height - pad + 2, text=f"{len(samples)} samples", fill="#8b9bae", anchor="ne", font=("DejaVu Sans", 8))

    @staticmethod
    def _scale_chart_y(value: float, low: float, high: float, height: int, pad: int) -> float:
        usable = max(height - (pad * 2), 1)
        return pad + ((high - value) / (high - low)) * usable

    @staticmethod
    def _history_plot_points(samples: list[float], width: int, height: int, pad: int) -> list[tuple[float, float]]:
        if len(samples) < 2:
            return []
        recent = samples[-24:]
        low = min(recent)
        high = max(recent)
        if high <= low:
            high = low + 1
        usable_width = max(width - (pad * 2), 1)
        step = usable_width / max(len(recent) - 1, 1)
        points: list[tuple[float, float]] = []
        for index, value in enumerate(recent):
            x = pad + (index * step)
            y = SensorApp._scale_chart_y(value, low, high, height, pad)
            points.append((x, y))
        return points

    @staticmethod
    def _default_thresholds(sensor_type: str) -> dict[str, float] | None:
        if sensor_type == "Temperature":
            return {"warn": 75.0, "critical": 90.0}
        if sensor_type in {"Load", "Control"}:
            return {"warn": 80.0, "critical": 95.0}
        if sensor_type == "Power":
            return {"warn": 220.0, "critical": 300.0}
        return None

    @staticmethod
    def _bar_fill(value: float | None, sensor_type: str) -> float:
        """Return 0.0–1.0 fill fraction for a summary card progress bar."""
        if value is None:
            return 0.0
        if sensor_type == "Fan":
            return min(value / 3000.0, 1.0)
        thresholds = SensorApp._default_thresholds(sensor_type)
        if thresholds is None:
            return 0.0
        return min(value / thresholds["critical"], 1.0)

    @staticmethod
    def _bar_color(severity: str) -> str:
        """Return progress bar fill color for a given severity string."""
        return {"warn": "#ffb020", "critical": "#ff5d5d"}.get(severity, "#37c871")

    @staticmethod
    def _scope_button_style_name(scope: str, active_scope: str) -> str:
        """Return the ttk style name for a scope button given the currently active scope."""
        return "Scope.Active.TButton" if scope == active_scope else "Scope.TButton"

    @staticmethod
    def _hardware_names_from_payload(payload: dict) -> list[str]:
        """Return names of direct hardware-kind children of a machine payload node."""
        return [child["name"] for child in payload.get("children", []) if child.get("kind") == "hardware"]

    def _threshold_text(self, path: str, sensor_type: str, value: float | None, unit: str) -> str:
        thresholds = self._thresholds_for_path(path, sensor_type)
        if thresholds:
            origin = "custom" if path in self.threshold_overrides else "default"
            return self._threshold_text_for_levels(
                value,
                unit,
                warn_at=thresholds["warn"],
                critical_at=thresholds["critical"],
                label=origin,
            )
        return "Thresholds: no built-in alert threshold for this sensor type"

    @staticmethod
    def _threshold_text_for_levels(value: float | None, unit: str, *, warn_at: float, critical_at: float, label: str = "default") -> str:
        warn_text = SensorApp._format_value(warn_at, unit)
        critical_text = SensorApp._format_value(critical_at, unit)
        if value is None:
            return f"Thresholds ({label}): warning at {warn_text}, critical at {critical_text}"
        if value >= critical_at:
            distance = SensorApp._format_value(value - critical_at, unit)
            return f"Thresholds ({label}): critical by +{distance}  |  warning at {warn_text}, critical at {critical_text}"
        if value >= warn_at:
            distance = SensorApp._format_value(critical_at - value, unit)
            return f"Thresholds ({label}): warning active  |  {distance} to critical"
        distance = SensorApp._format_value(warn_at - value, unit)
        return f"Thresholds ({label}): {distance} below warning  |  warning at {warn_text}, critical at {critical_text}"

    @staticmethod
    def _category_for_type(sensor_type: str) -> str:
        mapping = {
            "Temperature": "temperature",
            "Load": "load",
            "Fan": "cooling",
            "Control": "cooling",
            "Power": "power",
            "Voltage": "power",
            "Current": "power",
            "Clock": "clock",
            "Frequency": "clock",
            "Data": "storage",
            "SmallData": "storage",
            "Throughput": "storage",
        }
        return mapping.get(sensor_type, "other")

    @staticmethod
    def _severity_for(sensor_type: str, value: float | None) -> str:
        thresholds = SensorApp._default_thresholds(sensor_type)
        if value is None or not thresholds:
            return "normal"
        if value >= thresholds["critical"]:
            return "critical"
        if value >= thresholds["warn"]:
            return "warn"
        if sensor_type in {"Temperature", "Load", "Control", "Power"}:
            return "cool"
        return "normal"

    @staticmethod
    def _severity(node: dict | "SensorRow") -> str:
        if isinstance(node, SensorRow):
            return SensorApp._severity_for(node.sensor_type, node.value)
        return SensorApp._severity_for(node.get("type", ""), node.get("value"))

    @staticmethod
    def _severity_text(severity: str) -> str:
        return {
            "critical": "Critical",
            "warn": "Warning",
            "cool": "Cool",
            "normal": "Normal",
        }.get(severity, severity.title())

    @staticmethod
    def _matches_severity_filter(severity: str, filter_value: str) -> bool:
        if filter_value == "all":
            return True
        if filter_value == "active":
            return severity in {"warn", "critical"}
        return severity == filter_value

    @staticmethod
    def _alert_counts(rows: list["SensorRow"]) -> tuple[int, int]:
        critical_count = 0
        warn_count = 0
        for row in rows:
            if row.kind != "sensor":
                continue
            if row.severity == "critical":
                critical_count += 1
            elif row.severity == "warn":
                warn_count += 1
        return critical_count, warn_count

    @staticmethod
    def _label_prefix(severity: str, is_favorite: bool = False) -> str:
        parts: list[str] = []
        if severity == "critical":
            parts.append("!!")
        elif severity == "warn":
            parts.append("!")
        if is_favorite:
            parts.append("*")
        return " ".join(parts)

    @staticmethod
    def _display_label(label: str, severity: str, is_favorite: bool = False) -> str:
        prefix = SensorApp._label_prefix(severity, is_favorite)
        return f"{prefix} {label}".strip()

    @staticmethod
    def _delta_text(samples: list[float], unit: str) -> str:
        if len(samples) < 2:
            return "steady"
        delta = samples[-1] - samples[-2]
        if abs(delta) < 0.1:
            return "steady"
        direction = "rising" if delta > 0 else "falling"
        return f"{direction} {'+' if delta > 0 else '-'}{SensorApp._format_value(abs(delta), unit)}"

    @staticmethod
    def _compute_alerts_static(
        rows: list["SensorRow"],
        existing_states: dict[str, str],
    ) -> tuple[list[tuple[str, str, str, str]], dict[str, str]]:
        """Returns (new_alerts, updated_states).
        new_alerts: list of (path, name, severity, value_text) for sensors that worsened.
        updated_states: new alert_states dict (only contains warn/critical sensors).
        """
        new_alerts: list[tuple[str, str, str, str]] = []
        new_states: dict[str, str] = {}
        order = SensorApp._SEVERITY_ORDER

        for row in rows:
            if row.kind != "sensor" or row.value is None:
                continue
            severity = SensorApp._severity_for(row.sensor_type, row.value)
            if severity in ("warn", "critical"):
                new_states[row.path] = severity
                prev = existing_states.get(row.path, "normal")
                if order[severity] > order[prev]:
                    value_text = SensorApp._format_value(row.value, row.unit)
                    new_alerts.append((row.path, row.name, severity, value_text))

        return new_alerts, new_states

    @staticmethod
    def _value_text(row: SensorRow) -> str:
        return SensorApp._format_value(row.value, row.unit)

    @staticmethod
    def _format_value(value, unit: str) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            value = int(value) if value.is_integer() else round(value, 1)
        return f"{value} {unit}".strip()

    @staticmethod
    def _default_hint_text() -> str:
        return "F5/Ctrl+R refresh  |  Ctrl+F search  |  All/Alerts/HWiNFO/Native quick scopes  |  P pin sensor  |  Esc clear filters/selection"

    @staticmethod
    def _source_for_path(path: str) -> str:
        if "/HWiNFO/" in f"/{path}/":
            return "HWiNFO"
        return "LibreHardwareMonitorLib"

    @staticmethod
    def _source_priority_for_path(path: str) -> int:
        source = SensorApp._source_for_path(path)
        if source == "LibreHardwareMonitorLib":
            return 18
        if source == "HWiNFO":
            return 8
        return 0

    @staticmethod
    def _is_compact_noise(path: str, name: str, sensor_type: str) -> bool:
        if SensorApp._source_for_path(path) != "HWiNFO":
            return False
        haystack = f"{path} {name} {sensor_type}".lower()
        if sensor_type == "Clock" and "effective clock" in haystack:
            return True
        return any(hint in haystack for hint in COMPACT_NOISE_HINTS)

    def _count_label_text(self) -> str:
        parts = [f"{self.visible_sensor_count} sensors", f"{self.visible_group_count} groups"]
        critical_count, warn_count = SensorApp._alert_counts(self.current_rows)
        if critical_count or warn_count:
            alert_bits = []
            if critical_count:
                alert_bits.append(f"{critical_count} critical")
            if warn_count:
                alert_bits.append(f"{warn_count} warn")
            parts.append(" / ".join(alert_bits))
        active_filters = []
        search = self.search_var.get().strip()
        if search:
            active_filters.append(f"search={search}")
        if self.category_var.get() != "all":
            active_filters.append(f"category={self.category_var.get()}")
        if self.severity_filter_var.get() != "all":
            active_filters.append(f"severity={self.severity_filter_var.get()}")
        if self.source_var.get() != "all":
            active_filters.append(f"source={self.source_var.get()}")
        if self.hardware_var.get() != "all":
            active_filters.append(f"hardware={self.hardware_var.get()}")
        if self.compact_mode_var.get():
            active_filters.append("compact")
        if active_filters:
            parts.append("filtered: " + ", ".join(active_filters))
        return "  |  ".join(parts)

    def _persist_config(self) -> None:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "url": self.url_var.get(),
                    "interval_ms": self.interval_var.get(),
                    "category_filter": self.category_var.get(),
                    "severity_filter": self.severity_filter_var.get(),
                    "source_filter": self.source_var.get(),
                    "hardware_filter": self.hardware_var.get(),
                    "compact_mode": self.compact_mode_var.get(),
                    "selected_preset": self.source_preset_var.get(),
                    "source_presets": self.source_presets,
                    "wallboard_mode": self.wallboard_mode_var.get(),
                    "favorite_paths": sorted(self.favorite_paths),
                    "muted_paths": sorted(self.muted_paths),
                    "threshold_overrides": self.threshold_overrides,
                    "alert_history": [event.__dict__ for event in self.alert_history[:200]],
                },
                handle,
                indent=2,
            )


def load_config() -> tuple[str, int]:
    data = SensorApp._load_config_data()
    return data.get("url", DEFAULT_URL), int(data.get("interval_ms", 2000))


def main() -> None:
    saved_url, saved_interval = load_config()

    parser = argparse.ArgumentParser(description="Desktop remote hardware monitor for LibreHardwareMonitor data.")
    parser.add_argument("--url", default=saved_url, help="JSON endpoint URL")
    parser.add_argument("--interval-ms", type=int, default=saved_interval, help="Refresh interval in milliseconds")
    args = parser.parse_args()

    root = tk.Tk()
    SensorApp(root, args.url, args.interval_ms)
    root.mainloop()


if __name__ == "__main__":
    main()

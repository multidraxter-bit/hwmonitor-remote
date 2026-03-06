#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from dataclasses import dataclass
from tkinter import ttk


DEFAULT_URL = "ssh://loofi@192.168.1.3"
CONFIG_PATH = os.path.expanduser("~/.config/hwremote-monitor.json")
CATEGORY_VALUES = ("all", "temperature", "load", "cooling", "power", "clock", "storage")


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


class SensorApp:
    _SEVERITY_ORDER: dict[str, int] = {"normal": 0, "cool": 0, "warn": 1, "critical": 2}

    def __init__(self, root: tk.Tk, url: str, interval_ms: int) -> None:
        self.root = root
        self.url_var = tk.StringVar(value=url)
        self.interval_var = tk.IntVar(value=interval_ms)
        self.status_var = tk.StringVar(value="Waiting for first refresh")
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.category_var = tk.StringVar(value="all")
        self.hardware_var = tk.StringVar(value="all")
        self.refresh_job = None
        self.current_payload: dict = {}
        self.summary_value_vars: dict[str, tk.StringVar] = {}
        self.summary_detail_vars: dict[str, tk.StringVar] = {}
        self.favorite_rows: list[tuple[str, str, str]] = []
        self.cpu_core_rows: list[tuple[str, str]] = []
        self.favorite_paths: set[str] = set()
        self.favorite_item_paths: dict[str, str] = {}
        self.history: dict[str, list[float]] = {}
        self.alert_states: dict[str, str] = {}
        self.item_paths: dict[str, str] = {}
        self.item_nodes: dict[str, dict] = {}
        self.open_paths: set[str] = set()
        self.selected_path: str | None = None
        self.visible_sensor_count = 0
        self.visible_group_count = 0
        self.detail_name_var = tk.StringVar(value="No sensor selected")
        self.detail_meta_var = tk.StringVar(value="")
        self.detail_value_var = tk.StringVar(value="")
        self.detail_range_var = tk.StringVar(value="")
        self.detail_history_var = tk.StringVar(value="")
        self.hint_var = tk.StringVar(value="F5 refresh  |  Ctrl+F search  |  Double-click sensor to pin")
        self._banner_dismissed = False
        self._load_saved_state()

        self._build_ui()
        self.root.after(250, self.refresh)

    def _build_ui(self) -> None:
        self.root.title("HWMonitor Remote")
        self.root.geometry("1540x930")
        self.root.minsize(1180, 720)
        self.root.configure(bg="#11161c")
        self.root.option_add("*tearOff", False)

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
        style.configure("TButton", background=card, foreground=text, bordercolor=edge)
        style.map("TButton", background=[("active", "#24303b")])
        style.configure("TCheckbutton", background=panel, foreground=text)

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
        ttk.Checkbutton(controls, text="Auto", variable=self.auto_refresh_var, command=self._toggle_auto).grid(row=0, column=3, padx=(0, 8))
        ttk.Label(controls, text="Interval", style="Muted.TLabel").grid(row=0, column=4, sticky="e")
        interval_box = ttk.Combobox(controls, width=8, state="readonly", textvariable=self.interval_var, values=(1000, 2000, 3000, 5000, 10000))
        interval_box.grid(row=0, column=5, padx=(6, 0))
        interval_box.bind("<<ComboboxSelected>>", lambda _event: self._reschedule())

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

        ttk.Label(overview, text="Pinned Favorites", style="Section.TLabel").pack(anchor="w", pady=(8, 4))
        fav_frame = ttk.Frame(overview, style="Card.TFrame", padding=8)
        fav_frame.pack(fill="x")
        self.favorites_tree = ttk.Treeview(fav_frame, columns=("sensor", "value"), show="headings", height=8)
        self.favorites_tree.heading("sensor", text="Sensor", command=lambda: self._sort_table(self.favorites_tree, "sensor", numeric=False))
        self.favorites_tree.heading("value", text="Value", command=lambda: self._sort_table(self.favorites_tree, "value", numeric=True))
        self.favorites_tree.column("sensor", width=175, anchor="w")
        self.favorites_tree.column("value", width=85, anchor="e")
        self.favorites_tree.pack(fill="x")
        self.favorites_tree.bind("<Double-1>", self._on_favorite_activate)
        self.favorites_tree.bind("<Button-3>", self._show_favorite_context_menu)

        ttk.Label(overview, text="Hottest CPU Cores", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        cores_frame = ttk.Frame(overview, style="Card.TFrame", padding=8)
        cores_frame.pack(fill="both", expand=True)
        self.cores_tree = ttk.Treeview(cores_frame, columns=("temp",), show="headings", height=12)
        self.cores_tree.heading("temp", text="Temp", command=lambda: self._sort_table(self.cores_tree, "temp", numeric=True))
        self.cores_tree.column("#0", width=0, stretch=False)
        self.cores_tree.column("temp", width=100, anchor="e")
        self.cores_tree.pack(fill="both", expand=True)

        filter_bar = ttk.Frame(explorer, style="Panel.TFrame")
        filter_bar.pack(fill="x")
        ttk.Label(filter_bar, text="Filter", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.search_entry = ttk.Entry(filter_bar, textvariable=self.search_var, width=34)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._rebuild_tree())
        ttk.Label(filter_bar, text="Category", style="Muted.TLabel").grid(row=0, column=2, sticky="e")
        category_box = ttk.Combobox(filter_bar, width=12, state="readonly", textvariable=self.category_var, values=CATEGORY_VALUES)
        category_box.grid(row=0, column=3, padx=(6, 0))
        category_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        ttk.Label(filter_bar, text="Hardware", style="Muted.TLabel").grid(row=0, column=4, sticky="e", padx=(10, 0))
        self.hardware_box = ttk.Combobox(filter_bar, width=22, state="readonly", textvariable=self.hardware_var, values=("all",))
        self.hardware_box.grid(row=0, column=5, padx=(6, 6))
        self.hardware_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        ttk.Button(filter_bar, text="Expand", command=lambda: self._set_all_open(True)).grid(row=0, column=6, padx=(6, 6))
        ttk.Button(filter_bar, text="Collapse", command=lambda: self._set_all_open(False)).grid(row=0, column=7, padx=(0, 6))
        ttk.Button(filter_bar, text="Reset", command=self._reset_filters).grid(row=0, column=8, padx=(0, 10))
        self.count_label = ttk.Label(filter_bar, text="0 sensors", style="Muted.TLabel")
        self.count_label.grid(row=0, column=9, sticky="e")
        filter_bar.columnconfigure(1, weight=1)
        filter_bar.columnconfigure(9, weight=1)
        ttk.Label(explorer, textvariable=self.hint_var, style="Muted.TLabel").pack(anchor="w", pady=(2, 8))

        self.tree_frame = ttk.Frame(explorer, style="Card.TFrame", padding=6)
        self.tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(self.tree_frame, columns=("value", "min", "max"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Sensor", command=lambda: self._sort_main_tree("#0", numeric=False))
        self.tree.heading("value", text="Value", command=lambda: self._sort_main_tree("value", numeric=True))
        self.tree.heading("min", text="Min", command=lambda: self._sort_main_tree("min", numeric=True))
        self.tree.heading("max", text="Max", command=lambda: self._sort_main_tree("max", numeric=True))
        self.tree.column("#0", width=620, anchor="w")
        self.tree.column("value", width=130, anchor="e")
        self.tree.column("min", width=110, anchor="e")
        self.tree.column("max", width=110, anchor="e")
        self.tree.tag_configure("hardware", foreground="#d9e2ec", font=("DejaVu Sans", 10, "bold"))
        self.tree.tag_configure("group", foreground="#a9b8c7", font=("DejaVu Sans", 10, "bold"))
        self.tree.tag_configure("sensor", foreground=text)
        self.tree.tag_configure("favorite", foreground="#7fd4ff", font=("DejaVu Sans Mono", 10, "bold"))
        self.tree.tag_configure("warn", foreground=amber)
        self.tree.tag_configure("critical", foreground=red)
        self.tree.tag_configure("cool", foreground=green)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._toggle_selected_favorite)
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
        # Not packed initially — shown only when a sensor is selected
        ttk.Label(self.detail_frame, text="Selected Sensor", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.detail_frame, textvariable=self.detail_name_var, style="Title.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_meta_var, style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(2, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_value_var, style="CardValue.TLabel").grid(row=1, column=1, sticky="e", padx=(20, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_range_var, style="CardDetail.TLabel").grid(row=2, column=1, sticky="e", padx=(20, 0))
        ttk.Label(self.detail_frame, textvariable=self.detail_history_var, style="Muted.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        actions = ttk.Frame(self.detail_frame, style="Card.TFrame")
        actions.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(actions, text="Pin", command=self._toggle_selected_favorite).pack(side="left")
        ttk.Button(actions, text="Copy Path", command=self._copy_selected_path).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Copy Value", command=self._copy_selected_value).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Focus Hardware", command=self._focus_selected_hardware).pack(side="left", padx=(6, 0))
        self.detail_frame.columnconfigure(0, weight=1)

        self.tree_menu = tk.Menu(self.root, tearoff=False)
        self.tree_menu.add_command(label="Pin / Unpin Sensor", command=self._toggle_selected_favorite)
        self.tree_menu.add_command(label="Copy Sensor Path", command=self._copy_selected_path)
        self.tree_menu.add_command(label="Copy Sensor Value", command=self._copy_selected_value)
        self.tree_menu.add_command(label="Filter To Hardware", command=self._focus_selected_hardware)
        self.tree_menu.add_command(label="Search Sensor Name", command=self._search_selected_name)

        self.favorite_menu = tk.Menu(self.root, tearoff=False)
        self.favorite_menu.add_command(label="Pin / Unpin Favorite", command=self._on_favorite_activate)
        self.favorite_menu.add_command(label="Copy Favorite Path", command=self._copy_selected_favorite_path)

        self.root.bind("<F5>", lambda _event: self.refresh())
        self.root.bind("<Control-f>", self._focus_search)
        self.root.bind("<Control-l>", self._focus_source)
        self.root.bind("<Control-c>", self._copy_selected_value)

        self.root.after(150, self._set_initial_layout)

    def _toggle_auto(self) -> None:
        self._reschedule()

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
        self.hint_var.set("Last refresh failed  |  Check source host, SSH, and Windows sensor script")
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
        self._update_hardware_choices(payload)
        self._update_overview(payload)
        self._rebuild_tree()
        rows = self._flatten_rows(payload)
        self._update_alert_banner(rows)
        generated = payload.get("generatedAt", "unknown time")
        self.status_var.set(f"Updated in {elapsed_ms} ms, snapshot {generated}")
        self.hint_var.set("F5 refresh  |  Ctrl+F search  |  Double-click sensor to pin")
        self._reschedule()

    def _dismiss_alert_banner(self) -> None:
        self._banner_dismissed = True
        self.alert_banner.pack_forget()

    def _update_alert_banner(self, rows: list[SensorRow]) -> None:
        breached = [
            row for row in rows
            if row.kind == "sensor"
            and row.value is not None
            and SensorApp._severity_for(row.sensor_type, row.value) in ("warn", "critical")
        ]
        if not breached:
            self.alert_banner.pack_forget()
            self._banner_dismissed = False
            return

        if self._banner_dismissed:
            return

        parts = [f"{row.name} {self._format_value(row.value, row.unit)}" for row in breached[:5]]
        if len(breached) > 5:
            parts.append(f"+{len(breached) - 5} more")

        has_critical = any(
            SensorApp._severity_for(r.sensor_type, r.value) == "critical" for r in breached
        )
        color = "#7c2020" if has_critical else "#7c5c00"
        self.alert_banner.configure(bg=color)
        for widget in self.alert_banner.winfo_children():
            try:
                widget.configure(bg=color)
            except tk.TclError:
                pass

        self.alert_text_var.set("  ALERT:  " + "  |  ".join(parts))
        self.alert_banner.pack(fill="x", pady=(4, 0), before=self.body)

    def _set_initial_layout(self) -> None:
        try:
            total_width = max(self.root.winfo_width(), 1540)
            self.body.sashpos(0, int(total_width * 0.30))
        except tk.TclError:
            pass

    def _update_overview(self, payload: dict) -> None:
        rows = self._flatten_rows(payload)
        self._update_history(rows)
        cpu_temp = self._best_row(
            rows,
            hardware_hints=("intel", "amd", "cpu", "ryzen"),
            sensor_hints=("package", "cpu package", "core max"),
            sensor_type="Temperature",
            exclude_hints=("distance to tjmax", "nvidia", "radeon", "arc", "gpu"),
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
                self.summary_detail_vars[name].set(f"{row.name}  {self._history_text(row.path)}")
            else:
                self.summary_value_vars[name].set("--")
                self.summary_detail_vars[name].set("No sensor")

        favorites = self._favorite_rows(rows)
        self.favorite_rows = favorites
        self.favorites_tree.delete(*self.favorites_tree.get_children())
        self.favorite_item_paths.clear()
        for label, sensor, value in favorites:
            item_id = self.favorites_tree.insert("", "end", values=(f"{label}: {sensor}", value))
            path = None
            if label.startswith("* "):
                path = next((row.path for row in rows if row.kind == "sensor" and row.name == label[2:]), None)
            else:
                path = self._favorite_path_for_label(rows, label)
            if path:
                self.favorite_item_paths[item_id] = path

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
            return
        search = self.search_var.get().strip().lower()
        category = self.category_var.get() or "all"
        self._insert_tree_node("", self.current_payload, search, category, 0, "")
        self.count_label.configure(text=f"{self.visible_sensor_count} sensors, {self.visible_group_count} groups")
        self._restore_selection()
        self._persist_config()

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

        matches_search = not search or search in path_blob
        matches_category = True
        if kind == "sensor" and category != "all":
            matches_category = self._category_for_type(node_type) == category
        matches_hardware = True
        if hardware_filter != "all" and kind != "machine":
            matches_hardware = hardware_filter.lower() in path_blob
        if kind == "machine":
            return any(self._node_visible(child, search, category, current_path) for child in node.get("children", []))
        if matches_search and matches_category and matches_hardware:
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

        label = name
        values = ("", "", "")
        if kind == "sensor":
            label = f"* {name}" if current_path in self.favorite_paths else name
            values = (
                self._format_value(node.get("value"), node.get("unit")),
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
        self.hardware_var.set("all")
        self._rebuild_tree()

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

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            self.detail_frame.pack_forget()
            self.detail_name_var.set("No sensor selected")
            self.detail_meta_var.set("")
            self.detail_value_var.set("")
            self.detail_range_var.set("")
            self.detail_history_var.set("")
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
            self.detail_frame.pack(fill="x", pady=(8, 0), after=self.tree_frame)
            value_text = self._format_value(node.get("value"), unit) or "--"
            min_text = self._format_value(node.get("min"), unit) or "--"
            max_text = self._format_value(node.get("max"), unit) or "--"
            self.detail_value_var.set(value_text)
            self.detail_range_var.set(f"Min {min_text}   Max {max_text}")
            pin_state = "Pinned" if path in self.favorite_paths else "Double-click tree to pin"
            self.detail_history_var.set(f"{pin_state}  |  Trend {self._history_text(path)}")
        else:
            self.detail_frame.pack_forget()
            child_count = len(node.get("children", []))
            self.detail_value_var.set(f"{child_count} items")
            self.detail_range_var.set("")
            self.detail_history_var.set("")

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
        self._update_overview(self.current_payload)

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
        self._update_overview(self.current_payload)
        self._on_tree_select()

    def _update_hardware_choices(self, payload: dict) -> None:
        hardware_names = ["all"]
        for child in payload.get("children", []):
            if child.get("kind") == "hardware":
                hardware_names.append(child.get("name", "Unknown"))
        self.hardware_box.configure(values=tuple(hardware_names))
        if self.hardware_var.get() not in hardware_names:
            self.hardware_var.set("all")

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
        chars = "._-~=^"
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
        hardware = data.get("hardware_filter", "all")
        if isinstance(hardware, str):
            self.hardware_var.set(hardware)

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
            score -= sum(35 for hint in exclude_hints if hint in haystack)
            if row.severity == "critical" and sensor_type == "Temperature":
                score -= 10
            if score > best_score:
                best = row
                best_score = score
        return best

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

    def _favorite_rows(self, rows: list[SensorRow]) -> list[tuple[str, str, str]]:
        auto_candidates = self._favorite_candidates(rows)
        row_by_path = {row.path: row for row in rows if row.kind == "sensor"}
        out: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for path in sorted(self.favorite_paths):
            row = row_by_path.get(path)
            if not row or row.path in seen:
                continue
            seen.add(row.path)
            out.append((f"* {row.name}", row.path.split("/")[-2], self._value_text(row)))
        for label, row in auto_candidates:
            if not row or row.path in seen:
                continue
            seen.add(row.path)
            out.append((label, row.name, self._value_text(row)))
        return out

    def _favorite_path_for_label(self, rows: list[SensorRow], label: str) -> str | None:
        for candidate_label, row in self._favorite_candidates(rows):
            if candidate_label == label and row:
                return row.path
        return None

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
        if value is None:
            return "normal"
        if sensor_type == "Temperature":
            if value >= 90:
                return "critical"
            if value >= 75:
                return "warn"
            return "cool"
        if sensor_type in {"Load", "Control"}:
            if value >= 95:
                return "critical"
            if value >= 80:
                return "warn"
            return "cool"
        if sensor_type == "Power":
            if value >= 300:
                return "critical"
            if value >= 220:
                return "warn"
        return "normal"

    @staticmethod
    def _severity(node: dict | "SensorRow") -> str:
        if isinstance(node, SensorRow):
            return SensorApp._severity_for(node.sensor_type, node.value)
        return SensorApp._severity_for(node.get("type", ""), node.get("value"))

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

    def _persist_config(self) -> None:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "url": self.url_var.get(),
                    "interval_ms": self.interval_var.get(),
                    "hardware_filter": self.hardware_var.get(),
                    "favorite_paths": sorted(self.favorite_paths),
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

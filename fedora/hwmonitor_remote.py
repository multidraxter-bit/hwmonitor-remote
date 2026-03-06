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
    def __init__(self, root: tk.Tk, url: str, interval_ms: int) -> None:
        self.root = root
        self.url_var = tk.StringVar(value=url)
        self.interval_var = tk.IntVar(value=interval_ms)
        self.status_var = tk.StringVar(value="Waiting for first refresh")
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.category_var = tk.StringVar(value="all")
        self.refresh_job = None
        self.current_payload: dict = {}
        self.summary_value_vars: dict[str, tk.StringVar] = {}
        self.summary_detail_vars: dict[str, tk.StringVar] = {}
        self.favorite_rows: list[tuple[str, str, str]] = []
        self.cpu_core_rows: list[tuple[str, str]] = []

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
        source_entry = ttk.Entry(controls, textvariable=self.url_var, width=38)
        source_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        ttk.Button(controls, text="Refresh", command=self.refresh).grid(row=0, column=2, padx=(0, 8))
        ttk.Checkbutton(controls, text="Auto", variable=self.auto_refresh_var, command=self._toggle_auto).grid(row=0, column=3, padx=(0, 8))
        ttk.Label(controls, text="Interval", style="Muted.TLabel").grid(row=0, column=4, sticky="e")
        interval_box = ttk.Combobox(controls, width=8, state="readonly", textvariable=self.interval_var, values=(1000, 2000, 3000, 5000, 10000))
        interval_box.grid(row=0, column=5, padx=(6, 0))
        interval_box.bind("<<ComboboxSelected>>", lambda _event: self._reschedule())

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(10, 0))

        overview = ttk.Frame(body, style="Panel.TFrame", padding=10)
        explorer = ttk.Frame(body, style="Panel.TFrame", padding=10)
        body.add(overview, weight=1)
        body.add(explorer, weight=3)

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
        self.favorites_tree.heading("sensor", text="Sensor")
        self.favorites_tree.heading("value", text="Value")
        self.favorites_tree.column("sensor", width=175, anchor="w")
        self.favorites_tree.column("value", width=85, anchor="e")
        self.favorites_tree.pack(fill="x")

        ttk.Label(overview, text="Hottest CPU Cores", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        cores_frame = ttk.Frame(overview, style="Card.TFrame", padding=8)
        cores_frame.pack(fill="both", expand=True)
        self.cores_tree = ttk.Treeview(cores_frame, columns=("temp",), show="headings", height=12)
        self.cores_tree.heading("temp", text="Temp")
        self.cores_tree.column("#0", width=0, stretch=False)
        self.cores_tree.column("temp", width=100, anchor="e")
        self.cores_tree.pack(fill="both", expand=True)

        filter_bar = ttk.Frame(explorer, style="Panel.TFrame")
        filter_bar.pack(fill="x")
        ttk.Label(filter_bar, text="Filter", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(filter_bar, textvariable=self.search_var, width=34)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        search_entry.bind("<KeyRelease>", lambda _event: self._rebuild_tree())
        ttk.Label(filter_bar, text="Category", style="Muted.TLabel").grid(row=0, column=2, sticky="e")
        category_box = ttk.Combobox(filter_bar, width=12, state="readonly", textvariable=self.category_var, values=CATEGORY_VALUES)
        category_box.grid(row=0, column=3, padx=(6, 0))
        category_box.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_tree())
        filter_bar.columnconfigure(1, weight=1)

        favorites_bar = ttk.Frame(explorer, style="Card.TFrame", padding=6)
        favorites_bar.pack(fill="x", pady=(8, 8))
        ttk.Label(favorites_bar, text="Favorites", style="Section.TLabel").pack(anchor="w")
        self.favorite_label = ttk.Label(favorites_bar, text="Waiting for data", style="Muted.TLabel")
        self.favorite_label.pack(anchor="w", pady=(4, 0))

        tree_frame = ttk.Frame(explorer, style="Card.TFrame", padding=6)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("value", "min", "max"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Sensor")
        self.tree.heading("value", text="Value")
        self.tree.heading("min", text="Min")
        self.tree.heading("max", text="Max")
        self.tree.column("#0", width=520, anchor="w")
        self.tree.column("value", width=120, anchor="e")
        self.tree.column("min", width=100, anchor="e")
        self.tree.column("max", width=100, anchor="e")
        self.tree.tag_configure("hardware", foreground="#d9e2ec", font=("DejaVu Sans", 10, "bold"))
        self.tree.tag_configure("group", foreground="#a9b8c7", font=("DejaVu Sans", 10, "bold"))
        self.tree.tag_configure("sensor", foreground=text)
        self.tree.tag_configure("warn", foreground=amber)
        self.tree.tag_configure("critical", foreground=red)
        self.tree.tag_configure("cool", foreground=green)
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

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
        self._update_overview(payload)
        self._rebuild_tree()
        generated = payload.get("generatedAt", "unknown time")
        self.status_var.set(f"Updated in {elapsed_ms} ms, snapshot {generated}")
        self._reschedule()

    def _update_overview(self, payload: dict) -> None:
        rows = self._flatten_rows(payload)
        summaries = {
            "CPU": self._best_row(rows, hardware_hints=("intel", "amd", "cpu", "ryzen", "core"), sensor_hints=("package", "cpu package"), sensor_type="Temperature"),
            "GPU": self._best_row(rows, hardware_hints=("nvidia", "radeon", "arc", "gpu"), sensor_hints=("hot spot", "gpu core", "core"), sensor_type="Temperature"),
            "Cooling": self._best_row(rows, hardware_hints=("asus", "motherboard", "board"), sensor_hints=("fan", "cpu"), sensor_type="Fan"),
            "Drive": self._best_row(rows, hardware_hints=("ssd", "nvme", "samsung", "wd", "kingston", "crucial"), sensor_hints=("temperature", "assembly"), sensor_type="Temperature"),
        }
        for name, row in summaries.items():
            if row:
                self.summary_value_vars[name].set(self._value_text(row))
                self.summary_detail_vars[name].set(row.name)
            else:
                self.summary_value_vars[name].set("--")
                self.summary_detail_vars[name].set("No sensor")

        favorites = self._favorite_rows(rows)
        self.favorite_rows = favorites
        self.favorite_label.configure(text="  |  ".join(f"{label}: {value}" for label, _sensor, value in favorites) or "No favorite sensors found")
        self.favorites_tree.delete(*self.favorites_tree.get_children())
        for label, sensor, value in favorites:
            self.favorites_tree.insert("", "end", values=(f"{label}: {sensor}", value))

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
        self.tree.delete(*self.tree.get_children())
        if not self.current_payload:
            return
        search = self.search_var.get().strip().lower()
        category = self.category_var.get() or "all"
        self._insert_tree_node("", self.current_payload, search, category, 0)
        for item in self.tree.get_children():
            self.tree.item(item, open=True)

    def _insert_tree_node(self, parent: str, node: dict, search: str, category: str, depth: int) -> bool:
        kind = node.get("kind", "sensor")
        name = node.get("name", "Unknown")
        node_type = node.get("type", "")
        path_blob = f"{name} {node_type}".lower()

        matches_search = not search or search in path_blob
        matches_category = True
        if kind == "sensor" and category != "all":
            matches_category = self._category_for_type(node_type) == category

        inserted_children = []
        for child in node.get("children", []):
            child_visible = self._insert_tree_node(parent="__probe__", node=child, search=search, category=category, depth=depth + 1)
            inserted_children.append((child, child_visible))

        visible = kind != "machine" and ((matches_search and matches_category) or any(flag for _, flag in inserted_children))

        if kind == "machine":
            for child, child_visible in inserted_children:
                if child_visible:
                    self._insert_tree_node(parent, child, search="", category="all", depth=0)
            return True

        if parent == "__probe__":
            return visible

        if not visible:
            return False

        tags = [kind.lower()]
        severity = self._severity(node)
        if severity in ("warn", "critical", "cool"):
            tags.append(severity)

        label = name if kind == "sensor" else f"{name}"
        values = ("", "", "")
        if kind == "sensor":
            values = (
                self._format_value(node.get("value"), node.get("unit")),
                self._format_value(node.get("min"), node.get("unit")),
                self._format_value(node.get("max"), node.get("unit")),
            )

        item = self.tree.insert(parent, "end", text=("   " * depth) + label, values=values, tags=tuple(tags))
        for child, child_visible in inserted_children:
            if child_visible:
                self._insert_tree_node(item, child, search="", category="all", depth=depth + 1)
        return True

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

    def _best_row(self, rows: list[SensorRow], hardware_hints: tuple[str, ...], sensor_hints: tuple[str, ...], sensor_type: str) -> SensorRow | None:
        best = None
        best_score = -10**9
        for row in rows:
            if row.kind != "sensor" or row.value is None:
                continue
            score = 0
            haystack = f"{row.path} {row.name}".lower()
            if row.sensor_type == sensor_type:
                score += 50
            else:
                score -= 25
            score += sum(12 for hint in hardware_hints if hint in haystack)
            score += sum(20 for hint in sensor_hints if hint in haystack)
            if score > best_score:
                best = row
                best_score = score
        return best

    def _favorite_rows(self, rows: list[SensorRow]) -> list[tuple[str, str, str]]:
        picks = [
            ("CPU Package", self._best_row(rows, ("intel", "amd", "cpu", "ryzen", "core"), ("package", "cpu package"), "Temperature")),
            ("CPU Load", self._best_row(rows, ("intel", "amd", "cpu", "ryzen", "core"), ("total", "cpu total"), "Load")),
            ("GPU Hotspot", self._best_row(rows, ("nvidia", "radeon", "arc", "gpu"), ("hot spot", "hotspot", "gpu core"), "Temperature")),
            ("GPU Load", self._best_row(rows, ("nvidia", "radeon", "arc", "gpu"), ("gpu core", "d3d 3d", "core"), "Load")),
            ("GPU Power", self._best_row(rows, ("nvidia", "radeon", "arc", "gpu"), ("board power", "gpu power"), "Power")),
            ("CPU Fan", self._best_row(rows, ("asus", "motherboard", "board"), ("fan", "cpu"), "Fan")),
            ("Drive Temp", self._best_row(rows, ("ssd", "nvme", "samsung", "wd", "kingston", "crucial"), ("temperature", "assembly"), "Temperature")),
        ]
        out: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for label, row in picks:
            if not row or row.path in seen:
                continue
            seen.add(row.path)
            out.append((label, row.name, self._value_text(row)))
        return out

    def _cpu_core_rows(self, rows: list[SensorRow]) -> list[tuple[str, str]]:
        core_rows = []
        for row in rows:
            if row.kind != "sensor" or row.sensor_type != "Temperature" or row.value is None:
                continue
            haystack = f"{row.path} {row.name}".lower()
            if "core" not in haystack:
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
    def _severity(node: dict | SensorRow) -> str:
        if isinstance(node, SensorRow):
            sensor_type = node.sensor_type
            value = node.value
        else:
            sensor_type = node.get("type", "")
            value = node.get("value")

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
            json.dump({"url": self.url_var.get(), "interval_ms": self.interval_var.get()}, handle, indent=2)


def load_config() -> tuple[str, int]:
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_URL, 2000
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("url", DEFAULT_URL), int(data.get("interval_ms", 2000))
    except Exception:
        return DEFAULT_URL, 2000


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

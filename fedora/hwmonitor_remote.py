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
from tkinter import ttk


DEFAULT_URL = "ssh://loofi@192.168.1.3"
CONFIG_PATH = os.path.expanduser("~/.config/hwremote-monitor.json")


class SensorApp:
    def __init__(self, root: tk.Tk, url: str, interval_ms: int) -> None:
        self.root = root
        self.url_var = tk.StringVar(value=url)
        self.interval_var = tk.IntVar(value=interval_ms)
        self.status_var = tk.StringVar(value="Waiting for first refresh")
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_job = None
        self.item_map = {}
        self.type_icons = {
            "machine": "[M]",
            "hardware": "[H]",
            "group": "[G]",
            "sensor": "",
        }

        self._build_ui()
        self.root.after(250, self.refresh)

    def _build_ui(self) -> None:
        self.root.title("HWMonitor Remote")
        self.root.geometry("1080x760")
        self.root.minsize(860, 540)
        self.root.configure(bg="#ececec")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Treeview", rowheight=24, font=("DejaVu Sans", 10))
        style.configure("Treeview.Heading", font=("DejaVu Sans", 10, "bold"))
        style.configure("Status.TLabel", padding=(8, 4))

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Sensor URL").grid(row=0, column=0, sticky="w")
        url_entry = ttk.Entry(top, textvariable=self.url_var, width=64)
        url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        ttk.Button(top, text="Refresh", command=self.refresh).grid(row=0, column=2, padx=(0, 8))
        ttk.Checkbutton(top, text="Auto", variable=self.auto_refresh_var, command=self._toggle_auto).grid(row=0, column=3, padx=(0, 8))

        ttk.Label(top, text="Interval").grid(row=0, column=4, sticky="e")
        interval_box = ttk.Combobox(
            top,
            width=8,
            state="readonly",
            textvariable=self.interval_var,
            values=(1000, 2000, 3000, 5000, 10000),
        )
        interval_box.grid(row=0, column=5, padx=(8, 0))
        interval_box.bind("<<ComboboxSelected>>", lambda _event: self._reschedule())
        top.columnconfigure(1, weight=1)

        body = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            body,
            columns=("value", "min", "max"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Sensor")
        self.tree.heading("value", text="Value")
        self.tree.heading("min", text="Min")
        self.tree.heading("max", text="Max")
        self.tree.column("#0", width=520, anchor="w")
        self.tree.column("value", width=160, anchor="e")
        self.tree.column("min", width=140, anchor="e")
        self.tree.column("max", width=140, anchor="e")

        yscroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        status = ttk.Label(self.root, textvariable=self.status_var, style="Status.TLabel", anchor="w")
        status.pack(fill="x", side="bottom")

    def _toggle_auto(self) -> None:
        self._reschedule()

    def _reschedule(self) -> None:
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
            self.refresh_job = None
        if self.auto_refresh_var.get():
            self.refresh_job = self.root.after(self.interval_var.get(), self.refresh)

    def refresh(self) -> None:
        self.status_var.set(f"Refreshing from {self.url_var.get()} ...")
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
        self.item_map.clear()
        self.tree.delete(*self.tree.get_children())
        self._insert_node("", payload)
        for item in self.tree.get_children():
            self.tree.item(item, open=True)
            self._open_hardware_nodes(item)
        generated = payload.get("generatedAt", "unknown time")
        self.status_var.set(f"Updated in {elapsed_ms} ms, snapshot {generated}")
        self._reschedule()

    def _open_hardware_nodes(self, item: str) -> None:
        for child in self.tree.get_children(item):
            kind = self.tree.set(child, "value")
            self.tree.item(child, open=True)
            self._open_hardware_nodes(child)

    def _insert_node(self, parent: str, node: dict) -> None:
        kind = node.get("kind", "sensor")
        label = node.get("name", "Unknown")
        if kind in self.type_icons and self.type_icons[kind]:
            label = f"{self.type_icons[kind]} {label}"

        values = ("", "", "")
        if kind == "sensor":
            values = (
                self._format_value(node.get("value"), node.get("unit")),
                self._format_value(node.get("min"), node.get("unit")),
                self._format_value(node.get("max"), node.get("unit")),
            )

        item = self.tree.insert(parent, "end", text=label, values=values)
        for child in node.get("children", []):
            self._insert_node(item, child)

    @staticmethod
    def _format_value(value, unit: str) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value} {unit}".strip()

    def _persist_config(self) -> None:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "url": self.url_var.get(),
                    "interval_ms": self.interval_var.get(),
                },
                handle,
                indent=2,
            )


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

    parser = argparse.ArgumentParser(description="HWMonitor-style remote viewer for LibreHardwareMonitor data.")
    parser.add_argument("--url", default=saved_url, help="JSON endpoint URL")
    parser.add_argument("--interval-ms", type=int, default=saved_interval, help="Refresh interval in milliseconds")
    args = parser.parse_args()

    root = tk.Tk()
    app = SensorApp(root, args.url, args.interval_ms)
    root.mainloop()


if __name__ == "__main__":
    main()

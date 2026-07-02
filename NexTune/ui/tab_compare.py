"""
GameOptimizerPro v2.0 — Profile Comparison Tab
Side-by-side comparison of up to 4 saved profiles.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional
from ui.widgets import *
from core.nvtune_core import ProfileManager, TuneProfile


COMPARE_COLORS = [ACC, VOLT, "#22c55e", "#f59e0b"]


class CompareBar(tk.Frame):
    """Mini horizontal bar for a single metric comparison."""

    def __init__(self, parent, label, **kw):
        super().__init__(parent, bg=BG2, **kw)
        tk.Label(self, text=label, font=FM, fg=DIM, bg=BG2,
                 width=10, anchor="w").pack(side="left", padx=(8, 4))
        self.bar_frame = tk.Frame(self, bg=BG2)
        self.bar_frame.pack(side="left", fill="x", expand=True)

    def set_values(self, values: list[tuple[str, float, float, str]]):
        """values: list of (label, value, max_val, color)"""
        for w in self.bar_frame.winfo_children():
            w.destroy()
        for i, (label, val, max_val, color) in enumerate(values):
            row = tk.Frame(self.bar_frame, bg=BG2)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label[:14], font=("Segoe UI", 7),
                     fg=DIM, bg=BG2, width=14, anchor="w"
                     ).pack(side="left", padx=(0, 4))
            pct = min(1.0, val / max_val) if max_val else 0
            bar_bg = tk.Frame(row, bg=BG3, height=12)
            bar_bg.pack(side="left", fill="x", expand=True)
            bar_bg.update_idletasks()

            def _draw_bar(f=bar_bg, p=pct, c=color, v=val):
                f.update_idletasks()
                fw = int(f.winfo_width() * p)
                if fw > 0:
                    bar = tk.Frame(f, bg=c, height=12, width=fw)
                    bar.place(x=0, y=0)

            bar_bg.after(50, _draw_bar)
            tk.Label(row, text=f"{val:.0f}", font=("Consolas", 7),
                     fg=color, bg=BG2, width=6, anchor="e"
                     ).pack(side="right", padx=4)


class CompareTab(tk.Frame):
    def __init__(self, parent, pm: ProfileManager, **kw):
        super().__init__(parent, bg=BG1, **kw)
        self.pm = pm
        self._selected: list[Optional[TuneProfile]] = [None, None, None, None]
        self._build()

    def _build(self):
        tk.Label(self, text="Profile Comparison", font=FT, fg=WHT, bg=BG1
                 ).pack(padx=14, pady=(12, 4), anchor="w")
        tk.Label(self,
                 text="Select up to 4 profiles to compare side-by-side.",
                 font=FL, fg=DIM, bg=BG1).pack(padx=14, anchor="w")

        # Profile selectors
        sel_f = tk.Frame(self, bg=BG2)
        sel_f.pack(fill="x", padx=14, pady=8)
        for i in range(4):
            sel_f.columnconfigure(i, weight=1)

        self._combos: list[ttk.Combobox] = []
        for i in range(4):
            col_f = tk.Frame(sel_f, bg=BG2, padx=6, pady=6)
            col_f.grid(row=0, column=i, padx=4, sticky="nsew")
            color = COMPARE_COLORS[i]
            tk.Label(col_f, text=f"● Profile {i+1}", font=FL,
                     fg=color, bg=BG2).pack(anchor="w")
            cb = ttk.Combobox(col_f, state="readonly", font=FM, width=18)
            cb.pack(fill="x", pady=4)
            cb.bind("<<ComboboxSelected>>",
                    lambda e, idx=i: self._on_select(idx))
            self._combos.append(cb)

        tk.Button(sel_f, text="⟳ Refresh Profiles",
                  font=FL, bg=BG3, fg=TXT, relief="flat",
                  padx=10, cursor="hand2",
                  command=self._refresh_list
                  ).grid(row=1, column=0, columnspan=4,
                         padx=4, pady=(0, 4), sticky="w")

        # Metric bars
        metrics_f = tk.Frame(self, bg=BG1)
        metrics_f.pack(fill="both", expand=True, padx=14, pady=4)

        SecHdr(metrics_f, "Metrics Comparison").pack(fill="x", pady=(4, 8))

        self._metric_bars: dict[str, CompareBar] = {}
        metrics = [
            ("Core +MHz",  "core"),
            ("Mem +MHz",   "mem"),
            ("Power %",    "pwr"),
            ("Avg Volt mV","volt"),
            ("Score /100", "score"),
        ]
        for label, key in metrics:
            bar = CompareBar(metrics_f, label)
            bar.pack(fill="x", padx=4, pady=3)
            self._metric_bars[key] = bar

        # Detail table
        SecHdr(metrics_f, "Full Details").pack(fill="x", pady=(12, 4))
        # Force dark background on treeview via style
        style = ttk.Style()
        style.configure("TV.Treeview",
            background="#161b22", foreground="#d0d8e8",
            fieldbackground="#161b22", rowheight=26, font=("Segoe UI", 9))
        style.configure("TV.Treeview.Heading",
            background="#1e2530", foreground="#00d9ff",
            font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("TV.Treeview",
            background=[("selected", "#7c3aed")],
            foreground=[("selected", "#f0f4ff")])

        cols = ("metric", "p1", "p2", "p3", "p4")
        self.detail_tree = ttk.Treeview(
            metrics_f, columns=cols, show="headings",
            height=10, style="TV.Treeview"
        )
        self.detail_tree.heading("metric", text="Metric")
        self.detail_tree.column("metric", width=130, anchor="w")
        for i in range(4):
            self.detail_tree.heading(f"p{i+1}", text=f"Profile {i+1}")
            self.detail_tree.column(f"p{i+1}", width=140, anchor="center")
        self.detail_tree.pack(fill="both", expand=True, pady=4)

        self._refresh_list()

    def _refresh_list(self):
        profiles = [p for p in self.pm.list_all() if not p.name.startswith("__")]
        names    = ["(none)"] + [p.name for p in profiles]
        for cb in self._combos:
            cb["values"] = names
            if not cb.get():
                cb.set("(none)")
        self._update_comparison()

    def _on_select(self, idx: int):
        name = self._combos[idx].get()
        self._selected[idx] = self.pm.load(name) if name != "(none)" else None
        self._update_comparison()

    def _update_comparison(self):
        active = [(i, p) for i, p in enumerate(self._selected) if p is not None]
        if not active:
            return

        def max_of(attr):
            vals = [getattr(p, attr, 0) or 0 for _, p in active]
            return max(vals) if vals else 1

        max_core  = max(max_of("core_offset_mhz"), 1)
        max_mem   = max(max_of("mem_offset_mhz"), 1)
        max_volt  = max(max_of("stage1_voltage"), 1)
        max_score = 100
        max_pwr   = 100

        # Update bars
        def bar_vals(attr, max_val, label_fn=None):
            vals = []
            for i, p in active:
                v = getattr(p, attr, 0) or 0
                lbl = label_fn(v) if label_fn else str(v)
                vals.append((p.name[:14], v, max_val, COMPARE_COLORS[i]))
            return vals

        self._metric_bars["core"].set_values(
            bar_vals("core_offset_mhz", max_core))
        self._metric_bars["mem"].set_values(
            bar_vals("mem_offset_mhz", max_mem))
        self._metric_bars["volt"].set_values(
            bar_vals("stage1_voltage", max_volt))
        self._metric_bars["score"].set_values(
            bar_vals("stability_score", max_score))

        # Power bar — lower is better, invert display
        pwr_vals = []
        for i, p in active:
            v = p.power_limit_pct or 100
            pwr_vals.append((p.name[:14], 100 - v, 50, COMPARE_COLORS[i]))
        self._metric_bars["pwr"].set_values(pwr_vals)

        # Detail table
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)

        def fmt(p, attr, suffix=""):
            v = getattr(p, attr, None)
            if v is None or v == 0:
                return "--"
            return f"{v}{suffix}"

        rows = [
            ("Name",        lambda p: p.name[:20]),
            ("Core Offset", lambda p: fmt(p, "core_offset_mhz", " MHz")),
            ("Mem Offset",  lambda p: fmt(p, "mem_offset_mhz",  " MHz")),
            ("Power Limit", lambda p: fmt(p, "power_limit_pct", "%")),
            ("Avg Voltage", lambda p: fmt(p, "stage1_voltage",  " mV")),
            ("Score",       lambda p: fmt(p, "stability_score", "/100")),
            ("Stable",      lambda p: "✓" if p.is_stable else "⚠"),
            ("GPU",         lambda p: (p.gpu_name or "")[:20]),
            ("Created",     lambda p: (p.created_at or "")[:16]),
        ]
        for label, fn in rows:
            cells = [label]
            for i in range(4):
                p = self._selected[i]
                cells.append(fn(p) if p else "")
            self.detail_tree.insert("", "end", values=cells)

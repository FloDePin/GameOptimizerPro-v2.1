"""
GameOptimizerPro v2.0 — Profile Comparison Tab
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional
from ui.widgets import *
from core.nvtune_core import ProfileManager, TuneProfile

DARK       = "#0d1117"
DARK2      = "#161b22"
DARK3      = "#1c2128"
BORDER     = "#2d333b"
CYN        = "#00d9ff"
COMPARE_COLORS = [CYN, "#a78bfa", "#22c55e", "#f59e0b"]


def _apply_dark_style(root=None):
    style = ttk.Style()
    # Force dark dropdown listbox for all Comboboxes
    if root:
        try:
            root.option_add("*TCombobox*Listbox.background",  "#1c2128")
            root.option_add("*TCombobox*Listbox.foreground",  "#d0d8e8")
            root.option_add("*TCombobox*Listbox.selectBackground", "#7c3aed")
            root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        except: pass
    # Treeview — fully dark
    style.configure("CMP.Treeview",
        background=DARK2, foreground="#d0d8e8",
        fieldbackground=DARK2, rowheight=24,
        font=("Consolas", 8), borderwidth=0)
    style.configure("CMP.Treeview.Heading",
        background=DARK3, foreground=CYN,
        font=("Consolas", 8, "bold"), relief="flat")
    style.map("CMP.Treeview",
        background=[("selected", "#7c3aed")],
        foreground=[("selected", "#ffffff")])
    # Combobox — dark
    style.configure("CMP.TCombobox",
        fieldbackground=DARK3, background=DARK3,
        foreground="#d0d8e8", arrowcolor=CYN,
        bordercolor=BORDER, lightcolor=DARK3, darkcolor=DARK3)
    style.map("CMP.TCombobox",
        fieldbackground=[("readonly", DARK3)],
        background=[("readonly", DARK3)],
        foreground=[("readonly", "#d0d8e8")])


class CompareTab(tk.Frame):
    def __init__(self, parent, pm: ProfileManager, **kw):
        super().__init__(parent, bg=DARK, **kw)
        self.pm = pm
        self._selected: list[Optional[TuneProfile]] = [None, None, None, None]
        _apply_dark_style(self)
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=DARK)
        hdr.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(hdr, text="[CMP]  Profile Comparison",
                 font=("Segoe UI", 10, "bold"),
                 fg="#7c3aed", bg=DARK).pack(side="left")
        tk.Button(hdr, text="⟳ Refresh",
                  command=self._refresh_list,
                  font=("Consolas", 8), bg=DARK3, fg="#9ca3af",
                  relief="flat", padx=8, pady=4, cursor="hand2"
                  ).pack(side="right")

        tk.Label(self,
                 text="Bis zu 4 GPU-Profile nebeneinander vergleichen.",
                 font=("Segoe UI", 8), fg="#6b7280", bg=DARK
                 ).pack(padx=14, anchor="w")

        # Profile selector row
        sel_f = tk.Frame(self, bg=DARK2)
        sel_f.pack(fill="x", padx=14, pady=8)
        for i in range(4):
            sel_f.columnconfigure(i, weight=1)

        self._combos: list[ttk.Combobox] = []
        for i in range(4):
            col_f = tk.Frame(sel_f, bg=DARK2, padx=8, pady=8)
            col_f.grid(row=0, column=i, padx=3, sticky="nsew")
            color = COMPARE_COLORS[i]
            tk.Label(col_f, text=f"● Profile {i+1}",
                     font=("Consolas", 8, "bold"),
                     fg=color, bg=DARK2).pack(anchor="w", pady=(0, 4))
            cb = ttk.Combobox(col_f, state="readonly",
                              font=("Consolas", 8), style="CMP.TCombobox")
            cb.pack(fill="x")
            cb.bind("<<ComboboxSelected>>",
                    lambda e, idx=i: self._on_select(idx))
            self._combos.append(cb)

        # Metrics section
        SecHdr(self, "Metrics Comparison").pack(fill="x", padx=14, pady=(8, 4))

        metrics_f = tk.Frame(self, bg=DARK)
        metrics_f.pack(fill="x", padx=14)

        self._metric_rows: dict[str, "MetricRow"] = {}
        for label, key in [
            ("Core +MHz",   "core"),
            ("Mem +MHz",    "mem"),
            ("Power %",     "pwr"),
            ("Avg Volt mV", "volt"),
            ("Score /100",  "score"),
        ]:
            row = MetricRow(metrics_f, label)
            row.pack(fill="x", pady=2)
            self._metric_rows[key] = row

        # Full details table
        SecHdr(self, "Full Details").pack(fill="x", padx=14, pady=(12, 4))

        tree_f = tk.Frame(self, bg=DARK)
        tree_f.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        sb = ttk.Scrollbar(tree_f, orient="vertical")
        cols = ("metric", "p1", "p2", "p3", "p4")
        self.detail_tree = ttk.Treeview(
            tree_f, columns=cols, show="headings",
            style="CMP.Treeview", yscrollcommand=sb.set
        )
        sb.config(command=self.detail_tree.yview)

        self.detail_tree.heading("metric", text="Metric")
        self.detail_tree.column("metric", width=120, anchor="w")
        for i in range(4):
            color = COMPARE_COLORS[i]
            self.detail_tree.heading(f"p{i+1}", text=f"● Profile {i+1}")
            self.detail_tree.column(f"p{i+1}", width=160, anchor="center")

        self.detail_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Alternating row colors
        self.detail_tree.tag_configure("odd",  background=DARK2)
        self.detail_tree.tag_configure("even", background=DARK3)

        self._refresh_list()

    def _refresh_list(self):
        profiles = [p for p in self.pm.list_all() if not p.name.startswith("__")]
        names    = ["(none)"] + [p.name for p in profiles]
        for cb in self._combos:
            current = cb.get()
            cb["values"] = names
            cb.set(current if current in names else "(none)")
        self._update_comparison()

    def _on_select(self, idx: int):
        name = self._combos[idx].get()
        self._selected[idx] = self.pm.load(name) if name != "(none)" else None
        self._update_comparison()

    def _update_comparison(self):
        active = [(i, p) for i, p in enumerate(self._selected) if p is not None]
        if not active:
            return

        def mx(attr): return max((getattr(p, attr, 0) or 0 for _, p in active), default=1) or 1

        max_core  = mx("core_offset_mhz")
        max_mem   = mx("mem_offset_mhz")
        max_volt  = mx("stage1_voltage")

        def bar_vals(attr, max_val):
            return [(p.name[:14], getattr(p, attr, 0) or 0, max_val, COMPARE_COLORS[i])
                    for i, p in active]

        self._metric_rows["core"].set_values(bar_vals("core_offset_mhz", max_core))
        self._metric_rows["mem"].set_values( bar_vals("mem_offset_mhz",  max_mem))
        self._metric_rows["volt"].set_values(bar_vals("stage1_voltage",  max_volt))
        self._metric_rows["score"].set_values(bar_vals("stability_score", 100))
        # Power: lower = better, invert
        pwr = [(p.name[:14], 100 - (p.power_limit_pct or 100), 50, COMPARE_COLORS[i])
               for i, p in active]
        self._metric_rows["pwr"].set_values(pwr)

        # Detail table
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)

        def fmt(p, attr, suf=""):
            v = getattr(p, attr, None)
            return f"{v}{suf}" if v else "--"

        row_defs = [
            ("Name",        lambda p: p.name[:22]),
            ("Core Offset", lambda p: fmt(p, "core_offset_mhz", " MHz")),
            ("Mem Offset",  lambda p: fmt(p, "mem_offset_mhz",  " MHz")),
            ("Power Limit", lambda p: fmt(p, "power_limit_pct", "%")),
            ("Avg Voltage", lambda p: fmt(p, "stage1_voltage",  " mV")),
            ("Score",       lambda p: fmt(p, "stability_score", "/100")),
            ("Stable",      lambda p: "✓" if p.is_stable else "⚠"),
            ("GPU",         lambda p: (p.gpu_name or "")[:24]),
            ("Created",     lambda p: (p.created_at or "")[:16]),
        ]
        for row_i, (label, fn) in enumerate(row_defs):
            cells = [label] + [fn(self._selected[i]) if self._selected[i] else "" for i in range(4)]
            tag = "odd" if row_i % 2 else "even"
            self.detail_tree.insert("", "end", values=cells, tags=(tag,))


class MetricRow(tk.Frame):
    """Single metric comparison row with colored bars per profile."""
    def __init__(self, parent, label, **kw):
        super().__init__(parent, bg=DARK, **kw)
        tk.Label(self, text=label, font=("Consolas", 8),
                 fg="#6b7280", bg=DARK, width=12, anchor="w"
                 ).pack(side="left", padx=(4, 8))
        self._bar_area = tk.Frame(self, bg=DARK)
        self._bar_area.pack(side="left", fill="x", expand=True)

    def set_values(self, values: list[tuple[str, float, float, str]]):
        for w in self._bar_area.winfo_children():
            w.destroy()
        for label, val, max_val, color in values:
            row = tk.Frame(self._bar_area, bg=DARK)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label[:16], font=("Consolas", 7),
                     fg="#4b5563", bg=DARK, width=16, anchor="w"
                     ).pack(side="left")
            # Bar background
            bar_bg = tk.Frame(row, bg=DARK3, height=10)
            bar_bg.pack(side="left", fill="x", expand=True, padx=(4, 0))
            # Draw fill after geometry is ready
            pct = min(1.0, val / max_val) if max_val else 0
            def _draw(f=bar_bg, p=pct, c=color):
                f.update_idletasks()
                w = f.winfo_width()
                fw = int(w * p)
                if fw > 2:
                    tk.Frame(f, bg=c, height=10, width=fw).place(x=0, y=0)
            bar_bg.after(60, _draw)
            tk.Label(row, text=f"{val:.0f}", font=("Consolas", 7),
                     fg=color, bg=DARK, width=6, anchor="e"
                     ).pack(side="right", padx=4)

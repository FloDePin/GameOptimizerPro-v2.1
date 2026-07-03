"""
GameOptimizerPro v2.1 — BIOS Guide Tab
Zeigt hardware-spezifische BIOS-Empfehlungen mit Live-Status-Erkennung.
Grüner Kreis = bereits aktiv, Roter Kreis = noch einstellen.
"""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Optional

from ui.widgets import *
from core.hardware    import HardwareInfo
from core.bios_guide  import match_profiles, BiosProfile, BiosSetting
from core.bios_guide  import get_impact_color, get_risk_color
from core.bios_detector import BiosDetector, DetectResult

DARK  = "#0d1117"
DARK2 = "#161b22"
DARK3 = "#1c2128"
BORD  = "#2d333b"

# Status colors for detection result
COL_OK      = "#22c55e"   # already active
COL_TODO    = "#ef4444"   # needs to be set
COL_UNKNOWN = "#6b7280"   # can't detect


class BiosGuideTab(tk.Frame):
    def __init__(self, parent, hw: HardwareInfo, **kw):
        super().__init__(parent, bg=DARK, **kw)
        self.hw       = hw
        self.detector = BiosDetector()
        self._profiles: list[BiosProfile] = []
        self._active_idx = 0
        self._detect_results: dict[str, DetectResult] = {}
        self._detecting = False
        self._build()
        self.after(100, self._load_profiles)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Header row
        hdr = tk.Frame(self, bg=DARK)
        hdr.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(hdr, text="[BIOS]  BIOS & System Guide",
                 font=("Segoe UI", 10, "bold"),
                 fg="#f59e0b", bg=DARK).pack(side="left")

        self.btn_detect = tk.Button(
            hdr, text="⟳  System-Status prüfen",
            command=self._run_detect,
            font=("Consolas", 8, "bold"),
            bg="#f59e0b", fg="#000",
            relief="flat", padx=10, pady=4, cursor="hand2"
        )
        self.btn_detect.pack(side="right")

        self.lbl_detect_status = tk.Label(
            hdr, text="", font=FM, fg=DIM, bg=DARK)
        self.lbl_detect_status.pack(side="right", padx=10)

        # Legend
        leg = tk.Frame(self, bg=DARK)
        leg.pack(fill="x", padx=14, pady=(0, 4))
        for color, label in [
            (COL_OK,      "● Bereits aktiv"),
            (COL_TODO,    "● Noch einstellen"),
            (COL_UNKNOWN, "● Nicht prüfbar"),
        ]:
            tk.Label(leg, text=label, font=("Consolas", 8),
                     fg=color, bg=DARK).pack(side="left", padx=8)
        tk.Label(leg, text="|", fg=BORD, bg=DARK).pack(side="left", padx=4)
        tk.Label(leg,
                 text="Read-only — alle Werte manuell im BIOS einstellen",
                 font=("Segoe UI", 8), fg=DIM, bg=DARK
                 ).pack(side="left")

        # Detected hardware bar
        hw_f = tk.Frame(self, bg=DARK2)
        hw_f.pack(fill="x", padx=14, pady=(0, 4))
        hw_t = (
            f"CPU: {self.hw.cpu_name[:38]}   |   "
            f"Board: {self.hw.mb_manufacturer} {self.hw.mb_product}   |   "
            f"GPU: {self.hw.gpu_name[:28]}"
        )
        tk.Label(hw_f, text=hw_t, font=("Consolas", 8),
                 fg=ACC, bg=DARK2, anchor="w", padx=10, pady=5
                 ).pack(fill="x")

        # Profile selector
        prof_f = tk.Frame(self, bg=DARK)
        prof_f.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(prof_f, text="Profil:", font=FM, fg=DIM, bg=DARK).pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(
            prof_f, textvariable=self.profile_var,
            state="readonly", font=FM, width=62)
        self.profile_combo.pack(side="left", padx=8)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_change)
        self.lbl_no_match = tk.Label(prof_f, text="", font=FM, fg=WRN, bg=DARK)
        self.lbl_no_match.pack(side="left")

        # Filter bar
        filt_f = tk.Frame(self, bg=DARK)
        filt_f.pack(fill="x", padx=14, pady=(0, 2))
        tk.Label(filt_f, text="Anzeigen:", font=FM, fg=DIM, bg=DARK).pack(side="left")

        self._filter_vars = {}
        for cat, color in [("Memory","#a78bfa"),("CPU","#00d9ff"),
                           ("GPU","#22c55e"),("Power","#f59e0b"),("Boot","#6b7280")]:
            v = tk.BooleanVar(value=True)
            self._filter_vars[cat] = v
            tk.Checkbutton(filt_f, text=cat, variable=v,
                           command=self._refresh_view,
                           bg=DARK, activebackground=DARK,
                           selectcolor=DARK3, fg=color,
                           highlightthickness=0, bd=0,
                           font=("Consolas", 8)).pack(side="left", padx=5)

        tk.Label(filt_f, text="|", fg=BORD, bg=DARK).pack(side="left", padx=4)

        self._only_todo = tk.BooleanVar(value=False)
        tk.Checkbutton(filt_f, text="Nur noch zu erledigende",
                       variable=self._only_todo,
                       command=self._refresh_view,
                       bg=DARK, activebackground=DARK,
                       selectcolor=DARK3, fg=COL_TODO,
                       highlightthickness=0, bd=0,
                       font=("Consolas", 8)).pack(side="left", padx=5)

        self._show_reg = tk.BooleanVar(value=True)
        tk.Checkbutton(filt_f, text="Registry-Tipps",
                       variable=self._show_reg,
                       command=self._refresh_view,
                       bg=DARK, activebackground=DARK,
                       selectcolor=DARK3, fg="#7c3aed",
                       highlightthickness=0, bd=0,
                       font=("Consolas", 8)).pack(side="left", padx=5)

        # Separator
        tk.Frame(self, bg=BORD, height=1).pack(fill="x")

        # Scrollable content
        self._canvas = tk.Canvas(self, bg=DARK, highlightthickness=0)
        _sb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=DARK)
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=_sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        _sb.pack(side="right", fill="y")

        # Bind scroll to canvas AND all children (recursive)
        self._canvas.bind("<MouseWheel>", self._scroll)

    def _scroll(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _bind_scroll_recursive(self, widget):
        widget.bind("<MouseWheel>", self._scroll)
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

    # ── Profile loading ────────────────────────────────────────────────────────

    def _load_profiles(self):
        self._profiles = match_profiles(
            self.hw.cpu_name, self.hw.mb_manufacturer,
            self.hw.mb_product, self.hw.gpu_name)
        if not self._profiles:
            self.lbl_no_match.config(
                text=f"Keine Profile für '{self.hw.cpu_name[:28]}' — generisch empfohlen: XMP/EXPO, ReBAR aktivieren.")
            return
        names = [p.name for p in self._profiles]
        self.profile_combo["values"] = names
        self.profile_combo.set(names[0])
        self._active_idx = 0
        self._refresh_view()
        # Auto-detect on first load
        self._run_detect()

    def _on_profile_change(self, _=None):
        name = self.profile_var.get()
        for i, p in enumerate(self._profiles):
            if p.name == name:
                self._active_idx = i
                break
        self._refresh_view()

    # ── Detection ─────────────────────────────────────────────────────────────

    def _run_detect(self):
        if self._detecting:
            return
        self._detecting = True
        self.btn_detect.config(state="disabled", text="Prüfe...")
        self.lbl_detect_status.config(text="Lese System-Zustand...", fg=DIM)

        def _do():
            results = self.detector.detect_all()
            self._detect_results = results
            self._detecting = False
            self.after(0, self._on_detect_done)

        threading.Thread(target=_do, daemon=True).start()

    def _on_detect_done(self):
        self.btn_detect.config(state="normal", text="⟳  System-Status prüfen")
        active_count = sum(1 for r in self._detect_results.values() if r.active)
        total        = len(self._detect_results)
        self.lbl_detect_status.config(
            text=f"{active_count}/{total} Einstellungen bereits aktiv",
            fg=COL_OK if active_count == total else WRN
        )
        self._refresh_view()

    # ── Render ─────────────────────────────────────────────────────────────────

    def _refresh_view(self):
        for w in self._inner.winfo_children():
            w.destroy()

        if not self._profiles:
            return

        profile  = self._profiles[self._active_idx]
        only_todo = self._only_todo.get()

        cats_order = ["Memory", "CPU", "GPU", "Power", "Boot"]
        cat_colors = {
            "Memory": "#a78bfa", "CPU": "#00d9ff",
            "GPU":    "#22c55e", "Power": "#f59e0b", "Boot": "#6b7280",
        }

        # Profile notes
        if profile.notes:
            nf = tk.Frame(self._inner, bg=DARK3)
            nf.pack(fill="x", padx=8, pady=(8, 4))
            tk.Label(nf, text=f"ℹ  {profile.notes}",
                     font=("Segoe UI", 8), fg="#f59e0b", bg=DARK3,
                     anchor="w", padx=10, pady=5, wraplength=820,
                     justify="left").pack(fill="x")

        # Summary bar (only when detection ran)
        if self._detect_results:
            detected_active = 0
            detected_total  = 0
            for s in profile.settings:
                if s.detect_key and s.detect_key in self._detect_results:
                    detected_total += 1
                    if self._detect_results[s.detect_key].active:
                        detected_active += 1

            sum_f = tk.Frame(self._inner, bg="#0f2217" if detected_active == detected_total else "#1a0f0f")
            sum_f.pack(fill="x", padx=8, pady=(4, 8))
            ratio_txt = f"{detected_active}/{detected_total} prüfbare Einstellungen bereits aktiv"
            ratio_col = COL_OK if detected_active == detected_total else WRN
            tk.Label(sum_f, text=ratio_txt, font=("Consolas", 8, "bold"),
                     fg=ratio_col, bg=sum_f.cget("bg"),
                     anchor="w", padx=10, pady=5).pack(fill="x")

        row_idx = 0
        for cat in cats_order:
            if not self._filter_vars.get(cat, tk.BooleanVar(value=True)).get():
                continue

            settings = [s for s in profile.settings if s.category == cat]
            if not settings:
                continue

            # Apply "only todo" filter
            if only_todo and self._detect_results:
                settings = [
                    s for s in settings
                    if not (s.detect_key and
                            self._detect_results.get(s.detect_key, DetectResult("", False)).active)
                ]
            if not settings:
                continue

            color = cat_colors.get(cat, DIM)
            # Category header
            ch = tk.Frame(self._inner, bg=DARK)
            ch.pack(fill="x", padx=8, pady=(12, 3))
            tk.Label(ch, text=f"── {cat.upper()} ",
                     font=("Consolas", 8, "bold"),
                     fg=color, bg=DARK).pack(side="left")
            tk.Frame(ch, bg=BORD, height=1).pack(side="left", fill="x", expand=True)

            for s in settings:
                self._build_card(s, color, row_idx)
                row_idx += 1

        if row_idx == 0:
            tk.Label(self._inner,
                     text="✓ Alle prüfbaren Einstellungen sind bereits aktiv!",
                     font=("Segoe UI", 11, "bold"),
                     fg=COL_OK, bg=DARK).pack(pady=30)

        # Bind scroll recursively after render
        self._inner.after(80, lambda: self._bind_scroll_recursive(self._inner))

    def _build_card(self, s: BiosSetting, color: str, idx: int):
        # Determine detection status
        detect = self._detect_results.get(s.detect_key) if s.detect_key else None
        if detect is None:
            status_color = COL_UNKNOWN
            status_icon  = "●"
            status_tip   = "Nicht automatisch prüfbar"
        elif detect.active:
            status_color = COL_OK
            status_icon  = "●"
            status_tip   = f"Aktiv: {detect.detected_val}"
        else:
            status_color = COL_TODO
            status_icon  = "●"
            status_tip   = f"Noch einstellen: {detect.note}"

        bg = DARK2 if idx % 2 == 0 else DARK3
        card = tk.Frame(self._inner, bg=bg)
        card.pack(fill="x", padx=8, pady=2)

        # Top row: status dot + name + badges
        top = tk.Frame(card, bg=bg)
        top.pack(fill="x", padx=10, pady=(8, 2))

        # Big status circle
        tk.Label(top, text=status_icon,
                 font=("Consolas", 16),
                 fg=status_color, bg=bg).pack(side="left", padx=(0, 8))

        name_f = tk.Frame(top, bg=bg)
        name_f.pack(side="left", fill="x", expand=True)
        tk.Label(name_f, text=s.name,
                 font=("Segoe UI", 9, "bold"),
                 fg=color, bg=bg, anchor="w").pack(anchor="w")

        # Status tip below name
        tk.Label(name_f, text=status_tip,
                 font=("Consolas", 7),
                 fg=status_color, bg=bg, anchor="w").pack(anchor="w")

        # Badges right
        badge_f = tk.Frame(top, bg=bg)
        badge_f.pack(side="right")
        tk.Label(badge_f, text=f"[{get_impact_color(s.impact) and s.impact.upper()}]",
                 font=("Consolas", 7, "bold"),
                 fg=get_impact_color(s.impact), bg=bg).pack()
        tk.Label(badge_f, text=f"[{s.risk}]",
                 font=("Consolas", 7),
                 fg=get_risk_color(s.risk), bg=bg).pack()

        # Value row: default → recommended
        val_f = tk.Frame(card, bg=bg)
        val_f.pack(fill="x", padx=14, pady=2)
        tk.Label(val_f, text="Standard:", font=FM, fg=DIM, bg=bg).pack(side="left")
        tk.Label(val_f, text=s.default,
                 font=("Consolas", 8), fg="#6b7280", bg=bg).pack(side="left", padx=4)
        tk.Label(val_f, text="→", font=FM, fg=DIM, bg=bg).pack(side="left", padx=6)
        tk.Label(val_f, text="Empfohlen:", font=FM, fg=DIM, bg=bg).pack(side="left")
        tk.Label(val_f, text=s.recommended,
                 font=("Consolas", 8, "bold"),
                 fg=color, bg=bg).pack(side="left", padx=4)

        # BIOS path
        pf = tk.Frame(card, bg=bg)
        pf.pack(fill="x", padx=14, pady=(0, 2))
        tk.Label(pf, text="📍", font=FM, fg=DIM, bg=bg).pack(side="left")
        tk.Label(pf, text=s.path,
                 font=("Consolas", 8), fg="#7c3aed", bg=bg,
                 wraplength=720, justify="left", anchor="w"
                 ).pack(side="left", padx=6)

        # Explanation
        tk.Label(card, text=s.explanation,
                 font=("Segoe UI", 8), fg="#9ca3af", bg=bg,
                 anchor="w", justify="left", wraplength=840
                 ).pack(fill="x", padx=14, pady=(0, 4))

        # Registry tip
        if s.registry_tweak and self._show_reg.get():
            rf = tk.Frame(card, bg="#0d1117", padx=10, pady=4)
            rf.pack(fill="x", padx=14, pady=(0, 6))
            tk.Label(rf, text="🔧 Registry:",
                     font=("Consolas", 7, "bold"),
                     fg="#7c3aed", bg="#0d1117").pack(side="left")
            reg_str = f"{s.registry_tweak}  →  {s.registry_value} = {s.registry_data}"
            tk.Label(rf, text=reg_str,
                     font=("Consolas", 7), fg="#6b7280",
                     bg="#0d1117", wraplength=680).pack(side="left", padx=8)
            def _copy(t=reg_str):
                try: self.clipboard_clear(); self.clipboard_append(t)
                except: pass
            tk.Button(rf, text="📋", command=_copy,
                      font=("Consolas", 7), bg=DARK3, fg=DIM,
                      relief="flat", padx=3, cursor="hand2").pack(side="left")

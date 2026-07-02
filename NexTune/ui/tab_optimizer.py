"""
GameOptimizerPro v2.0 — Optimizer Tab
Layout: Left sidebar with section buttons (like v1.0 tabs but as sidebar),
Right = content area. Everything visible, no hidden sub-tabs.
Sections: Presets | [WIN] Windows | [GAME] Gaming | [NET] Network | Verify | Export/Import
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
from datetime import datetime
from typing import Optional

from ui.widgets import *
from core.tweaks         import ALL_TWEAKS, get_groups, Tweak, get_by_id
from core.tweak_runner   import TweakRunner
from core.tweak_verifier import TweakVerifier, VERIFY_MAP
from core.tweak_presets  import TweakPreset, BUILTIN_PRESETS, get_all_presets
from core.export_import  import ExportImport
from core.hardware       import HardwareInfo


# Section definitions: (key, label, color)
SECTIONS = [
    ("presets",  "⭐  Presets",       "#e53935"),
    ("windows",  "[WIN]  Windows",    "#e53935"),
    ("gaming",   "[GAME] Gaming",     "#f59e0b"),
    ("network",  "[NET]  Network",    "#00b4d8"),
    ("verify",   "[✓]   Verify",      "#22c55e"),
    ("exim",     "[↕]   Export/Import","#7c3aed"),
]


class OptimizerTab(tk.Frame):
    def __init__(self, parent, runner: TweakRunner, hw: HardwareInfo,
                 profiles_dir: str = "profiles", logs_dir: str = "logs", **kw):
        super().__init__(parent, bg="#0d1117", **kw)
        self.runner       = runner
        self.hw           = hw
        self.verifier     = TweakVerifier()
        self.exim         = ExportImport(profiles_dir, logs_dir)
        self._vars:         dict[str, tk.BooleanVar] = {}
        self._user_presets: list[TweakPreset]         = []
        self._section_btns: dict[str, tk.Button]      = {}
        self._section_frames: dict[str, tk.Frame]     = {}
        self._active_section = "presets"
        self._import_data: Optional[dict] = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Top: action bar (Select All / Apply / Revert / DE/EN)
        self._build_action_bar()

        # Body: left sidebar + right content
        body = tk.Frame(self, bg="#0d1117")
        body.pack(fill="both", expand=True)

        self._sidebar = tk.Frame(body, bg="#161b22", width=155)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._content_area = tk.Frame(body, bg="#0d1117")
        self._content_area.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_all_sections()

        # Bottom: status log — uses remaining vertical space
        tk.Frame(self, bg="#2d333b", height=1).pack(fill="x")
        self.log = LogBox(self)
        self.log.pack(fill="both", expand=False, padx=0, pady=0)
        self.log.configure(height=80)

        self._show_section("presets")

    def _build_action_bar(self):
        bar = tk.Frame(self, bg="#161b22")
        bar.pack(fill="x")

        # Left: title
        tk.Label(bar, text="Optimizer", font=("Segoe UI", 11, "bold"),
                 fg="#e53935", bg="#161b22").pack(side="left", padx=12, pady=6)

        # Right: action buttons matching v1.0 style
        for text, cmd, bg, fg in [
            ("[x] Select All",   self._select_all,     "#1c2128", "#9ca3af"),
            ("[ ] Deselect All", self._deselect_all,   "#1c2128", "#9ca3af"),
            (">> Apply Selected",self._apply_selected, "#e53935", "#ffffff"),
            ("↩ Revert All",     self._revert_all,     "#f59e0b", "#000000"),
        ]:
            tk.Button(
                bar, text=text, command=cmd,
                font=("Consolas", 8, "bold"),
                bg=bg, fg=fg, relief="flat",
                padx=10, pady=6, cursor="hand2",
                activebackground=bg
            ).pack(side="right", padx=2, pady=4)

    def _build_sidebar(self):
        tk.Label(self._sidebar, text="SECTIONS",
                 font=("Consolas", 7, "bold"),
                 fg="#4b5563", bg="#161b22"
                 ).pack(pady=(10, 4))

        for key, label, color in SECTIONS:
            btn = tk.Button(
                self._sidebar, text=label,
                font=("Consolas", 8, "bold"),
                bg="#1c2128", fg="#6b7280",
                relief="flat", bd=0,
                padx=10, pady=9,
                cursor="hand2", anchor="w",
                command=lambda k=key: self._show_section(k)
            )
            btn.pack(fill="x", padx=4, pady=1)
            self._section_btns[key] = btn

    def _build_all_sections(self):
        for key, _, _ in SECTIONS:
            f = tk.Frame(self._content_area, bg="#0d1117")
            self._section_frames[key] = f

        self._build_presets(self._section_frames["presets"])
        self._build_tweaks_section(self._section_frames["windows"], "Windows")
        self._build_tweaks_section(self._section_frames["gaming"], "Gaming")
        self._build_tweaks_section(self._section_frames["network"], "Network")
        self._build_verify(self._section_frames["verify"])
        self._build_exim(self._section_frames["exim"])

    def _show_section(self, key: str):
        self._active_section = key
        for k, frame in self._section_frames.items():
            frame.pack_forget()
        self._section_frames[key].pack(fill="both", expand=True)

        # Update sidebar button colors
        for k, btn in self._section_btns.items():
            color = next(c for sk, _, c in SECTIONS if sk == k)
            if k == key:
                btn.config(bg=color, fg="#ffffff")
            else:
                btn.config(bg="#1c2128", fg="#6b7280")

    # ── Presets Section ───────────────────────────────────────────────────────

    def _build_presets(self, p):
        hdr = tk.Frame(p, bg="#0d1117")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(hdr, text="Tweak Presets — 1-Klick Optimierung",
                 font=("Segoe UI", 10, "bold"),
                 fg="#e53935", bg="#0d1117").pack(side="left")
        tk.Button(hdr, text="+ Eigenes Preset",
                  command=self._create_user_preset,
                  font=("Consolas", 8), bg="#7c3aed", fg="white",
                  relief="flat", padx=8, pady=4, cursor="hand2"
                  ).pack(side="right")

        canvas = tk.Canvas(p, bg="#0d1117", highlightthickness=0)
        sb     = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg="#0d1117")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=4, pady=2)
        sb.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e, c=canvas:
                    c.bind_all("<MouseWheel>",
                    lambda ev, cv=c: cv.yview_scroll(int(-1*(ev.delta/120)), "units")))
        canvas.bind("<Leave>", lambda e, c=canvas: c.unbind_all("<MouseWheel>"))
        self._preset_inner = inner
        self._refresh_presets()

    def _refresh_presets(self):
        for w in self._preset_inner.winfo_children():
            w.destroy()
        for preset in get_all_presets(self._user_presets):
            if preset.id == "all_safe":
                from core.tweak_presets import get_all_safe_ids
                preset.tweak_ids = get_all_safe_ids()
            self._build_preset_card(self._preset_inner, preset)

    def _build_preset_card(self, parent, preset: TweakPreset):
        card = tk.Frame(parent, bg="#161b22", pady=8, padx=12)
        card.pack(fill="x", padx=8, pady=3)

        hdr = tk.Frame(card, bg="#161b22")
        hdr.pack(fill="x")

        tk.Label(hdr, text=preset.icon, font=("Segoe UI", 14),
                 fg=preset.color, bg="#161b22").pack(side="left", padx=(0, 8))

        txt = tk.Frame(hdr, bg="#161b22")
        txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=preset.name, font=("Segoe UI", 9, "bold"),
                 fg=preset.color, bg="#161b22", anchor="w").pack(anchor="w")

        n       = len(preset.tweak_ids)
        already = sum(1 for tid in preset.tweak_ids if self.runner.is_applied(tid))
        s_col   = OK if already == n else WRN if already > 0 else DIM
        tk.Label(txt, text=f"{already}/{n} aktiv", font=FM,
                 fg=s_col, bg="#161b22", anchor="w").pack(anchor="w")

        btn_f = tk.Frame(hdr, bg="#161b22")
        btn_f.pack(side="right")
        tk.Button(btn_f, text="▶ Apply",
                  command=lambda p=preset: self._apply_preset(p),
                  font=("Consolas", 8, "bold"),
                  bg=preset.color, fg="#000000" if preset.color in ("#e53935","#f59e0b","#00b4d8") else "#ffffff",
                  relief="flat", padx=8, pady=4, cursor="hand2"
                  ).pack(side="left", padx=2)
        tk.Button(btn_f, text="👁",
                  command=lambda p=preset: self._preview_preset(p),
                  font=("Consolas", 8), bg="#1c2128", fg="#9ca3af",
                  relief="flat", padx=6, pady=4, cursor="hand2"
                  ).pack(side="left", padx=2)
        if not preset.builtin:
            tk.Button(btn_f, text="🗑",
                      command=lambda p=preset: self._delete_user_preset(p),
                      font=("Consolas", 8), bg=ERR, fg=WHT,
                      relief="flat", padx=6, pady=4, cursor="hand2"
                      ).pack(side="left", padx=2)

        tk.Label(card, text=preset.desc, font=("Segoe UI", 8),
                 fg="#6b7280", bg="#161b22", anchor="w",
                 justify="left", wraplength=680).pack(anchor="w", pady=(4, 0))

    def _apply_preset(self, preset):
        to_apply = [get_by_id(tid) for tid in preset.tweak_ids
                    if get_by_id(tid) and not self.runner.is_applied(tid)]
        to_apply = [t for t in to_apply if t]
        if not to_apply:
            messagebox.showinfo("Preset", f"'{preset.name}' ist bereits vollständig aktiv.")
            return
        needs_rb = any(t.requires_reboot for t in to_apply)
        msg = f"Preset '{preset.name}' anwenden?\n{len(to_apply)} Tweak(s) werden aktiviert."
        if needs_rb: msg += "\n\n⚠ Einige benötigen einen Neustart."
        if not messagebox.askyesno("Preset anwenden", msg): return

        def _run():
            self.log.append(f"Preset: {preset.icon} {preset.name}", "header")
            for i, t in enumerate(to_apply):
                ok, out = self.runner.apply(t)
                self.log.append(f"  {t.name}: {'✓' if ok else '✗ '+out[:60]}",
                                "success" if ok else "error")
            self.log.append("Fertig.", "success")
            self.after(0, self._refresh_presets)
        threading.Thread(target=_run, daemon=True).start()

    def _preview_preset(self, preset):
        lines = [f"{preset.icon} {preset.name}\n"]
        for tid in preset.tweak_ids:
            t = get_by_id(tid)
            state = "✓ aktiv" if self.runner.is_applied(tid) else "○ inaktiv"
            lines.append(f"  {state}  {t.name if t else tid}")
        messagebox.showinfo(f"Preset: {preset.name}", "\n".join(lines))

    def _create_user_preset(self):
        name = simpledialog.askstring("Eigenes Preset", "Name:")
        if not name: return
        applied_ids = list(self.runner._applied.keys())
        if not applied_ids:
            messagebox.showinfo("Preset", "Keine aktiven Tweaks — wende zuerst welche an.")
            return
        self._user_presets.append(TweakPreset(
            id=f"user_{name.lower().replace(' ','_')}",
            name=name, icon="⭐",
            desc=f"Eigenes Preset: {len(applied_ids)} aktive Tweaks",
            tweak_ids=applied_ids, color=ACC3, builtin=False))
        self._refresh_presets()

    def _delete_user_preset(self, preset):
        if messagebox.askyesno("Löschen", f"Preset '{preset.name}' löschen?"):
            self._user_presets = [p for p in self._user_presets if p.id != preset.id]
            self._refresh_presets()

    # ── Tweaks Section (Windows / Gaming / Network) ───────────────────────────

    def _build_tweaks_section(self, p, category: str):
        # Header with category name
        hdr = tk.Frame(p, bg="#0d1117")
        hdr.pack(fill="x", padx=12, pady=(10, 2))

        cat_colors = {"Windows": "#e53935", "Gaming": "#f59e0b", "Network": "#00b4d8"}
        color = cat_colors.get(category, ACC)
        tk.Label(hdr, text=f"[{category[:3].upper()}]  {category}",
                 font=("Segoe UI", 10, "bold"),
                 fg=color, bg="#0d1117").pack(side="left")

        # Scrollable tweak list
        canvas = tk.Canvas(p, bg="#0d1117", highlightthickness=0)
        sb     = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        sf     = tk.Frame(canvas, bg="#0d1117")
        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=4, pady=2)
        sb.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e, c=canvas:
                    c.bind_all("<MouseWheel>",
                    lambda ev, cv=c: cv.yview_scroll(int(-1*(ev.delta/120)), "units")))
        canvas.bind("<Leave>", lambda e, c=canvas: c.unbind_all("<MouseWheel>"))

        for group in get_groups(category):
            tweaks = [t for t in ALL_TWEAKS
                      if t.category == category and t.group == group]

            # Group header line
            g_f = tk.Frame(sf, bg="#0d1117")
            g_f.pack(fill="x", padx=8, pady=(10, 2))
            tk.Label(g_f, text=f"-- {group}",
                     font=("Consolas", 8, "bold"),
                     fg=color, bg="#0d1117").pack(side="left")
            tk.Frame(g_f, bg="#2d333b", height=1).pack(
                side="left", fill="x", expand=True, padx=(8, 0))

            for tweak in tweaks:
                if tweak.requires_nvidia and not self.hw.is_nvidia: continue
                if tweak.requires_amd    and not self.hw.is_amd_gpu: continue
                self._build_tweak_row(sf, tweak, color)

    def _build_tweak_row(self, parent, tweak: Tweak, color: str = ACC):
        is_applied = self.runner.is_applied(tweak.id)
        var = tk.BooleanVar(value=is_applied)
        self._vars[tweak.id] = var

        bg = "#161b22" if len(self._vars) % 2 == 0 else "#0d1117"
        row = tk.Frame(parent, bg=bg, pady=3)
        row.pack(fill="x", padx=4, pady=1)

        # Status dot + checkbox
        dot_color = color if is_applied else "#374151"
        tk.Label(row, text="●", font=("Consolas", 10),
                 fg=dot_color, bg=bg).pack(side="left", padx=(6, 0))
        tk.Checkbutton(row, variable=var, bg=bg,
                       activebackground=bg, selectcolor="#1c2128",
                       fg=TXT, highlightthickness=0, bd=0
                       ).pack(side="left", padx=(0, 4))

        # Name + desc
        txt_f = tk.Frame(row, bg=bg)
        txt_f.pack(side="left", fill="x", expand=True)
        tk.Label(txt_f, text=tweak.name,
                 font=("Segoe UI", 9, "bold"),
                 fg=color if is_applied else "#d1d5db",
                 bg=bg, anchor="w").pack(anchor="w")
        tk.Label(txt_f, text=tweak.desc,
                 font=("Segoe UI", 8), fg="#6b7280", bg=bg,
                 anchor="w", wraplength=580, justify="left"
                 ).pack(anchor="w")

        # Right badges
        badge_f = tk.Frame(row, bg=bg)
        badge_f.pack(side="right", padx=8)
        if tweak.requires_reboot:
            tk.Label(badge_f, text="⚠ reboot",
                     font=("Consolas", 7), fg=WRN, bg=bg).pack()
        risk_col = {"safe": "#374151", "moderate": WRN, "advanced": ERR}
        tk.Label(badge_f, text=f"[{tweak.risk}]",
                 font=("Consolas", 7),
                 fg=risk_col.get(tweak.risk, DIM), bg=bg).pack()
        if is_applied:
            tk.Label(badge_f, text="✓ active",
                     font=("Consolas", 7), fg=color, bg=bg).pack()

    # ── Verify Section ────────────────────────────────────────────────────────

    def _build_verify(self, p):
        hdr = tk.Frame(p, bg="#0d1117")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(hdr, text="[✓]  Status Verification",
                 font=("Segoe UI", 10, "bold"),
                 fg="#22c55e", bg="#0d1117").pack(side="left")
        tk.Button(hdr, text="⟳ Jetzt prüfen",
                  command=self._run_verify,
                  font=("Consolas", 8, "bold"),
                  bg="#22c55e", fg="#000000",
                  relief="flat", padx=10, pady=5, cursor="hand2"
                  ).pack(side="right")

        tk.Label(p,
                 text="Liest den tatsächlichen Registry-Zustand und vergleicht mit GameOptimizerPro's Status. "
                      "Findet Tweaks die Windows-Update oder andere Tools rückgängig gemacht haben.",
                 font=("Segoe UI", 8), fg="#6b7280", bg="#0d1117",
                 wraplength=700, justify="left"
                 ).pack(padx=12, anchor="w")

        self.lbl_verify_summary = tk.Label(
            p, text="Noch nicht geprüft — klick auf 'Jetzt prüfen'",
            font=("Consolas", 8), fg="#6b7280", bg="#161b22",
            anchor="w", padx=10, pady=5)
        self.lbl_verify_summary.pack(fill="x", padx=12, pady=4)

        # Results tree
        cols = ("name", "expected", "actual", "status")
        tf = tk.Frame(p, bg="#0d1117")
        tf.pack(fill="both", expand=True, padx=12, pady=2)
        sb2 = ttk.Scrollbar(tf, orient="vertical")
        self.verify_tree = ttk.Treeview(
            tf, columns=cols, show="headings",
            height=14, style="TV.Treeview",
            yscrollcommand=sb2.set)
        sb2.config(command=self.verify_tree.yview)
        for col, label, w in [
            ("name",     "Tweak",       250),
            ("expected", "Erwartet",     90),
            ("actual",   "Tatsächlich",  90),
            ("status",   "Status",      110),
        ]:
            self.verify_tree.heading(col, text=label)
            self.verify_tree.column(col, width=w,
                anchor="w" if col == "name" else "center")
        self.verify_tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.verify_tree.tag_configure("ok",       foreground=OK)
        self.verify_tree.tag_configure("mismatch", foreground=ERR)
        self.verify_tree.tag_configure("unknown",  foreground=DIM)

        fix_f = tk.Frame(p, bg="#0d1117")
        fix_f.pack(fill="x", padx=12, pady=4)
        tk.Button(fix_f, text="🔧 Abweichungen beheben",
                  command=self._fix_mismatches,
                  font=("Consolas", 8, "bold"),
                  bg=WRN, fg="#000", relief="flat",
                  padx=10, pady=5, cursor="hand2"
                  ).pack(side="left")
        self.lbl_fix_result = tk.Label(fix_f, text="", font=FM, fg=DIM, bg="#0d1117")
        self.lbl_fix_result.pack(side="left", padx=12)

    def _run_verify(self):
        self.lbl_verify_summary.config(text="Prüfe System-Zustand...", fg=DIM)
        for row in self.verify_tree.get_children():
            self.verify_tree.delete(row)

        def _do():
            expected = {tid: True for tid in self.runner._applied.keys()}
            for tid in VERIFY_MAP:
                if tid not in expected: expected[tid] = False
            results = self.verifier.verify_all(list(expected.keys()), expected)
            ok_c  = sum(1 for r in results.values() if not r.mismatch and not r.error)
            mis_c = sum(1 for r in results.values() if r.mismatch)
            err_c = sum(1 for r in results.values() if r.error)

            def _update():
                for row in self.verify_tree.get_children():
                    self.verify_tree.delete(row)
                for tid, res in sorted(results.items(),
                                       key=lambda x: x[1].mismatch, reverse=True):
                    t = get_by_id(tid)
                    name = t.name if t else tid
                    if res.error:   tag, status = "unknown",  f"? {res.error[:30]}"
                    elif res.mismatch: tag, status = "mismatch", "⚠ Abweichung!"
                    else:           tag, status = "ok",       "✓ OK"
                    self.verify_tree.insert("", "end", iid=tid,
                        values=(name,
                                "aktiv" if res.expected else "inaktiv",
                                "aktiv" if res.actual   else "inaktiv",
                                status),
                        tags=(tag,))
                col = OK if mis_c == 0 else WRN
                self.lbl_verify_summary.config(
                    text=f"✓ {ok_c} OK   ⚠ {mis_c} Abweichungen   ? {err_c} Fehler   ({len(results)} geprüft)",
                    fg=col)
                # Sync state
                for tid, res in results.items():
                    if not res.error and not res.mismatch:
                        if res.actual and tid not in self.runner._applied:
                            self.runner._applied[tid] = datetime.now().isoformat()
                        elif not res.actual and tid in self.runner._applied:
                            del self.runner._applied[tid]
                self.runner._save_state()
            self.after(0, _update)
        threading.Thread(target=_do, daemon=True).start()

    def _fix_mismatches(self):
        mis = [get_by_id(item) for item in self.verify_tree.get_children()
               if "mismatch" in self.verify_tree.item(item, "tags")]
        mis = [t for t in mis if t]
        if not mis:
            self.lbl_fix_result.config(text="Keine Abweichungen.", fg=DIM)
            return
        if not messagebox.askyesno("Beheben", f"{len(mis)} Tweak(s) erneut anwenden?"):
            return
        def _do():
            ok_c = sum(1 for t in mis if self.runner.apply(t)[0])
            self.after(0, lambda: self.lbl_fix_result.config(
                text=f"{ok_c}/{len(mis)} behoben.", fg=OK))
            self.after(500, self._run_verify)
        threading.Thread(target=_do, daemon=True).start()

    # ── Export / Import Section ───────────────────────────────────────────────

    def _build_exim(self, p):
        tk.Label(p, text="[↕]  Export / Import",
                 font=("Segoe UI", 10, "bold"),
                 fg="#7c3aed", bg="#0d1117"
                 ).pack(padx=12, pady=(10, 6), anchor="w")

        # Export
        exp_f = tk.Frame(p, bg="#161b22", padx=12, pady=10)
        exp_f.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(exp_f, text="EXPORT", font=("Consolas", 8, "bold"),
                 fg="#7c3aed", bg="#161b22").pack(anchor="w")
        tk.Label(exp_f,
                 text="Speichert aktive Tweaks, GPU-Profile und eigene Presets in eine .nextune Datei.",
                 font=("Segoe UI", 8), fg="#6b7280", bg="#161b22",
                 wraplength=680).pack(anchor="w", pady=(2, 6))

        chk_row = tk.Frame(exp_f, bg="#161b22")
        chk_row.pack(anchor="w")
        self.v_exp_tweaks   = tk.BooleanVar(value=True)
        self.v_exp_profiles = tk.BooleanVar(value=True)
        self.v_exp_presets  = tk.BooleanVar(value=True)
        for var, label in [(self.v_exp_tweaks, "Tweaks"),
                           (self.v_exp_profiles, "GPU-Profile"),
                           (self.v_exp_presets, "Presets")]:
            tk.Checkbutton(chk_row, variable=var, text=label,
                           bg="#161b22", activebackground="#161b22",
                           selectcolor="#1c2128", fg=TXT,
                           highlightthickness=0, bd=0
                           ).pack(side="left", padx=8)

        exp_btn_f = tk.Frame(exp_f, bg="#161b22")
        exp_btn_f.pack(anchor="w", pady=(8, 0))
        tk.Button(exp_btn_f, text="💾 Exportieren...",
                  command=self._do_export,
                  font=("Consolas", 8, "bold"),
                  bg="#7c3aed", fg="white",
                  relief="flat", padx=10, pady=5, cursor="hand2"
                  ).pack(side="left")
        self.lbl_exp_result = tk.Label(exp_btn_f, text="", font=FM, fg=DIM, bg="#161b22")
        self.lbl_exp_result.pack(side="left", padx=10)

        # Import
        imp_f = tk.Frame(p, bg="#161b22", padx=12, pady=10)
        imp_f.pack(fill="x", padx=12)
        tk.Label(imp_f, text="IMPORT", font=("Consolas", 8, "bold"),
                 fg="#7c3aed", bg="#161b22").pack(anchor="w")
        tk.Label(imp_f,
                 text="Importiert Einstellungen aus einer .nextune Datei. Vorschau vor dem Apply.",
                 font=("Segoe UI", 8), fg="#6b7280", bg="#161b22",
                 wraplength=680).pack(anchor="w", pady=(2, 6))

        chk_imp = tk.Frame(imp_f, bg="#161b22")
        chk_imp.pack(anchor="w")
        self.v_imp_tweaks   = tk.BooleanVar(value=True)
        self.v_imp_profiles = tk.BooleanVar(value=True)
        self.v_imp_presets  = tk.BooleanVar(value=True)
        for var, label in [(self.v_imp_tweaks, "Tweaks"),
                           (self.v_imp_profiles, "GPU-Profile"),
                           (self.v_imp_presets, "Presets")]:
            tk.Checkbutton(chk_imp, variable=var, text=label,
                           bg="#161b22", activebackground="#161b22",
                           selectcolor="#1c2128", fg=TXT,
                           highlightthickness=0, bd=0
                           ).pack(side="left", padx=8)

        self.lbl_imp_preview = tk.Label(imp_f, text="", font=FM,
                                        fg=DIM, bg="#161b22", anchor="w", justify="left")
        self.lbl_imp_preview.pack(anchor="w", pady=4)

        imp_btn_f = tk.Frame(imp_f, bg="#161b22")
        imp_btn_f.pack(anchor="w", pady=(6, 0))
        tk.Button(imp_btn_f, text="📂 Datei öffnen & Vorschau",
                  command=self._preview_import,
                  font=("Consolas", 8), bg="#1c2128", fg="#9ca3af",
                  relief="flat", padx=10, pady=5, cursor="hand2"
                  ).pack(side="left", padx=(0, 8))
        self.btn_do_import = tk.Button(
            imp_btn_f, text="✓ Import bestätigen",
            command=self._do_import,
            font=("Consolas", 8, "bold"),
            bg=OK, fg="#000", relief="flat",
            padx=10, pady=5, cursor="hand2", state="disabled")
        self.btn_do_import.pack(side="left")
        self.lbl_imp_result = tk.Label(imp_btn_f, text="", font=FM,
                                       fg=DIM, bg="#161b22")
        self.lbl_imp_result.pack(side="left", padx=10)

    def _do_export(self):
        path = filedialog.asksaveasfilename(
            title="Export speichern", defaultextension=".nextune",
            filetypes=[("GameOptimizerPro Export", "*.nextune"), ("JSON", "*.json")])
        if not path: return
        user_pd = [{"id": p.id, "name": p.name, "icon": p.icon,
                    "desc": p.desc, "tweak_ids": p.tweak_ids, "color": p.color}
                   for p in self._user_presets] if self.v_exp_presets.get() else None
        ok, msg = self.exim.export(
            path,
            include_tweaks=self.v_exp_tweaks.get(),
            include_profiles=self.v_exp_profiles.get(),
            include_presets=self.v_exp_presets.get(),
            applied_tweaks=dict(self.runner._applied) if self.v_exp_tweaks.get() else None,
            user_presets=user_pd)
        self.lbl_exp_result.config(text="✓ OK" if ok else "✗ Fehler", fg=OK if ok else ERR)
        if ok: messagebox.showinfo("Export", msg)

    def _preview_import(self):
        path = filedialog.askopenfilename(
            title="Export öffnen",
            filetypes=[("GameOptimizerPro Export", "*.nextune"), ("JSON", "*.json"), ("Alle", "*.*")])
        if not path: return
        ok, data, msg = self.exim.import_file(path)
        if not ok: messagebox.showerror("Import Fehler", msg); return
        self._import_data = data
        self.lbl_imp_preview.config(text=msg, fg=ACC)
        self.btn_do_import.config(state="normal")

    def _do_import(self):
        if not self._import_data: return
        data = self._import_data
        msgs = []
        if self.v_imp_tweaks.get() and data.get("tweaks"):
            self.runner._applied.update(data["tweaks"])
            self.runner._save_state()
            msgs.append(f"{len(data['tweaks'])} Tweaks")
        if self.v_imp_profiles.get() and data.get("gpu_profiles"):
            n_ok, _ = self.exim.apply_imported_profiles(data["gpu_profiles"])
            msgs.append(f"{n_ok} Profile")
        if self.v_imp_presets.get() and data.get("user_presets"):
            for pd in data["user_presets"]:
                self._user_presets.append(TweakPreset(
                    id=pd.get("id",""), name=pd.get("name",""),
                    icon=pd.get("icon","⭐"), desc=pd.get("desc",""),
                    tweak_ids=pd.get("tweak_ids",[]),
                    color=pd.get("color", ACC3), builtin=False))
            msgs.append(f"{len(data['user_presets'])} Presets")
            self._refresh_presets()
        self.lbl_imp_result.config(text="✓ " + ", ".join(msgs), fg=OK)
        messagebox.showinfo("Import", "Import erfolgreich:\n" + "\n".join(f"  • {m}" for m in msgs))
        self._import_data = None
        self.btn_do_import.config(state="disabled")
        self.lbl_imp_preview.config(text="")

    # ── Global actions ────────────────────────────────────────────────────────

    def _select_all(self):
        for v in self._vars.values(): v.set(True)

    def _deselect_all(self):
        for v in self._vars.values(): v.set(False)

    def _apply_selected(self):
        selected = [t for t in ALL_TWEAKS
                    if t.id in self._vars and self._vars[t.id].get()
                    and not self.runner.is_applied(t.id)]
        if not selected:
            messagebox.showinfo("Nichts", "Keine neuen Tweaks ausgewählt.")
            return
        needs_rb = any(t.requires_reboot for t in selected)
        msg = f"{len(selected)} Tweak(s) anwenden?"
        if needs_rb: msg += "\n\n⚠ Einige benötigen einen Neustart."
        if not messagebox.askyesno("Anwenden", msg): return
        def _run():
            self.log.append(f"Wende {len(selected)} Tweak(s) an...", "header")
            for i, t in enumerate(selected):
                ok, out = self.runner.apply(t)
                self.log.append(
                    f"  [{i+1}/{len(selected)}] {t.name}: {'✓' if ok else '✗ '+out[:80]}",
                    "success" if ok else "error")
            self.log.append("Fertig.", "success")
        threading.Thread(target=_run, daemon=True).start()

    def _revert_all(self):
        applied = [t for t in ALL_TWEAKS if self.runner.is_applied(t.id) and t.revert_cmd]
        if not applied:
            messagebox.showinfo("Nichts", "Keine aktiven Tweaks mit Revert-Befehl.")
            return
        if not messagebox.askyesno("Zurücksetzen", f"{len(applied)} Tweak(s) zurücksetzen?"):
            return
        def _run():
            self.log.append(f"Setze {len(applied)} zurück...", "warning")
            for t in applied:
                ok, out = self.runner.revert(t)
                self.log.append(f"  ↩ {t.name}: {'OK' if ok else out[:80]}",
                                "success" if ok else "error")
            self.log.append("Revert abgeschlossen.", "success")
        threading.Thread(target=_run, daemon=True).start()

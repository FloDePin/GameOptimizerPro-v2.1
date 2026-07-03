"""
GameOptimizerPro v2.0 — Startup Manager
Eigenes Fenster das alle Autostart-Einträge auflistet.
Zeigt für jeden Eintrag:
  - Name, Publisher, Pfad
  - Status: Safe / Caution / Critical / Unknown
  - Empfehlung: ob man es deaktivieren kann
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess, os, json, threading
from pathlib import Path

DARK  = "#0d1117"
DARK2 = "#161b22"
DARK3 = "#1c2128"
BORD  = "#2d333b"
ACC   = "#00d9ff"
OK    = "#22c55e"
WRN   = "#f59e0b"
ERR   = "#ef4444"
DIM   = "#6b7280"
TXT   = "#d0d8e8"
WHT   = "#f0f4ff"
FM    = ("Consolas", 9)
FL    = ("Segoe UI", 9)


# ── Known process database ────────────────────────────────────────────────────
# status: "safe" | "caution" | "critical" | "system"
# can_disable: True = problemlos deaktivierbar

KNOWN_PROCESSES = {
    # ── System / Windows ──────────────────────────────────────────────────────
    "SecurityHealthSystray":    ("system",  False, "Windows Security",         "Windows Defender Tray — nicht deaktivieren"),
    "SecurityHealthService":    ("system",  False, "Windows Security",         "Windows Defender Service — kritisch"),
    "WindowsDefender":          ("system",  False, "Microsoft",                "Windows Defender — Systemschutz"),
    "OneDrive":                 ("safe",    True,  "Microsoft",                "Cloud-Sync. Deaktivierbar wenn nicht genutzt"),
    "Teams":                    ("safe",    True,  "Microsoft",                "Microsoft Teams — startet mit Windows. Sicher zu deaktivieren"),
    "MicrosoftTeams":           ("safe",    True,  "Microsoft",                "Microsoft Teams — sicher deaktivierbar"),
    "Slack":                    ("safe",    True,  "Slack Technologies",       "Slack — sicher deaktivierbar wenn nicht täglich genutzt"),
    "Discord":                  ("safe",    True,  "Discord Inc.",             "Discord — sicher deaktivierbar. Manuell starten"),
    "Spotify":                  ("safe",    True,  "Spotify AB",               "Spotify — sicher deaktivierbar"),
    "Steam":                    ("safe",    True,  "Valve Corporation",        "Steam — sicher. Manuell starten beim Gaming"),
    "EpicGamesLauncher":        ("safe",    True,  "Epic Games",               "Epic Launcher — sicher deaktivierbar"),
    "EABackgroundService":      ("caution", True,  "Electronic Arts",          "EA App Hintergrunddienst — deaktivierbar aber EA-Spiele brauchen ihn"),
    "RiotClientServices":       ("safe",    True,  "Riot Games",               "Riot Client — deaktivierbar, startet bei Bedarf"),
    "BattleNet":                ("safe",    True,  "Blizzard Entertainment",   "Battle.net Launcher — sicher deaktivierbar"),
    "upc":                      ("safe",    True,  "Ubisoft",                  "Ubisoft Connect — sicher deaktivierbar"),
    "GalaxyClient":             ("safe",    True,  "CD Projekt",               "GOG Galaxy — sicher deaktivierbar"),
    # ── NVIDIA ────────────────────────────────────────────────────────────────
    "NVDisplay.Container":      ("caution", False, "NVIDIA Corporation",       "NVIDIA Display Container — für OSD/Overlay nötig"),
    "nvcontainer":              ("caution", False, "NVIDIA Corporation",       "NVIDIA Container — Treiber-Komponente"),
    "NvBackend":                ("safe",    True,  "NVIDIA Corporation",       "NVIDIA GeForce Experience Backend — deaktivierbar wenn GFE nicht genutzt"),
    "NvTelemetryContainer":     ("safe",    True,  "NVIDIA Corporation",       "NVIDIA Telemetrie — sicher zu deaktivieren"),
    "NVIDIAGeForceExperience":  ("safe",    True,  "NVIDIA Corporation",       "GeForce Experience — sicher wenn manuell gestartet"),
    # ── AMD ───────────────────────────────────────────────────────────────────
    "RadeonSoftware":           ("safe",    True,  "AMD",                      "AMD Radeon Software — sicher deaktivierbar"),
    "AMDRSServ":                ("caution", False, "AMD",                      "AMD Radeon Service — für Treiberfunktionen nötig"),
    # ── Audio ─────────────────────────────────────────────────────────────────
    "RtkAudUService64":         ("caution", False, "Realtek",                  "Realtek Audio Manager — für Audio-Einstellungen nötig"),
    "RTHDVCPL":                 ("caution", False, "Realtek",                  "Realtek HD Audio — nötig für Audio-Konfiguration"),
    "nahimic":                  ("safe",    True,  "Nahimic / A-Volute",       "Nahimic Audio — deaktivierbar wenn nicht genutzt"),
    "SteelSeriesEngine":        ("safe",    True,  "SteelSeries",              "SteelSeries GG / Engine — deaktivierbar"),
    # ── Peripherals / RGB ─────────────────────────────────────────────────────
    "iCUE":                     ("safe",    True,  "Corsair",                  "Corsair iCUE — deaktivierbar wenn RGB nicht wichtig"),
    "CORSAIR":                  ("safe",    True,  "Corsair",                  "Corsair Software — sicher deaktivierbar"),
    "LGHUBUpdater":             ("safe",    True,  "Logitech",                 "Logitech G Hub — sicher deaktivierbar"),
    "LGHUB":                    ("safe",    True,  "Logitech",                 "Logitech G Hub — deaktivierbar"),
    "RazerCentral":             ("safe",    True,  "Razer Inc.",               "Razer Central — deaktivierbar wenn keine Razer-Geräte im Einsatz"),
    "RazerSynapse":             ("safe",    True,  "Razer Inc.",               "Razer Synapse — deaktivierbar, Makros/DPI-Profile gehen verloren"),
    "SteelSeriesGG":            ("safe",    True,  "SteelSeries",              "SteelSeries GG — sicher deaktivierbar"),
    "ASUS":                     ("safe",    True,  "ASUS",                     "ASUS Software — meist sicher deaktivierbar"),
    "ArmouryCrate":             ("safe",    True,  "ASUS",                     "ASUS Armoury Crate — sicher deaktivierbar"),
    # ── System Tools ──────────────────────────────────────────────────────────
    "ctfmon":                   ("system",  False, "Microsoft",                "Text Input / Spracherkennung — Systemkomponente"),
    "sihost":                   ("system",  False, "Microsoft",                "Shell Infrastructure Host — kritische Systemkomponente"),
    "taskhostw":                ("system",  False, "Microsoft",                "Task Host — Windows-Systemdienst"),
    "MSIAfterburner":           ("safe",    True,  "MSI / RivaTuner",          "MSI Afterburner — sicher deaktivierbar, OC-Profile müssen dann manuell geladen werden"),
    "RTSS":                     ("safe",    True,  "RivaTuner",                "RivaTuner Statistics Server — für FPS-Counter nötig"),
    "HWiNFO64":                 ("safe",    True,  "REALiX",                   "HWiNFO — sicher deaktivierbar"),
    "MSICenter":                ("safe",    True,  "MSI",                      "MSI Center — sicher deaktivierbar"),
    "GigabyteControlCenter":    ("safe",    True,  "Gigabyte",                 "Gigabyte Control Center — sicher deaktivierbar"),
    "EasyTune":                 ("safe",    True,  "Gigabyte",                 "Gigabyte EasyTune — sicher deaktivierbar"),
    # ── Security / Antivirus ──────────────────────────────────────────────────
    "MsMpEng":                  ("system",  False, "Microsoft",                "Windows Defender Antivirus — nicht deaktivieren"),
    "avgnt":                    ("caution", True,  "Avira",                    "Avira Antivirus — nur wenn anderer AV vorhanden"),
    "avastui":                  ("caution", True,  "Avast",                    "Avast Antivirus — nur wenn anderer AV vorhanden"),
    "mcshield":                 ("caution", True,  "McAfee",                   "McAfee — deaktivierbar wenn Windows Defender genutzt wird"),
}


STATUS_CONFIG = {
    "safe":     (OK,  "✓ Safe",     "Problemlos deaktivierbar"),
    "caution":  (WRN, "⚠ Caution",  "Deaktivierbar aber mit Einschränkungen"),
    "critical": (ERR, "✗ Critical", "NICHT deaktivieren — Systemfunktion"),
    "system":   (ERR, "⚙ System",   "Windows-Systemkomponente — nicht deaktivieren"),
    "unknown":  (DIM, "? Unknown",  "Unbekannt — recherchieren vor Deaktivierung"),
}


class StartupManagerWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("GameOptimizerPro — Startup Manager")
        self.geometry("1050x680")
        self.minsize(900, 500)
        self.configure(bg=DARK)
        self.resizable(True, True)

        # Dark titlebar style attempt
        try:
            self.wm_attributes("-alpha", 1.0)
        except: pass

        self._entries: list[dict] = []
        self._filtered: list[dict] = []
        self._filter_status = "all"
        self._sort_col = "name"
        self._sort_rev = False

        self._build()
        self.after(200, self._load_entries)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=DARK2, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🚀  Startup Manager",
                 font=("Segoe UI", 13, "bold"),
                 fg=ACC, bg=DARK2).pack(side="left", padx=16, pady=8)
        tk.Label(hdr,
                 text="Autostart-Einträge aus Registry + Task Manager",
                 font=FL, fg=DIM, bg=DARK2).pack(side="left")

        self.lbl_count = tk.Label(hdr, text="", font=FM, fg=DIM, bg=DARK2)
        self.lbl_count.pack(side="right", padx=16)

        tk.Button(hdr, text="⟳ Aktualisieren",
                  command=self._load_entries,
                  font=FM, bg=DARK3, fg=TXT,
                  relief="flat", padx=10, pady=4, cursor="hand2"
                  ).pack(side="right", padx=4)

        # Filter + search bar
        filt = tk.Frame(self, bg=DARK)
        filt.pack(fill="x", padx=10, pady=6)

        tk.Label(filt, text="Filter:", font=FM, fg=DIM, bg=DARK).pack(side="left")
        self._filter_var = tk.StringVar(value="all")
        for val, label, color in [
            ("all",     "Alle",     TXT),
            ("safe",    "Safe",     OK),
            ("caution", "Caution",  WRN),
            ("system",  "System",   ERR),
            ("unknown", "Unknown",  DIM),
        ]:
            tk.Radiobutton(
                filt, text=label, variable=self._filter_var, value=val,
                command=self._apply_filter,
                bg=DARK, activebackground=DARK,
                selectcolor=DARK3, fg=color,
                highlightthickness=0, font=FM
            ).pack(side="left", padx=6)

        tk.Label(filt, text="|", fg=BORD, bg=DARK).pack(side="left", padx=4)
        tk.Label(filt, text="Suche:", font=FM, fg=DIM, bg=DARK).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(filt, textvariable=self._search_var,
                 font=FM, bg=DARK3, fg=TXT,
                 insertbackground=ACC, relief="flat",
                 highlightthickness=1,
                 highlightbackground=BORD,
                 highlightcolor=ACC, width=22
                 ).pack(side="left", padx=6)

        # Treeview
        style = ttk.Style()
        style.configure("SM.Treeview",
            background=DARK2, foreground=TXT,
            fieldbackground=DARK2, rowheight=28,
            font=FM, borderwidth=0)
        style.configure("SM.Treeview.Heading",
            background=DARK3, foreground=ACC,
            font=("Consolas", 8, "bold"), relief="flat")
        style.map("SM.Treeview",
            background=[("selected", "#7c3aed")],
            foreground=[("selected", WHT)])

        tree_f = tk.Frame(self, bg=DARK)
        tree_f.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        sb = ttk.Scrollbar(tree_f, orient="vertical")
        cols = ("status", "name", "publisher", "recommendation", "path")
        self.tree = ttk.Treeview(
            tree_f, columns=cols, show="headings",
            style="SM.Treeview", yscrollcommand=sb.set
        )
        sb.config(command=self.tree.yview)

        headers = [
            ("status",         "Status",        100),
            ("name",           "Name",           180),
            ("publisher",      "Publisher",      150),
            ("recommendation", "Empfehlung",     280),
            ("path",           "Pfad",           260),
        ]
        for col, label, w in headers:
            self.tree.heading(col, text=label,
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w,
                anchor="center" if col == "status" else "w",
                minwidth=60)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Color tags
        self.tree.tag_configure("safe",    foreground=OK)
        self.tree.tag_configure("caution", foreground=WRN)
        self.tree.tag_configure("system",  foreground=ERR)
        self.tree.tag_configure("critical",foreground=ERR)
        self.tree.tag_configure("unknown", foreground=DIM)

        # Bottom action bar
        act = tk.Frame(self, bg=DARK2, height=44)
        act.pack(fill="x")
        act.pack_propagate(False)

        self.lbl_selected = tk.Label(act, text="Kein Eintrag ausgewählt",
                                     font=FM, fg=DIM, bg=DARK2)
        self.lbl_selected.pack(side="left", padx=14, pady=8)

        tk.Button(act, text="ⓘ  Details",
                  command=self._show_details,
                  font=FM, bg=DARK3, fg=TXT,
                  relief="flat", padx=12, pady=6, cursor="hand2"
                  ).pack(side="right", padx=4, pady=4)

        tk.Button(act, text="⊘  Im Task Manager öffnen",
                  command=self._open_task_manager,
                  font=FM, bg=DARK3, fg=TXT,
                  relief="flat", padx=12, pady=6, cursor="hand2"
                  ).pack(side="right", padx=4, pady=4)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<MouseWheel>", lambda e: None)

        # Loading label
        self.lbl_loading = tk.Label(tree_f,
            text="Lade Autostart-Einträge...",
            font=("Segoe UI", 11), fg=DIM, bg=DARK2)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_entries(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._entries = []
        self.lbl_count.config(text="Lade...")
        threading.Thread(target=self._fetch_entries, daemon=True).start()

    def _fetch_entries(self):
        """Read startup entries from registry via PowerShell."""
        ps_cmd = r'''
$entries = @()

# HKCU Run
$path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
if (Test-Path $path) {
    Get-ItemProperty $path | ForEach-Object {
        $_.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
            $entries += [PSCustomObject]@{
                Name    = $_.Name
                Command = $_.Value
                Source  = "HKCU\\Run"
            }
        }
    }
}

# HKLM Run
$path = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
if (Test-Path $path) {
    Get-ItemProperty $path | ForEach-Object {
        $_.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
            $entries += [PSCustomObject]@{
                Name    = $_.Name
                Command = $_.Value
                Source  = "HKLM\\Run"
            }
        }
    }
}

# HKLM Run (32-bit)
$path = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
if (Test-Path $path) {
    Get-ItemProperty $path | ForEach-Object {
        $_.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
            $entries += [PSCustomObject]@{
                Name    = $_.Name
                Command = $_.Value
                Source  = "HKLM\\Run (x86)"
            }
        }
    }
}

$entries | ConvertTo-Json -Compress
'''
        entries = []
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0

            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive",
                 "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass",
                 "-Command", ps_cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=flags, startupinfo=si
            )
            raw = result.stdout.strip()
            if raw and raw != "null":
                data = json.loads(raw)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    name    = item.get("Name", "")
                    command = item.get("Command", "")
                    source  = item.get("Source", "")

                    # Look up in known DB
                    info = self._lookup(name, command)
                    entries.append({
                        "name":     name,
                        "command":  command,
                        "source":   source,
                        "status":   info[0],
                        "can_disable": info[1],
                        "publisher": info[2],
                        "recommendation": info[3],
                    })
        except Exception as e:
            entries.append({
                "name": f"Fehler: {e}", "command": "", "source": "",
                "status": "unknown", "can_disable": False,
                "publisher": "", "recommendation": "PowerShell-Fehler beim Laden"
            })

        self._entries = entries
        self.after(0, self._apply_filter)

    def _lookup(self, name: str, command: str) -> tuple:
        """Match name/command against known process database."""
        name_upper = name.upper()
        cmd_upper  = command.upper()

        for key, info in KNOWN_PROCESSES.items():
            if key.upper() in name_upper or key.upper() in cmd_upper:
                status, can_dis, publisher, rec = info
                return status, can_dis, publisher, rec

        # Heuristics for unknowns
        if any(s in cmd_upper for s in ["WINDOWS\\SYSTEM32", "WINDOWS\\SYSWOW64"]):
            return "system", False, "Microsoft / System", "Systemdatei — nicht deaktivieren ohne zu recherchieren"
        if "UPDATE" in name_upper or "UPDATER" in name_upper:
            return "safe", True, "Unbekannt", "Updater-Prozess — sicher deaktivierbar, Updates dann manuell"
        if any(s in name_upper for s in ["TRAY", "HELPER", "AGENT", "LAUNCHER"]):
            return "safe", True, "Unbekannt", "Hintergrundprozess — meist sicher deaktivierbar"

        return "unknown", None, "Unbekannt", "Unbekannt — vor Deaktivierung recherchieren"

    # ── Filter & display ──────────────────────────────────────────────────────

    def _apply_filter(self, *_):
        filt   = self._filter_var.get()
        search = self._search_var.get().lower()

        self._filtered = [
            e for e in self._entries
            if (filt == "all" or e["status"] == filt)
            and (not search or search in e["name"].lower()
                 or search in e.get("publisher", "").lower()
                 or search in e["command"].lower())
        ]

        for row in self.tree.get_children():
            self.tree.delete(row)

        for e in self._filtered:
            status, _, label = STATUS_CONFIG.get(e["status"], (DIM, "?", "?"))
            can = "✓ Deaktivierbar" if e["can_disable"] else ("✗ Nicht empfohlen" if e["can_disable"] is False else "? Unbekannt")
            # Truncate command path
            cmd = e["command"]
            if len(cmd) > 55:
                cmd = "..." + cmd[-52:]

            self.tree.insert("", "end",
                values=(
                    label,
                    e["name"],
                    e.get("publisher", ""),
                    e["recommendation"],
                    cmd,
                ),
                tags=(e["status"],)
            )

        total = len(self._entries)
        shown = len(self._filtered)
        self.lbl_count.config(
            text=f"{shown} von {total} Einträgen | "
                 f"{sum(1 for e in self._entries if e['status']=='safe')} Safe  "
                 f"{sum(1 for e in self._entries if e['status']=='caution')} Caution  "
                 f"{sum(1 for e in self._entries if e['status'] in ('system','critical'))} System"
        )

    def _sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        self._entries.sort(key=lambda e: str(e.get(col, "")).lower(),
                           reverse=self._sort_rev)
        self._apply_filter()

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx < len(self._filtered):
            e = self._filtered[idx]
            status_cfg = STATUS_CONFIG.get(e["status"], (DIM, "?", "?"))
            self.lbl_selected.config(
                text=f"{e['name']}  |  {status_cfg[1]}  |  {e.get('publisher','?')}",
                fg=status_cfg[0]
            )

    def _show_details(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Details", "Keinen Eintrag ausgewählt.")
            return
        idx = self.tree.index(sel[0])
        if idx >= len(self._filtered):
            return
        e = self._filtered[idx]
        status_cfg = STATUS_CONFIG.get(e["status"], (DIM, "?", "Unbekannt"))

        detail = (
            f"Name:          {e['name']}\n"
            f"Publisher:     {e.get('publisher', 'Unbekannt')}\n"
            f"Status:        {status_cfg[1]}\n"
            f"Deaktivierbar: {'✓ Ja' if e['can_disable'] else ('✗ Nein' if e['can_disable'] is False else '? Unbekannt')}\n"
            f"Quelle:        {e.get('source', '?')}\n\n"
            f"Empfehlung:\n  {e['recommendation']}\n\n"
            f"Pfad:\n  {e['command']}"
        )
        messagebox.showinfo(f"Details: {e['name']}", detail)

    def _open_task_manager(self):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 1
            subprocess.Popen(
                ["taskmgr.exe"],
                startupinfo=si,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

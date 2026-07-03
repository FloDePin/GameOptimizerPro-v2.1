"""
GameOptimizerPro v2.1 — Per-Game Profile Monitor
Überwacht laufende Prozesse via psutil.
Wenn ein bekanntes Spiel startet → lädt das zugewiesene GPU-Profil.
Wenn das Spiel schließt → lädt das "default" Profil zurück.
Ressourcenschonend: prüft nur alle 3s, nur wenn Prozessliste sich geändert hat.
"""

import json, threading, time, os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Callable


@dataclass
class GameEntry:
    exe:          str    # z.B. "Cyberpunk2077.exe" (case-insensitive)
    display_name: str    # z.B. "Cyberpunk 2077"
    profile_name: str    # Name des GOP GPU-Profils
    restore_profile: str = "__tray_default__"  # Profil nach Spielende
    enabled:      bool = True


class GameMonitor:
    GAMES_FILE = "profiles/game_profiles.json"
    CHECK_INTERVAL = 3  # Sekunden zwischen Checks

    # Bekannte Spiele — vorgefüllt für komfort
    DEFAULT_GAMES = [
        GameEntry("Cyberpunk2077.exe",    "Cyberpunk 2077",          ""),
        GameEntry("cs2.exe",              "Counter-Strike 2",        ""),
        GameEntry("r5apex.exe",           "Apex Legends",            ""),
        GameEntry("RainbowSix.exe",       "Rainbow Six Siege",       ""),
        GameEntry("Overwatch.exe",        "Overwatch 2",             ""),
        GameEntry("Valorant-Win64-Shipping.exe", "Valorant",         ""),
        GameEntry("EscapeFromTarkov.exe", "Escape From Tarkov",      ""),
        GameEntry("RocketLeague.exe",     "Rocket League",           ""),
        GameEntry("FortniteClient-Win64-Shipping.exe", "Fortnite",   ""),
        GameEntry("GTA5.exe",             "GTA V",                   ""),
        GameEntry("eldenring.exe",        "Elden Ring",              ""),
        GameEntry("Witcher3.exe",         "The Witcher 3",           ""),
        GameEntry("DOOM.exe",             "DOOM Eternal",            ""),
        GameEntry("bf2042.exe",           "Battlefield 2042",        ""),
        GameEntry("HogwartsLegacy.exe",   "Hogwarts Legacy",         ""),
    ]

    def __init__(self, base_dir: str, ab, pm, cr=None):
        self.base    = Path(base_dir)
        self.ab      = ab
        self.pm      = pm
        self.cr      = cr
        self._games: list[GameEntry] = []
        self._active_game: Optional[str] = None  # currently running exe
        self._running    = False
        self._thread: Optional[threading.Thread] = None
        self._last_procs: set[str] = set()

        # Callbacks
        self._on_game_start: Optional[Callable] = None
        self._on_game_stop:  Optional[Callable] = None

        self._load_games()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _games_path(self) -> Path:
        return self.base / self.GAMES_FILE

    def _load_games(self):
        path = self._games_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._games = [GameEntry(**g) for g in data]
                return
            except:
                pass
        # First run: use defaults (no profile assigned yet)
        self._games = [GameEntry(g.exe, g.display_name, g.profile_name)
                       for g in self.DEFAULT_GAMES]
        self._save_games()

    def _save_games(self):
        self._games_path().parent.mkdir(parents=True, exist_ok=True)
        self._games_path().write_text(
            json.dumps([asdict(g) for g in self._games], indent=2),
            encoding="utf-8"
        )

    # ── Game list management ──────────────────────────────────────────────────

    def get_games(self) -> list[GameEntry]:
        return list(self._games)

    def add_game(self, exe: str, display_name: str, profile_name: str):
        # Avoid duplicates
        exe_lower = exe.lower()
        for g in self._games:
            if g.exe.lower() == exe_lower:
                g.display_name  = display_name
                g.profile_name  = profile_name
                self._save_games()
                return
        self._games.append(GameEntry(exe, display_name, profile_name))
        self._save_games()

    def update_game(self, exe: str, profile_name: str,
                    enabled: bool = True, restore: str = "__tray_default__"):
        for g in self._games:
            if g.exe.lower() == exe.lower():
                g.profile_name  = profile_name
                g.enabled       = enabled
                g.restore_profile = restore
                self._save_games()
                return

    def remove_game(self, exe: str):
        self._games = [g for g in self._games if g.exe.lower() != exe.lower()]
        self._save_games()

    # ── Monitor loop ──────────────────────────────────────────────────────────

    def on_game_start(self, cb: Callable): self._on_game_start = cb
    def on_game_stop(self,  cb: Callable): self._on_game_stop  = cb

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _get_process_names(self) -> set[str]:
        """Get current process names (lowercase). Lightweight psutil call."""
        try:
            import psutil
            return {p.name().lower() for p in psutil.process_iter(['name'])
                    if p.info['name']}
        except:
            return set()

    def _loop(self):
        while self._running:
            try:
                procs = self._get_process_names()

                # Only act if process list changed
                if procs == self._last_procs:
                    time.sleep(self.CHECK_INTERVAL)
                    continue
                self._last_procs = procs

                # Check each enabled game
                found_game = None
                for game in self._games:
                    if not game.enabled or not game.profile_name:
                        continue
                    if game.exe.lower() in procs:
                        found_game = game
                        break

                if found_game and self._active_game != found_game.exe.lower():
                    # New game started
                    self._active_game = found_game.exe.lower()
                    self._apply_profile(found_game.profile_name)
                    if self._on_game_start:
                        self._on_game_start(found_game)

                elif not found_game and self._active_game:
                    # Active game stopped
                    stopped_exe = self._active_game
                    self._active_game = None
                    # Find restore profile
                    for game in self._games:
                        if game.exe.lower() == stopped_exe:
                            self._apply_profile(game.restore_profile)
                            break
                    if self._on_game_stop:
                        self._on_game_stop(stopped_exe)

            except Exception as e:
                pass  # Never crash the monitor thread

            time.sleep(self.CHECK_INTERVAL)

    def _apply_profile(self, profile_name: str):
        """Apply a GPU profile by name."""
        if not profile_name or not self.ab.available:
            return
        try:
            p = self.pm.load(profile_name)
            if p:
                threading.Thread(
                    target=lambda: (
                        self.ab.write_and_apply(2, p),
                        self.cr.save_last_applied(p.to_dict()) if self.cr else None
                    ),
                    daemon=True
                ).start()
        except:
            pass

    @property
    def active_game(self) -> Optional[str]:
        return self._active_game

    @property
    def is_running(self) -> bool:
        return self._running

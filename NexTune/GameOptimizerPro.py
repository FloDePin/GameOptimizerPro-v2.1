"""
GameOptimizerPro v2.0 — All-in-one PC & GPU Optimizer
Entry point: crash recovery check → startup profile load → tray + window.
"""

import os, sys, time, threading, tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Optional

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from core.hardware        import detect as detect_hw
from core.nvtune_core     import GpuMonitor, AfterburnerController, ProfileManager
from core.nvtune_tuner    import AutoTuner, TunerConfig
from core.tweak_runner    import TweakRunner
from core.crash_recovery  import CrashRecovery
from core.startup_loader  import StartupLoader
from ui.main_window import GameOptimizerWindow


def is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except:
        return False


def relaunch_admin():
    import ctypes
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv), None, 1
    )
    sys.exit(0)


def make_icon():
    try:
        from PIL import Image, ImageDraw
        sz = 64
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        d.ellipse([1, 1, sz - 1, sz - 1], fill=(10, 12, 20, 230))
        # "N" letterform
        d.rectangle([14, 14, 22, 50], fill=(0, 217, 255, 255))
        d.rectangle([42, 14, 50, 50], fill=(0, 217, 255, 255))
        d.polygon([(22, 14), (42, 50), (42, 38), (22, 14)],
                  fill=(0, 217, 255, 255))
        return img
    except ImportError:
        try:
            from PIL import Image
            return Image.new("RGB", (64, 64), (0, 217, 255))
        except:
            return None


class GameOptimizerApp:
    def __init__(self):
        logs_dir = str(BASE / "logs")
        Path(logs_dir).mkdir(parents=True, exist_ok=True)

        self.hw  = detect_hw()
        self.monitor = GpuMonitor()
        self.ab      = AfterburnerController()
        self.pm      = ProfileManager(str(BASE / "profiles"))
        self.cr      = CrashRecovery(logs_dir)
        self.tuner   = AutoTuner(
            self.monitor, self.ab, self.pm, TunerConfig(),
            log_dir=logs_dir,
            crash_recovery=self.cr,
        )
        self.runner  = TweakRunner(log_dir=logs_dir)
        self.sl      = StartupLoader(logs_dir, self.ab, self.pm, self.cr)

        self._window: Optional[GameOptimizerWindow] = None
        self._tray    = None
        self._running = True

        # Cached stats for tray tooltip
        self._temp  = 0
        self._volt  = 0.0
        self._power = 0.0
        self._clk   = 0.0
        self._gpu   = "GPU"

    # ── Startup sequence ──────────────────────────────────────────────────────

    def startup(self):
        """Run crash check and startup profile load before opening window."""
        # 1. Crash recovery
        crashed = self.sl.check_and_handle_crash(
            on_crash_detected=self._show_crash_dialog
        )

        # 2. Load startup profile (if no crash, or after recovery)
        if self.ab.available:
            ok, msg = self.sl.load_startup_profile()
            if ok:
                print(f"[GameOptimizerPro] {msg}")

    def _show_crash_dialog(self, message: str):
        """Show crash recovery dialog in main thread."""
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("GameOptimizerPro v2.0 — Crash erkannt", message)
            root.destroy()
        except:
            pass

    # ── Stats loop ────────────────────────────────────────────────────────────

    def _stats_loop(self):
        while self._running:
            try:
                s = self.monitor.read()
                self._temp  = s.temp
                self._volt  = s.voltage_mv
                self._power = s.gpu_power_w
                self._clk   = s.core_mhz
                self._gpu   = s.name[:22]
                if self._tray:
                    volt_s = f" | {s.voltage_mv:.0f}mV" if s.voltage_mv > 0 else ""
                    try:
                        self._tray.title = (
                            f"GOP v2.0 | {self._gpu}\n"
                            f"{s.temp}°C | {s.core_mhz:.0f}MHz"
                            f"{volt_s} | {s.gpu_power_w:.0f}W"
                        )
                    except:
                        pass
            except:
                pass
            time.sleep(4)

    # ── Tray menu ─────────────────────────────────────────────────────────────

    def _build_menu(self):
        try:
            import pystray
            from pystray import MenuItem as MI, Menu
        except:
            return None

        profiles = [p for p in self.pm.list_all()
                    if not p.name.startswith("__")]

        def apply_fn(name):
            def _do():
                p = self.pm.load(name)
                if p and self.ab.available:
                    def _apply():
                        self.ab.write_and_apply(2, p)
                        self.cr.save_last_applied(p.to_dict())
                    threading.Thread(target=_apply, daemon=True).start()
            return _do

        p_items = [
            MI(
                f"{'✓' if p.is_stable else '⚠'} {p.name} "
                f"[+{p.core_offset_mhz}MHz | {p.power_limit_pct}%]",
                apply_fn(p.name)
            )
            for p in sorted(profiles, key=lambda x: x.name)
        ] or [MI("Keine Profile vorhanden", None, enabled=False)]

        volt_s     = f"{self._volt:.0f}mV  |  " if self._volt > 0 else ""
        stats_lbl  = (
            f"{self._temp}°C  |  {self._clk:.0f}MHz  |  "
            f"{volt_s}{self._power:.0f}W"
        )

        return Menu(
            MI("⚡ GameOptimizerPro öffnen",     lambda i, _: self._open()),
            Menu.SEPARATOR,
            MI("GPU Profil ▶",          Menu(*p_items)),
            MI("GPU auf Stock zurücksetzen",
               lambda i, _: self._reset_gpu()),
            Menu.SEPARATOR,
            MI(stats_lbl, None, enabled=False),
            Menu.SEPARATOR,
            MI("Beenden", lambda i, _: self._exit()),
        )

    # ── Window management ─────────────────────────────────────────────────────

    def _open(self):
        if self._window:
            try:
                self._window.deiconify()
                self._window.lift()
                self._window.focus_force()
                return
            except:
                pass

        def _create():
            self._window = GameOptimizerWindow(
                self.hw, self.monitor, self.ab, self.pm,
                self.tuner, self.runner,
                startup_loader=self.sl,
            )
            self._window.protocol("WM_DELETE_WINDOW", self._hide)
            self._window.mainloop()
            self._window = None

        threading.Thread(target=_create, daemon=True).start()

    def _hide(self):
        if self._window:
            try:
                self._window.withdraw()
            except:
                pass

    def _reset_gpu(self):
        def _do():
            self.ab.reset_to_stock()
            _, _, mx = self.monitor.get_power_constraints()
            if mx > 0:
                self.monitor.set_power_limit(mx)
        threading.Thread(target=_do, daemon=True).start()

    def _menu_refresh(self):
        while self._running:
            time.sleep(20)
            if self._tray:
                try:
                    self._tray.menu = self._build_menu()
                    self._tray.update_menu()
                except:
                    pass

    def _exit(self):
        self._running = False
        if self._tray:
            try:
                self._tray.stop()
            except:
                pass
        self.monitor.close()
        if self._window:
            try:
                self._window.destroy()
            except:
                pass
        sys.exit(0)

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        # Crash check + startup profile in background
        threading.Thread(target=self.startup, daemon=True).start()
        threading.Thread(target=self._stats_loop,   daemon=True).start()
        threading.Thread(target=self._menu_refresh,  daemon=True).start()

        try:
            import pystray
            icon_img = make_icon()
            if not icon_img:
                self._run_window_only()
                return

            self._tray = pystray.Icon(
                "GameOptimizerPro", icon_img, "GameOptimizerPro",
                menu=self._build_menu()
            )

            def setup(icon):
                icon.visible = True
                self._open()

            self._tray.run(setup=setup)

        except ImportError:
            self._run_window_only()

    def _run_window_only(self):
        self._window = GameOptimizerWindow(
            self.hw, self.monitor, self.ab, self.pm,
            self.tuner, self.runner,
            startup_loader=self.sl,
        )
        self._window.protocol("WM_DELETE_WINDOW", self._window.on_close)
        self._window.mainloop()


def main():
    if os.name == "nt" and not is_admin():
        root = tk.Tk()
        root.withdraw()
        ans = messagebox.askyesno(
            "GameOptimizerPro v2.0 — Admin erforderlich",
            "GameOptimizerPro benötigt Administrator-Rechte für:\n"
            "  • Windows Registry Tweaks\n"
            "  • GPU Power Limit Kontrolle\n"
            "  • Afterburner Profil-Schreiben\n\n"
            "Als Administrator neu starten?"
        )
        root.destroy()
        if ans:
            relaunch_admin()

    GameOptimizerApp().run()


if __name__ == "__main__":
    main()

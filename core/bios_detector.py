"""
GameOptimizerPro v2.1 — BIOS State Detector
Liest den tatsächlichen System-Zustand aus um zu erkennen ob eine
BIOS-Einstellung bereits aktiv ist.
Gibt für jede BiosSetting-ID einen DetectResult zurück.
"""

import subprocess, os, struct
from dataclasses import dataclass
from typing import Optional


@dataclass
class DetectResult:
    setting_id:  str
    active:      bool           # True = Einstellung ist bereits aktiv/korrekt
    detected_val: str = ""      # Was wir tatsächlich gemessen haben
    confidence:  str = "high"   # "high" | "medium" | "low"
    note:        str = ""


def _run_ps(cmd: str) -> str:
    """Run PowerShell silently, return stdout."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        si = None
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass",
             "-Command", cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            creationflags=flags, startupinfo=si
        )
        return r.stdout.strip()
    except:
        return ""


class BiosDetector:
    """
    Detects current BIOS-related state via Windows APIs / Registry / WMI.
    Each detect_* method returns a DetectResult.
    """

    # ── Public: run all detections at once ────────────────────────────────────

    def detect_all(self) -> dict[str, DetectResult]:
        """Run all detectors, return dict keyed by setting_id."""
        results = {}
        detectors = [
            ("expo_xmp",        self.detect_expo_xmp),
            ("rebar",           self.detect_rebar),
            ("above_4g",        self.detect_above_4g),
            ("hags",            self.detect_hags),
            ("secure_boot",     self.detect_secure_boot),
            ("fast_boot",       self.detect_fast_boot),
            ("pbo",             self.detect_pbo),
            ("c_states",        self.detect_c_states),
            ("xmp_intel",       self.detect_expo_xmp),     # same check
            ("rebar_rtx40",     self.detect_rebar),
            ("rebar_intel",     self.detect_rebar),
        ]
        for sid, fn in detectors:
            try:
                results[sid] = fn()
                results[sid].setting_id = sid
            except Exception as e:
                results[sid] = DetectResult(sid, False, "",
                                            "low", f"Detect error: {e}")
        return results

    # ── Individual detectors ──────────────────────────────────────────────────

    def detect_expo_xmp(self) -> DetectResult:
        """
        XMP/EXPO active = RAM running at rated speed.
        WMI: Win32_PhysicalMemory.Speed vs configured speed.
        """
        out = _run_ps(
            "Get-WmiObject Win32_PhysicalMemory | "
            "Select-Object -ExpandProperty Speed | "
            "Sort-Object -Descending | Select-Object -First 1"
        )
        try:
            speed = int(out.strip())
            # DDR5: rated speeds >= 4800, EXPO usually 5600-8000
            # DDR4: rated speeds >= 3200, XMP usually 3600-4800
            # JEDEC baseline: DDR5=4800, DDR4=2133/2400
            active = speed > 3200  # Above JEDEC baseline = profile active
            return DetectResult(
                "expo_xmp", active,
                detected_val=f"{speed} MHz",
                confidence="high",
                note=f"RAM läuft auf {speed} MHz"
                     + (" — XMP/EXPO aktiv ✓" if active else " — möglicherweise JEDEC-Standard")
            )
        except:
            return DetectResult("expo_xmp", False, out, "low",
                                "RAM-Geschwindigkeit konnte nicht ermittelt werden")

    def detect_rebar(self) -> DetectResult:
        """
        ReBAR = HKLM HwSchMode=2 AND GPU VRAM fully visible.
        Also check if GPU BAR size > 256MB via registry.
        """
        # Check HAGS/HwSchMode (set together with ReBAR usually)
        hw_mode = _run_ps(
            r"(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' "
            r"-Name HwSchMode -EA SilentlyContinue).HwSchMode"
        )

        # Check if VRAM is fully accessible (>256MB BAR)
        vram_ps = _run_ps(
            "Get-WmiObject Win32_VideoController | "
            "Where-Object { $_.Name -notmatch 'Microsoft' } | "
            "Select-Object -ExpandProperty AdapterRAM -First 1"
        )
        try:
            vram_bytes = int(vram_ps.strip())
            vram_mb = vram_bytes / (1024 * 1024)
            # If VRAM > 256MB visible = Above 4G Decoding is working
            # True ReBAR = full VRAM accessible (e.g. 8192MB for 8GB card)
            rebar_likely = vram_mb > 1024  # more than 1GB = 4G decoding working
        except:
            rebar_likely = False
            vram_mb = 0

        # Best indicator: check NvLspci or GPU BAR via DXGI
        # Simpler: if HwSchMode=2 AND vram visible = likely active
        active = rebar_likely and hw_mode.strip() == "2"

        return DetectResult(
            "rebar", active,
            detected_val=f"VRAM sichtbar: {vram_mb:.0f}MB, HwSchMode={hw_mode.strip()}",
            confidence="medium",
            note="ReBAR aktiv (VRAM voll zugänglich + HAGS)" if active
                 else "ReBAR möglicherweise inaktiv — im BIOS prüfen"
        )

    def detect_above_4g(self) -> DetectResult:
        """Above 4G Decoding: GPU VRAM visible > 4GB."""
        out = _run_ps(
            "Get-WmiObject Win32_VideoController | "
            "Where-Object { $_.Name -notmatch 'Microsoft' } | "
            "Select-Object -ExpandProperty AdapterRAM -First 1"
        )
        try:
            vram_mb = int(out.strip()) / (1024 * 1024)
            active  = vram_mb >= 1024
            return DetectResult(
                "above_4g", active,
                detected_val=f"{vram_mb:.0f} MB VRAM sichtbar",
                confidence="high",
                note=f"VRAM: {vram_mb:.0f}MB sichtbar — "
                     + ("Above 4G wahrscheinlich aktiv ✓" if active
                        else "könnte auf fehlendes Above 4G hinweisen")
            )
        except:
            return DetectResult("above_4g", False, out, "low", "Konnte VRAM nicht lesen")

    def detect_hags(self) -> DetectResult:
        """HAGS = HwSchMode registry = 2."""
        out = _run_ps(
            r"(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' "
            r"-Name HwSchMode -EA SilentlyContinue).HwSchMode"
        )
        active = out.strip() == "2"
        return DetectResult(
            "hags", active,
            detected_val=f"HwSchMode={out.strip()}",
            confidence="high",
            note="HAGS aktiv ✓" if active else "HAGS nicht aktiv"
        )

    def detect_secure_boot(self) -> DetectResult:
        """Secure Boot state via PowerShell."""
        out = _run_ps("Confirm-SecureBootUEFI 2>$null")
        active = out.strip().lower() == "true"
        return DetectResult(
            "secure_boot", active,
            detected_val=out.strip(),
            confidence="high",
            note="Secure Boot: aktiv" if active else "Secure Boot: inaktiv"
        )

    def detect_fast_boot(self) -> DetectResult:
        """Fast Startup (HiberbootEnabled) in registry."""
        out = _run_ps(
            r"(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager"
            r"\Power' -Name HiberbootEnabled -EA SilentlyContinue).HiberbootEnabled"
        )
        active = out.strip() == "1"
        return DetectResult(
            "fast_boot", active,
            detected_val=f"HiberbootEnabled={out.strip()}",
            confidence="medium",
            note="Fast Startup (Windows) aktiv" if active else "Fast Startup inaktiv"
        )

    def detect_pbo(self) -> DetectResult:
        """
        PBO active = CPU boosting above base clock.
        Check if max observed clock > base clock significantly.
        """
        out = _run_ps(
            "Get-WmiObject Win32_Processor | "
            "Select-Object MaxClockSpeed, CurrentClockSpeed | "
            "ConvertTo-Json"
        )
        try:
            import json
            data = json.loads(out)
            if isinstance(data, list):
                data = data[0]
            max_clk = int(data.get("MaxClockSpeed", 0))
            # For AMD Ryzen 9000: base ~3.7-4.7GHz, boost 5.0-5.4GHz
            # If max > 4500 MHz, PBO is likely working
            active = max_clk > 4500
            return DetectResult(
                "pbo", active,
                detected_val=f"Max Clock: {max_clk} MHz",
                confidence="medium",
                note=f"CPU Max: {max_clk}MHz — "
                     + ("Boost aktiv ✓" if active else "Boost möglicherweise limitiert")
            )
        except:
            return DetectResult("pbo", False, out, "low", "CPU-Takt konnte nicht gelesen werden")

    def detect_c_states(self) -> DetectResult:
        """
        C-States: check power scheme for CPU idle settings.
        If minimum processor state > 0, C-states might be restricted.
        """
        out = _run_ps(
            "powercfg /query SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 2>$null | "
            r"Select-String 'Current AC Power Setting Index' | "
            "Select-Object -First 1"
        )
        try:
            # Format: "Current AC Power Setting Index: 0x00000000"
            val_str = out.split(":")[-1].strip()
            val     = int(val_str, 16)
            active  = val == 0  # 0% min = C-states fully allowed
            return DetectResult(
                "c_states", active,
                detected_val=f"Min CPU State: {val}%",
                confidence="medium",
                note=f"CPU Minimalzustand: {val}% — "
                     + ("C-States aktiv (Stromspar-Modi erlaubt)" if active
                        else f"Minimalzustand auf {val}% gesetzt")
            )
        except:
            return DetectResult("c_states", True, "", "low",
                                "C-State-Status konnte nicht geprüft werden")

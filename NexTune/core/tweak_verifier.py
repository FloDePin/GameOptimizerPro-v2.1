"""
GameOptimizerPro Tweak Verifier
Liest den tatsächlichen System-Zustand für jeden Tweak und vergleicht
mit dem erwarteten Wert. Unabhängig von der gespeicherten JSON-State-Datei.

Jeder verifizierbare Tweak bekommt einen verify_ps_command (PowerShell)
der "APPLIED" oder "NOT_APPLIED" zurückgibt.
"""

import subprocess, os
from dataclasses import dataclass
from typing import Optional


# ── Verification result ───────────────────────────────────────────────────────

@dataclass
class VerifyResult:
    tweak_id:   str
    expected:   bool        # Was es laut JSON sein sollte
    actual:     bool        # Was es tatsächlich ist
    mismatch:   bool        # True wenn expected != actual
    error:      str = ""    # Falls Verifikation fehlschlug


# ── Verification commands per tweak_id ───────────────────────────────────────
# PowerShell-Befehl muss "APPLIED" oder "NOT_APPLIED" ausgeben.

VERIFY_MAP: dict[str, str] = {

    # Privacy / Telemetry
    "disable_telemetry": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection" -Name AllowTelemetry -EA SilentlyContinue).AllowTelemetry
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_activity_history": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" -Name EnableActivityFeed -EA SilentlyContinue).EnableActivityFeed
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_advertising_id": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo" -Name Enabled -EA SilentlyContinue).Enabled
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_location": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\location" -Name Value -EA SilentlyContinue).Value
if($v -eq "Deny"){"APPLIED"}else{"NOT_APPLIED"}''',

    "remove_copilot": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Policies\\Microsoft\\Windows\\WindowsCopilot" -Name TurnOffWindowsCopilot -EA SilentlyContinue).TurnOffWindowsCopilot
if($v -eq 1){"APPLIED"}else{"NOT_APPLIED"}''',

    "remove_recall": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsAI" -Name DisableAIDataAnalysis -EA SilentlyContinue).DisableAIDataAnalysis
if($v -eq 1){"APPLIED"}else{"NOT_APPLIED"}''',

    # Performance
    "disable_prefetch": '''
$svc=(Get-Service SysMain -EA SilentlyContinue).StartType
if($svc -eq "Disabled"){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_search_indexing": '''
$svc=(Get-Service WSearch -EA SilentlyContinue).StartType
if($svc -eq "Disabled"){"APPLIED"}else{"NOT_APPLIED"}''',

    "timer_resolution": '''
$v=(Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\kernel" -Name GlobalTimerResolutionRequests -EA SilentlyContinue).GlobalTimerResolutionRequests
if($v -eq 1){"APPLIED"}else{"NOT_APPLIED"}''',

    "visual_effects_perf": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\VisualEffects" -Name VisualFXSetting -EA SilentlyContinue).VisualFXSetting
if($v -eq 2){"APPLIED"}else{"NOT_APPLIED"}''',

    # Gaming
    "enable_game_mode": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Microsoft\\GameBar" -Name AutoGameModeEnabled -EA SilentlyContinue).AutoGameModeEnabled
if($v -eq 1){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_game_bar": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR" -Name AppCaptureEnabled -EA SilentlyContinue).AppCaptureEnabled
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "cpu_priority_games": '''
$v=(Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\PriorityControl" -Name Win32PrioritySeparation -EA SilentlyContinue).Win32PrioritySeparation
if($v -eq 26){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_fullscreen_opt": '''
$v=(Get-ItemProperty "HKCU:\\System\\GameConfigStore" -Name GameDVR_FSEBehaviorMode -EA SilentlyContinue).GameDVR_FSEBehaviorMode
if($v -eq 2){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_wu_gaming": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU" -Name NoAutoUpdate -EA SilentlyContinue).NoAutoUpdate
if($v -eq 1){"APPLIED"}else{"NOT_APPLIED"}''',

    "mmcss_gaming": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile\\Tasks\\Games" -Name "GPU Priority" -EA SilentlyContinue)."GPU Priority"
if($v -eq 8){"APPLIED"}else{"NOT_APPLIED"}''',

    # GPU
    "enable_hags": '''
$v=(Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers" -Name HwSchMode -EA SilentlyContinue).HwSchMode
if($v -eq 2){"APPLIED"}else{"NOT_APPLIED"}''',

    "nvidia_low_latency": '''
$v=(Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\nvlddmkm\\Global\\NVTweak" -Name NVLatency -EA SilentlyContinue).NVLatency
if($v -eq 1){"APPLIED"}else{"NOT_APPLIED"}''',

    # Mouse & UI
    "disable_mouse_accel": '''
$v=(Get-ItemProperty "HKCU:\\Control Panel\\Mouse" -Name MouseSpeed -EA SilentlyContinue).MouseSpeed
if($v -eq "0"){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_sticky_keys": '''
$v=(Get-ItemProperty "HKCU:\\Control Panel\\Accessibility\\StickyKeys" -Name Flags -EA SilentlyContinue).Flags
if($v -eq "506"){"APPLIED"}else{"NOT_APPLIED"}''',

    "enable_dark_mode": '''
$v=(Get-ItemProperty "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" -Name AppsUseLightTheme -EA SilentlyContinue).AppsUseLightTheme
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_transparency": '''
$v=(Get-ItemProperty "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" -Name EnableTransparency -EA SilentlyContinue).EnableTransparency
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    # Network
    "dns_cloudflare": '''
$dns=(Get-DnsClientServerAddress -AddressFamily IPv4 -EA SilentlyContinue | Select -ExpandProperty ServerAddresses -EA SilentlyContinue)
if($dns -contains "1.1.1.1"){"APPLIED"}else{"NOT_APPLIED"}''',

    "dns_google": '''
$dns=(Get-DnsClientServerAddress -AddressFamily IPv4 -EA SilentlyContinue | Select -ExpandProperty ServerAddresses -EA SilentlyContinue)
if($dns -contains "8.8.8.8"){"APPLIED"}else{"NOT_APPLIED"}''',

    "disable_network_throttle": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile" -Name NetworkThrottlingIndex -EA SilentlyContinue).NetworkThrottlingIndex
if($v -eq 4294967295){"APPLIED"}else{"NOT_APPLIED"}''',

    # Power
    "disable_usb_suspend": '''
$v=(powercfg /query SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 2>$null)
if($v -match "Current AC Power Setting Index: 0x00000000"){"APPLIED"}else{"NOT_APPLIED"}''',

    # Win11
    "w11_classic_context_menu": '''
$p="HKCU:\\Software\\Classes\\CLSID\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\\InprocServer32"
if(Test-Path $p){"APPLIED"}else{"NOT_APPLIED"}''',

    "w11_taskbar_left": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name TaskbarAl -EA SilentlyContinue).TaskbarAl
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "w11_disable_widgets": '''
$v=(Get-ItemProperty "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Dsh" -Name AllowNewsAndInterests -EA SilentlyContinue).AllowNewsAndInterests
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',

    "w11_disable_snap_suggest": '''
$v=(Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name EnableSnapAssistFlyout -EA SilentlyContinue).EnableSnapAssistFlyout
if($v -eq 0){"APPLIED"}else{"NOT_APPLIED"}''',
}


class TweakVerifier:
    """
    Verifies actual system state for each tweak.
    Runs all checks via a single batched PowerShell call for speed.
    """

    def __init__(self, timeout_s: int = 30):
        self.timeout = timeout_s

    def verify_all(
        self, tweak_ids: list[str], expected: dict[str, bool]
    ) -> dict[str, VerifyResult]:
        """
        Verify a list of tweaks. expected = {tweak_id: True/False}.
        Returns dict of VerifyResult per tweak_id.
        """
        results = {}

        # Only verify tweaks we have commands for
        verifiable = [tid for tid in tweak_ids if tid in VERIFY_MAP]

        if not verifiable:
            return results

        # Build a batched PS script that outputs "tweak_id|APPLIED" or "tweak_id|NOT_APPLIED"
        lines = []
        for tid in verifiable:
            cmd = VERIFY_MAP[tid].strip().replace("\n", "; ")
            lines.append(
                f'$r=({cmd}); Write-Output "{tid}|$r"'
            )

        batch_script = "\n".join(lines)

        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", batch_script],
                capture_output=True, text=True, timeout=self.timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            output = result.stdout

            # Parse output lines
            parsed = {}
            for line in output.splitlines():
                line = line.strip()
                if "|" in line:
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        tid, state = parts[0].strip(), parts[1].strip()
                        parsed[tid] = (state == "APPLIED")

            for tid in verifiable:
                actual   = parsed.get(tid, False)
                exp      = expected.get(tid, False)
                results[tid] = VerifyResult(
                    tweak_id=tid,
                    expected=exp,
                    actual=actual,
                    mismatch=(exp != actual)
                )

        except subprocess.TimeoutExpired:
            for tid in verifiable:
                results[tid] = VerifyResult(
                    tweak_id=tid,
                    expected=expected.get(tid, False),
                    actual=False,
                    mismatch=False,
                    error="Timeout"
                )
        except Exception as e:
            for tid in verifiable:
                results[tid] = VerifyResult(
                    tweak_id=tid,
                    expected=expected.get(tid, False),
                    actual=False,
                    mismatch=False,
                    error=str(e)
                )

        return results

    def verify_single(self, tweak_id: str, expected: bool) -> Optional[VerifyResult]:
        results = self.verify_all([tweak_id], {tweak_id: expected})
        return results.get(tweak_id)

    def has_verify(self, tweak_id: str) -> bool:
        return tweak_id in VERIFY_MAP

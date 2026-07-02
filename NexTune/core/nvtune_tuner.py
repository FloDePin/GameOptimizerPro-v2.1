"""
GameOptimizerPro Auto-Tuner v1.2
Stage 1: Max stable core offset
Stage 2: Min stable power limit (indirect undervolt)
Final:   2-min verification
Features: TuneMode selector, crash recovery, TDR detection, per-step flag writing
"""

import time, threading, os, sys, subprocess, logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Optional
from datetime import datetime
from pathlib import Path

from core.nvtune_core import GpuMonitor, AfterburnerController, TuneProfile, ProfileManager


class TuneMode(Enum):
    OC_ONLY = "oc_only"
    UV_ONLY = "uv_only"
    OC_UV   = "oc_uv"


class TunerState(Enum):
    IDLE       = auto()
    BASELINE   = auto()
    STAGE1     = auto()
    STAGE2     = auto()
    FINAL_TEST = auto()
    BACKOFF    = auto()
    SAVING     = auto()
    DONE       = auto()
    ERROR      = auto()
    ABORTED    = auto()


@dataclass
class StressResult:
    passed:         bool  = False
    max_temp:       float = 0.0
    avg_temp:       float = 0.0
    min_voltage_mv: float = 0.0
    max_voltage_mv: float = 0.0
    avg_voltage_mv: float = 0.0
    throttle_hit:   bool  = False
    crash_detected: bool  = False
    tdr_detected:   bool  = False
    abort_reason:   str   = ""
    avg_core_mhz:   float = 0.0
    core_clocks:    list  = field(default_factory=list)


@dataclass
class TunerConfig:
    mode:            TuneMode = TuneMode.OC_UV
    core_step_mhz:   int = 15
    core_max_mhz:    int = 300
    core_start_mhz:  int = 0
    power_step_pct:  int = 5
    power_min_pct:   int = 65
    power_start_pct: int = 100
    max_temp_c:      int = 85
    baseline_s:      int = 30
    step_test_s:     int = 45
    final_test_s:    int = 120
    ab_slot:         int = 2
    mem_offset_mhz:  int = 0


class StressTester:
    def __init__(self, monitor: GpuMonitor, crash_recovery=None):
        self.monitor = monitor
        self.cr      = crash_recovery
        self._proc: Optional[subprocess.Popen] = None

    def _worker_path(self):
        # Worker lives at project root, not in core/
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "_stress_worker.py"
        )

    def start(self):
        wp = self._worker_path()
        if os.path.exists(wp):
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                self._proc = subprocess.Popen(
                    [sys.executable, wp],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags
                )
            except:
                pass

    def stop(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except:
                pass
            self._proc = None

    def run(
        self,
        duration_s: int,
        max_temp: int,
        on_tick: Optional[Callable] = None
    ) -> StressResult:
        result = StressResult()
        temps, voltages, clocks = [], [], []

        self.start()
        start = time.time()

        while True:
            elapsed = int(time.time() - start)
            if elapsed >= duration_s:
                break

            stats = self.monitor.read()
            temps.append(stats.temp)
            if stats.voltage_mv > 0:
                voltages.append(stats.voltage_mv)
            clocks.append(stats.core_mhz)

            if on_tick:
                try:
                    on_tick(elapsed, duration_s, stats)
                except:
                    pass

            if stats.temp >= max_temp:
                self.stop()
                result.abort_reason = f"Temp {stats.temp}°C >= limit {max_temp}°C"
                result.max_temp = stats.temp
                result.passed   = False
                return result

            if stats.throttle not in ("None", ""):
                result.throttle_hit = True

            # Worker crash = GPU instability
            if self._proc and self._proc.poll() is not None:
                result.crash_detected = True
                result.abort_reason   = "Stress worker crashed (GPU unstable)"
                break

            # TDR check every 10s
            if elapsed % 10 == 0 and elapsed > 0 and self.cr:
                if self.cr.check_tdr_since(seconds_back=15):
                    result.tdr_detected   = True
                    result.crash_detected = True
                    result.abort_reason   = "TDR (GPU driver timeout) detected"
                    break

            time.sleep(1.0)

        self.stop()

        result.max_temp     = max(temps) if temps else 0
        result.avg_temp     = round(sum(temps) / len(temps), 1) if temps else 0
        result.avg_core_mhz = round(sum(clocks) / len(clocks), 1) if clocks else 0
        if voltages:
            result.min_voltage_mv = min(voltages)
            result.max_voltage_mv = max(voltages)
            result.avg_voltage_mv = round(sum(voltages) / len(voltages), 1)

        result.passed = (
            not result.crash_detected
            and not result.tdr_detected
            and result.max_temp < max_temp
        )
        return result


class AutoTuner:
    def __init__(
        self,
        monitor:  GpuMonitor,
        ab:       AfterburnerController,
        pm:       ProfileManager,
        config:   TunerConfig,
        log_dir:  str = "logs",
        crash_recovery=None
    ):
        self.monitor = monitor
        self.ab      = ab
        self.pm      = pm
        self.config  = config
        self.cr      = crash_recovery

        self.state        = TunerState.IDLE
        self._stop        = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.best_profile: Optional[TuneProfile] = None

        self._cb_state:    Optional[Callable] = None
        self._cb_log:      Optional[Callable] = None
        self._cb_progress: Optional[Callable] = None
        self._cb_tick:     Optional[Callable] = None

        Path(log_dir).mkdir(parents=True, exist_ok=True)
        logfile = os.path.join(
            log_dir, f"tune_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        # Use a named logger so multiple inits don't conflict
        self.logger = logging.getLogger(f"nextune.tuner.{id(self)}")
        if not self.logger.handlers:
            fh = logging.FileHandler(logfile, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            self.logger.addHandler(fh)
            self.logger.setLevel(logging.INFO)

    def on_state(self,    cb): self._cb_state    = cb
    def on_log(self,      cb): self._cb_log      = cb
    def on_progress(self, cb): self._cb_progress = cb
    def on_tick(self,     cb): self._cb_tick     = cb

    def _set_state(self, s):
        self.state = s
        if self._cb_state:
            self._cb_state(s)

    def _log(self, msg, lvl="info"):
        getattr(self.logger, lvl)(msg)
        if self._cb_log:
            self._cb_log(msg, lvl)

    def _progress(self, pct, msg):
        if self._cb_progress:
            self._cb_progress(pct, msg)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_safe, daemon=True)
        self._thread.start()

    def abort(self):
        self._stop.set()
        self._set_state(TunerState.ABORTED)
        self._log("Aborted by user", "warning")
        self._safe_reset()
        if self.cr:
            self.cr.clear_tuning_flag()

    def _safe_reset(self):
        try:
            reset = TuneProfile(
                name="__reset__",
                core_offset_mhz=0,
                mem_offset_mhz=0,
                power_limit_pct=100
            )
            self.ab.write_and_apply(self.config.ab_slot, reset)
            _, _, mx = self.monitor.get_power_constraints()
            if mx > 0:
                self.monitor.set_power_limit(mx)
        except:
            pass

    def _apply(self, core=0, mem=0, pwr_pct=100) -> bool:
        p = TuneProfile(
            name="__tuning__",
            core_offset_mhz=core,
            mem_offset_mhz=mem,
            power_limit_pct=pwr_pct,
        )
        # Write crash flag before applying
        if self.cr:
            self.cr.set_tuning_active(p.to_dict())
        ok, _ = self.ab.write_and_apply(self.config.ab_slot, p)
        if ok:
            _, _, mx = self.monitor.get_power_constraints()
            if mx > 0 and pwr_pct < 100:
                self.monitor.set_power_limit(mx * (pwr_pct / 100.0))
        return ok

    def _save_stable(self, core, mem, pwr):
        """Save current values as last-known-stable for crash recovery."""
        if self.cr:
            p = TuneProfile(
                name="__last_stable__",
                core_offset_mhz=core,
                mem_offset_mhz=mem,
                power_limit_pct=pwr
            )
            self.cr.save_last_stable(p.to_dict())

    def _run_safe(self):
        try:
            self._run()
        except Exception as e:
            self._log(f"Tuner exception: {e}", "error")
            self._set_state(TunerState.ERROR)
            self._safe_reset()
            if self.cr:
                self.cr.clear_tuning_flag()

    def _run(self):
        cfg     = self.config
        mode    = cfg.mode
        stress  = StressTester(self.monitor, self.cr)

        self._log("═══════════════════════════════════════")
        self._log(f"  GameOptimizerPro Auto-Tune [{mode.value.upper().replace('_',' ')}]")
        self._log("═══════════════════════════════════════")

        # ── Baseline ──────────────────────────────────────────────────────────
        self._set_state(TunerState.BASELINE)
        self._progress(5, "Measuring baseline (stock settings)...")
        self._apply(0, 0, 100)
        time.sleep(2)

        base = stress.run(
            cfg.baseline_s, cfg.max_temp_c,
            on_tick=lambda e, d, s: (
                self._progress(
                    5 + int(e / d * 10),
                    f"Baseline: {e}/{d}s | {s.temp}°C | {s.voltage_mv:.0f}mV"
                ),
                self._cb_tick(s) if self._cb_tick else None
            )
        )
        if not base.passed:
            self._log(f"Baseline FAILED: {base.abort_reason}", "error")
            self._set_state(TunerState.ERROR)
            if self.cr: self.cr.clear_tuning_flag()
            return

        self._log(
            f"Baseline OK | temp={base.avg_temp}°C | "
            f"volt={base.avg_voltage_mv:.0f}mV | clk={base.avg_core_mhz:.0f}MHz"
        )
        # Baseline is our first "stable" point
        self._save_stable(0, 0, 100)

        if self._stop.is_set(): return

        # ── Stage 1: Core Clock Offset ─────────────────────────────────────────
        best_core = cfg.core_start_mhz

        if mode in (TuneMode.OC_ONLY, TuneMode.OC_UV):
            self._set_state(TunerState.STAGE1)
            self._log("Stage 1: Finding max stable core offset...")
            self._progress(15, "Stage 1: Core clock optimization")

            cur_core    = cfg.core_start_mhz
            total_steps = max(cfg.core_max_mhz // cfg.core_step_mhz, 1)
            step_n      = 0

            while not self._stop.is_set():
                candidate = cur_core + cfg.core_step_mhz
                if candidate > cfg.core_max_mhz:
                    self._log(f"Stage 1: Hard limit +{cfg.core_max_mhz}MHz reached")
                    break

                self._apply(candidate, cfg.mem_offset_mhz, 100)
                time.sleep(2)

                sn_capture = step_n

                def _tick1(e, d, s, c=candidate, sn=sn_capture):
                    self._progress(
                        15 + int(sn / total_steps * 35),
                        f"Stage 1: +{c}MHz | {e}/{d}s | {s.temp}°C | {s.voltage_mv:.0f}mV"
                    )
                    if self._cb_tick: self._cb_tick(s)

                result = stress.run(cfg.step_test_s, cfg.max_temp_c, on_tick=_tick1)
                step_n += 1

                if result.passed and not result.throttle_hit:
                    best_core = candidate
                    cur_core  = candidate
                    # Save this as new stable point
                    self._save_stable(best_core, cfg.mem_offset_mhz, 100)
                    self._log(
                        f"  +{candidate}MHz ✓  "
                        f"avg={result.avg_temp:.1f}°C  "
                        f"volt={result.avg_voltage_mv:.0f}mV  "
                        f"clk={result.avg_core_mhz:.0f}MHz"
                    )
                else:
                    tdr_note = " [TDR!]" if result.tdr_detected else ""
                    reason = result.abort_reason or (
                        "Throttle" if result.throttle_hit else "Unstable")
                    self._log(
                        f"  +{candidate}MHz ✗{tdr_note}  {reason}"
                        f" — backoff to +{best_core}MHz", "warning"
                    )
                    self._set_state(TunerState.BACKOFF)
                    # Restore last stable
                    self._apply(best_core, cfg.mem_offset_mhz, 100)
                    time.sleep(1)
                    break

            self._log(f"Stage 1 done: best core = +{best_core}MHz")
        else:
            self._log("Stage 1 skipped (UV Only mode)")

        if self._stop.is_set(): return

        # ── Stage 2: Power Limit Reduction ─────────────────────────────────────
        best_pwr = cfg.power_start_pct

        if mode in (TuneMode.UV_ONLY, TuneMode.OC_UV):
            self._set_state(TunerState.STAGE2)
            self._log("Stage 2: Power limit reduction (indirect undervolt)...")
            s2_base  = 50 if mode == TuneMode.OC_UV else 15
            pwr_steps = max(
                (cfg.power_start_pct - cfg.power_min_pct) // cfg.power_step_pct, 1)
            pwr_step_n = 0
            cur_pwr    = cfg.power_start_pct

            self._progress(s2_base, "Stage 2: Power limit optimization")

            while not self._stop.is_set():
                candidate = cur_pwr - cfg.power_step_pct
                if candidate < cfg.power_min_pct:
                    self._log(f"Stage 2: Min {cfg.power_min_pct}% reached")
                    break

                self._apply(best_core, cfg.mem_offset_mhz, candidate)
                time.sleep(2)

                sn_capture = pwr_step_n

                def _tick2(e, d, s, p=candidate, sn=sn_capture):
                    self._progress(
                        s2_base + int(sn / pwr_steps * 25),
                        f"Stage 2: {p}% | {e}/{d}s | {s.temp}°C | {s.voltage_mv:.0f}mV"
                    )
                    if self._cb_tick: self._cb_tick(s)

                result = stress.run(cfg.step_test_s, cfg.max_temp_c, on_tick=_tick2)
                pwr_step_n += 1

                if result.passed and not result.throttle_hit:
                    best_pwr   = candidate
                    cur_pwr    = candidate
                    self._save_stable(best_core, cfg.mem_offset_mhz, best_pwr)
                    self._log(
                        f"  {candidate}% ✓  "
                        f"avg={result.avg_temp:.1f}°C  "
                        f"volt={result.avg_voltage_mv:.0f}mV"
                    )
                else:
                    tdr_note = " [TDR!]" if result.tdr_detected else ""
                    reason   = result.abort_reason or "Unstable"
                    self._log(
                        f"  {candidate}%{tdr_note} ✗  {reason}"
                        f" — locking at {best_pwr}%", "warning"
                    )
                    self._set_state(TunerState.BACKOFF)
                    self._apply(best_core, cfg.mem_offset_mhz, best_pwr)
                    time.sleep(1)
                    break

            self._log(f"Stage 2 done: best power = {best_pwr}%")
        else:
            self._log("Stage 2 skipped (OC Only mode)")

        if self._stop.is_set(): return

        # ── Final Test ─────────────────────────────────────────────────────────
        self._set_state(TunerState.FINAL_TEST)
        self._log(
            f"Final test: +{best_core}MHz | {best_pwr}% pwr | {cfg.final_test_s}s")
        self._progress(
            75,
            f"Final verification: +{best_core}MHz | {best_pwr}% ({cfg.final_test_s}s)"
        )

        self._apply(best_core, cfg.mem_offset_mhz, best_pwr)
        time.sleep(2)

        def _tick_final(e, d, s):
            self._progress(
                75 + int(e / d * 20),
                f"Final: {e}/{d}s | {s.temp}°C | {s.voltage_mv:.0f}mV | {s.core_mhz:.0f}MHz"
            )
            if self._cb_tick: self._cb_tick(s)

        final = stress.run(cfg.final_test_s, cfg.max_temp_c, on_tick=_tick_final)

        # ── Save ───────────────────────────────────────────────────────────────
        self._set_state(TunerState.SAVING)
        mode_tag = {"oc_only": "OC", "uv_only": "UV", "oc_uv": "OC+UV"}.get(
            mode.value, "")

        try:
            gpu_name = self.monitor.read().name
        except:
            gpu_name = "Unknown"

        if final.passed:
            score = self._score(final)
            profile = TuneProfile(
                name=f"GOP_{mode_tag}_{datetime.now().strftime('%m%d_%H%M')}",
                core_offset_mhz=best_core,
                mem_offset_mhz=cfg.mem_offset_mhz,
                power_limit_pct=best_pwr,
                is_stable=True,
                stability_score=score,
                stage1_freq=int(final.avg_core_mhz),
                stage1_voltage=int(final.avg_voltage_mv),
                notes=(
                    f"[{mode_tag}] Core+{best_core}MHz | Pwr {best_pwr}% | "
                    f"MaxTemp {final.max_temp:.0f}°C | "
                    f"AvgVolt {final.avg_voltage_mv:.0f}mV | Score {score}/100"
                ),
                created_at=datetime.now().isoformat(),
                gpu_name=gpu_name,
            )
            self.best_profile = profile
            self.pm.save(profile)
            # Track as last applied for startup loader
            if self.cr:
                self.cr.save_last_applied(profile.to_dict())
            self._log(f"Profile saved: {profile.name}")
            self._log(f"  Mode:        {mode_tag}")
            self._log(f"  Core offset: +{best_core}MHz")
            self._log(f"  Power limit: {best_pwr}%")
            self._log(f"  Avg voltage: {final.avg_voltage_mv:.0f}mV")
            self._log(f"  Max temp:    {final.max_temp:.0f}°C")
            self._log(f"  Score:       {score}/100")
            self._progress(
                100,
                f"✓ Done! [{mode_tag}] +{best_core}MHz | {best_pwr}% | "
                f"Score {score}/100 | {final.avg_voltage_mv:.0f}mV"
            )
        else:
            safe_core = (max(0, best_core - cfg.core_step_mhz)
                         if mode != TuneMode.UV_ONLY else 0)
            safe_pwr  = min(100, best_pwr + cfg.power_step_pct)
            self._log(
                f"Final failed ({final.abort_reason}) — saving conservative profile",
                "warning"
            )
            profile = TuneProfile(
                name=f"GOP_{mode_tag}_Safe_{datetime.now().strftime('%m%d_%H%M')}",
                core_offset_mhz=safe_core,
                mem_offset_mhz=0,
                power_limit_pct=safe_pwr,
                is_stable=True,
                stability_score=55,
                notes=f"[{mode_tag}] Conservative | +{safe_core}MHz | {safe_pwr}%",
                created_at=datetime.now().isoformat(),
                gpu_name=gpu_name,
            )
            self.best_profile = profile
            self.pm.save(profile)
            self._apply(safe_core, 0, safe_pwr)
            self._progress(
                100, f"Safe profile: +{safe_core}MHz | {safe_pwr}%")

        # Clean up crash flag — we finished cleanly
        if self.cr:
            self.cr.clear_tuning_flag()

        self._log("═══════════════════════════════════════")
        self._log("        Auto-Tune Complete")
        self._log("═══════════════════════════════════════")
        self._set_state(TunerState.DONE)

    def _score(self, r: StressResult) -> int:
        score  = 100
        margin = 85 - r.max_temp
        if margin < 5:
            score -= 20
        elif margin < 10:
            score -= 10
        if r.throttle_hit:
            score -= 15
        if r.tdr_detected:
            score -= 30
        return max(0, min(100, score))

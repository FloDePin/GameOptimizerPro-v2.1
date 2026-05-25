"""
GameOptimizerPro v2.0 — Tune History
Liest alle .log Dateien aus dem logs/ Ordner und parst die Tune-Runs.
"""

import os, re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TuneRun:
    filename:    str
    date:        str
    mode:        str   # OC / UV / OC+UV
    core_offset: int   = 0
    power_pct:   int   = 100
    avg_volt_mv: int   = 0
    max_temp:    float = 0.0
    score:       int   = 0
    gpu_name:    str   = ""
    passed:      bool  = False
    log_lines:   list  = field(default_factory=list)


class TuneHistory:
    def __init__(self, logs_dir: str):
        self.logs_dir = Path(logs_dir)

    def get_runs(self) -> list[TuneRun]:
        """Parse all tune_*.log files and return TuneRun list sorted newest first."""
        runs = []
        if not self.logs_dir.exists():
            return runs

        for log_file in sorted(self.logs_dir.glob("tune_*.log"), reverse=True):
            run = self._parse_log(log_file)
            if run:
                runs.append(run)
        return runs

    def _parse_log(self, path: Path) -> Optional[TuneRun]:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except:
            return None

        if not lines:
            return None

        run = TuneRun(
            filename=path.name,
            date=path.name.replace("tune_", "").replace(".log", ""),
            log_lines=lines,
            mode="Unknown",
        )

        # Format date nicely: 20260524_193045 → 24.05.2026 19:30:45
        try:
            d = run.date
            run.date = f"{d[6:8]}.{d[4:6]}.{d[0:4]} {d[9:11]}:{d[11:13]}:{d[13:15]}"
        except:
            pass

        for line in lines:
            # Extract mode
            m = re.search(r'\[([A-Z+]+)\].*Auto-Tune|Auto-Tune.*\[([A-Z+]+)\]', line)
            if m:
                run.mode = m.group(1) or m.group(2) or "Unknown"

            # Extract results
            if "Core offset:" in line or "Core offset" in line:
                m2 = re.search(r'\+(\d+)MHz', line)
                if m2: run.core_offset = int(m2.group(1))

            if "Power limit:" in line:
                m2 = re.search(r'(\d+)%', line)
                if m2: run.power_pct = int(m2.group(1))

            if "Avg voltage:" in line:
                m2 = re.search(r'(\d+)mV', line)
                if m2: run.avg_volt_mv = int(m2.group(1))

            if "Max temp:" in line:
                m2 = re.search(r'([\d.]+)°C', line)
                if m2: run.max_temp = float(m2.group(1))

            if "Score:" in line:
                m2 = re.search(r'(\d+)/100', line)
                if m2: run.score = int(m2.group(1))

            if "Profile saved:" in line:
                run.passed = True

            # GPU name from "GPU:" line
            if line.strip().startswith("GPU:") or "gpu_name" in line.lower():
                m2 = re.search(r'(?:GPU:|gpu_name["\s:]+)([A-Za-z0-9 ]+)', line)
                if m2 and not run.gpu_name:
                    run.gpu_name = m2.group(1).strip()

        return run if run.mode != "Unknown" or run.passed else None

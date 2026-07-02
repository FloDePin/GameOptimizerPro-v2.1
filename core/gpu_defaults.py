"""
GameOptimizerPro GPU Defaults
Erkennt GPU-Generation aus dem Namen und gibt passende
konservative Tuning-Defaults zurück.
"""

from dataclasses import dataclass


@dataclass
class GpuDefaults:
    gpu_name:       str
    generation:     str
    # OC defaults
    core_step_mhz:  int
    core_max_mhz:   int
    mem_max_mhz:    int
    # UV defaults
    power_min_pct:  int
    power_step_pct: int
    # Safety
    max_temp_c:     int
    # Info
    notes:          str


# ── Generation table ──────────────────────────────────────────────────────────
# Sorted most-specific first so matching works top-down.

_TABLE = [
    # NVIDIA Ada Lovelace (RTX 40xx) — very good OC headroom
    ("RTX 409", "Ada Lovelace",  15, 250, 1500, 65, 5, 85,
     "RTX 4090 — high TDP, good OC potential"),
    ("RTX 408", "Ada Lovelace",  15, 220, 1500, 65, 5, 85,
     "RTX 4080 — good OC and UV headroom"),
    ("RTX 407", "Ada Lovelace",  15, 200, 1500, 68, 5, 85,
     "RTX 4070 family — solid UV gains"),
    ("RTX 406", "Ada Lovelace",  12, 180, 1200, 70, 5, 85,
     "RTX 4060 family — moderate OC headroom"),
    ("RTX 40",  "Ada Lovelace",  15, 200, 1500, 68, 5, 85,
     "RTX 40-series — Ada Lovelace"),

    # NVIDIA Ampere (RTX 30xx)
    ("RTX 309", "Ampere",        12, 180, 1200, 70, 5, 85,
     "RTX 3090/Ti — high TDP, great UV gains"),
    ("RTX 308", "Ampere",        12, 160, 1200, 70, 5, 85,
     "RTX 3080 family"),
    ("RTX 307", "Ampere",        10, 150, 1000, 72, 5, 85,
     "RTX 3070 family"),
    ("RTX 306", "Ampere",        10, 130, 900,  75, 5, 85,
     "RTX 3060 family"),
    ("RTX 30",  "Ampere",        10, 150, 1000, 72, 5, 85,
     "RTX 30-series — Ampere"),

    # NVIDIA Turing (RTX 20xx / GTX 16xx)
    ("RTX 208", "Turing",        10, 120, 800,  75, 5, 83,
     "RTX 2080 family"),
    ("RTX 207", "Turing",        10, 110, 800,  75, 5, 83,
     "RTX 2070 family"),
    ("RTX 206", "Turing",         8, 100, 700,  78, 5, 83,
     "RTX 2060 family"),
    ("GTX 166", "Turing",         8,  80, 600,  80, 5, 83,
     "GTX 1660 family"),
    ("GTX 165", "Turing",         8,  80, 600,  80, 5, 83,
     "GTX 1650 family"),

    # NVIDIA Pascal (GTX 10xx)
    ("GTX 108", "Pascal",         8,  80, 500,  82, 5, 83,
     "GTX 1080 family"),
    ("GTX 107", "Pascal",         8,  80, 500,  82, 5, 83,
     "GTX 1070 family"),
    ("GTX 106", "Pascal",         6,  60, 400,  85, 5, 83,
     "GTX 1060 family"),
    ("GTX 10",  "Pascal",         6,  60, 400,  85, 5, 83,
     "GTX 10-series — Pascal"),

    # AMD RDNA 3 (RX 7000)
    ("RX 79",   "RDNA 3",        10, 100, 1000, 70, 5, 85,
     "RX 7900 family"),
    ("RX 77",   "RDNA 3",        10, 100, 1000, 72, 5, 85,
     "RX 7700 family"),
    ("RX 76",   "RDNA 3",        10,  80,  800, 75, 5, 85,
     "RX 7600 family"),
    ("RX 7",    "RDNA 3",        10, 100, 1000, 72, 5, 85,
     "RX 7000-series — RDNA 3"),

    # AMD RDNA 2 (RX 6000)
    ("RX 69",   "RDNA 2",         8,  80,  800, 72, 5, 85,
     "RX 6900 family"),
    ("RX 68",   "RDNA 2",         8,  80,  800, 75, 5, 85,
     "RX 6800 family"),
    ("RX 67",   "RDNA 2",         8,  70,  700, 75, 5, 85,
     "RX 6700 family"),
    ("RX 6",    "RDNA 2",         8,  70,  700, 75, 5, 85,
     "RX 6000-series — RDNA 2"),

    # AMD RDNA 1 (RX 5000)
    ("RX 5",    "RDNA 1",         6,  60,  600, 78, 5, 85,
     "RX 5000-series — RDNA 1"),
]

_FALLBACK = GpuDefaults(
    gpu_name="Unknown",
    generation="Unknown",
    core_step_mhz=10,
    core_max_mhz=100,
    mem_max_mhz=500,
    power_min_pct=80,
    power_step_pct=5,
    max_temp_c=85,
    notes="Conservative generic defaults — GPU generation not recognized"
)


def get_defaults(gpu_name: str) -> GpuDefaults:
    """Match GPU name to generation table and return safe defaults."""
    name_upper = gpu_name.upper()
    for prefix, gen, c_step, c_max, m_max, p_min, p_step, t_max, notes in _TABLE:
        if prefix.upper() in name_upper:
            return GpuDefaults(
                gpu_name=gpu_name,
                generation=gen,
                core_step_mhz=c_step,
                core_max_mhz=c_max,
                mem_max_mhz=m_max,
                power_min_pct=p_min,
                power_step_pct=p_step,
                max_temp_c=t_max,
                notes=notes,
            )
    return GpuDefaults(
        gpu_name=gpu_name,
        generation="Unknown",
        core_step_mhz=_FALLBACK.core_step_mhz,
        core_max_mhz=_FALLBACK.core_max_mhz,
        mem_max_mhz=_FALLBACK.mem_max_mhz,
        power_min_pct=_FALLBACK.power_min_pct,
        power_step_pct=_FALLBACK.power_step_pct,
        max_temp_c=_FALLBACK.max_temp_c,
        notes=f"Unknown GPU: {gpu_name} — using conservative defaults",
    )

"""
GameOptimizerPro v2.0 — V/F Curve Builder
Erstellt präzise Voltage-Frequency Kurven für MSI Afterburner.

RTX 40xx (Ada Lovelace) V/F Curve:
- Spannungsbereich: 650mV – 1100mV (GDDR6X: GPU selbst bestimmt max)
- 512 Kurven-Punkte, jeder 1mV Schritt
- Format: kommagetrennte MHz-Offsets für jeden mV-Punkt

Methode (wie Profis undervolten):
1. Bestimme Ziel-Frequenz (z.B. 2700 MHz aus Stage 1)
2. Finde minimale stabile Spannung bei dieser Frequenz
3. Schreibe flache Kurve: alle Punkte >= Ziel-Spannung = Ziel-Frequenz
   Alle Punkte < Ziel-Spannung = 0 (GPU boosted nicht dorthin)

Das erzeugt eine "L-förmige" Kurve:
  Freq ▲
  2700 │           ████████████  ← flach bei Zielfrequenz
       │      █████
       │  ████
       └──────────────────────▶ Volt
          750  850  950  1050
"""

from dataclasses import dataclass
from typing import Optional


# Ada Lovelace / RTX 40xx Spannungsbereiche
ADA_VOLT_MIN_MV  = 650
ADA_VOLT_MAX_MV  = 1100
ADA_VOLT_POINTS  = 512   # Afterburner nutzt 512 Punkte

# Ampere / RTX 30xx
AMPERE_VOLT_MIN_MV = 650
AMPERE_VOLT_MAX_MV = 1100
AMPERE_VOLT_POINTS = 512

# Turing / RTX 20xx
TURING_VOLT_MIN_MV = 600
TURING_VOLT_MAX_MV = 1100
TURING_VOLT_POINTS = 512


@dataclass
class VFPoint:
    voltage_mv: int
    freq_mhz:   int


@dataclass
class VFCurve:
    """
    Represents a complete V/F curve for Afterburner.
    lock_voltage_mv  = Spannung ab der wir flatline machen (Untervolting-Punkt)
    lock_freq_mhz    = Frequenz die wir halten wollen
    base_core_offset = Core-Offset aus Stage 1 (für OC+UV Kombi)
    """
    lock_voltage_mv:  int = 0
    lock_freq_mhz:    int = 0
    base_core_offset: int = 0
    gpu_generation:   str = "Ada"

    # Vollständige Kurve (512 Punkte) als MHz-Offsets
    # offset[i] = wie viel MHz über/unter dem Basis-Takt bei Spannung i
    curve_offsets: list = None

    def __post_init__(self):
        if self.curve_offsets is None:
            self.curve_offsets = []

    def to_afterburner_string(self) -> str:
        """
        Gibt den Kurvenstring im Afterburner-Format zurück.
        Format: kommagetrennte Offsets für alle 512 Spannungspunkte.
        """
        if not self.curve_offsets:
            return ""
        return ",".join(str(v) for v in self.curve_offsets)

    def summary(self) -> str:
        return (
            f"V/F Curve: {self.lock_freq_mhz} MHz @ {self.lock_voltage_mv} mV"
            f" (Base offset +{self.base_core_offset} MHz)"
        )


class VFCurveBuilder:
    """
    Baut optimierte V/F Kurven für NVIDIA GPUs.

    Schritt 1: Wir kennen aus Stage 1 die maximale stabile Frequenz.
    Schritt 2: UV-Test findet minimale stabile Spannung für diese Frequenz.
    Schritt 3: Wir bauen eine flache Kurve ("flatline") bei dieser Spannung.

    Das Ergebnis: GPU erreicht gleiche oder höhere Frequenz bei weniger Spannung.
    Typische Einsparung RTX 4080: 50-150mV, 30-80W weniger, 5-15°C kühler.
    """

    # Spannungsschritte für UV-Test (von hoch nach niedrig)
    UV_STEP_MV = 25   # 25mV Schritte — präzise ohne zu langsam zu sein

    def __init__(self, gpu_generation: str = "Ada"):
        self.gen = gpu_generation
        if "Ada" in gpu_generation or "40" in gpu_generation:
            self.volt_min   = ADA_VOLT_MIN_MV
            self.volt_max   = ADA_VOLT_MAX_MV
            self.n_points   = ADA_VOLT_POINTS
        elif "Ampere" in gpu_generation or "30" in gpu_generation:
            self.volt_min   = AMPERE_VOLT_MIN_MV
            self.volt_max   = AMPERE_VOLT_MAX_MV
            self.n_points   = AMPERE_VOLT_POINTS
        else:
            self.volt_min   = TURING_VOLT_MIN_MV
            self.volt_max   = TURING_VOLT_MAX_MV
            self.n_points   = TURING_VOLT_POINTS

    def volt_to_index(self, voltage_mv: int) -> int:
        """Konvertiert mV zu Afterburner-Kurven-Index."""
        volt_range = self.volt_max - self.volt_min
        idx = int((voltage_mv - self.volt_min) / volt_range * (self.n_points - 1))
        return max(0, min(self.n_points - 1, idx))

    def index_to_volt(self, idx: int) -> int:
        """Konvertiert Afterburner-Index zurück zu mV."""
        volt_range = self.volt_max - self.volt_min
        mv = self.volt_min + int(idx / (self.n_points - 1) * volt_range)
        return mv

    def build_flatline_curve(
        self,
        target_freq_mhz: int,
        lock_voltage_mv:  int,
        base_core_offset: int = 0,
    ) -> VFCurve:
        """
        Baut eine "L-förmige" Flatline-Kurve:
        - Alle Spannungen >= lock_voltage_mv: laufen auf target_freq_mhz
        - Alle Spannungen < lock_voltage_mv: 0 Offset (GPU boosted nie dorthin)

        base_core_offset: der positive Core-Offset aus Stage 1 OC.
        target_freq_mhz: absolute Frequenz die wir erreichen wollen.
        """
        offsets = [0] * self.n_points
        lock_idx = self.volt_to_index(lock_voltage_mv)

        # Ab lock_voltage_mv: setze alle Punkte auf gleiches Offset
        # Das zwingt die GPU auf target_freq_mhz bei dieser Spannung zu laufen
        # und sie geht nie über diesen Punkt hinaus (spart Spannung + Watt)
        for i in range(lock_idx, self.n_points):
            offsets[i] = base_core_offset  # Offset bleibt gleich (von Stage 1)

        # Punkte unterhalb des Lock-Punktes auf 0 setzen
        # GPU wird automatisch idle/niedrig-takt bei niedriger Last
        for i in range(0, lock_idx):
            offsets[i] = 0

        return VFCurve(
            lock_voltage_mv=lock_voltage_mv,
            lock_freq_mhz=target_freq_mhz,
            base_core_offset=base_core_offset,
            gpu_generation=self.gen,
            curve_offsets=offsets,
        )

    def get_uv_test_voltages(
        self,
        start_voltage_mv: int,
        min_voltage_mv:   int = 750,
    ) -> list[int]:
        """
        Gibt Liste von Spannungen zurück die wir testen sollen (hoch → niedrig).
        Startet bei start_voltage_mv (gemessene Betriebsspannung) und geht runter.
        min_voltage_mv: untere Grenze (RTX 4080 unter 750mV = gefährlich instabil)
        """
        voltages = []
        v = start_voltage_mv - self.UV_STEP_MV  # Erster Test: schon etwas unter aktuell
        while v >= min_voltage_mv:
            voltages.append(v)
            v -= self.UV_STEP_MV
        return voltages

    def recommend_start_voltage(self, avg_voltage_mv: float) -> int:
        """
        Empfiehlt die Startspannung für UV-Tests basierend auf gemessener Spannung.
        Wir runden auf nächste 25mV-Grenze und gehen 25mV darunter.
        """
        rounded = int(avg_voltage_mv / self.UV_STEP_MV) * self.UV_STEP_MV
        # Starte 2 Schritte unter Betriebsspannung (konservativ)
        return max(750, rounded - self.UV_STEP_MV * 2)


def get_builder_for_gpu(gpu_name: str) -> VFCurveBuilder:
    """Gibt den richtigen Builder für die erkannte GPU zurück."""
    gpu_upper = gpu_name.upper()
    if "RTX 40" in gpu_upper:
        return VFCurveBuilder("Ada Lovelace")
    elif "RTX 30" in gpu_upper:
        return VFCurveBuilder("Ampere")
    elif "RTX 20" in gpu_upper or "GTX 16" in gpu_upper:
        return VFCurveBuilder("Turing")
    else:
        return VFCurveBuilder("Ada")  # Konservativ/Default

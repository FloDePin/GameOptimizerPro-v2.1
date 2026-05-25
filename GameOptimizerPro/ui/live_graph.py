"""
GameOptimizerPro Live Graph
Rolling canvas-based line chart for Voltage and Core Clock during tuning.
No external deps — pure tkinter Canvas.
"""

import tkinter as tk
from collections import deque
from ui.widgets import BG2, BG3, BOR, ACC, VOLT, ERR, WRN, DIM, TXT, FM


class LiveGraph(tk.Frame):
    """
    Dual-series rolling line graph.
    Series A = Core Clock (MHz, cyan)
    Series B = Voltage (mV, purple)
    """

    MAX_POINTS = 120   # 2 minutes at 1s resolution

    def __init__(self, parent, height=160, **kw):
        super().__init__(parent, bg=BG2, **kw)

        # Data
        self._clocks   = deque(maxlen=self.MAX_POINTS)
        self._voltages = deque(maxlen=self.MAX_POINTS)
        self._temps    = deque(maxlen=self.MAX_POINTS)

        # Ranges (auto-scaled)
        self._clk_min  = 0
        self._clk_max  = 3000
        self._volt_min = 700
        self._volt_max = 1100
        self._temp_max = 100

        self._height = height
        self._build()

    def _build(self):
        # Legend
        leg = tk.Frame(self, bg=BG2)
        leg.pack(fill="x", padx=8, pady=(4, 0))
        for color, label in ((ACC, "Core MHz"), (VOLT, "Voltage mV"), (ERR, "Temp °C")):
            dot = tk.Label(leg, text="●", font=("Consolas", 10),
                           fg=color, bg=BG2)
            dot.pack(side="left")
            tk.Label(leg, text=label, font=FM, fg=DIM, bg=BG2,
                     padx=6).pack(side="left")

        # Canvas
        self.cv = tk.Canvas(self, bg=BG3, height=self._height,
                            highlightthickness=1, highlightbackground=BOR)
        self.cv.pack(fill="x", padx=4, pady=4)
        self.cv.bind("<Configure>", lambda e: self._redraw())

        # Last-value labels
        vals = tk.Frame(self, bg=BG2)
        vals.pack(fill="x", padx=8, pady=(0, 4))
        self.lbl_clk  = tk.Label(vals, text="Clock: -- MHz", font=FM,
                                  fg=ACC,  bg=BG2)
        self.lbl_volt = tk.Label(vals, text="Volt: -- mV",   font=FM,
                                  fg=VOLT, bg=BG2)
        self.lbl_temp = tk.Label(vals, text="Temp: -- °C",   font=FM,
                                  fg=ERR,  bg=BG2)
        for w in (self.lbl_clk, self.lbl_volt, self.lbl_temp):
            w.pack(side="left", padx=10)

    def push(self, core_mhz: float, voltage_mv: float, temp: float):
        self._clocks.append(core_mhz)
        self._voltages.append(voltage_mv)
        self._temps.append(temp)

        # Auto-scale
        if self._clocks:
            self._clk_min  = max(0,   min(self._clocks)   - 50)
            self._clk_max  = max(100, max(self._clocks)   + 50)
        if self._voltages and max(self._voltages) > 0:
            self._volt_min = max(0,   min(v for v in self._voltages if v > 0) - 50)
            self._volt_max = max(100, max(self._voltages) + 50)

        self.lbl_clk.config( text=f"Clock: {core_mhz:.0f} MHz")
        self.lbl_volt.config(text=f"Volt: {voltage_mv:.0f} mV"
                             if voltage_mv > 0 else "Volt: -- mV")
        self.lbl_temp.config(text=f"Temp: {temp:.0f}°C")
        self._redraw()

    def clear(self):
        self._clocks.clear()
        self._voltages.clear()
        self._temps.clear()
        self.cv.delete("all")

    def _redraw(self, *_):
        self.cv.delete("all")
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        if w < 10 or h < 10:
            return

        pad_l, pad_r, pad_t, pad_b = 40, 10, 8, 20
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        # Grid lines
        for i in range(1, 4):
            y = pad_t + plot_h * i // 4
            self.cv.create_line(pad_l, y, w - pad_r, y,
                                fill=BOR, dash=(2, 4))

        n = len(self._clocks)
        if n < 2:
            # Draw empty axes
            self.cv.create_line(pad_l, pad_t, pad_l, h - pad_b, fill=BOR)
            self.cv.create_line(pad_l, h - pad_b, w - pad_r, h - pad_b, fill=BOR)
            return

        def x_pos(i):
            return pad_l + plot_w * i / (self.MAX_POINTS - 1)

        def y_norm(val, lo, hi):
            if hi == lo:
                return pad_t + plot_h // 2
            frac = (val - lo) / (hi - lo)
            return h - pad_b - int(frac * plot_h)

        # Draw series
        def draw_series(data, lo, hi, color):
            pts = list(data)
            if len(pts) < 2:
                return
            offset = self.MAX_POINTS - len(pts)
            coords = []
            for i, v in enumerate(pts):
                if v > 0:
                    coords.append(x_pos(i + offset))
                    coords.append(y_norm(v, lo, hi))
            if len(coords) >= 4:
                self.cv.create_line(*coords, fill=color, width=1.5, smooth=True)

        draw_series(self._clocks,   self._clk_min,  self._clk_max,  ACC)
        draw_series(self._voltages, self._volt_min, self._volt_max, VOLT)
        draw_series(self._temps,    0,              self._temp_max, ERR)

        # Axes
        self.cv.create_line(pad_l, pad_t, pad_l, h - pad_b, fill=BOR)
        self.cv.create_line(pad_l, h - pad_b, w - pad_r, h - pad_b, fill=BOR)

        # Y axis labels (clock)
        for val, label in (
            (self._clk_max, f"{self._clk_max:.0f}"),
            (self._clk_min, f"{self._clk_min:.0f}"),
        ):
            y = y_norm(val, self._clk_min, self._clk_max)
            self.cv.create_text(pad_l - 4, y, text=label,
                                anchor="e", font=("Consolas", 7), fill=DIM)

"""NVTuner Stress Worker — runs in subprocess to load GPU."""
import sys

def cuda_stress():
    import cupy as cp
    a = cp.random.rand(8192, 8192, dtype=cp.float32)
    b = cp.random.rand(8192, 8192, dtype=cp.float32)
    while True:
        c = cp.dot(a, b)
        cp.cuda.Stream.null.synchronize()
        a = c % 1.0 + 0.001

def cpu_stress():
    try:
        import numpy as np
        s = 4096
        a = np.random.rand(s, s).astype(np.float32)
        b = np.random.rand(s, s).astype(np.float32)
        while True:
            c = np.dot(a, b)
            a = c % 1.0 + 0.001
    except KeyboardInterrupt:
        pass
    except ImportError:
        while True:
            _ = sum(i * i for i in range(200000))

if __name__ == "__main__":
    try:
        cuda_stress()
    except (ImportError, Exception):
        cpu_stress()

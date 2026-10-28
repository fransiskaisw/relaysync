"""Processing 1: estimasi jarak relatif dari hitungan langkah."""
from __future__ import annotations


class CalibrationError(ValueError):
    """Data kalibrasi panjang langkah tidak masuk akal."""


def estimate_distance_m(steps: int, step_len_m: float) -> float:
    """Jarak = langkah x panjang langkah. Ini estimasi, bukan pengukuran."""
    return steps * step_len_m


def step_length_from_run(distance_m: float, steps: int, lo_m: float, hi_m: float) -> float:
    """Panjang langkah dari lintasan berjarak diketahui; ditolak bila di luar [lo, hi]."""
    if steps <= 0:
        raise CalibrationError("tidak ada langkah tercatat selama kalibrasi")
    length = distance_m / steps
    if not lo_m <= length <= hi_m:
        raise CalibrationError(
            f"panjang langkah {length:.2f} m di luar rentang wajar [{lo_m}, {hi_m}] m"
        )
    return length

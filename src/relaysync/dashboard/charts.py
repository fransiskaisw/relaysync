"""Konversi deret waktu menjadi DataFrame pandas untuk grafik Streamlit."""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from relaysync.settings.models import FusionSettings

from .feed import TimePoint


def build_timeseries_df(points: Sequence[TimePoint], fusion: FusionSettings) -> pd.DataFrame:
    if not points:
        return pd.DataFrame()
    rows = [
        {
            "waktu_s": p.t_s,
            "x1_m": p.x1_m,
            "x2_m": p.x2_m,
            "gap_m": p.gap_m,
            "gap_opt_max_m": fusion.gap_opt_max_m,
            "gap_far_m": fusion.gap_far_m,
            "v1_mps": p.v1_mps,
            "v2_mps": p.v2_mps,
            "cadence1_spm": p.cadence1_spm,
            "cadence2_spm": p.cadence2_spm,
        }
        for p in points
    ]
    return pd.DataFrame(rows).set_index("waktu_s")

"""Halaman 2: Grafik deret waktu gap, jarak tempuh, kadens, dan kecepatan."""
from __future__ import annotations

import streamlit as st

from relaysync.dashboard.charts import build_timeseries_df
from relaysync.dashboard.feed import FeedSnapshot
from relaysync.settings.models import Settings


def render_charts(snap: FeedSnapshot, settings: Settings) -> None:
    st.subheader("Grafik Deret Waktu")
    df = build_timeseries_df(snap.points, settings.fusion)
    if df.empty:
        st.info("Belum ada data deret waktu. Jalankan sesi atau muat berkas replay.")
        return

    f = settings.fusion
    st.markdown(
        f"**1. Gap Antar Pelari terhadap Waktu (m)** "
        f"(Batas optimal maks: `{f.gap_opt_max_m:g} m`, batas terlalu jauh: `{f.gap_far_m:g} m`)"
    )
    st.line_chart(df[["gap_m", "gap_opt_max_m", "gap_far_m"]])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**2. Jarak Posisi Kedua Pelari (x1 dan x2 dalam m)**")
        st.line_chart(df[["x1_m", "x2_m"]])
    with col2:
        st.markdown("**3. Kecepatan Estimasi (v1 dan v2 dalam m/s)**")
        st.line_chart(df[["v1_mps", "v2_mps"]])

    st.markdown("**4. Kadens Langkah (cadence1 dan cadence2 dalam langkah/menit)**")
    st.line_chart(df[["cadence1_spm", "cadence2_spm"]])

"""Halaman 3: Tabel riwayat percobaan, skor kualitas, dan unduh CSV."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from relaysync.dashboard.feed import FeedSnapshot


def render_attempts(snap: FeedSnapshot) -> None:
    st.subheader(" Evaluasi dan Riwayat Percobaan")
    if not snap.attempts:
        st.info(
            "Belum ada percobaan yang selesai. Serah terima tercatat otomatis di zona optimal "
            "atau saat tombol 'Tandai Serah Terima' ditekan."
        )
        return

    rows = [
        {
            "percobaan": a.attempt_no,
            "jenis": a.kind,
            "gap_saat_handoff_m": round(a.gap_m, 2),
            "v1_mps": round(a.v1_mps, 2),
            "v2_mps": round(a.v2_mps, 2),
            "selisih_v_mps": round(abs(a.v1_mps - a.v2_mps), 2),
            "durasi_cue_ke_handoff_s": (
                None if a.cue_to_handoff_s is None else round(a.cue_to_handoff_s, 2)
            ),
            "jumlah_alert": len(a.alerts),
            "daftar_alert": ", ".join(a.alerts) if a.alerts else "-",
            "skor_kualitas": a.score,
        }
        for a in snap.attempts
    ]
    df = pd.DataFrame(rows)

    best = max(a.score for a in snap.attempts)
    avg = sum(a.score for a in snap.attempts) / len(snap.attempts)
    c1, c2, c3 = st.columns(3)
    c1.metric("Jumlah Percobaan", len(snap.attempts))
    c2.metric("Rata-rata Skor Kualitas", f"{avg:.1f} / 100")
    c3.metric("Skor Terbaik", f"{best} / 100")

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Unduh Riwayat Percobaan (CSV)",
        data=csv_bytes,
        file_name="relaysync_percobaan.csv",
        mime="text/csv",
    )

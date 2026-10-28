"""Halaman 5: Log event engine, alert, dan cue dua arah."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from relaysync.dashboard.feed import FeedSnapshot


def _fmt_ms(epoch_ms: int) -> str:
    try:
        return datetime.fromtimestamp(epoch_ms / 1000.0).strftime("%H:%M:%S.%f")[:-3]
    except (OSError, OverflowError, ValueError):
        return str(epoch_ms)


def render_log(snap: FeedSnapshot) -> None:
    st.subheader("Log Event dan Alert")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Riwayat Alert dan Cue (Komunikasi 2 Arah)**")
        alert_rows = [
            {
                "waktu": _fmt_ms(a.issued_ms),
                "jenis": a.event.value,
                "alasan": a.reason.value,
                "gap_m": round(a.gap_m, 2),
            }
            for a in snap.alerts
        ]
        if alert_rows:
            st.dataframe(pd.DataFrame(alert_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada pesan di topic alerts.")

        if snap.cues:
            cue_times = ", ".join(_fmt_ms(c.issued_ms) for c in snap.cues[:10])
            st.caption(f"Cue GO terkirim ({len(snap.cues)} kali): {cue_times}")

    with col2:
        st.markdown("**Log Event Engine**")
        event_rows = [
            {
                "waktu": _fmt_ms(e.at_ms),
                "kategori": e.kind.value,
                "pesan": e.message,
            }
            for e in snap.events
        ]
        if event_rows:
            st.dataframe(pd.DataFrame(event_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada pesan di topic events.")

"""Entry point dashboard Streamlit RelaySync."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from relaysync.dashboard.feed import LiveFeed
from relaysync.dashboard.views.about_view import render_about
from relaysync.dashboard.views.attempts_view import render_attempts
from relaysync.dashboard.views.calibration_view import render_calibration_and_settings
from relaysync.dashboard.views.charts_view import render_charts
from relaysync.dashboard.views.live_view import render_live
from relaysync.dashboard.views.log_view import render_log
from relaysync.settings import ConfigError, load_runtime

DISCLAIMER_BANNER = (
    "Jarak adalah estimasi dari hitungan langkah, bukan GPS. Bukan alat ukur resmi."
)


@st.cache_resource
def get_live_feed() -> LiveFeed:
    runtime = load_runtime()
    return LiveFeed(runtime)


def _render_sidebar(feed: LiveFeed) -> float:
    with st.sidebar:
        st.header("RelaySync")
        st.caption(f"TEAM_ID: `{feed.runtime.team_id}`")
        refresh_s = st.slider(
            "Interval segarkan layar (detik)", min_value=0.5, max_value=5.0, value=1.0, step=0.5
        )
        st.divider()
        st.subheader("Mode Replay (Tanpa Broker)")
        uploaded = st.file_uploader(
            "Muat berkas CSV / JSONL hasil record atau simulate_race",
            type=["csv", "json", "jsonl"],
        )
        if uploaded is not None:
            if st.button("Jalankan Replay Berkas Upload", use_container_width=True):
                content = uploaded.getvalue().decode("utf-8", errors="replace")
                count = feed.load_replay_text(uploaded.name, content)
                st.success(f"Replay dimuat ({count} rekaman).")

        recordings_dir = Path("recordings")
        sample_files = (
            sorted(
                p
                for p in recordings_dir.glob("*")
                if p.suffix.lower() in {".csv", ".json", ".jsonl"}
            )
            if recordings_dir.is_dir()
            else []
        )
        if sample_files:
            chosen = st.selectbox(
                "Atau pilih berkas dari folder recordings/",
                options=[str(p) for p in sample_files],
            )
            if st.button("Muat dari recordings/", use_container_width=True):
                path = Path(chosen)
                count = feed.load_replay_text(path.name, path.read_text(encoding="utf-8"))
                st.success(f"Replay '{path.name}' dimuat ({count} rekaman).")

        if st.button("Kembali ke Mode MQTT Live", use_container_width=True):
            feed.clear_replay()
            st.info("Beralih ke aliran MQTT Live.")

    return float(refresh_s)


def main() -> None:
    st.set_page_config(
        page_title="RelaySync Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.info(DISCLAIMER_BANNER)

    try:
        feed = get_live_feed()
    except ConfigError as exc:
        st.error(f"Konfigurasi belum siap: {exc}")
        st.stop()
        return

    refresh_s = _render_sidebar(feed)

    @st.fragment(run_every=refresh_s)
    def _dashboard_body() -> None:
        snap = feed.snapshot()
        tabs = st.tabs(
            [
                "1. Live",
                "2. Grafik",
                "3. Percobaan",
                "4. Kalibrasi dan Pengaturan",
                "5. Log",
                "6. Tentang",
            ]
        )
        with tabs[0]:
            render_live(feed, snap)
        with tabs[1]:
            render_charts(snap, feed.runtime.settings)
        with tabs[2]:
            render_attempts(snap)
        with tabs[3]:
            render_calibration_and_settings(feed, snap)
        with tabs[4]:
            render_log(snap)
        with tabs[5]:
            render_about(feed)

    _dashboard_body()


if __name__ == "__main__":
    main()

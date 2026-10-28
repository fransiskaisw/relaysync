"""Halaman 1: Pemantauan Live lintasan estafet, metrik, dan tombol kontrol."""
from __future__ import annotations

import streamlit as st

from relaysync.dashboard.feed import FeedSnapshot, LiveFeed
from relaysync.dashboard.track_view import state_badge_html, track_svg_html
from relaysync.domain.models import Role
from relaysync.domain.states import ALERT_TEXT
from relaysync.messaging.codec import CommandName, ControlCommand


def render_live(feed: LiveFeed, snap: FeedSnapshot) -> None:
    _render_presence_bar(feed, snap)
    _render_controls(feed)

    session = snap.session
    if session is None:
        _render_diagnostics(feed, snap)
        return

    if session.alert_active and session.alert_reason is not None:
        reason_text = ALERT_TEXT.get(session.alert_reason, session.alert_reason.value)
        st.error(f"PERINGATAN AKTIF [{session.alert_reason.value}]: {reason_text}")

    st.markdown(state_badge_html(session.state, session.reason), unsafe_allow_html=True)
    st.markdown(
        track_svg_html(session, feed.runtime.settings.track.entry_margin_m),
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Posisi Pelari 1 (x1)", f"{session.x1_m:.1f} m")
    c2.metric("Posisi Pelari 2 (x2)", f"{session.x2_m:.1f} m")
    c3.metric("Gap Antar Pelari", f"{session.gap_m:.2f} m")
    c4.metric("Jarak ke Zona (Z - x1)", f"{session.remaining_to_zone_m:.1f} m")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Kecepatan (v1 / v2)", f"{session.v1_mps:.1f} / {session.v2_mps:.1f} m/s")
    c6.metric("Kadens (P1 / P2)", f"{session.cadence1_spm:.0f} / {session.cadence2_spm:.0f} spm")
    ready_text = session.readiness2.value if session.readiness2 else "-"
    c7.metric("Kesiapan Pelari 2", ready_text)
    eta_text = "-" if session.eta_s is None else f"{session.eta_s:.1f} s"
    c8.metric("ETA ke Zona / Skor", f"{eta_text} | Skor: {session.quality_score or '-'}")

    _render_edge_details(snap)


def _render_presence_bar(feed: LiveFeed, snap: FeedSnapshot) -> None:
    broker_cfg = feed.runtime.settings.broker
    b_status = "Terhubung" if snap.connected else "Menghubungkan..."
    e1_status = "ONLINE" if snap.online.get(Role.EDGE1) else "OFFLINE"
    e2_status = "ONLINE" if snap.online.get(Role.EDGE2) else "OFFLINE"
    mode_label = "REPLAY BERKAS" if snap.mode == "replay" else "MQTT LIVE"
    st.caption(
        f"Mode: **{mode_label}** | TEAM_ID: `{feed.runtime.team_id}` | "
        f"Broker `{broker_cfg.host}:{broker_cfg.port}`: **{b_status}** | "
        f"HP edge1: **{e1_status}** | HP edge2: **{e2_status}**"
    )


def _render_controls(feed: LiveFeed) -> None:
    cols = st.columns(6)
    buttons = [
        ("Start", CommandName.START),
        ("Stop", CommandName.STOP),
        ("Reset", CommandName.RESET),
        ("Ack Alert", CommandName.ACK),
        ("Tandai Serah Terima", CommandName.HANDOFF),
        ("Percobaan Baru", CommandName.NEW_ATTEMPT),
    ]
    for col, (label, cmd_name) in zip(cols, buttons, strict=True):
        if col.button(label, key=f"btn_{cmd_name.value}", use_container_width=True):
            feed.send_command(ControlCommand(cmd_name))
            st.toast(f"Perintah '{cmd_name.value}' dikirim.")


def _render_diagnostics(feed: LiveFeed, snap: FeedSnapshot) -> None:
    st.warning("Belum ada paket session yang diterima dari engine.")
    cfg = feed.runtime.settings.broker
    st.markdown(
        f"""
**Diagnostik Koneksi:**
- **TEAM_ID aktif**: `{feed.runtime.team_id}`
- **Broker MQTT**: `{cfg.host}:{cfg.port}` (TLS: `{cfg.tls}`)
- **Status Koneksi Dashboard**: `{"Terhubung" if snap.connected else "Belum terhubung"}`
- **Status Presence HP**: edge1=`{"ONLINE" if snap.online.get(Role.EDGE1) else "OFFLINE"}`, edge2=`{"ONLINE" if snap.online.get(Role.EDGE2) else "OFFLINE"}`

**Langkah Pemeriksaan:**
1. Pastikan `relaysync-engine` sudah berjalan di laptop dengan `.env` (`TEAM_ID`) yang sama.
2. Jalankan `relaysync-edge --role edge1` dan `relaysync-edge --role edge2` di HP (atau tambahkan `--simulate`).
3. Atau gunakan **Mode Replay** di bilah samping untuk memuat berkas hasil `tools/simulate_race.py`.
"""
    )


def _render_edge_details(snap: FeedSnapshot) -> None:
    if not snap.last_telemetry:
        return
    with st.expander("Detail Telemetry Terakhir per Perangkat"):
        cols = st.columns(2)
        for idx, role in enumerate((Role.EDGE1, Role.EDGE2)):
            tele = snap.last_telemetry.get(role)
            if tele is None:
                cols[idx].info(f"Belum ada telemetry dari {role.value}.")
                continue
            f = tele.features
            extra = (
                f", gyro_path={f.gyro_path_rad:.2f} rad, readiness={f.readiness.value if f.readiness else '-'}"
                if role is Role.EDGE2
                else ""
            )
            cols[idx].markdown(
                f"**{role.value}** (run `{tele.run}`, msg #{tele.n_msg})\n"
                f"- Langkah: `{f.steps_total}` (sumber: `{f.steps_src.value}`)\n"
                f"- Panjang langkah: `{f.step_len_m:.3f} m` (kalibrasi: `{f.calibrated}`)\n"
                f"- Jarak estimasi: `{f.dist_est_m:.2f} m`\n"
                f"- Kadens: `{f.cadence_spm:.1f} spm`, accel_dev_rms: `{f.accel_dev_rms:.2f} m/s^2`{extra}"
            )

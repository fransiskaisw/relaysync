"""Halaman 4: Kalibrasi panjang langkah dan pengaturan panjang lintasan serta zona."""
from __future__ import annotations

import streamlit as st

from relaysync.dashboard.feed import FeedSnapshot, LiveFeed
from relaysync.domain.models import Role
from relaysync.messaging.codec import CommandName, ControlCommand


def render_calibration_and_settings(feed: LiveFeed, snap: FeedSnapshot) -> None:
    eng = feed.runtime.settings.engine
    st.subheader("Kalibrasi Panjang Langkah (calibrate_step)")
    st.markdown(
        """
**Panduan Kalibrasi 2 Langkah:**
1. Pilih target perangkat (`edge1` atau `edge2`) dan masukkan jarak lintasan ukur (misalnya `20` meter).
2. Klik tombol **Kirim Perintah calibrate_step** pertama kali untuk **memulai** perekaman langkah.
3. Pelari berjalan atau berlari menempuh jarak tersebut secara konstan.
4. Klik tombol **Kirim Perintah calibrate_step** kedua kali untuk **menyelesaikan** dan menyimpan `step_len_m` ke `~/.relaysync/calibration.json`.
"""
    )

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        target_str = st.selectbox("Perangkat Target", [Role.EDGE1.value, Role.EDGE2.value])
    with col_b:
        dist_m = st.number_input(
            "Jarak Ukur Kalibrasi (m)",
            min_value=float(eng.calibrate_min_m),
            max_value=float(eng.calibrate_max_m),
            value=float(eng.calibrate_default_m),
            step=5.0,
        )
    with col_c:
        st.write("")
        st.write("")
        if st.button("Kirim Perintah calibrate_step", use_container_width=True):
            cmd = ControlCommand(
                CommandName.CALIBRATE_STEP,
                target=Role(target_str),
                distance_m=float(dist_m),
            )
            feed.send_command(cmd)
            st.success(f"Perintah calibrate_step ({target_str}, {dist_m:g} m) dikirim.")

    _render_current_calibration(snap)

    st.subheader("Pengaturan Geometri Lintasan (config)")
    cur_leg = snap.session.leg_length_m if snap.session else feed.runtime.settings.track.leg_length_m
    cur_zone = (
        snap.session.zone_length_m if snap.session else feed.runtime.settings.track.zone_length_m
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        new_leg = st.number_input(
            "Posisi Awal Zona / leg_length_m (m)",
            min_value=float(eng.leg_min_m),
            max_value=float(eng.leg_max_m),
            value=float(cur_leg),
            step=5.0,
        )
    with c2:
        new_zone = st.number_input(
            "Panjang Zona Transisi / zone_length_m (m)",
            min_value=float(eng.zone_min_m),
            max_value=float(eng.zone_max_m),
            value=float(cur_zone),
            step=5.0,
        )
    with c3:
        st.write("")
        st.write("")
        if st.button("Terapkan Konfigurasi Lintasan", use_container_width=True):
            cmd = ControlCommand(
                CommandName.CONFIG,
                leg_length_m=float(new_leg),
                zone_length_m=float(new_zone),
            )
            feed.send_command(cmd)
            st.success(
                f"Konfigurasi lintasan dikirim: leg_length_m={new_leg:g} m, zone_length_m={new_zone:g} m."
            )


def _render_current_calibration(snap: FeedSnapshot) -> None:
    cols = st.columns(2)
    for idx, role in enumerate((Role.EDGE1, Role.EDGE2)):
        tele = snap.last_telemetry.get(role)
        if tele is None:
            cols[idx].info(f"{role.value}: belum ada laporan telemetry.")
        else:
            f = tele.features
            status = "Terkalibrasi" if f.calibrated else "Default konfigurasi"
            cols[idx].metric(
                f"Panjang Langkah {role.value}",
                f"{f.step_len_m:.3f} m ({status})",
                help=f"Sumber langkah aktif: {f.steps_src.value}",
            )

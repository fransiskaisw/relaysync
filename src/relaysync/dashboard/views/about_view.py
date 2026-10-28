"""Halaman 6: Tentang proyek, disclaimer kejujuran, daftar topic, dan versi."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from relaysync import __version__
from relaysync.dashboard.feed import LiveFeed


def render_about(feed: LiveFeed) -> None:
    st.subheader(f"Tentang RelaySync (v{__version__})")
    st.markdown(
        """
**RelaySync: Sistem Pemantau Transisi dan Jarak Lari Estafet** adalah sistem IoT
multisensor dan komunikasi 2 arah untuk membantu pelatih serta pelari mengevaluasi
ketepatan waktu mulai berlari dan jarak serah terima tongkat estafet.

### Pernyataan Kejujuran Teknis (Disclaimer)
- **Jarak adalah estimasi dari hitungan langkah dikalikan panjang langkah** (`dist_est_m = steps_total * step_len_m`), **bukan GPS dan bukan pengukuran presisi**.
- Akurasi sangat bergantung pada kalibrasi panjang langkah masing-masing pelari dan posisi penempatan HP (disarankan di saku celana atau armband).
- Deteksi serah terima otomatis (`auto_handoff`) adalah estimasi kedekatan posisi dan kecocokan kecepatan di zona transisi, bukan deteksi kontak fisik tongkat.
- Sistem menggunakan **algoritma rule-based sensor fusion dengan state machine** (tanpa AI/ML).
- Tidak ditujukan untuk kompetisi resmi atau pengambilan keputusan keselamatan kritis.
"""
    )

    t = feed.topics
    st.markdown("### Peta Topic MQTT Aktif")
    topic_rows = [
        {"Topic": f"{t.root}/edge/edge1/telemetry", "Arah": "edge1 -> engine, dashboard", "Retained": "Tidak"},
        {"Topic": f"{t.root}/edge/edge2/telemetry", "Arah": "edge2 -> engine, dashboard", "Retained": "Tidak"},
        {"Topic": f"{t.root}/edge/<role>/presence", "Arah": "edge -> semua (Last Will)", "Retained": "Ya"},
        {"Topic": t.session, "Arah": "engine -> semua", "Retained": "Ya"},
        {"Topic": t.alerts, "Arah": "engine -> edge1, edge2, dashboard", "Retained": "Tidak"},
        {"Topic": t.cues, "Arah": "engine -> edge2", "Retained": "Tidak"},
        {"Topic": t.events, "Arah": "engine -> dashboard", "Retained": "Tidak"},
        {"Topic": t.control, "Arah": "dashboard -> engine, edge1, edge2", "Retained": "Tidak"},
    ]
    st.dataframe(pd.DataFrame(topic_rows), use_container_width=True, hide_index=True)

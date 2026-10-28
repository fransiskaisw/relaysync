# RelaySync: Sistem Pemantau Transisi dan Jarak Lari Estafet

RelaySync adalah sistem Internet of Things (IoT) multisensor dengan komunikasi dua arah berbasis MQTT untuk memantau transisi tongkat pada lari estafet. Dua perangkat HP Android (satu pada pelari pembawa tongkat `edge1` dan satu pada pelari penerima tongkat `edge2`) membaca sensor langkah serta gerak via Termux:API, menghitung fitur di edge, dan mengirimkannya ke broker MQTT. Mesin fusi (`relaysync-engine`) di laptop mengevaluasi geometri lintasan secara real time, mengirim aba-aba getar **GO** ke pelari 2 pada saat yang tepat, memicu alarm pada kedua HP bila terjadi kesalahan transisi, dan menyajikan visualisasi lintasan serta skor kualitas percobaan pada dashboard Streamlit.

> **Pernyataan Kejujuran Teknis (Disclaimer):**
> Jarak pada sistem ini adalah **ESTIMASI** dari hitungan langkah dikalikan panjang langkah (`dist_est_m = steps_total * step_len_m`), **bukan GPS dan bukan pengukuran presisi**. Akurasi bergantung pada kalibrasi panjang langkah dan posisi HP (saku atau armband). Sistem menggunakan algoritma *rule-based sensor fusion dengan state machine* (tanpa AI/ML) dan tidak ditujukan untuk kompetisi resmi atau keputusan keselamatan.

## Diagram Singkat Alur Sistem

```text
[HP 1: edge1] (Step Counter + Accelerometer)
      |
      | Telemetry (QoS 1) & Presence (Last Will)
      v
+---------------------------------------------------+
| Broker Cloud MQTT (broker.hivemq.com:8883 TLS)    |
+---------------------------------------------------+
      ^                                   |
      | Telemetry (QoS 1)                 | Cues ("go") & Alerts (Getar + Notifikasi)
      |                                   v
[HP 2: edge2] (Step Counter + Accelerometer + Gyroscope)
      ^
      | Session (retained), Events, Control (2 Arah)
      v
[Laptop: relaysync-engine + Dashboard Streamlit Lokal]
```

## Jalan dalam 10 Menit (Laptop dan 2 HP)

1. **Siapkan repositori dan `.env` di Laptop (Linux/macOS/Windows PowerShell):**
   ```bash
   python -m venv .venv
   # Linux/macOS:
   source .venv/bin/activate
   # Windows PowerShell: .\.venv\Scripts\Activate.ps1

   pip install -e ".[dashboard]"
   python tools/suggest_team_id.py
   cp .env.example .env
   # Edit .env dan isi TEAM_ID dengan hasil suggest_team_id.py (misal: relaysync-kelompok-9a4f)
   ```

2. **Siapkan kedua HP Android (Termux + Termux:API):**
   - Pasang aplikasi **Termux** dan **Termux:API** dari F-Droid, lalu berikan izin **Physical activity** dan **Notifications** ke Termux:API.
   - Di dalam Termux pada kedua HP, salin kode proyek, buat `.env` dengan `TEAM_ID` yang **sama persis** dengan laptop, lalu jalankan `pip install -e .` (panduan lengkap di `docs/SETUP.md`).

3. **Tiga Perintah Inti Menjalankan Sistem:**
   - **Terminal 1 (Laptop - Mesin Fusi Estafet):**
     ```bash
     relaysync-engine
     ```
   - **Terminal 2 (HP 1 dan HP 2 - Node Edge per Peran):**
     ```bash
     # Di HP Pelari 1 (pembawa tongkat):
     relaysync-edge --role edge1

     # Di HP Pelari 2 (penerima tongkat):
     relaysync-edge --role edge2
     ```
     *(Untuk mencoba di laptop tanpa HP, tambahkan opsi `--simulate` pada perintah `relaysync-edge`)*
   - **Terminal 3 (Laptop - Dashboard Streamlit Lokal):**
     ```bash
     streamlit run src/relaysync/dashboard/app.py
     ```

## Utilitas Tambahan (`tools/`)

- `python tools/suggest_team_id.py` : Menghasilkan saran `TEAM_ID` unik 4 karakter.
- `python tools/check_sensors.py` : Memeriksa daftar sensor Termux di HP dan pencocokan kata kunci sensor.
- `python tools/send_command.py start` : Mengirim perintah kontrol (`start`, `stop`, `reset`, `ack`, `handoff`, `calibrate_step`, `config`, `new_attempt`).
- `python tools/record_telemetry.py --out recordings/sesi1.jsonl` : Merekam paket MQTT langsung dari broker.
- `python tools/simulate_race.py --scenario optimal` : Menghasilkan berkas rekaman simulasi (`optimal`, `early_start`, `gap_too_far`, `no_data`) untuk diuji pada mode Replay di dashboard.

## Catatan Cloud dan Jaringan

Engine dan dashboard Streamlit dijalankan secara lokal di laptop yang berada pada jaringan Wi-Fi atau hotspot yang sama dengan pengguna. Komunikasi antar perangkat menggunakan broker MQTT publik (`broker.hivemq.com:8883` dengan TLS). Bila diinginkan, dashboard juga dapat dijalankan di server cloud dengan menunjuk variabel lingkungan `.env` ke `TEAM_ID` dan broker yang sama.

## Peta Dokumentasi (`docs/`)

- `docs/SETUP.md` : Panduan instalasi Termux, izin Android, variabel `.env` sensor, dan *troubleshooting*.
- `docs/ARCHITECTURE.md` : Diagram arsitektur, *sequence diagram* 2 arah, *state machine*, tabel topic, dan skema payload.
- `docs/ALGORITHM.md` : Rumus pemrosesan edge, geometri lintasan, aturan fusi, tabel transisi, dan rumus skor kualitas.
- `docs/TESTING.md` : Skenario pengujian lapangan, template tabel pengamatan, dan catatan status pengujian.
- `docs/DESIGN_DECISIONS.md` : Keputusan desain, fleksibilitas variabel sensor, cara pakai ulang modul, dan orisinalitas.
- `docs/PANDUAN_MEMBACA_KODE.md` : Urutan membaca modul dan pelacakan alur satu pesan dari langkah kaki hingga alert.
- `docs/SLIDES_DAN_DEMO.md` : Kerangka presentasi PPT, naskah video demo 3-4 menit, pemetaan rubrik, dan pembagian tugas tim.

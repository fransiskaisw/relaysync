# Kerangka Presentasi Slide, Skrip Video Demo, dan Rubrik (SLIDES DAN DEMO)

Dokumen ini disiapkan untuk membantu kelompok menyusun file presentasi (PPT) dan merekam video demonstrasi berdurasi 3 sampai 4 menit sesuai ketentuan tugas **Praktek Multicommunication 2 Arah dan Multisensor**.

## 1. Outline Slide Presentasi (10 Slide)

1. **Slide 1 - Judul dan Identitas Kelompok:**
   - Judul: *RelaySync: Sistem Pemantau Transisi dan Jarak Lari Estafet Berbasis Multisensor dan Komunikasi MQTT 2 Arah*.
   - Nama dan NIM 3-4 anggota kelompok serta tautan repositori GitHub.
2. **Slide 2 - Masalah dan Ide Solusi (Skor Rubrik: 20 Poin):**
   - Masalah: Kegagalan serah terima tongkat estafet akibat pelari penerima terlambat atau terlalu cepat berlari, serta ketiadaan metrik objektif bagi pelatih.
   - Solusi: Dua HP Android pada pelari mengirim estimasi langkah/gerak ke engine laptop untuk memicu aba-aba getar GO tepat waktu, alarm jarak, dan skor evaluasi percobaan.
3. **Slide 3 - Arsitektur Sistem 2 Edge, Multisensor, Satu Jaringan (Skor Rubrik: 15 Poin):**
   - Diagram alur `edge1` (Pelari 1) + `edge2` (Pelari 2) <-> Broker Cloud HiveMQ (TLS 8883) <-> `relaysync-engine` + Dashboard Streamlit di jaringan Wi-Fi/hotspot lokal.
4. **Slide 4 - Perangkat Keras dan Multisensor di Tiap Edge:**
   - `edge1`: Step Counter + Accelerometer (posisi saku/armband).
   - `edge2`: Step Counter + Accelerometer + Gyroscope.
   - Penjelasan mekanisme *fallback* otomatis dari *hardware step counter* ke detektor puncak *accelerometer*.
5. **Slide 5 - Pemrosesan Data di Edge (Data Processing 1 & 2):**
   - Processing 1: *Relative Distance Estimation* (`dist_est_m = steps_total * step_len_m`) beserta fitur kalibrasi 20 m.
   - Processing 2: *Step Cadence* (jendela geser 5 detik) dan *Run Readiness* (`STATIONARY`, `ARMING`, `RUNNING`) menggunakan `accel_dev_rms` dan `gyro_path_rad`.
6. **Slide 6 - Algoritma Sensor Fusion dan State Machine di Engine (Skor Rubrik: 20 Poin):**
   - Geometri lintasan 1D ($x_1$, $x_2 = Z + d_2$, $\text{gap\_m} = x_2 - x_1$, $\text{ETA}$).
   - *Rule-based sensor fusion dengan state machine* (`IDLE`, `APPROACHING`, `OPTIMAL_TRANSFER_ZONE`, `GAP_TOO_FAR_ALERT`, `HANDOFF_DONE`, `NO_DATA`) dan rumus *Transfer Quality Score* (0-100).
7. **Slide 7 - Protokol Komunikasi Cloud 2 Arah (Skor Rubrik: 15 Poin):**
   - Tabel 8 topic MQTT di bawah `relaysync/<TEAM_ID>/...`, penggunaan TLS, QoS 1, *retained message* pada `session` dan `presence` (Last Will).
   - Alur 2 arah: Telemetry naik ke engine; Cue GO, Alert getar, dan perintah Control (`start`, `calibrate_step`, `config`) turun ke HP.
8. **Slide 8 - Antarmuka Dashboard Real-Time dan Mode Replay:**
   - Tangkapan layar 6 tab dashboard Streamlit: visualisasi SVG lintasan estafet, grafik deret waktu, tabel riwayat percobaan & unduh CSV, kalibrasi, log event, dan diagnostik.
9. **Slide 9 - Rencana/Hasil Pengujian dan Keterbatasan Jujur (Skor Rubrik: 15 Poin):**
   - Tabel hasil pengujian kalibrasi jarak dan pengujian skenario alert (`EARLY_START`, `GAP_TOO_FAR`, `RUNNER1_STALLED`, `NO_DATA`).
   - Pernyataan jujur: jarak adalah estimasi langkah $\times$ panjang langkah (bukan GPS/alat ukur resmi).
10. **Slide 10 - Kesimpulan dan Tautan Repositori GitHub (Skor Rubrik: 15 Poin):**
    - Ringkasan capaian spesifikasi dan QR/link menuju kode sumber serta video demo.

## 2. Skrip Video Demo (Durasi 3 sampai 4 Menit)

- **00:00 - 00:35 | Pembukaan dan Masalah:**
  - Tampilkan kedua HP (masing-masing menjalankan Termux) dan laptop yang membuka dashboard Streamlit serta terminal `relaysync-engine`.
  - Jelaskan singkat masalah serah terima tongkat estafet dan cara kerja RelaySync beserta *disclaimer* bahwa jarak diestimasi dari langkah kaki.
- **00:35 - 01:15 | Pembuktian Multisensor dan Kalibrasi (2 Arah Control -> Edge):**
  - Tunjukkan status kedua HP `ONLINE` di dashboard.
  - Buka tab **Kalibrasi dan Pengaturan**, kirim perintah `calibrate_step` ke `edge1`, peragakan langkah sepanjang jarak uji, lalu kirim `calibrate_step` lagi hingga `calibrated=true`.
- **01:15 - 02:15 | Skenario 1: Transisi Estafet Optimal dan Aba-aba Cue GO:**
  - Klik **Start** di dashboard. Pelari 1 bergerak mendekati zona.
  - Tunjukkan posisi $x_1$ bergerak di visual lintasan. Saat sisa jarak $\le 10\text{ m}$, tunjukkan HP Pelari 2 bergetar dan memunculkan notifikasi **GO!**.
  - Pelari 2 ikut berlari hingga status berubah hijau menjadi `OPTIMAL_TRANSFER_ZONE` lalu `HANDOFF_DONE`, dan tunjukkan skor kualitas percobaan di tab **Percobaan**.
- **02:15 - 03:10 | Skenario 2: Peringatan Kesalahan (`EARLY_START` / `GAP_TOO_FAR`) dan `Ack`:**
  - Klik **Percobaan Baru**. Pelari 2 langsung berlari saat pelari 1 masih jauh.
  - Tunjukkan status berubah merah menjadi `GAP_TOO_FAR_ALERT (EARLY_START)` dan kedua HP bergetar 3 kali.
  - Klik tombol **Ack Alert** di dashboard dan tunjukkan getaran berhenti serta alert padam (komunikasi 2 arah).
- **03:10 - 03:45 | Grafik, Unduh CSV, dan Penutup:**
  - Tunjukkan tab **Grafik** (kurva `gap_m` terhadap batas ambang) dan tab **Log**.
  - Unduh CSV riwayat percobaan dan tutup presentasi.

## 3. Pemetaan Pemenuhan Rubrik Tugas Kuliah

| Komponen Rubrik | Bobot | Implementasi pada RelaySync |
|---|---|---|
| Ide dan Orisinalitas | 20% | Pemantau sinkronisasi lari estafet 2 pelari dengan estimasi jarak langkah, aba-aba GO otomatis, dan evaluasi kualitas serah terima |
| Arsitektur Sistem | 15% | Arsitektur berlapis (*Ports & Adapters*), 2 edge Android (Termux:API) + 1 engine laptop + 1 dashboard Streamlit pada satu jaringan |
| Processing & Algoritma | 20% | 2 processing di edge (Estimasi Jarak Relatif & Kadens + Kesiapan Lari) + *Rule-Based Sensor Fusion dengan State Machine* di engine |
| Komunikasi Cloud | 15% | MQTT di atas TLS (`broker.hivemq.com:8883`), QoS 1, *retained session/presence*, *Last Will*, komunikasi penuh 2 arah (telemetry & control/cue/alert) |
| Pengujian dan Demo | 15% | Panduan 7 skenario di `docs/TESTING.md`, alat `simulate_race.py`, `record_telemetry.py`, dan `check_sensors.py` |
| Dokumentasi | 15% | `README.md` + 7 dokumen teknis berbahasa Indonesia di `docs/` dengan diagram Mermaid dan tabel skema lengkap |

## 4. Usulan Pembagian Tugas Kelompok (3 sampai 4 Anggota)

| Peran Anggota | Tanggung Jawab Kode & Modul | Tanggung Jawab Saat Demo & Laporan |
|---|---|---|
| **Anggota 1 (Edge & Sensor)** | `adapters/termux_sensor.py`, `accel_step_detector.py`, `step_sources.py`, `termux_actuator.py`, `tools/check_sensors.py` | Menyiapkan kedua HP Android, memegang `edge1` saat demo, menjelaskan bagian sensor & aktuator |
| **Anggota 2 (Processing & Domain Fusion)** | `domain/distance.py`, `cadence.py`, `readiness.py`, `geometry.py`, `fusion.py`, `states.py`, `scoring.py` | Memegang `edge2` saat demo, menjelaskan rumus pemrosesan sinyal dan *state machine* |
| **Anggota 3 (Cloud MQTT & Engine)** | `messaging/topics.py`, `codec.py`, `adapters/mqtt_bus.py`, `services/edge_node.py`, `services/relay_engine.py` | Menjalankan `relaysync-engine` & perekaman data, menjelaskan arsitektur MQTT 2 arah dan validasi |
| **Anggota 4 (Dashboard & Pengujian)** *(atau dibagi ke 1-3 bila 3 orang)* | `dashboard/` (`app.py`, `feed.py`, `track_view.py`, `views/`), `tools/simulate_race.py`, dokumentasi & PPT | Mengoperasikan dashboard Streamlit saat demo, memandu skenario uji, dan mengompilasi tabel hasil |

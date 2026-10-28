# Panduan Membaca Kode (PANDUAN MEMBACA KODE)

Dokumen ini memandu anggota kelompok dan penguji memahami organisasi kode **RelaySync** secara cepat dan terstruktur.

## 1. Peta Direktori dan Modul

```text
relaysync/
├── configs/default.yaml              # Semua ambang parameter algoritma dan broker
├── .env.example                      # Template variabel lingkungan (TEAM_ID, sensor, broker)
├── pyproject.toml                    # Definisi paket Python dan entry point CLI
├── src/relaysync/
│   ├── settings/                     # Pemuatan dan validasi konfigurasi
│   │   ├── models.py                 # Dataclass bertipe untuk seluruh bagian default.yaml
│   │   ├── identity.py               # Validasi TEAM_ID dan generator saran unik
│   │   └── loader.py                 # Penggabungan YAML + .env serta validasi logika ambang
│   ├── domain/                       # Logika murni (tanpa I/O, tanpa MQTT, tanpa Streamlit)
│   │   ├── models.py                 # Struktur data domain (Telemetry, SessionSnapshot, dll.)
│   │   ├── geometry.py               # Geometri lintasan 1D (x1, x2, gap, remaining, ETA)
│   │   ├── distance.py               # Processing 1: estimasi jarak dan kalibrasi langkah
│   │   ├── cadence.py                # Processing 2a: kadens langkah pada jendela geser 5 detik
│   │   ├── readiness.py              # Processing 2b: accel_dev_rms, gyro_path_rad, ReadinessClassifier
│   │   ├── speed.py                  # Turunan numerik jarak menjadi kecepatan (m/s)
│   │   ├── cue_policy.py             # Kebijakan pengiriman aba-aba GO dan Cooldown
│   │   ├── fusion.py                 # Evaluasi kondisi optimal, alert, AlertLatch, HoldTimer
│   │   ├── states.py                 # Enum State, AlertReason, dan fungsi transisi murni
│   │   └── scoring.py                # Perhitungan Transfer Quality (0-100)
│   ├── messaging/                    # Protokol pesan dan serialisasi
│   │   ├── topics.py                 # Pemetaan topic relaysync/<TEAM_ID>/...
│   │   ├── codec.py                  # Encode/decode JSON dengan validasi ketat dan SequenceGuard
│   │   └── recording.py              # Format baca/tulis JSONL dan CSV untuk perekaman & replay
│   ├── ports/                        # Antarmuka abstrak (Protocol)
│   │   └── interfaces.py             # SensorReader, StepSource, MessageBus, Clock, Actuator
│   ├── adapters/                     # Implementasi nyata ke perangkat keras & jaringan
│   │   ├── termux_sensor.py          # Pembacaan subprocess termux-sensor dan resolusi nama sensor
│   │   ├── accel_step_detector.py    # Detektor puncak langkah dari accelerometer
│   │   ├── step_sources.py           # HardwareStepSource dan AutoStepSource (fallback otomatis)
│   │   ├── simulated_sensor.py       # Generator sampel sensor sintetis untuk mode --simulate
│   │   ├── mqtt_bus.py               # Klien paho-mqtt v2 (TLS, reconnect, Last Will)
│   │   ├── memory_bus.py             # Broker dalam memori untuk simulasi dan replay
│   │   ├── termux_actuator.py        # Pemanggil termux-vibrate dan termux-notification
│   │   ├── console_actuator.py       # Fallback aktuator ke log konsol
│   │   └── json_calibration_store.py # Penyimpanan panjang langkah di ~/.relaysync/calibration.json
│   ├── services/                     # Orkestrasi alur aplikasi
│   │   ├── edge_node.py              # Siklus baca sensor -> hitung fitur -> publish telemetry & terima cue/alert
│   │   └── relay_engine.py           # Siklus terima telemetry -> fusi 2 pelari -> publish session/cue/alert
│   ├── apps/                         # Entry point baris perintah (CLI)
│   │   ├── edge_cli.py               # Perintah `relaysync-edge`
│   │   └── engine_cli.py             # Perintah `relaysync-engine`
│   └── dashboard/                    # Antarmuka visual Streamlit
│       ├── app.py                    # Halaman utama Streamlit dan navigasi tab
│       ├── feed.py                   # Langganan MQTT thread-safe dan pemutar mode replay
│       ├── track_view.py             # Visualisasi SVG lintasan estafet horizontal
│       ├── charts.py                 # Pembentuk DataFrame deret waktu
│       └── views/                    # Implementasi 6 tab halaman dashboard
├── tools/                            # Skrip bantu pengujian, perekaman, dan simulasi
└── browser_edge/index.html           # Klien edge cadangan berbasis WebSocket di browser
```

## 2. Urutan Membaca yang Disarankan

1. **Mulai dari Konfigurasi dan Model Data:** Baca `configs/default.yaml` bersama `src/relaysync/domain/models.py` dan `src/relaysync/domain/states.py` untuk memahami kosakata utama sistem.
2. **Pahami Pemrosesan dan Algoritma Murni:** Baca `distance.py`, `cadence.py`, `readiness.py`, `geometry.py`, `fusion.py`, dan `scoring.py` di folder `domain/`. Semua file ini pendek (sekitar 40-180 baris) dan berisi logika matematika/aturan murni.
3. **Pelajari Kontrak Pesan:** Baca `messaging/topics.py` dan `messaging/codec.py` untuk melihat bagaimana JSON dibentuk dan divalidasi.
4. **Ikuti Orkestrasi Service:** Baca `services/edge_node.py` (apa yang dikerjakan HP setiap 1 detik) lalu `services/relay_engine.py` (apa yang dikerjakan laptop saat telemetry masuk).
5. **Lihat Adaptor dan UI:** Baca `adapters/termux_sensor.py`, `adapters/mqtt_bus.py`, dan `dashboard/app.py`.

## 3. Penelusuran Alur Satu Pesan: Dari Langkah Kaki sampai Alert

1. **Pembacaan Sensor di HP (`TermuxSensor.read_batch`):**
   - `termux-sensor` mengalirkan JSON nilai *step counter*, *accelerometer*, dan *gyroscope* selama `window_s = 1.0` detik ke dalam objek `SensorBatch`.
2. **Ekstraksi Fitur di Edge (`EdgeNode._compute`):**
   - `AutoStepSource.update(batch)` menghitung langkah kumulatif sejak awal percobaan (`steps_total`).
   - `estimate_distance_m` mengalikan langkah dengan `step_len_m` menjadi `dist_est_m`.
   - `CadenceCounter` menghitung `cadence_spm` dari jendela geser 5 detik.
   - `accel_dev_rms` dan (khusus `edge2`) `gyro_path_rad` serta `ReadinessClassifier.update` menghasilkan objek `WindowFeatures`.
3. **Pengiriman Telemetry (`EdgeNode.step` -> `MqttBus.publish`):**
   - `codec.encode_telemetry` mengubah objek `Telemetry` menjadi byte JSON dan mengirimkannya ke `relaysync/<TEAM_ID>/edge/edge2/telemetry` dengan QoS 1.
4. **Penerimaan dan Validasi di Laptop (`RelayEngine._on_edge_message`):**
   - `codec.decode_telemetry` memeriksa kelengkapan field, tipe, rentang, kecocokan `dev`, dan selisih jam `t_ms`.
   - `SequenceGuard.check` memastikan `n_msg` naik monoton.
   - `SpeedEstimator.record` mencatat pasangan `(waktu_terima, dist_est_m)` untuk memperbarui kecepatan `v2_mps`.
5. **Fusi Dua Pelari dan Evaluasi Status (`RelayEngine._refresh` & `_evaluate`):**
   - `build_inputs` menggabungkan data terbaru `edge1` dan `edge2` menjadi `FusionInputs` ($x_1, x_2, \text{gap\_m}, \text{remaining\_m}, v_1, v_2$).
   - `raw_alert_reason` mendeteksi apakah ada pelanggaran (misalnya `GAP_TOO_FAR` karena $\text{gap\_m} > 8.0\text{ m}$ saat `edge2` berlari).
   - Bila pelanggaran bertahan melewati `hold_s` ($2.0\text{ s}$) di dalam `AlertLatch`, status sesi berpindah ke `GAP_TOO_FAR_ALERT`.
6. **Pengiriman Balik Alert 2 Arah (`RelayEngine._dispatch_alert`):**
   - Engine mempublikasikan JSON alert ke `relaysync/<TEAM_ID>/alerts` dan memperbarui ringkasan di `relaysync/<TEAM_ID>/session`.
   - Kedua HP menerima pesan di `EdgeNode._on_alert` lalu memanggil `TermuxActuator.vibrate` (getar 3 pulsa) dan `TermuxActuator.notify`, sementara `DashboardStore` di Streamlit menampilkan banner peringatan merah secara real time.

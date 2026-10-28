# Keputusan Desain, Cara Pakai Ulang, dan Orisinalitas (DESIGN DECISIONS)

## 1. Keputusan Arsitektur dan Teknis Penting

1. **Pemisahan Lapisan Ports and Adapters (`domain`, `ports`, `adapters`, `services`):**
   - Seluruh rumus fisika dasar, penghitung kadens, klasifikasi kesiapan lari, aturan fusi dua pelari, dan mesin status ditempatkan di `src/relaysync/domain/` tanpa impor jaringan (`paho-mqtt`), UI (`streamlit`), maupun proses sistem (`subprocess`).
   - Interaksi ke dunia luar didefinisikan sebagai `typing.Protocol` di `src/relaysync/ports/interfaces.py` (`SensorReader`, `StepSource`, `MessageBus`, `Clock`, `Actuator`, `CalibrationStore`).
   - Alasan: memudahkan pergantian antara sensor Termux asli (`TermuxSensor`) dan sensor simulasi (`SimulatedSensor`), serta antara broker MQTT cloud (`MqttBus`) dan broker memori lokal (`MemoryBus`) untuk mode *replay* tanpa mengubah satu baris pun logika bisnis.

2. **Kombinasi Step Counter Perangkat Keras (`hw`) dan Cadangan Accelerometer (`accel`):**
   - Pada Android 10+, sensor *step counter* perangkat keras membutuhkan izin *Physical activity* dan sering mengalami penundaan *batching*.
   - Alasan: `AutoStepSource` memantau kedua sumber secara paralel. Jika `hw` tidak bertambah selama `hw_stall_s` (8 detik) padahal `accel` mendeteksi minimal 8 langkah, sistem otomatis beralih ke `accel` dengan menjaga kontinuitas nilai `steps_total` melalui *offset*.

3. **Fleksibilitas Variabel Lingkungan Sensor di `.env`:**
   - Setiap merek HP Android menamai sensor di `termux-sensor -l` secara beragam (misalnya `bmi160 Accelerometer`, `LSM6DSO Gyroscope`, atau `step_counter`).
   - Selain pencocokan kata kunci otomatis yang mengabaikan karakter non-alfanumerik dan menghindari varian *uncalibrated* / *wakeup*, pengguna dapat mengatur variabel `STEP_SENSOR`, `ACCEL_SENSOR`, `GYRO_SENSOR`, dan `TIME_SCALE` langsung di berkas `.env` (serta kompatibilitas alias `PROJECT_ID` selain `TEAM_ID`).

4. **Penggunaan Waktu Terima Laptop untuk Pewaktu Durasi Engine:**
   - Jam sistem antara dua HP Android dan laptop sering berselisih beberapa detik.
   - Alasan: `t_ms` pada telemetry hanya dipakai untuk menolak pesan basi (`max_clock_skew_s = 60.0` detik) dan pencatatan, sedangkan seluruh durasi tahan (`hold_s`, `stall_s`, `clear_s`, `pass_hold_s`, dan turunan kecepatan `SpeedEstimator`) dihitung menggunakan `Clock` di sisi engine agar bebas dari loncatan selisih jam antar perangkat.

5. **Keamanan Eksekusi dan Broker Publik:**
   - Broker `broker.hivemq.com` bersifat publik tanpa autentikasi; siapa pun yang mengetahui nama topic dapat membaca atau mengirim pesan. Oleh karena itu:
     - Program menolak berjalan bila `TEAM_ID` masih bernilai placeholder `relaysync-kelompok-GANTI`.
     - Hanya fitur turunan numerik yang dikirim ke MQTT (tidak ada data pribadi, GPS, atau audio).
     - Semua payload divalidasi secara ketat di `messaging/codec.py` (tipe, rentang, `math.isfinite`, *whitelist* perintah kontrol).
     - Pemanggilan `termux-vibrate` dan `termux-notification` selalu menggunakan daftar argumen `subprocess.run([...])` tanpa `shell=True`, dan teks notifikasi diambil dari kamus konstan internal (`ALERT_TEXT`), bukan dari string bebas jaringan.

## 2. Penamaan Field Telemetry yang Konsisten

Nama field telemetry diselaraskan di seluruh kode (`edge_node.py`, `codec.py`, `relay_engine.py`, `recording.py`, `dashboard/`, `browser_edge/index.html`, dan dokumen):
- Field bersama (`edge1` dan `edge2`): `v`, `dev`, `run`, `n_msg`, `t_ms`, `window_s`, `steps_total`, `dist_est_m`, `step_len_m`, `cadence_spm`, `accel_dev_rms`, `steps_src`, `calibrated`.
- Field khusus `edge2`: `gyro_path_rad`, `readiness`.

## 3. Cara Pakai Ulang (Reusability) Komponen Domain

Modul-modul di dalam `src/relaysync/domain/` dirancang generik dan tidak bergantung pada MQTT maupun Android:
- **`CadenceCounter` (`relaysync.domain.cadence`):** Dapat dipakai ulang pada aplikasi kebugaran, rehabilitasi jalan kaki, atau metronom olahraga cukup dengan memanggil `record(timestamp_s, cumulative_steps)` dan `cadence_spm()`.
- **`ReadinessClassifier` (`relaysync.domain.readiness`):** Dapat dipakai ulang untuk mendeteksi transisi postur diam -> bersiap -> berlari pada cabang olahraga lain (misalnya *sprint start* atau latihan kelincahan).
- **`SpeedEstimator` (`relaysync.domain.speed`):** Menghitung kecepatan halus dari sembarang sensor jarak monoton pada jendela geser.
- **`AlertLatch`, `HoldTimer`, dan `ReleaseDelay` (`relaysync.domain.fusion`):** Primitif histeresis dan *debounce* waktu murni yang dapat dipakai ulang pada sistem pemantauan industri atau alarm IoT apa pun agar bebas dari gejala *flickering* (status berkedip).

Contoh pemakaian ulang di skrip Python lain setelah `pip install -e .`:
```python
from relaysync.domain.cadence import CadenceCounter
from relaysync.domain.distance import estimate_distance_m

counter = CadenceCounter(window_s=5.0)
counter.record(0.0, 0)
counter.record(5.0, 14)
print("Kadens:", counter.cadence_spm(), "Jarak:", estimate_distance_m(14, 0.78))
```

## 4. Pernyataan Orisinalitas

Proyek **RelaySync** dirancang khusus untuk kasus penggunaan lari estafet (dua pelari bergerak searah pada geometri lintasan 1 dimensi dengan zona serah terima, aba-aba *cue* GO berbasis sisa jarak/ETA, evaluasi sinkronisasi kecepatan, dan skor kualitas serah terima). Struktur paket berlapis (`settings`, `domain`, `messaging`, `ports`, `adapters`, `services`, `apps`, `dashboard`), model domain, skema payload, dan implementasi kode ditulis dari awal secara mandiri.

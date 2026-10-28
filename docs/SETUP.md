# Panduan Instalasi dan Konfigurasi (SETUP)

Dokumen ini menjelaskan langkah persiapan pada kedua HP Android (Termux + Termux:API) dan pada laptop (Linux, macOS, atau Windows PowerShell).

## 1. Persiapan HP Android (Edge 1 dan Edge 2)

### A. Instalasi Termux dan Termux:API dari F-Droid
Jangan memasang Termux dari Google Play Store karena versinya sudah usang.
1. Unduh dan pasang aplikasi **F-Droid** dari situs resminya (`https://f-droid.org`).
2. Melalui F-Droid, cari dan pasang dua aplikasi berikut:
   - **Termux**
   - **Termux:API** (wajib agar perintah `termux-sensor`, `termux-vibrate`, dan `termux-notification` berfungsi)

### B. Pengaturan Izin Android dan Penghemat Baterai
1. Buka **Settings -> Apps -> Termux:API -> Permissions**:
   - Izinkan **Physical activity** (wajib pada Android 10+ agar sensor *step counter* perangkat keras dapat dibaca).
   - Izinkan **Notifications** (agar banner aba-aba GO dan peringatan muncul).
2. Buka **Settings -> Apps -> Termux -> Battery** dan **Termux:API -> Battery**:
   - Pilih **Unrestricted** / matikan *Battery Saver* agar proses pembacaan sensor tidak dihentikan saat layar HP mati di dalam saku.

### C. Instalasi Paket di dalam Termux
Buka aplikasi Termux di masing-masing HP lalu jalankan:
```bash
pkg update && pkg upgrade -y
pkg install -y python git termux-api
```
Aktifkan *wake lock* agar CPU tetap bangun selama sesi latihan:
```bash
termux-wake-lock
```

### D. Pemeriksaan Sensor di HP
Periksa daftar sensor yang tersedia pada perangkat keras HP:
```bash
termux-sensor -l
```
Setelah repositori RelaySync disalin dan dipasang (`pip install -e .`), Anda juga dapat menjalankan alat pemeriksa otomatis:
```bash
python tools/check_sensors.py --sample-seconds 3
```
Bila HP memiliki nama sensor khusus yang berbeda, Anda dapat menyesuaikannya melalui berkas `.env` tanpa mengubah kode:
```ini
STEP_SENSOR=stepcounter
ACCEL_SENSOR=accelerometer
GYRO_SENSOR=gyroscope
```
Bila sensor *step counter* perangkat keras tidak ditemukan atau tidak berubah saat ada gerakan, RelaySync pada mode `--steps-source auto` otomatis beralih menggunakan penghitung langkah cadangan berbasis *accelerometer*.

### E. Posisi Penempatan HP saat Berlari
Masukkan HP ke dalam **saku celana depan yang rapat** atau pasang pada **armband** di lengan atas. Hindari memegang HP di tangan yang mengayun bebas secara acak agar deteksi langkah dan energi gerak tetap konsisten.

## 2. Persiapan Laptop (Engine dan Dashboard)

Pastikan Python 3.10 atau lebih baru sudah terpasang.

### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dashboard]"
cp .env.example .env
python tools/suggest_team_id.py
```

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dashboard]"
Copy-Item .env.example .env
python tools/suggest_team_id.py
```

Edit berkas `.env` di laptop dan kedua HP sehingga ketiganya memiliki nilai `TEAM_ID` yang **sama persis** (misalnya `TEAM_ID=relaysync-kelompok-8b2d`).

## 3. Menjalankan Sistem

1. **Di Laptop (Terminal 1 - Engine):**
   ```bash
   relaysync-engine
   ```
2. **Di Laptop (Terminal 2 - Dashboard):**
   ```bash
   streamlit run src/relaysync/dashboard/app.py
   ```
3. **Di HP Pelari 1 (Pembawa Tongkat):**
   ```bash
   relaysync-edge --role edge1
   ```
4. **Di HP Pelari 2 (Penerima Tongkat):**
   ```bash
   relaysync-edge --role edge2
   ```

## 4. Troubleshooting Singkat

| Gejala | Penyebab Umum | Solusi |
|---|---|---|
| Program menolak jalan dengan pesan `TEAM_ID masih kosong atau placeholder` | Berkas `.env` belum dibuat atau masih berisi `relaysync-kelompok-GANTI` | Jalankan `python tools/suggest_team_id.py` dan salin hasilnya ke `.env` |
| `termux-sensor -l gagal` atau menggantung tanpa keluaran | Aplikasi pendamping Termux:API belum terpasang dari F-Droid | Pasang APK `Termux:API` dari F-Droid dan jalankan ulang Termux |
| Langkah `hw` tetap 0 saat pelari berjalan | Izin *Physical activity* belum diberikan ke Termux:API | Berikan izin *Physical activity* di pengaturan Android, atau gunakan `--steps-source accel` |
| Dashboard menampilkan `Pesan ditolak: t_ms terlalu jauh dari waktu engine` | Jam sistem di HP dan laptop berselisih lebih dari 60 detik | Aktifkan sinkronisasi waktu otomatis (NTP) di pengaturan tanggal/waktu HP dan laptop |
| HP berhenti mengirim data saat layar terkunci | *Battery optimization* Android membekukan Termux | Jalankan `termux-wake-lock` di Termux dan matikan penghemat baterai untuk Termux |

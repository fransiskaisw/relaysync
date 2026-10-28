# Panduan Pengujian Lapangan dan Skenario Demo (TESTING)

> **Catatan Jujur Status Pengujian:**
> Kode pada repositori ini dibangun secara lengkap dan konsisten sesuai spesifikasi arsitektur, namun **belum diuji coba secara langsung pada perangkat HP fisik maupun dijalankan oleh penulis**. Seluruh pengujian fungsional, pengujian simulasi, dan pengambilan data lapangan dilakukan oleh pengguna/mahasiswa mengikuti panduan di bawah ini.

## 1. Persiapan Sebelum Pengujian

1. Pastikan `.env` pada laptop dan kedua HP memiliki `TEAM_ID` yang sama.
2. Siapkan lintasan lurus (misalnya lapangan atau koridor sepanjang 60-80 meter, atau sesuaikan `leg_length_m` menjadi `30` meter pada halaman **Kalibrasi dan Pengaturan** bila ruang terbatas).
3. Tandai titik awal pelari 1 ($0\text{ m}$), titik tunggu pelari 2 ($Z$), dan akhir zona transisi ($Z + L_z$) menggunakan kerucut (*cone*) atau lakban.
4. Jalankan perekam di laptop bila ingin menyimpan seluruh sesi untuk analisis laporan:
   ```bash
   python tools/record_telemetry.py --out recordings/uji_lapangan.jsonl
   ```

## 2. Tujuh Skenario Pengujian Wajib

### Skenario 1: Kalibrasi Panjang Langkah 20 Meter (`calibrate_step`)
- **Langkah:**
  1. Ukur lintasan lurus sepanjang $20\text{ m}$ dengan meteran.
  2. Pada tab **4. Kalibrasi dan Pengaturan**, pilih `edge1`, isi jarak `20` m, lalu klik **Kirim Perintah calibrate_step**.
  3. Pelari 1 berlari dengan ritme normal dari garis $0\text{ m}$ hingga $20\text{ m}$ lalu berhenti.
  4. Klik **Kirim Perintah calibrate_step** sekali lagi.
  5. Ulangi langkah yang sama untuk `edge2`.
- **Hasil yang Diharapkan:** Log edge mencatat `Kalibrasi selesai: panjang langkah ... m (disimpan)` dan field `calibrated` pada telemetry berubah menjadi `true`.

### Skenario 2: Pendekatan Normal sampai `OPTIMAL_TRANSFER_ZONE` dan `HANDOFF_DONE`
- **Langkah:**
  1. Pelari 1 berdiri di titik $0\text{ m}$, pelari 2 berdiri diam di titik $Z$.
  2. Klik tombol **Start** di dashboard. Status menjadi `APPROACHING`.
  3. Pelari 1 berlari menuju titik $Z$. Saat sisa jarak $\le 10\text{ m}$ (atau $\text{ETA} \le 1.5\text{ s}$), HP pelari 2 bergetar menerima cue **GO**.
  4. Pelari 2 mulai berlari sehingga saat pelari 1 masuk zona $[Z-5, Z+L_z]$, gap berada di $[0, 4]\text{ m}$ dan kecepatan seimbang.
- **Hasil yang Diharapkan:** Status berubah ke `OPTIMAL_TRANSFER_ZONE` lalu `HANDOFF_DONE` (otomatis ketika gap $< 1.5\text{ m}$ selama $1\text{ s}$ atau saat tombol **Tandai Serah Terima** ditekan), dan skor kualitas muncul pada tab **Percobaan**.

### Skenario 3: Pelari 2 Berlari Terlalu Awal (`EARLY_START`)
- **Langkah:**
  1. Klik **Percobaan Baru**.
  2. Saat pelari 1 baru mulai berlari dan masih berjarak $> 25\text{ m}$ dari titik $Z$, pelari 2 langsung berlari kencang selama minimal 2 detik.
- **Hasil yang Diharapkan:** Status berubah menjadi `GAP_TOO_FAR_ALERT` dengan kode alasan `EARLY_START`, kedua HP bergetar 3 pulsa, dan banner merah muncul di dashboard.

### Skenario 4: Pelari 1 Melambat Mendadak (`RUNNER1_STALLED`)
- **Langkah:**
  1. Klik **Percobaan Baru**.
  2. Saat pelari 2 sudah berstatus `RUNNING`, pelari 1 berhenti atau berjalan sangat pelan (kadens $< 60\text{ spm}$) selama minimal 3 detik sebelum serah terima.
- **Hasil yang Diharapkan:** Engine memicu `GAP_TOO_FAR_ALERT` dengan kode alasan `RUNNER1_STALLED`.

### Skenario 5: Jarak Antar Pelari Terlalu Jauh (`GAP_TOO_FAR`)
- **Langkah:**
  1. Klik **Percobaan Baru**.
  2. Pelari 2 mulai berlari saat pelari 1 mendekat, tetapi pelari 2 berlari jauh lebih cepat atau pelari 1 tertinggal sehingga $\text{gap\_m} > 8.0\text{ m}$ selama minimal 2 detik.
- **Hasil yang Diharapkan:** Engine memicu `GAP_TOO_FAR_ALERT` dengan kode alasan `GAP_TOO_FAR`.

### Skenario 6: Zona Transisi Terlewati Tanpa Serah Terima (`ZONE_EXCEEDED`)
- **Langkah:**
  1. Matikan opsi serah terima atau jaga jarak agar tidak terjadi serah terima hingga pelari 1 berlari melewati batas akhir zona ($x_1 > Z + L_z$) selama 2 detik.
- **Hasil yang Diharapkan:** Engine memicu `GAP_TOO_FAR_ALERT` dengan kode alasan `ZONE_EXCEEDED`.

### Skenario 7: Kehilangan Data Salah Satu HP (`NO_DATA`)
- **Langkah:**
  1. Saat sesi sedang berjalan (`APPROACHING`), hentikan `relaysync-edge` pada salah satu HP (tekan `Ctrl+C`) atau matikan koneksi datanya selama $> 6$ detik.
- **Hasil yang Diharapkan:** Indikator presence berubah menjadi `OFFLINE` (bila melalui Last Will/disconnect) dan setelah 6 detik tanpa telemetry status sesi beralih ke `NO_DATA`.

## 3. Template Tabel Hasil Pengujian (Diisi Saat Praktikum)

### Tabel A: Akurasi Estimasi Jarak terhadap Jarak Ukur Meteran
| Perangkat | Jarak Ukur Sebenarnya (m) | Langkah Tercatat (`steps_total`) | Panjang Langkah (`step_len_m`) | Jarak Estimasi (`dist_est_m`) | Galat Absolut (m) | Galat Relatif (%) |
|---|---|---|---|---|---|---|
| `edge1` | 20,0 | ... | ... | ... | ... | ... |
| `edge1` | 60,0 | ... | ... | ... | ... | ... |
| `edge2` | 20,0 | ... | ... | ... | ... | ... |

### Tabel B: Evaluasi Deteksi Status, Alert, dan Latensi Komunikasi 2 Arah
| No | Skenario Uji | Status / Alasan yang Diharapkan | Status yang Muncul di Dashboard | Deteksi Benar (Ya/Tidak) | Alarm Palsu (Ya/Tidak) | Latensi Cue / Alert (ms) | Catatan |
|---|---|---|---|---|---|---|---|
| 1 | Pendekatan Optimal | `OPTIMAL_TRANSFER_ZONE` -> `HANDOFF_DONE` | ... | ... | ... | ... | ... |
| 2 | Start Terlalu Awal | `GAP_TOO_FAR_ALERT` (`EARLY_START`) | ... | ... | ... | ... | ... |
| 3 | Pelari 1 Melambat | `GAP_TOO_FAR_ALERT` (`RUNNER1_STALLED`) | ... | ... | ... | ... | ... |
| 4 | Jarak Terlalu Jauh | `GAP_TOO_FAR_ALERT` (`GAP_TOO_FAR`) | ... | ... | ... | ... | ... |
| 5 | Melewati Zona | `GAP_TOO_FAR_ALERT` (`ZONE_EXCEEDED`) | ... | ... | ... | ... | ... |
| 6 | Satu HP Mati | `NO_DATA` | ... | ... | ... | ... | ... |

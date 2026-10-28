# Spesifikasi Pemrosesan Sinyal dan Algoritma Fusi (ALGORITHM)

RelaySync menggunakan **algoritma lain: rule-based sensor fusion dengan state machine** (tanpa AI/ML). Seluruh ambang parameter disimpan di `configs/default.yaml` dan divalidasi saat aplikasi dimuat.

> **Pernyataan Kejujuran:** Jarak yang dihitung adalah estimasi dari hitungan langkah dikalikan panjang langkah (`dist_est_m`), bukan GPS dan bukan pengukuran presisi.

## 1. Pemrosesan di Edge (`window_s = 1.0` detik)

Setiap perangkat membaca sensor pada interval `sample_interval_ms = 50` ms (20 Hz) dan mengekstrak fitur setiap `window_s = 1.0` detik.

### A. Sumber Langkah (`hw` dan Cadangan `accel`)
1. **Hardware Step Counter (`hw`):** Sensor *step counter* Android mengembalikan jumlah langkah kumulatif sejak HP dinyalakan (*boot*). Saat sesi dimulai atau di-*reset*, nilai awal disimpan sebagai $S_{\text{base}}$, sehingga langkah sesi adalah:
   $$\text{steps\_total} = \max(0, S_{\text{now}} - S_{\text{base}})$$
2. **Cadangan Accelerometer (`accel`):** Menghitung magnitudo percepatan $\|a_i\| = \sqrt{a_x^2 + a_y^2 + a_z^2}$ dan simpangannya terhadap gravitasi standar $d_i = \|a_i\| - 9.81$. Sinyal dihaluskan dengan filter eksponensial ($\alpha = 0.4$):
   $$s_i = \alpha d_i + (1 - \alpha) s_{i-1}$$
   Satu langkah dihitung bila $s_{i-1}$ merupakan puncak lokal ($s_{i-1} > s_{i-2}$ dan $s_{i-1} \ge s_i$), melewati ambang `threshold_dev_ms2` ($2.5\text{ m/s}^2$), dan berjarak waktu minimal `refractory_s` ($0.25\text{ s}$) dari langkah sebelumnya.
3. **Peralihan Otomatis (`AutoStepSource`):** Bila dalam jendela `hw_stall_s` ($8.0\text{ s}$) langkah `hw` tidak bertambah sedangkan detektor `accel` mencatat minimal `hw_stall_min_accel_steps` ($8$ langkah), sumber otomatis beralih ke `accel` sambil menjaga nilai `steps_total` tetap kontinu.

### B. Processing 1: Relative Distance Estimation
Jarak tempuh relatif tiap pelari sejak awal percobaan dihitung dari langkah kumulatif dan panjang langkah per peran:
$$\text{dist\_est\_m} = \text{steps\_total} \times \text{step\_len\_m}$$
Saat kalibrasi panjang langkah (`calibrate_step`) dijalankan sepanjang jarak ukur $D_{\text{cal}}$ (default $20\text{ m}$) dengan selisih langkah $\Delta S$:
$$\text{step\_len\_m} = \frac{D_{\text{cal}}}{\Delta S}, \quad \text{diterima bila } \text{step\_len\_min\_m} (0.3) \le \text{step\_len\_m} \le \text{step\_len\_max\_m} (2.5)$$

### C. Processing 2: Step Cadence dan Run Readiness
1. **Kadens Jendela Geser (`cadence_spm`):** Karena sensor *step counter* perangkat keras Android sering melakukan *batching* (laporan langkah tertunda beberapa ratus milidetik), kadens dihitung pada jendela geser `cadence_window_s` ($5.0\text{ s}$) antara titik tertua $(t_0, S_0)$ dan terbaru $(t_1, S_1)$ dengan syarat $t_1 - t_0 \ge 1.0\text{ s}$:
   $$\text{cadence\_spm} = \frac{S_1 - S_0}{t_1 - t_0} \times 60$$
2. **Fitur Pendukung Gerak dan Rotasi:**
   - Simpangan RMS percepatan terhadap gravitasi:
     $$\text{accel\_dev\_rms} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \left(\|a_i\| - 9.81\right)^2}$$
   - Panjang lintasan sudut rotasi pada `edge2` (untuk syarat $0 < \Delta t_i \le \text{max\_gyro\_dt\_s}$):
     $$\text{gyro\_path\_rad} = \sum \|\omega_i\| \cdot \Delta t_i$$
3. **Klasifikasi Kesiapan Lari (`readiness` pada `edge2`):**
   - `RUNNING`: `cadence_spm >= run_cadence_spm` ($140\text{ spm}$) bertahan minimal `run_hold_s` ($2.0\text{ s}$). Setelah masuk `RUNNING`, status dipertahankan selama `cadence_spm >= run_cadence_spm - hysteresis_spm` ($140 - 15 = 125\text{ spm}$).
   - `STATIONARY`: belum `RUNNING`, `accel_dev_rms < stationary_dev_max` ($0.8\text{ m/s}^2$), `gyro_path_rad < turn_gyro_path_rad` ($0.5\text{ rad}$), dan `cadence_spm < walk_cadence_spm` ($110\text{ spm}$).
   - `ARMING`: kondisi di antara keduanya (pelari mulai menggerakkan tubuh, memutar badan menoleh ke pelari 1, atau mulai melangkah tetapi belum mencapai kadens lari stabil).

## 2. Geometri Lintasan, Kecepatan, dan ETA di Engine

- Posisi pelari 1 (mulai dari $x = 0$):
  $$x_1 = \text{dist\_est\_m}(\text{edge1})$$
- Posisi awal zona transisi: $Z = \text{track.leg\_length\_m}$ (default $60.0\text{ m}$), panjang zona $L_z = \text{track.zone\_length\_m}$ (default $20.0\text{ m}$).
- Posisi pelari 2 (menunggu di titik $Z$):
  $$x_2 = Z + \text{dist\_est\_m}(\text{edge2})$$
- Jarak antar pelari (*gap*) dan sisa jarak pelari 1 ke awal zona:
  $$\text{gap\_m} = x_2 - x_1, \qquad \text{remaining\_to\_zone\_m} = Z - x_1$$
- Kecepatan estimasi $v_1, v_2$ ($\text{m/s}$) dihitung dari turunan numerik `dist_est_m` pada jendela geser `speed.window_s` ($4.0\text{ s}$) menggunakan waktu terima laptop:
  $$v = \frac{d(t_1) - d(t_0)}{t_1 - t_0} \quad (\text{untuk } t_1 - t_0 \ge 1.0\text{ s})$$
- Estimasi waktu tiba pelari 1 ke titik $Z$ (`eta_s`):
  $$\text{eta\_s} = \begin{cases} \dfrac{\max(0, \text{remaining\_to\_zone\_m})}{v_1}, & \text{bila } v_1 > \text{min\_speed\_mps } (0.5\text{ m/s}) \\ \text{None}, & \text{bila } v_1 \le 0.5\text{ m/s} \end{cases}$$

## 3. Aturan Cue GO, State Machine, dan Kode Alasan Alert

### A. Pemicu Cue GO ke Pelari 2
Engine mengirim pesan `{"cue":"go"}` ke topic `cues` (dengan *cooldown* `cue_cooldown_s = 5.0` detik) apabila `readiness2 != RUNNING` dan salah satu syarat terpenuhi:
- $\text{remaining\_to\_zone\_m} \le \text{go\_trigger\_m}$ ($10.0\text{ m}$), atau
- $\text{eta\_s} \ne \text{None}$ dan $\text{eta\_s} \le \text{go\_cue\_eta\_s}$ ($1.5\text{ s}$).

### B. Tabel Kondisi Alert (`GAP_TOO_FAR_ALERT`)
Evaluasi alasan alert sesaat (`raw_alert_reason`) diperiksa sesuai urutan prioritas berikut dan harus bertahan minimal durasi tahan sebelum *latch* menyala:

| Prioritas | Kode Alasan (`AlertReason`) | Syarat Kondisi | Durasi Tahan |
|---|---|---|---|
| 1 | `ZONE_EXCEEDED` | $x_1 > Z + L_z$ (pelari 1 melewati akhir zona tanpa serah terima) | `hold_s` ($2.0\text{ s}$) |
| 2 | `EARLY_START` | `readiness2 == RUNNING` dan $\text{remaining\_to\_zone\_m} > \text{early\_start\_margin\_m}$ ($25.0\text{ m}$) | `hold_s` ($2.0\text{ s}$) |
| 3 | `RUNNER1_STALLED` | `readiness2 == RUNNING` dan $\text{cadence1\_spm} < \text{stall\_cadence\_spm}$ ($60.0\text{ spm}$) | `stall_s` ($3.0\text{ s}$) |
| 4 | `GAP_TOO_FAR` | `readiness2 == RUNNING` dan $\text{gap\_m} > \text{gap\_far\_m}$ ($8.0\text{ m}$) | `hold_s` ($2.0\text{ s}$) |

*Alert latching:* Begitu alert menyala, status bertahan sampai kondisi buruk hilang terus-menerus selama `clear_s` ($3.0\text{ s}$) atau pengguna menekan tombol `Ack`.

### C. Tabel Prioritas Transisi Status (`State`)

| Urutan | Status (`State`) | Syarat Aktif |
|---|---|---|
| 1 | `IDLE` | Sesi belum `active` (`start` belum dikirim) |
| 2 | `HANDOFF_DONE` | Serah terima sudah tercatat pada percobaan ini (manual atau `auto_handoff`) |
| 3 | `IDLE` | Belum ada paket telemetry dari kedua perangkat (`edge1` dan `edge2`) |
| 4 | `NO_DATA` | Salah satu perangkat tidak mengirim telemetry lebih dari `data_gap_s` ($6.0\text{ s}$) |
| 5 | `GAP_TOO_FAR_ALERT` | `AlertLatch` sedang aktif |
| 6 | `OPTIMAL_TRANSFER_ZONE` | $x_1 \in [Z - \text{entry\_margin\_m}, Z + L_z]$, `readiness2 == RUNNING`, $\text{gap\_m} \in [\text{gap\_opt\_min\_m}, \text{gap\_opt\_max\_m}]$ ($[0, 4]\text{ m}$), dan $|v_1 - v_2| < \text{speed\_match\_tol\_mps}$ ($1.5\text{ m/s}$), dilengkapi penahan keluar `optimal_exit_s` ($1.0\text{ s}$) |
| 7 | `APPROACHING` | Kondisi default saat sesi aktif dan pelari 1 mendekati zona |

## 4. Rumus Evaluasi Skor Percobaan (`Transfer Quality` 0-100)

Saat serah terima terjadi (baik melalui perintah `handoff` manual maupun `auto_handoff` ketika berada di `OPTIMAL_TRANSFER_ZONE` dengan $\text{gap\_m} < \text{pass\_gap\_m}$ ($1.5\text{ m}$) selama `pass_hold_s` ($1.0\text{ s}$)), skor kualitas dihitung sebagai berikut:

$$\text{raw\_score} = S_{\text{start}} - P_{\text{gap}} \cdot |\text{gap\_m} - G_{\text{target}}| - P_{\text{speed}} \cdot |v_1 - v_2| - P_{\text{alert}} \cdot N_{\text{alert}} + B_{\text{clean}} \cdot \mathbb{I}(N_{\text{alert}} = 0)$$

$$\text{quality\_score} = \text{round}\left(\min(100, \max(0, \text{raw\_score}))\right)$$

Dengan nilai parameter awal pada `configs/default.yaml`:
- $S_{\text{start}} = 100.0$
- $G_{\text{target}} = 2.0\text{ m}$, $P_{\text{gap}} = 8.0\text{ poin/m}$
- $P_{\text{speed}} = 6.0\text{ poin/(m/s)}$
- $P_{\text{alert}} = 10.0\text{ poin/alert}$
- $B_{\text{clean}} = 5.0\text{ poin}$ (bonus bila $N_{\text{alert}} = 0$)

## 5. Tabel Ringkasan Ambang Awal (`configs/default.yaml`)

| Kunci Konfigurasi | Nilai Awal | Satuan | Fungsi |
|---|---|---|---|
| `edge.window_s` | `1.0` | detik | Periode pengiriman telemetry edge |
| `edge.cadence_window_s` | `5.0` | detik | Lebar jendela geser perhitungan kadens |
| `readiness.walk_cadence_spm` | `110` | spm | Batas atas kadens diam/jalan pelan |
| `readiness.run_cadence_spm` | `140` | spm | Batas bawah kadens lari (`RUNNING`) |
| `readiness.run_hold_s` | `2.0` | detik | Waktu tahan masuk status `RUNNING` |
| `track.leg_length_m` | `60.0` | meter | Posisi awal zona transisi $Z$ |
| `track.zone_length_m` | `20.0` | meter | Panjang zona transisi $L_z$ |
| `fusion.gap_opt_min_m` / `max_m` | `0.0` / `4.0` | meter | Rentang gap optimal serah terima |
| `fusion.gap_far_m` | `8.0` | meter | Ambang alert `GAP_TOO_FAR` |
| `fusion.early_start_margin_m` | `25.0` | meter | Ambang sisa jarak untuk `EARLY_START` |
| `cue.go_trigger_m` | `10.0` | meter | Sisa jarak pelari 1 saat cue GO dikirim |
| `cue.go_cue_eta_s` | `1.5` | detik | ETA pelari 1 ke zona saat cue GO dikirim |

## 6. Keterbatasan Teknis

1. **Akumulasi Galat Langkah (*Drift*):** Karena jarak diestimasi dari langkah $\times$ panjang langkah rata-rata, perubahan panjang langkah saat akselerasi awal atau melambat akan menimbulkan simpangan terhadap jarak sebenarnya di lapangan.
2. **Latensi Sensor Step Counter:** Sensor *step counter* perangkat keras Android memiliki penundaan *batching* sekitar 0,5 hingga 2 detik.
3. **Estimasi Serah Terima:** Mode `auto_handoff` mengevaluasi kedekatan jarak estimasi dan kesamaan kecepatan, bukan mendeteksi perpindahan fisik tongkat estafet.

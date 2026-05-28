# Monitor-PC

**Monitor-PC v3.0** adalah tool CLI berbasis Python untuk memantau performa PC atau laptop secara realtime langsung dari terminal. Tampilan dashboard dibuat dengan gaya Task Manager, lengkap dengan grafik CPU, RAM, network, disk I/O, informasi sistem, battery status, ping, local IP, dan daftar proses yang paling banyak memakai resource.

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-brightgreen)
![Interface](https://img.shields.io/badge/Interface-Terminal%20Dashboard-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Preview

![Monitor-PC CLI Dashboard](img/image.png)

---

## Fitur Utama

| Fitur | Detail |
| --- | --- |
| **CPU realtime** | Menampilkan total CPU usage, frekuensi CPU, penggunaan per core, dan grafik rolling realtime. |
| **RAM realtime** | Menampilkan persentase RAM, RAM terpakai, total RAM, RAM tersedia, dan grafik penggunaan. |
| **Network monitor** | Menampilkan kecepatan download/upload realtime, total data diterima, total data dikirim, dan grafik traffic. |
| **Disk monitor** | Menampilkan kapasitas disk, used/free space, progress bar, read speed, write speed, dan grafik disk activity. |
| **System info** | Menampilkan hostname, OS, versi Python, CPU name, jumlah core, uptime, dan jumlah proses aktif. |
| **Battery status** | Menampilkan persentase baterai, status charging, dan estimasi waktu jika tersedia dari sistem. |
| **Ping & local IP** | Menampilkan local IP aktif dan latency ke `8.8.8.8` melalui background thread. |
| **Top processes** | Menampilkan 3 proses tertinggi berdasarkan CPU dan 3 proses tertinggi berdasarkan penggunaan RAM. |
| **Grafik terminal** | Menggunakan `asciichartpy` untuk grafik terminal yang smooth dan otomatis berubah warna. |
| **Live rendering** | Menggunakan `rich.Live` agar dashboard update di tempat tanpa spam output terminal. |

---

## Cara Kerja Singkat

Monitor-PC membaca statistik sistem menggunakan `psutil`, lalu merender dashboard terminal menggunakan `rich`. Grafik realtime dibuat dari data history yang disimpan dalam `deque`, sehingga tampilan bisa memperlihatkan pergerakan resource dari beberapa detik sebelumnya sampai kondisi saat ini.

Beberapa proses berjalan di background thread:

- `ping_worker()` memperbarui local IP dan ping latency setiap 3 detik.
- `process_worker()` memperbarui daftar top CPU/RAM process setiap 2 detik.
- Loop utama memperbarui dashboard setiap 1 detik.

---

## Kebutuhan Sistem

- Python **3.7 atau lebih baru**
- Terminal yang mendukung ANSI color
- Koneksi internet opsional untuk ping check ke `8.8.8.8`
- Dependency Python:
  - `psutil>=5.9.0`
  - `rich>=13.0.0`
  - `asciichartpy>=1.5.25`

Tool ini dapat berjalan di:

- Windows
- Linux
- macOS

Catatan: beberapa data seperti battery status, CPU name, atau permission proses bisa berbeda tergantung OS dan izin terminal.

---

## Instalasi

### 1. Masuk ke folder project

```bash
cd Monitoring-pc
```

### 2. Buat virtual environment

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependency

```bash
pip install -r requirements.txt
```

### 4. Jalankan dashboard

Windows:

```powershell
python monitor_pc.py
```

Linux/macOS:

```bash
python3 monitor_pc.py
```

---

## Penggunaan

Setelah dijalankan, dashboard akan langsung tampil di terminal dan update otomatis setiap 1 detik.

```bash
python monitor_pc.py
```

Untuk menghentikan dashboard:

| Tombol | Fungsi |
| --- | --- |
| `Ctrl+C` | Menghentikan Monitor-PC dengan aman |

Saat berhenti, program akan membersihkan terminal dan menampilkan pesan bahwa Monitor-PC sudah berhenti.

---

## Detail Dashboard

### Header

Menampilkan nama tool, versi, waktu saat ini, dan petunjuk keluar menggunakan `Ctrl+C`.

### CPU Panel

Menampilkan:

- Total CPU usage dalam persen
- CPU frequency dalam MHz jika tersedia
- Grafik CPU realtime
- Penggunaan tiap core/logical processor

Warna otomatis:

| Beban | Warna |
| --- | --- |
| `< 50%` | Hijau |
| `50% - 79%` | Kuning |
| `>= 80%` | Merah |

### Memory Panel

Menampilkan:

- Persentase RAM
- RAM terpakai dan total RAM
- Grafik RAM realtime
- RAM yang masih tersedia

### Network Panel

Menampilkan:

- Download speed realtime
- Upload speed realtime
- Grafik download traffic
- Total bytes received
- Total bytes sent

Kecepatan dihitung dari selisih nilai `psutil.net_io_counters()` antar update.

### Disk Panel

Menampilkan:

- Persentase penggunaan disk
- Used space dan total space
- Free space melalui progress indicator
- Read speed realtime
- Write speed realtime
- Grafik gabungan aktivitas read/write

Path disk utama:

- Windows: `C:\`
- Linux/macOS: `/`

### System Info Panel

Menampilkan:

- Hostname
- Operating system
- Versi Python
- Nama CPU
- Jumlah physical/logical core
- Uptime
- Jumlah proses aktif
- Local IP
- Ping ke `8.8.8.8`
- Battery status jika tersedia

### Top Processes Panel

Menampilkan:

- 3 proses dengan penggunaan CPU tertinggi
- 3 proses dengan penggunaan RAM tertinggi
- PID, nama proses, dan nilai resource

Jika proses tidak bisa dibaca karena permission OS, proses tersebut akan dilewati.

---

## Struktur Project

```text
Monitoring-pc/
├── img/
│   └── image.png          # Screenshot preview dashboard
├── monitor_pc.py          # Aplikasi utama Monitor-PC
├── requirements.txt       # Dependency Python
└── README.md              # Dokumentasi project
```

---

## Konfigurasi Teknis

Nilai default berada di bagian atas `monitor_pc.py`:

```python
HISTORY_SIZE = 60
REFRESH_RATE = 1.0
GRAPH_HEIGHT = 10
```

| Konfigurasi | Fungsi |
| --- | --- |
| `HISTORY_SIZE` | Jumlah data awal untuk grafik rolling. |
| `REFRESH_RATE` | Interval update dashboard utama dalam detik. |
| `GRAPH_HEIGHT` | Tinggi default grafik terminal. |

Dashboard juga menyesuaikan ukuran history dan tinggi grafik berdasarkan ukuran terminal saat program berjalan.

---

## Troubleshooting

### Dashboard terlihat berantakan

Perbesar ukuran terminal, lalu jalankan ulang:

```bash
python monitor_pc.py
```

Dashboard membutuhkan terminal yang cukup lebar agar panel CPU, RAM, Network, Disk, System Info, dan Top Processes terlihat rapi.

### Ping tampil `Offline / Timeout`

Artinya koneksi ke `8.8.8.8:53` gagal atau diblokir firewall/jaringan. Dashboard tetap berjalan, hanya informasi ping yang tidak tersedia.

### Battery tampil `Not available`

Ini normal pada PC desktop atau sistem yang tidak menyediakan sensor baterai ke `psutil`.

### Sebagian proses tidak muncul

Beberapa proses sistem mungkin tidak bisa dibaca karena permission OS. Jalankan terminal sebagai administrator/root jika ingin akses proses lebih luas.

### Module tidak ditemukan

Pastikan dependency sudah terinstall:

```bash
pip install -r requirements.txt
```

---

## Validasi Development

Untuk mengecek syntax Python:

```bash
python -m py_compile monitor_pc.py
```

Untuk menjalankan manual:

```bash
python monitor_pc.py
```

Karena tool ini adalah dashboard realtime terminal, validasi utama dilakukan dengan menjalankan program dan memastikan panel update normal.

---

## Catatan

- Monitor-PC tidak menyimpan log dan tidak mengirim data monitoring ke server.
- Semua data diambil lokal dari sistem yang sedang menjalankan tool.
- Data ping hanya digunakan untuk menampilkan status koneksi sederhana.
- Tampilan terbaik diperoleh pada terminal modern seperti Windows Terminal, PowerShell 7, macOS Terminal, GNOME Terminal, atau terminal lain yang mendukung ANSI color.


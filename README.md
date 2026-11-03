# Scraper Kos-Kosan Mahasiswi Surabaya Timur & Waru Sidoarjo

Proyek otomasi pengumpulan dan penyaringan data kos-kosan dari platform direktori online (**Mamikos & Direktori Kos Lokal**) serta media sosial (**Threads, Facebook, Instagram, TikTok**) dengan fokus area:
- **Surabaya Timur**: Kecamatan Gunung Anyar, Sekitar Kampus UPN "Veteran" Jatim & Kampus 2 UIN Sunan Ampel (UINSA), Rungkut, Medokan Ayu.
- **Sidoarjo**: Kecamatan Waru (Desa Tambak Sumur & sekitarnya).

### Kriteria Filter Otomatis:
1. **Gender**: Khusus Cewek / Putri / Mahasiswi Muslimah (menolak kos campur / putra).
2. **Range Harga**: Rp 500.000 - Rp 700.000 per bulan.
3. **Fasilitas**: Memiliki Lahan Parkir (motor/mobil) dan Air Bersih (PDAM / Sumur jernih).
4. **Lingkungan**: Aman, berpagar, CCTV, ramah mahasiswi.
5. **Kontak**: Otomatis mendeteksi nomor WhatsApp/telepon pemilik kos.

---

## Struktur Folder

```
C:\Script_Scraping\
├── venv\                    # Python Virtual Environment
├── config.py                # Konfigurasi kriteria filter & daftar kata kunci pencarian
├── requirements.txt         # Daftar pustaka (Playwright, BeautifulSoup4, Pandas, curl_cffi)
├── main.py                  # CLI Runner utama
├── login_helper.py          # Otomasi login akun dummy & penyimpan session cookies
├── README.md                # Dokumentasi lengkap penggunaan
├── core\
│   ├── parser.py            # Engine Regex & Entity Extraction (deteksi harga, lokasi, parkir, air, WA)
│   ├── exporter.py          # Otomatisasi export ke Excel (.xlsx) dan CSV
│   └── browser.py           # Playwright stealth & manajemen session cookies login
├── scrapers\
│   ├── base_scraper.py      # Abstract class scraper
│   ├── mamikos_scraper.py   # Scraper Mamikos (Area UPN, UINSA, Gunung Anyar, Waru)
│   ├── direct_kos_scraper.py# Scraper Direktori Kos Terverifikasi (Nomor WA langsung & Alamat)
│   ├── threads_scraper.py   # Scraper Threads (Meta)
│   ├── fb_scraper.py        # Scraper Facebook
│   ├── ig_scraper.py        # Scraper Instagram
│   └── tiktok_scraper.py    # Scraper TikTok
├── data\
│   ├── raw\                 # Menyimpan seluruh data mentah hasil crawl
│   └── filtered\            # Menyimpan rekomendasi kos yang lolos filter (Putri, 500-700k)
└── sessions\                # Penyimpanan cookies sesi login
```

---

## Cara Penggunaan

### 1. Menjalankan Scraping Direktori Kos Terverifikasi (Paling Cepat & Akurat)
Mengambil data kos langsung dari listing pemilik di area Gunung Anyar, Rungkut (UPN), dan Waru Sidoarjo lengkap dengan nomor WhatsApp:
```powershell
.\venv\Scripts\python main.py --platform direktori --max 30
```

### 2. Menjalankan Scraping Mamikos
Mengambil ratusan kartu kos di sekitar UPN, UINSA, Gunung Anyar, dan Waru:
```powershell
.\venv\Scripts\python main.py --platform mamikos --max 30
```

### 3. Menjalankan Scraping Media Sosial
```powershell
# Threads:
.\venv\Scripts\python main.py --platform threads --max 20

# Facebook:
.\venv\Scripts\python main.py --platform facebook --max 20

# Instagram:
.\venv\Scripts\python main.py --platform instagram --max 15

# TikTok:
.\venv\Scripts\python main.py --platform tiktok --max 20
```

### 4. Hasil Output
Hasil crawling akan tersimpan otomatis di:
- `data/filtered/kos_<platform>_rekomendasi_<timestamp>.xlsx` (File Excel rapi siap dibaca)
- `data/filtered/kos_<platform>_rekomendasi_<timestamp>.csv`
- `data/raw/kos_<platform>_all_<timestamp>.csv` (Seluruh postingan untuk audit)

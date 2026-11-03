"""
Konfigurasi Pencarian dan Parameter Filter Scraping Kos-Kosan
Wilayah: Surabaya Timur (Gunung Anyar, Sekitar UPN, Sekitar UINSA) & Waru Sidoarjo (Tambak Sumur)
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
FILTERED_DATA_DIR = DATA_DIR / "filtered"
SESSION_DIR = BASE_DIR / "sessions"

for folder in [RAW_DATA_DIR, FILTERED_DATA_DIR, SESSION_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Kriteria Filter Kos
FILTER_CRITERIA = {
    "price_min": 500_000,
    "price_max": 700_000,
    "gender_allowed": ["putri", "cewek", "cewe", "wanita", "mahasiswi", "muslimah"],
    "gender_excluded": [
        "khusus cowok", "khusus cowo", "khusus pria", "khusus putra", 
        "putra only", "cowok only", "pria only"
    ],
    "locations_target": [
        "gunung anyar", "upn", "uinsa", "tambak sumur", 
        "waru", "rungkut", "medokan ayu", "medokan asri"
    ],
    "facilities_parking": [
        "parkir", "parkiran", "garasi", "lahan parkir"
    ],
    "facilities_water": [
        "air", "pdam", "sumur", "jernih", "bersih"
    ],
    "environment_positive": [
        "aman", "pagar", "cctv", "tenang", "nyaman", "bersahabat"
    ]
}

# Keyword Queries untuk Scraping
SEARCH_QUERIES = [
    # Area UPN & Gunung Anyar
    "kost putri upn surabaya 500 600 700",
    "kost cewek gunung anyar murah",
    "kost mahasiswi upn veteran jatim",
    "kost putri gunung anyar tambak sumur",
    # Area UINSA (Kampus 2 Gunung Anyar)
    "kost putri uinsa gunung anyar",
    "kost cewek uinsa surabaya 600",
    # Area Tambak Sumur & Waru
    "kost putri tambak sumur waru sidoarjo",
    "kos cewek tambak sumur dekat upn",
    "kost murah tambak sumur parkir motor"
]

# Hashtags untuk Instagram & TikTok
SEARCH_HASHTAGS = [
    "kostupn",
    "kostupnsurabaya",
    "kostuinsa",
    "kostgununganyar",
    "kosttambaksumur",
    "kostsurabayatimur",
    "kostputrisurabaya",
    "kostceweksurabaya"
]

# Grup Facebook Target (Relevan untuk area Gunung Anyar, UPN, UINSA, Sidoarjo)
FACEBOOK_GROUPS = [
    {
        "name": "Info Kost & Kontrakan UPN Veteran Jatim",
        "url": "https://www.facebook.com/groups/infokostupn/"
    },
    {
        "name": "Info Kost Mahasiswa UINSA Surabaya",
        "url": "https://www.facebook.com/groups/infokostuinsa/"
    },
    {
        "name": "Info Kost Rungkut Gunung Anyar Sidoarjo",
        "url": "https://www.facebook.com/groups/kostrungkutgununganyar/"
    }
]

"""
Scraper Direktori Kos Terverifikasi (Direktori Web Kos Surabaya & Sidoarjo)
Mengambil data kos langsung dari listing pemilik di area Gunung Anyar, Rungkut (UPN), dan Waru Sidoarjo.
Mendapatkan nomor WhatsApp asli pemilik, harga sewa, alamat lengkap, dan fasilitas.
"""

from typing import List
from curl_cffi import requests
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from core.parser import KosItem

PORTAL_TARGET_URLS = [
    {
        "area": "Gunung Anyar Surabaya (Sekitar UINSA 2 & UPN)",
        "url": "https://www.sewakost.com/kost/surabaya/gunung-anyar/"
    },
    {
        "area": "Rungkut Surabaya (Sekitar UPN Jatim)",
        "url": "https://www.sewakost.com/kost/surabaya/rungkut/"
    },
    {
        "area": "Waru Sidoarjo (Tambak Sumur)",
        "url": "https://www.sewakost.com/kost/sidoarjo/"
    }
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

class DirectKosScraper(BaseScraper):
    def __init__(self):
        super().__init__("direktori_kos")

    async def scrape(self, max_results: int = 50) -> List[KosItem]:
        results: List[KosItem] = []
        seen_links = set()

        for target in PORTAL_TARGET_URLS:
            if len(results) >= max_results:
                break

            area_name = target["area"]
            list_url = target["url"]
            print(f"\n[DIREKTORI KOS] Mengambil listing: {area_name} -> {list_url}")

            try:
                r = requests.get(list_url, headers=HEADERS, impersonate="chrome124", timeout=15)
                if r.status_code != 200:
                    print(f"[DIREKTORI KOS] Gagal memuat {list_url} (HTTP {r.status_code})")
                    continue

                soup = BeautifulSoup(r.text, "html.parser")
                articles = soup.find_all("article")
                print(f"[DIREKTORI KOS] Ditemukan {len(articles)} listing di {area_name}")

                for art in articles:
                    if len(results) >= max_results:
                        break

                    link_el = art.find("a")
                    if not link_el:
                        continue
                    detail_url = link_el.get("href")
                    if not detail_url or detail_url in seen_links:
                        continue
                    seen_links.add(detail_url)

                    # Ambil informasi ringkas di kartu
                    card_text = art.get_text(" | ", strip=True)

                    # Ambil halaman detail untuk nomor WhatsApp dan fasilitas lengkap
                    detail_text = card_text
                    contact_phone = None
                    author_name = None

                    try:
                        r_detail = requests.get(detail_url, headers=HEADERS, impersonate="chrome124", timeout=12)
                        if r_detail.status_code == 200:
                            soup_det = BeautifulSoup(r_detail.text, "html.parser")
                            
                            # Ekstraksi nama pemilik
                            pemilik_el = soup_det.find(text=lambda t: t and any(k in t.lower() for k in ["bunda", "ibu", "bapak", "pak"]))
                            if pemilik_el:
                                author_name = pemilik_el.strip()

                            # Ekstraksi konten utama
                            main_content = soup_det.find("div", class_="entry-content") or soup_det.find("main") or soup_det.body
                            if main_content:
                                detail_text = main_content.get_text(" \n ", strip=True)
                    except Exception as e_det:
                        # Jika detail gagal, tetap gunakan teks kartu
                        pass

                    # Masukkan konteks lokasi
                    enriched_text = f"{detail_text}\nLokasi Target: {area_name}"

                    item = self.parser.analyze_post(
                        id_post=f"dir_{abs(hash(detail_url))}",
                        platform="direktori_kos",
                        url_post=detail_url,
                        author=author_name,
                        raw_text=enriched_text
                    )
                    results.append(item)

            except Exception as e:
                print(f"[DIREKTORI KOS] Error scraping {area_name}: {e}")

        return results

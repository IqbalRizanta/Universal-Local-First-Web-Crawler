"""
Scraper untuk Platform Mamikos (mamikos.com)
Mengambil data kos di sekitar UPN, UINSA (Gunung Anyar), dan Waru Sidoarjo (Tambak Sumur).
Mendukung ekstraksi nama kos, gender (Putri), fasilitas, harga, dan link kamar.
"""

import asyncio
from typing import List
from playwright.async_api import async_playwright
from scrapers.base_scraper import BaseScraper
from core.browser import USER_AGENT
from core.parser import KosItem

MAMIKOS_TARGET_URLS = [
    {
        "area": "UPN Veteran Jawa Timur",
        "url": "https://mamikos.com/kost/kost-dekat-upn-surabaya-murah"
    },
    {
        "area": "Gunung Anyar Surabaya",
        "url": "https://mamikos.com/kost/kost-gunung-anyar-surabaya-murah"
    },
    {
        "area": "UINSA Surabaya (Gunung Anyar)",
        "url": "https://mamikos.com/kost/kost-dekat-uin-surabaya-murah"
    },
    {
        "area": "Waru Sidoarjo (Tambak Sumur)",
        "url": "https://mamikos.com/kost/kost-waru-sidoarjo-murah"
    }
]

class MamikosScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        super().__init__("mamikos")
        self.headless = headless

    async def scrape(self, max_results: int = 40) -> List[KosItem]:
        results: List[KosItem] = []
        seen_items = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 850},
                locale="id-ID"
            )
            page = await context.new_page()

            for target in MAMIKOS_TARGET_URLS:
                if len(results) >= max_results:
                    break

                area_name = target["area"]
                target_url = target["url"]
                print(f"\n[MAMIKOS] Membuka listing: {area_name} -> {target_url}")

                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=35000)
                    await asyncio.sleep(4)

                    # Scroll ke bawah secara bertahap untuk memicu lazy loading
                    for _ in range(5):
                        await page.mouse.wheel(0, 1400)
                        await asyncio.sleep(2)

                    # Ambil semua kartu kos dengan selector Mamikos
                    card_locators = page.locator('div[class*="kost-rc__content"], div.rc-info, div.kost-rc')
                    card_count = await card_locators.count()
                    print(f"[MAMIKOS] Terdeteksi {card_count} kartu kos di area {area_name}")

                    # Ambil juga semua link kamar jika ada
                    room_links = await page.locator('a').all()
                    url_mapping = {}
                    for rl in room_links:
                        href = await rl.get_attribute("href")
                        if href and ("/room/" in href or "/kost/" in href):
                            text_snippet = (await rl.inner_text()).strip()[:40]
                            if text_snippet:
                                url_mapping[text_snippet] = href

                    for i in range(card_count):
                        if len(results) >= max_results:
                            break

                        card = card_locators.nth(i)
                        card_text = await card.inner_text()
                        if not card_text or len(card_text.strip()) < 25:
                            continue

                        # Hindari duplikasi
                        hash_key = hash(card_text[:90])
                        if hash_key in seen_items:
                            continue
                        seen_items.add(hash_key)

                        # Cari URL relevan
                        matched_url = target_url
                        for title_snippet, href in url_mapping.items():
                            if title_snippet in card_text:
                                matched_url = f"https://mamikos.com{href}" if href.startswith("/") else href
                                break

                        # Tambahkan konteks lokasi area agar parser mengenali
                        full_content = f"{card_text}\nLokasi Area: {area_name}"

                        # Jalankan parser dan filter
                        item = self.parser.analyze_post(
                            id_post=f"mamikos_{abs(hash_key)}",
                            platform="mamikos",
                            url_post=matched_url,
                            raw_text=full_content
                        )
                        results.append(item)

                except Exception as e:
                    print(f"[MAMIKOS] Gagal memuat area {area_name}: {e}")

            await browser.close()

        return results

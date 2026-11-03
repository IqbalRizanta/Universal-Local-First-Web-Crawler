"""
Scraper untuk Platform Threads (Meta)
Mencari postingan berdasarkan keyword kos putri di area Gunung Anyar, UPN, UINSA, Tambak Sumur.
"""

import asyncio
import urllib.parse
from typing import List
from playwright.async_api import async_playwright
from config import SEARCH_QUERIES
from scrapers.base_scraper import BaseScraper
from core.browser import get_browser_context
from core.parser import KosItem

class ThreadsScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        super().__init__("threads")
        self.headless = headless

    async def scrape(self, max_results: int = 30) -> List[KosItem]:
        results: List[KosItem] = []
        seen_texts = set()

        async with async_playwright() as p:
            context = await get_browser_context(p, platform=self.platform_name, headless=self.headless)
            page = await context.new_page()

            # Jalankan untuk beberapa query pencarian terpilih
            queries = [
                "kost putri upn surabaya",
                "kost cewek gunung anyar",
                "kost putri tambak sumur waru",
                "kost putri uinsa 600"
            ]

            for q in queries:
                if len(results) >= max_results:
                    break

                encoded_q = urllib.parse.quote(q)
                url = f"https://www.threads.net/search?q={encoded_q}&filter=recent"
                print(f"[THREADS] Mencari: '{q}' -> {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)

                    # Lakukan scrolling untuk memuat postingan dinamis
                    for scroll_idx in range(4):
                        await page.mouse.wheel(0, 1500)
                        await asyncio.sleep(2.5)

                    # Cari elemen postingan di Threads
                    # Threads menyusun post dalam elemen artikel atau div dengan data-pressable-container
                    post_elements = await page.locator('div[data-pressable-container="true"], article').all()
                    print(f"[THREADS] Ditemukan {len(post_elements)} kontainer postingan untuk query '{q}'")

                    for el in post_elements:
                        text_content = await el.inner_text()
                        if not text_content or len(text_content.strip()) < 20:
                            continue

                        # Hindari duplikasi postingan
                        content_hash = hash(text_content[:80])
                        if content_hash in seen_texts:
                            continue
                        seen_texts.add(content_hash)

                        # Ambil permalink jika ada
                        link_el = el.locator('a[href*="/post/"]').first
                        post_href = ""
                        if await link_el.count() > 0:
                            href = await link_el.get_attribute("href")
                            if href:
                                post_href = f"https://www.threads.net{href}" if href.startswith("/") else href

                        # Parse menggunakan parser
                        item = self.parser.analyze_post(
                            id_post=f"threads_{abs(content_hash)}",
                            platform="threads",
                            url_post=post_href or url,
                            raw_text=text_content
                        )
                        results.append(item)

                except Exception as e:
                    print(f"[THREADS] Gagal memuat query '{q}': {e}")

            await context.close()

        return results

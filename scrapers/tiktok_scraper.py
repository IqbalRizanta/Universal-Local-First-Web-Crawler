"""
Scraper untuk Platform TikTok
Mencari video spill & review kos mahasiswi di area UPN, UINSA, Gunung Anyar, Tambak Sumur.
"""

import asyncio
import urllib.parse
from typing import List
from playwright.async_api import async_playwright
from scrapers.base_scraper import BaseScraper
from core.browser import get_browser_context
from core.parser import KosItem

class TikTokScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        super().__init__("tiktok")
        self.headless = headless

    async def scrape(self, max_results: int = 30) -> List[KosItem]:
        results: List[KosItem] = []
        seen_texts = set()

        async with async_playwright() as p:
            context = await get_browser_context(p, platform=self.platform_name, headless=self.headless)
            page = await context.new_page()

            queries = [
                "kost putri upn surabaya 600",
                "kost cewek gunung anyar murah",
                "kost mahasiswi uinsa tambak sumur"
            ]

            for q in queries:
                if len(results) >= max_results:
                    break

                encoded_q = urllib.parse.quote(q)
                url = f"https://www.tiktok.com/search?q={encoded_q}"
                print(f"[TIKTOK] Mencari: '{q}' -> {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                    await asyncio.sleep(4)

                    # Scroll feed video
                    for _ in range(4):
                        await page.mouse.wheel(0, 1600)
                        await asyncio.sleep(2.5)

                    # Cari kartu video di hasil pencarian
                    video_cards = await page.locator('div[data-e2e="search_video-item"], div[class*="DivItemContainer"]').all()
                    print(f"[TIKTOK] Ditemukan {len(video_cards)} video untuk query '{q}'")

                    for card in video_cards:
                        text_content = await card.inner_text()
                        if not text_content or len(text_content.strip()) < 15:
                            continue

                        content_hash = hash(text_content[:80])
                        if content_hash in seen_texts:
                            continue
                        seen_texts.add(content_hash)

                        link_el = card.locator('a[href*="/video/"]').first
                        video_href = ""
                        if await link_el.count() > 0:
                            video_href = await link_el.get_attribute("href")

                        item = self.parser.analyze_post(
                            id_post=f"tiktok_{abs(content_hash)}",
                            platform="tiktok",
                            url_post=video_href or url,
                            raw_text=text_content
                        )
                        results.append(item)

                except Exception as e:
                    print(f"[TIKTOK] Gagal memuat query '{q}': {e}")

            await context.close()

        return results

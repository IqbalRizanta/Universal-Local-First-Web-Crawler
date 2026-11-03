"""
Scraper untuk Platform Facebook (Grup & Postingan Pencarian)
Mengambil postingan dari grup info kos sekitar UPN, UINSA, Gunung Anyar, dan Tambak Sumur Waru.
"""

import asyncio
import urllib.parse
from pathlib import Path
from typing import List
from playwright.async_api import async_playwright
from config import FACEBOOK_GROUPS, SESSION_DIR
from scrapers.base_scraper import BaseScraper
from core.browser import get_browser_context
from core.parser import KosItem

class FacebookScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        super().__init__("facebook")
        self.headless = headless

    async def scrape(self, max_results: int = 30) -> List[KosItem]:
        session_file = SESSION_DIR / f"{self.platform_name}_session.json"
        if not session_file.exists():
            print(f"\n[WARNING] Sesi Facebook belum ada di '{session_file}'.")
            print("[PETUNJUK] Jalankan perintah: 'python main.py --login facebook' terlebih dahulu agar Facebook tidak memblokir feed grup.\n")

        results: List[KosItem] = []
        seen_texts = set()

        search_urls = [
            # Pencarian publik di Facebook
            "https://www.facebook.com/search/posts/?q=kost%20putri%20gunung%20anyar%20surabaya",
            "https://www.facebook.com/search/posts/?q=kost%20cewek%20upn%20surabaya%20600",
            "https://www.facebook.com/search/posts/?q=kost%20putri%20tambak%20sumur%20waru"
        ]

        async with async_playwright() as p:
            context = await get_browser_context(p, platform=self.platform_name, headless=self.headless)
            page = await context.new_page()

            for target_url in search_urls:
                if len(results) >= max_results:
                    break

                print(f"[FACEBOOK] Membuka URL: {target_url}")
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=35000)
                    await asyncio.sleep(4)

                    # Scroll feed untuk memuat postingan
                    for _ in range(5):
                        await page.mouse.wheel(0, 1800)
                        await asyncio.sleep(2.5)

                    # Facebook meletakkan teks postingan dalam div dengan dir="auto" di dalam feed
                    feed_blocks = await page.locator('div[role="feed"] > div, div[role="article"]').all()
                    print(f"[FACEBOOK] Ditemukan {len(feed_blocks)} blok postingan di halaman ini")

                    for block in feed_blocks:
                        text_content = await block.inner_text()
                        if not text_content or len(text_content.strip()) < 30:
                            continue

                        # Filter teks yang terlalu pendek atau hanya menu UI Facebook
                        if "Bagikan" not in text_content and "Suka" not in text_content and "Like" not in text_content:
                            continue

                        content_hash = hash(text_content[:90])
                        if content_hash in seen_texts:
                            continue
                        seen_texts.add(content_hash)

                        # Cari tautan post
                        link_el = block.locator('a[href*="/posts/"], a[href*="/permalink/"], a[href*="fbid="]').first
                        post_href = ""
                        if await link_el.count() > 0:
                            href = await link_el.get_attribute("href")
                            if href:
                                post_href = href.split("?")[0]  # bersihkan tracking query params

                        item = self.parser.analyze_post(
                            id_post=f"fb_{abs(content_hash)}",
                            platform="facebook",
                            url_post=post_href or target_url,
                            raw_text=text_content
                        )
                        results.append(item)

                except Exception as e:
                    print(f"[FACEBOOK] Error saat scraping {target_url}: {e}")

            await context.close()

        return results

"""
Scraper untuk Platform Instagram
Mencari postingan kos berdasarkan hashtag dan lokasi seputar Surabaya Timur & UPN/UINSA.
"""

import asyncio
from typing import List
from playwright.async_api import async_playwright
from config import SEARCH_HASHTAGS, SESSION_DIR
from scrapers.base_scraper import BaseScraper
from core.browser import get_browser_context
from core.parser import KosItem

class InstagramScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        super().__init__("instagram")
        self.headless = headless

    async def scrape(self, max_results: int = 30) -> List[KosItem]:
        session_file = SESSION_DIR / f"{self.platform_name}_session.json"
        if not session_file.exists():
            print(f"\n[WARNING] Sesi Instagram belum ada di '{session_file}'.")
            print("[PETUNJUK] Jalankan perintah: 'python main.py --login instagram' agar Instagram tidak memblokir explore tags.\n")

        results: List[KosItem] = []
        seen_texts = set()

        async with async_playwright() as p:
            context = await get_browser_context(p, platform=self.platform_name, headless=self.headless)
            page = await context.new_page()

            # Telusuri 3 hashtag utama
            tags_to_search = ["kostupn", "kostuinsa", "kostgununganyar"]

            for tag in tags_to_search:
                if len(results) >= max_results:
                    break

                url = f"https://www.instagram.com/explore/tags/{tag}/"
                print(f"[INSTAGRAM] Membuka hashtag: #{tag} -> {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                    await asyncio.sleep(4)

                    # Scroll feed hashtag
                    for _ in range(4):
                        await page.mouse.wheel(0, 1600)
                        await asyncio.sleep(2.5)

                    # Ambil tautan postingan / reels
                    post_links = await page.locator('a[href*="/p/"], a[href*="/reel/"]').all()
                    print(f"[INSTAGRAM] Ditemukan {len(post_links)} link postingan di #{tag}")

                    # Ambil beberapa post teratas untuk diekstrak teks captionnya
                    urls_to_visit = []
                    for link in post_links[:10]:
                        href = await link.get_attribute("href")
                        if href and href not in urls_to_visit:
                            urls_to_visit.append(f"https://www.instagram.com{href}" if href.startswith("/") else href)

                    for post_url in urls_to_visit:
                        try:
                            post_page = await context.new_page()
                            await post_page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
                            await asyncio.sleep(2)

                            # Caption biasanya berada di dalam elemen h1 atau div teks pertama di samping avatar
                            caption_el = post_page.locator('h1, span[dir="auto"]').first
                            if await caption_el.count() > 0:
                                caption_text = await caption_el.inner_text()
                                if len(caption_text.strip()) > 20:
                                    content_hash = hash(caption_text[:80])
                                    if content_hash not in seen_texts:
                                        seen_texts.add(content_hash)
                                        item = self.parser.analyze_post(
                                            id_post=f"ig_{abs(content_hash)}",
                                            platform="instagram",
                                            url_post=post_url,
                                            raw_text=caption_text
                                        )
                                        results.append(item)
                            await post_page.close()
                        except Exception as e_inner:
                            print(f"[INSTAGRAM] Error membaca post {post_url}: {e_inner}")

                except Exception as e:
                    print(f"[INSTAGRAM] Gagal memuat tag #{tag}: {e}")

            await context.close()

        return results

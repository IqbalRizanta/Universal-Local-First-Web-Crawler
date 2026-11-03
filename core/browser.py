"""
Modul Browser Automation Playwright
Menyediakan browser context dengan proteksi stealth, user agent realistis,
serta manajemen session cookies untuk Threads, Facebook, Instagram, dan TikTok.
"""

import os
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config import SESSION_DIR

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

async def get_browser_context(
    playwright_instance,
    platform: str,
    headless: bool = True
) -> BrowserContext:
    """
    Membuat browser context dengan session tersimpan jika ada.
    """
    session_file = SESSION_DIR / f"{platform}_session.json"
    
    browser = await playwright_instance.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars"
        ]
    )

    context_kwargs = {
        "user_agent": USER_AGENT,
        "viewport": {"width": 1280, "height": 800},
        "locale": "id-ID",
        "timezone_id": "Asia/Jakarta"
    }

    if session_file.exists():
        context_kwargs["storage_state"] = str(session_file)

    context = await browser.new_context(**context_kwargs)
    return context

async def interactive_login(platform: str, target_url: str):
    """
    Membuka browser tampak (non-headless) agar pengguna bisa login manual satu kali.
    Setelah login, sesi cookies akan disimpan ke file sessions/{platform}_session.json.
    """
    session_file = SESSION_DIR / f"{platform}_session.json"
    print(f"\n[INFO] Membuka browser untuk login {platform.upper()}...")
    print(f"[INFO] Silakan login di jendela browser yang terbuka.")
    print(f"[INFO] Sesi akan disimpan ke: {session_file}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 850}
        )
        page = await context.new_page()
        await page.goto(target_url)

        input("\n>>> Setelah berhasil login dan berada di halaman beranda, tekan [ENTER] di terminal ini untuk menyimpan sesi... <<<")
        
        await context.storage_state(path=str(session_file))
        print(f"[SUCCESS] Sesi {platform} berhasil disimpan ke {session_file}!\n")
        await browser.close()

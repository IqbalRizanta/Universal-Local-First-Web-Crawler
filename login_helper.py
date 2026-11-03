"""
Otomasi Login Interaktif & Penyimpan Sesi Cookies
Membantu login ke Instagram, Threads, Facebook, dan TikTok menggunakan akun dummy,
serta menyimpan session cookies agar proses scraping selanjutnya berjalan otomatis tanpa login berulang.
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel

from config import SESSION_DIR
from core.browser import USER_AGENT

load_dotenv()
console = Console()

async def auto_login_instagram():
    """Login ke Instagram & Threads menggunakan akun dummy"""
    ig_user = os.getenv("IG_USER", "fourpointeight_")
    ig_pass = os.getenv("IG_PASS", "#Barbell22")
    session_file_ig = SESSION_DIR / "instagram_session.json"
    session_file_threads = SESSION_DIR / "threads_session.json"

    console.print(Panel(f"[bold cyan]Memulai Login Instagram / Threads[/bold cyan]\nUser: {ig_user}"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 850},
            locale="id-ID"
        )
        page = await context.new_page()

        try:
            console.print("[yellow]Membuka halaman login Instagram...[/yellow]")
            await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(3)

            # Isi input username & password jika ada form
            user_input = page.locator('input[name="username"]')
            pass_input = page.locator('input[name="password"]')

            if await user_input.count() > 0:
                console.print("[dim]Mengisi username & password secara otomatis...[/dim]")
                await user_input.fill(ig_user)
                await asyncio.sleep(0.5)
                await pass_input.fill(ig_pass)
                await asyncio.sleep(0.8)

                # Klik tombol login
                submit_btn = page.locator('button[type="submit"]')
                if await submit_btn.count() > 0:
                    await submit_btn.click()

            console.print("\n[bold green]>>> PETUNJUK: Jendela browser terbuka. <<<[/bold green]")
            console.print("[white]Jika muncul verifikasi kode email/SMS atau simpan info login, silakan selesaikan di jendela browser.[/white]")
            
            input("\nTekan [ENTER] di terminal ini SETELAH berhasil masuk ke beranda Instagram...")

            # Simpan session untuk Instagram
            await context.storage_state(path=str(session_file_ig))
            console.print(f"[bold green]✓ Sesi Instagram berhasil disimpan ke: {session_file_ig}[/bold green]")

            # Juga simpan session untuk Threads
            await context.storage_state(path=str(session_file_threads))
            console.print(f"[bold green]✓ Sesi Threads berhasil disimpan ke: {session_file_threads}[/bold green]")

        except Exception as e:
            console.print(f"[bold red]Terjadi kesalahan saat login Instagram: {e}[/bold red]")
        finally:
            await browser.close()


async def auto_login_facebook():
    """Login ke Facebook menggunakan akun dummy"""
    fb_user = os.getenv("FB_USER", "Scraping Data")
    fb_pass = os.getenv("FB_PASS", "#Barbell22")
    session_file_fb = SESSION_DIR / "facebook_session.json"

    console.print(Panel(f"[bold cyan]Memulai Login Facebook[/bold cyan]\nUser / Nama: {fb_user}"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 850},
            locale="id-ID"
        )
        page = await context.new_page()

        try:
            console.print("[yellow]Membuka halaman login Facebook...[/yellow]")
            await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(2)

            email_input = page.locator('input#email, input[name="email"]')
            pass_input = page.locator('input#pass, input[name="pass"]')

            if await email_input.count() > 0:
                console.print("[dim]Mencoba mengisi form login Facebook...[/dim]")
                await email_input.fill(fb_user)
                await asyncio.sleep(0.5)
                await pass_input.fill(fb_pass)
                await asyncio.sleep(0.8)

                login_btn = page.locator('button#loginbutton, button[name="login"]')
                if await login_btn.count() > 0:
                    await login_btn.click()

            console.print("\n[bold green]>>> PETUNJUK: Jendela browser terbuka. <<<[/bold green]")
            console.print("[white]Catatan: Jika Facebook meminta email atau no telepon (bukan nama tampilan), silakan ketik email/nomor ponsel akun Anda di browser tersebut.[/white]")
            
            input("\nTekan [ENTER] di terminal ini SETELAH berhasil masuk ke beranda Facebook...")

            await context.storage_state(path=str(session_file_fb))
            console.print(f"[bold green]✓ Sesi Facebook berhasil disimpan ke: {session_file_fb}[/bold green]")

        except Exception as e:
            console.print(f"[bold red]Terjadi kesalahan saat login Facebook: {e}[/bold red]")
        finally:
            await browser.close()


async def auto_login_tiktok():
    """Login ke TikTok menggunakan akun dummy"""
    tiktok_email = os.getenv("TIKTOK_EMAIL", "woiwoiyoiyoi@gmail.com")
    tiktok_pass = os.getenv("TIKTOK_PASS", "#Bench22")
    session_file_tiktok = SESSION_DIR / "tiktok_session.json"

    console.print(Panel(f"[bold cyan]Memulai Login TikTok[/bold cyan]\nEmail: {tiktok_email}"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 850},
            locale="id-ID"
        )
        page = await context.new_page()

        try:
            console.print("[yellow]Membuka halaman login TikTok...[/yellow]")
            await page.goto("https://www.tiktok.com/login/phone-or-email/email", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(3)

            email_input = page.locator('input[name="username"], input[type="text"]')
            pass_input = page.locator('input[type="password"]')

            if await email_input.count() > 0:
                console.print("[dim]Mengisi email & password TikTok...[/dim]")
                await email_input.fill(tiktok_email)
                await asyncio.sleep(0.5)
                await pass_input.fill(tiktok_pass)

            console.print("\n[bold green]>>> PETUNJUK: Jendela browser terbuka. <<<[/bold green]")
            console.print("[white]TikTok biasanya meminta verifikasi puzzle slider (geser puzzle). Silakan selesaikan di jendela browser.[/white]")

            input("\nTekan [ENTER] di terminal ini SETELAH berhasil masuk ke beranda TikTok...")

            await context.storage_state(path=str(session_file_tiktok))
            console.print(f"[bold green]✓ Sesi TikTok berhasil disimpan ke: {session_file_tiktok}[/bold green]")

        except Exception as e:
            console.print(f"[bold red]Terjadi kesalahan saat login TikTok: {e}[/bold red]")
        finally:
            await browser.close()


async def main():
    parser = argparse.ArgumentParser(description="Helper Login Akun Dummy Scraper")
    parser.add_argument("--platform", choices=["instagram", "threads", "facebook", "tiktok", "all"], default="instagram",
                        help="Platform target login (default: instagram)")
    args = parser.parse_args()

    if args.platform in ["instagram", "threads"]:
        await auto_login_instagram()
    elif args.platform == "facebook":
        await auto_login_facebook()
    elif args.platform == "tiktok":
        await auto_login_tiktok()
    elif args.platform == "all":
        await auto_login_instagram()
        await auto_login_facebook()
        await auto_login_tiktok()

if __name__ == "__main__":
    asyncio.run(main())

"""
Main CLI Runner untuk Scraper Kos-Kosan Surabaya Timur & Waru Sidoarjo
Kriteria: Khusus Cewek, Range Harga 500-700k, Lahan Parkir, Air Bersih, Lingkungan Aman.
"""

import sys
import asyncio
import argparse
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from core.parser import KosItem, KosParser
from core.exporter import KosExporter
from core.browser import interactive_login
from scrapers.threads_scraper import ThreadsScraper
from scrapers.fb_scraper import FacebookScraper
from scrapers.ig_scraper import InstagramScraper
from scrapers.tiktok_scraper import TikTokScraper
from scrapers.mamikos_scraper import MamikosScraper
from scrapers.direct_kos_scraper import DirectKosScraper

console = Console()

SAMPLE_TEST_POSTS = [
    {
        "id": "sample_1",
        "platform": "facebook",
        "url": "https://facebook.com/groups/infokostupn/permalink/101",
        "author": "Ibu Kos Barokah",
        "text": (
            "INFO KOST PUTRI DEKAT KAMPUS UPN VETERAN JATIM SURABAYA\n"
            "Lokasi: Jalan Gunung Anyar Sawah No. 12 (5 menit dari UPN & UINSA Kampus 2).\n"
            "Khusus mahasiswi / cewek muslimah baik-baik.\n"
            "Harga: Rp 600.000 / bulan (sudah termasuk air PDAM & listrik standard).\n"
            "Fasilitas:\n"
            "- Kasur springbed, lemari baju\n"
            "- Lahan parkir motor luas berpagar aman digembok\n"
            "- Kamar mandi luar bersih, air sumur jernih & PDAM lancar\n"
            "- Lingkungan sangat aman, tenang, bebas banjir dan ramah mahasiswi.\n"
            "Minat hubungi WA: 081234567890"
        )
    },
    {
        "id": "sample_2",
        "platform": "threads",
        "url": "https://threads.net/@anissaa/post/202",
        "author": "anissaa",
        "text": (
            "Spill kos cewek di Tambak Sumur Waru Sidoarjo deket perbatasan Rungkut/UPN, "
            "sewa cuma 650rb/bln dapet parkir motor dalem aman ada CCTV, air jernih ga bau. "
            "Ibu kosnya ramah bgt. WA 085711223344"
        )
    },
    {
        "id": "sample_3",
        "platform": "tiktok",
        "url": "https://tiktok.com/@infokost/video/303",
        "author": "infokost",
        "text": (
            "Kost Putra & Campur bebas area Medokan Rungkut Surabaya. "
            "Harga 1.200.000 AC kamar mandi dalam. Parkir mobil luas."
        )
    },
    {
        "id": "sample_4",
        "platform": "instagram",
        "url": "https://instagram.com/p/404",
        "author": "kost_uinsa_sby",
        "text": (
            "Kos putri murah 550k per bulan belakang UINSA Gunung Anyar. "
            "Kamar ukuran 3x3, kasur busa, parkiran motor aman, air pdam. "
            "Khusus cewe mahasiswi. CP: 087899001122"
        )
    }
]

def run_test_suite():
    """Menguji engine parser dengan postingan realistis bahasa Indonesia"""
    console.print(Panel.fit(
        "[bold cyan]Menjalankan Pengujian Parser Kriteria Kos (Khusus Cewek, 500-700k, Parkir & Air)[/bold cyan]"
    ))

    parser = KosParser()
    items: List[KosItem] = []

    table = Table(title="Hasil Analisis & Filter Kriteria Kos")
    table.add_column("ID / Platform", style="cyan")
    table.add_column("Gender", style="magenta")
    table.add_column("Harga / Bulan", style="green")
    table.add_column("Lokasi", style="yellow")
    table.add_column("Parkir", style="blue")
    table.add_column("Air", style="blue")
    table.add_column("WA", style="bold green")
    table.add_column("Skor", justify="right")
    table.add_column("Rekomendasi?", justify="center")

    for p in SAMPLE_TEST_POSTS:
        item = parser.analyze_post(
            id_post=p["id"],
            platform=p["platform"],
            url_post=p["url"],
            author=p["author"],
            raw_text=p["text"]
        )
        items.append(item)

        status_icon = "[bold green]LULUS (100%)[/bold green]" if item.is_fully_matched else (
            f"[bold yellow]{item.match_score}%[/bold yellow]" if item.match_score >= 50 else "[bold red]DITOLAK[/bold red]"
        )

        table.add_row(
            f"{item.id_post}\n({item.platform})",
            item.gender,
            f"Rp {item.harga_per_bulan:,}" if item.harga_per_bulan else "-",
            ", ".join(item.lokasi_terdeteksi) if item.lokasi_terdeteksi else "-",
            item.parkir_detail or "-",
            item.air_detail or "-",
            item.kontak_wa or "-",
            f"{item.match_score}%",
            status_icon
        )

    console.print(table)

    # Test export to excel/csv
    export_result = KosExporter.export(items, filename_prefix="test_sample")
    console.print(f"\n[bold green]Hasil Ekspor Pengujian:[/bold green]")
    console.print(f"• Total Data: {export_result['total_scraped']}")
    console.print(f"• Lolos Rekomendasi (500k-700k Putri): {export_result['total_matched']}")
    console.print(f"• File Excel Rekomendasi: [underline]{export_result['file_filtered_excel']}[/underline]")
    console.print(f"• File CSV Rekomendasi: [underline]{export_result['file_filtered_csv']}[/underline]\n")


async def main_async():
    parser_arg = argparse.ArgumentParser(description="Scraper Kos-Kosan Surabaya Timur & Waru Sidoarjo")
    parser_arg.add_argument("--platform", 
                            choices=["mamikos", "direktori", "threads", "facebook", "instagram", "tiktok", "all"], 
                            default="direktori",
                            help="Platform target scraping (default: direktori)")
    parser_arg.add_argument("--max", type=int, default=30, help="Maksimal data yang diambil per platform")
    parser_arg.add_argument("--no-headless", action="store_true", help="Tampilkan jendela browser saat scraping")
    parser_arg.add_argument("--login", choices=["facebook", "instagram", "threads", "tiktok"],
                            help="Jalankan login interaktif untuk menyimpan session cookies")
    parser_arg.add_argument("--test", action="store_true", help="Jalankan simulasi pengujian parser & filter")

    args = parser_arg.parse_args()

    if args.test:
        run_test_suite()
        return

    if args.login:
        from login_helper import auto_login_instagram, auto_login_facebook, auto_login_tiktok
        if args.login in ["instagram", "threads"]:
            await auto_login_instagram()
        elif args.login == "facebook":
            await auto_login_facebook()
        elif args.login == "tiktok":
            await auto_login_tiktok()
        return

    headless = not args.no_headless
    all_items: List[KosItem] = []

    console.print(f"\n[bold cyan]=== MEMULAI CRAWLING KOS-KOSAN ({args.platform.upper()}) ===[/bold cyan]")
    console.print("[dim]Target: Gunung Anyar, UPN, UINSA, Tambak Sumur Waru | Cewek | 500k - 700k[/dim]\n")

    if args.platform in ["direktori", "all"]:
        scraper = DirectKosScraper()
        items = await scraper.scrape(max_results=args.max)
        all_items.extend(items)

    if args.platform in ["mamikos", "all"]:
        scraper = MamikosScraper(headless=headless)
        items = await scraper.scrape(max_results=args.max)
        all_items.extend(items)

    if args.platform in ["threads", "all"]:
        scraper = ThreadsScraper(headless=headless)
        items = await scraper.scrape(max_results=args.max)
        all_items.extend(items)

    if args.platform in ["facebook", "all"]:
        scraper = FacebookScraper(headless=headless)
        items = await scraper.scrape(max_results=args.max)
        all_items.extend(items)

    if args.platform in ["instagram", "all"]:
        scraper = InstagramScraper(headless=headless)
        items = await scraper.scrape(max_results=args.max)
        all_items.extend(items)

    if args.platform in ["tiktok", "all"]:
        scraper = TikTokScraper(headless=headless)
        items = await scraper.scrape(max_results=args.max)
        all_items.extend(items)

    if all_items:
        export_res = KosExporter.export(all_items, filename_prefix=f"kos_{args.platform}")
        console.print(f"\n[bold green]Proses Scraping Selesai![/bold green]")
        console.print(f"• Total Data Terambil: {export_res['total_scraped']}")
        console.print(f"• Rekomendasi Sesuai Kriteria (Putri, 500-700k): {export_res['total_matched']}")
        console.print(f"• File Excel: [cyan]{export_res['file_filtered_excel']}[/cyan]")
        console.print(f"• File CSV: [cyan]{export_res['file_filtered_csv']}[/cyan]")
    else:
        console.print("[yellow]Tidak ada data yang berhasil diekstrak. Pastikan koneksi lancar atau gunakan opsi --login jika terkena blokir halaman.[/yellow]")

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()

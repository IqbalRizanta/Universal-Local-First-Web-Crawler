"""
OmniCrawl Studio — Universal Local-First Multi-Platform Web Crawler Server (FastAPI + WebSocket)
Clean Code Architecture:
- Strategy & Factory Pattern (AdapterFactory: Research, Web Search, Social Media, Marketplace, Custom URL)
- Adaptive Load Balancer (Weighted Least-Connections + Round-Robin User-Agent Rotation)
- Token Bucket Rate Limiter & Circuit Breaker Pattern
- O(1) SHA-256 Content Deduplicator & BM25-Inspired Relevance Scoring Pipeline
- Zero-Server Storage (Browser LocalStorage + In-Memory BytesIO Excel/CSV Streaming)
"""

import io
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import BASE_DIR, SESSION_DIR
from core.algorithms import AdaptiveLoadBalancer, ContentDeduplicator
from core.universal_parser import UniversalFilterCriteria, UniversalProcessingPipeline, UniversalRecord
from core.exporter import KosExporter
from scrapers.universal_adapters import AdapterFactory

app = FastAPI(
    title="OmniCrawl Studio — Universal Local Web Crawler",
    description="Universal Multi-Platform Web Data Extraction Engine with Adaptive Load Balancing & Zero-Server Storage",
    version="2.0.0"
)

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global Load Balancer instance for telemetry & connection pooling
GLOBAL_LOAD_BALANCER = AdaptiveLoadBalancer(num_workers=4, max_concurrency=6)


class UniversalCrawlRequest(BaseModel):
    query: str = "machine learning healthcare"
    platforms: List[str] = Field(default_factory=lambda: ["openalex", "arxiv", "duckduckgo"])
    max_results_per_platform: int = 15
    must_include: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    custom_regex: Optional[str] = None
    custom_urls: List[str] = Field(default_factory=list)
    min_score_threshold: int = 45
    headless: bool = True


class ExportRequest(BaseModel):
    items: List[Dict[str, Any]]
    filename: str = "omnicrawl_export"


PRESET_TEMPLATES = {
    "research": {
        "name": "🔬 Riset Ilmiah & Akademik (Jurnal / Paper)",
        "query": "Large Language Models Medical Diagnosis",
        "platforms": ["openalex", "arxiv", "wikipedia"],
        "must_include": ["model", "clinical", "learning"],
        "exclude_keywords": [],
        "min_value": 2021,
        "max_value": 2026,
        "custom_regex": ""
    },
    "market_web": {
        "name": "🌐 Riset Tren Web, Komunitas & Berita",
        "query": "cybersecurity cloud computing trend",
        "platforms": ["duckduckgo", "reddit", "wikipedia"],
        "must_include": ["security", "cloud"],
        "exclude_keywords": ["hoax"],
        "min_value": None,
        "max_value": None,
        "custom_regex": ""
    },
    "social_media": {
        "name": "📱 Opini & Tren Media Sosial",
        "query": "remote work software engineer",
        "platforms": ["reddit", "threads", "duckduckgo"],
        "must_include": ["remote"],
        "exclude_keywords": [],
        "min_value": None,
        "max_value": None,
        "custom_regex": ""
    },
    "property_kos": {
        "name": "🏠 Pencarian Properti / Kos-Kosan Spesifik",
        "query": "kost putri gunung anyar upn surabaya",
        "platforms": ["direktori", "mamikos"],
        "must_include": ["putri", "gunung anyar", "upn", "parkir"],
        "exclude_keywords": ["khusus putra", "khusus cowok"],
        "min_value": 500000,
        "max_value": 700000,
        "custom_regex": ""
    }
}


@app.get("/", response_class=HTMLResponse)
async def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>UI belum tersedia.</h1>")
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.get("/api/status")
async def get_status():
    sessions = {}
    for plat in ["instagram", "threads", "facebook", "tiktok"]:
        f = SESSION_DIR / f"{plat}_session.json"
        sessions[plat] = {
            "logged_in": f.exists(),
            "updated_at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if f.exists() else None
        }
    return {
        "status": "ready",
        "sessions": sessions,
        "presets": PRESET_TEMPLATES,
        "telemetry": GLOBAL_LOAD_BALANCER.get_telemetry()
    }


@app.post("/api/crawl/sample")
async def run_sample_test():
    """Simulasi instan lintas domain (Research, Social Media, Web Search, Marketplace)."""
    pipeline = UniversalProcessingPipeline(
        UniversalFilterCriteria(query="AI Research & Data", min_score_threshold=40)
    )
    sample_raw = [
        {
            "id": "sample_openalex_1",
            "platform": "openalex",
            "category": "research",
            "title": "Transformer Architectures for Clinical Decision Support Systems",
            "url": "https://doi.org/10.1038/s41591-025-0001",
            "author": "Dr. A. Pratama, S. Wijaya",
            "published_date": "2025-08-14",
            "raw_content": "This study evaluates deep learning and large language models for automated medical diagnosis. DOI: 10.1038/s41591-025-0001. Contact: research@med-ai.org",
            "preset_numeric": 2025,
            "preset_numeric_label": "Tahun 2025 (84 sitasi)"
        },
        {
            "id": "sample_arxiv_2",
            "platform": "arxiv",
            "category": "research",
            "title": "Efficient Load Balancing Algorithms in Distributed Web Crawlers",
            "url": "https://arxiv.org/abs/2504.12345",
            "author": "K. Nakamura, L. Chen",
            "published_date": "2025-04-20",
            "raw_content": "We propose a weighted least-connections load balancer combined with token bucket rate limiting for high-throughput data extraction.",
            "preset_numeric": 2025,
            "preset_numeric_label": "Tahun 2025 (Preprint)"
        },
        {
            "id": "sample_reddit_3",
            "platform": "reddit",
            "category": "social",
            "title": "[r/datascience] Best open-source tools for local-first web scraping in Python?",
            "url": "https://reddit.com/r/datascience/comments/sample3",
            "author": "u/python_engineer",
            "published_date": "2026-10-12",
            "raw_content": "Playwright combined with curl_cffi and FastAPI WebSockets works great for zero-storage local data pipelines. #python #webscraping",
            "preset_numeric": 342,
            "preset_numeric_label": "342 Upvotes"
        },
        {
            "id": "sample_dir_4",
            "platform": "direktori",
            "category": "marketplace",
            "title": "Kost Putri Dekat Kampus UPN & UINSA Gunung Anyar Surabaya",
            "url": "https://www.sewakost.com/kost/surabaya/gunung-anyar/sample-200162/",
            "author": "Bunda Luluk",
            "published_date": "2026-11-01",
            "raw_content": "Khusus putri/mahasiswi. Harga Rp 550.000/bulan. Fasilitas lahan parkir motor aman, air PDAM bersih lancar. Hubungi WA: 081345134505",
            "preset_numeric": 550000,
            "preset_numeric_label": "Rp 550,000"
        }
    ]
    records = [
        pipeline.process(
            id_record=s["id"],
            platform=s["platform"],
            category=s["category"],
            title=s["title"],
            url=s["url"],
            raw_content=s["raw_content"],
            author=s["author"],
            published_date=s["published_date"],
            preset_numeric=s["preset_numeric"],
            preset_numeric_label=s["preset_numeric_label"]
        ).model_dump()
        for s in sample_raw
    ]
    return {
        "status": "success",
        "total": len(records),
        "items": records,
        "telemetry": GLOBAL_LOAD_BALANCER.get_telemetry()
    }


@app.websocket("/ws/crawl")
async def websocket_universal_crawl(websocket: WebSocket):
    """
    Menjalankan crawling multi-platform secara paralel & terdistribusi melalui AdaptiveLoadBalancer.
    Mengirimkan live log serta telemetri worker ke UI secara real-time.
    """
    await websocket.accept()
    start_time = time.perf_counter()

    try:
        raw_payload = await websocket.receive_text()
        payload = json.loads(raw_payload)
        req = UniversalCrawlRequest(**payload)

        criteria = UniversalFilterCriteria(
            query=req.query,
            must_include=[k.strip() for k in req.must_include if k.strip()],
            exclude_keywords=[k.strip() for k in req.exclude_keywords if k.strip()],
            min_value=req.min_value,
            max_value=req.max_value,
            custom_regex=req.custom_regex.strip() if req.custom_regex else None,
            min_score_threshold=req.min_score_threshold
        )

        pipeline = UniversalProcessingPipeline(criteria=criteria)
        deduplicator = ContentDeduplicator()

        await websocket.send_json({
            "type": "log",
            "message": f"⚡ Load Balancer menginisialisasi {len(req.platforms)} platform paralel untuk kueri: '{req.query}'"
        })

        all_records: List[UniversalRecord] = []
        total_platforms = len(req.platforms)
        completed_platforms = 0

        async def _crawl_single_platform(plat_id: str):
            nonlocal completed_platforms
            worker_preview = GLOBAL_LOAD_BALANCER.select_worker()
            await websocket.send_json({
                "type": "log",
                "message": f"🔄 [{plat_id.upper()}] Dijadwalkan ke {worker_preview.worker_id} (Weight={worker_preview.weight})..."
            })
            try:
                adapter = AdapterFactory.create(
                    platform_id=plat_id,
                    pipeline=pipeline,
                    lb=GLOBAL_LOAD_BALANCER,
                    dedup=deduplicator,
                    headless=req.headless
                )
                recs = await adapter.crawl(
                    query=req.query,
                    max_results=req.max_results_per_platform,
                    extra_params={"custom_urls": req.custom_urls}
                )
                completed_platforms += 1
                rec_matched = sum(1 for r in recs if r.is_recommended)
                await websocket.send_json({
                    "type": "progress",
                    "platform": plat_id,
                    "step": completed_platforms,
                    "total_steps": total_platforms,
                    "telemetry": GLOBAL_LOAD_BALANCER.get_telemetry(),
                    "message": f"✓ [{plat_id.upper()}] Selesai: {len(recs)} item unik ({rec_matched} lolos skor ≥{req.min_score_threshold}%)."
                })
                return recs
            except Exception as e:
                completed_platforms += 1
                await websocket.send_json({
                    "type": "error",
                    "telemetry": GLOBAL_LOAD_BALANCER.get_telemetry(),
                    "message": f"✗ [{plat_id.upper()}] Gagal / Ditahan Circuit Breaker: {str(e)}"
                })
                return []

        # Jalankan seluruh platform secara konkuren yang dikendalikan oleh AdaptiveLoadBalancer
        results_nested = await asyncio.gather(*[_crawl_single_platform(p) for p in req.platforms])
        for batch in results_nested:
            all_records.extend(batch)

        # Urutkan berdasarkan relevance_score tertinggi
        all_records.sort(key=lambda r: r.relevance_score, reverse=True)
        elapsed_sec = round(time.perf_counter() - start_time, 2)

        serialized = [r.model_dump() for r in all_records]
        await websocket.send_json({
            "type": "complete",
            "total": len(serialized),
            "duplicates_removed": deduplicator.duplicates_removed,
            "elapsed_seconds": elapsed_sec,
            "telemetry": GLOBAL_LOAD_BALANCER.get_telemetry(),
            "items": serialized,
            "message": (
                f"🚀 Selesai dalam {elapsed_sec}s! Total {len(serialized)} data bersih "
                f"({deduplicator.duplicates_removed} duplikat dieliminasi) disimpan ke Browser Storage Anda."
            )
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Server error: {str(e)}"})


@app.post("/api/export/excel")
async def export_excel(req: ExportRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk diekspor")

    excel_bytes = KosExporter.to_excel_bytes(req.items)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{req.filename}_{ts}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/api/export/csv")
async def export_csv(req: ExportRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk diekspor")

    csv_bytes = KosExporter.to_csv_bytes(req.items)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{req.filename}_{ts}.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


if __name__ == "__main__":
    import uvicorn
    print("\n============================================================")
    print(" ⚡ OMNICRAWL STUDIO — UNIVERSAL LOCAL WEB CRAWLER AKTIF!")
    print(" 🌐 Buka di Browser: http://localhost:8000")
    print("============================================================\n")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)

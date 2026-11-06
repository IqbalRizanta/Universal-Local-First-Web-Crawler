---
name: local-web-crawler
description: >-
  Orchestrates, extends, tests, and runs the Universal Local-First Multi-Platform Web Crawler
  (OmniCrawl Studio: FastAPI + Adaptive Load Balancer + Token Bucket + Circuit Breaker +
  Research/Social/Search/Marketplace Adapters). Use this skill when adding new platform
  adapters, tuning load balancing or BM25 scoring algorithms, or running the web dashboard.
---

# OmniCrawl Studio — Universal Local-First Web Crawler Skill

This skill defines the architecture, design patterns, algorithms, and extension workflows for the universal multi-platform web crawler in `C:\Script_Scraping`.

## Clean Code Architecture & Design Patterns

1. **Algorithms & Distributed Traffic Control ([`core/algorithms.py`](../../../core/algorithms.py))**:
   - `AdaptiveLoadBalancer`: **Weighted Least-Connections** worker selection (`active_connections / weight`) with average latency tie-breaking and Round-Robin User-Agent rotation.
   - `TokenBucketRateLimiter`: Per-domain asynchronous **Token Bucket** rate limiting.
   - `DomainCircuitBreaker`: **Circuit Breaker Pattern** (`CLOSED`, `OPEN`, `HALF_OPEN`) with Full-Jitter Exponential Backoff.
   - `ContentDeduplicator`: $O(1)$ SHA-256 content and canonical URL fingerprinting.
2. **Universal Processing Pipeline ([`core/universal_parser.py`](../../../core/universal_parser.py))**:
   - **Chain of Responsibility Pattern** & **BM25-Inspired Term Saturation Scoring** (`0–100%`).
   - Extracts emails, phone/WA numbers, DOIs, hashtags, prices/years, and custom regex patterns into `UniversalRecord`.
3. **Platform Adapters ([`scrapers/universal_adapters.py`](../../../scrapers/universal_adapters.py))**:
   - **Strategy & Factory Pattern** (`BasePlatformAdapter` & `AdapterFactory`).
   - Built-in adapters across 4 ecosystems:
     - **Research & Academic**: `OpenAlexAdapter`, `ArxivAdapter`, `WikipediaAdapter`
     - **Web Search & Custom URL**: `DuckDuckGoWebAdapter`, `CustomUrlAdapter`
     - **Social Media**: `RedditAdapter`, plus bridged `ThreadsScraper`, `FacebookScraper`, `InstagramScraper`, `TikTokScraper`
     - **Marketplace & Directories**: `DirectKosScraper`, `MamikosScraper`

---

## Standard Workflows

### 1. Launching the Universal Web UI Dashboard
```powershell
.\venv\Scripts\python app.py
```
Access at `http://localhost:8000` (or double-click `start_web.bat`).

### 2. Adding a New Platform Adapter
1. Subclass `BasePlatformAdapter` in [`scrapers/universal_adapters.py`](../../../scrapers/universal_adapters.py).
2. Route all network calls through `await self.lb.execute_task(self.domain, _fetch)` so the new platform automatically inherits Load Balancing, Token Bucket Rate Limiting, and Circuit Breaker protection.
3. Deduplicate via `self.dedup.is_unique(url, title, content)` and score via `self.pipeline.process(...)`.
4. Register the new `platform_id` in `AdapterFactory.create()`.

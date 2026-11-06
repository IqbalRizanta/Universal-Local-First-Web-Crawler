"""
Universal Platform Adapters (Strategy Pattern + Factory Pattern)
Mendukung ekstraksi data lintas domain:
1. Research & Academic: OpenAlex, arXiv, Wikipedia
2. Web Search & Custom URL: DuckDuckGo Web Search, Custom URL Scraper
3. Social Media & Community: Reddit, Threads, Facebook, Instagram, TikTok
4. Marketplace & Directories: Direktori Web, Mamikos
Semua request melewati AdaptiveLoadBalancer, TokenBucketRateLimiter, dan CircuitBreaker.
"""

import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

from core.algorithms import AdaptiveLoadBalancer, ContentDeduplicator, WorkerNode
from core.universal_parser import UniversalRecord, UniversalProcessingPipeline


class BasePlatformAdapter(ABC):
    """Abstract Strategy untuk setiap platform yang didukung."""

    def __init__(
        self,
        platform_id: str,
        category: str,
        domain: str,
        pipeline: UniversalProcessingPipeline,
        load_balancer: AdaptiveLoadBalancer,
        deduplicator: ContentDeduplicator
    ):
        self.platform_id = platform_id
        self.category = category
        self.domain = domain
        self.pipeline = pipeline
        self.lb = load_balancer
        self.dedup = deduplicator

    @abstractmethod
    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        pass


class OpenAlexAdapter(BasePlatformAdapter):
    """Adapter untuk platform riset ilmiah OpenAlex (250+ juta publikasi akademik)."""

    def __init__(self, pipeline, lb, dedup):
        super().__init__("openalex", "research", "api.openalex.org", pipeline, lb, dedup)

    @staticmethod
    def _reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
        if not inverted_index or not isinstance(inverted_index, dict):
            return ""
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        q = query.strip() or "machine learning"
        encoded_q = urllib.parse.quote(q)
        per_page = min(50, max(5, max_results))
        api_url = f"https://api.openalex.org/works?search={encoded_q}&per-page={per_page}&sort=publication_date:desc"

        async def _fetch(worker: WorkerNode):
            def _sync_get():
                return cf_requests.get(
                    api_url,
                    headers={"User-Agent": worker.user_agent, "Accept": "application/json"},
                    impersonate="chrome124",
                    timeout=15
                )
            resp = await asyncio.to_thread(_sync_get)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAlex HTTP {resp.status_code}")
            return resp.json()

        data = await self.lb.execute_task(self.domain, _fetch)
        results: List[UniversalRecord] = []

        for work in data.get("results", [])[:max_results]:
            title = work.get("title") or "Untitled Research Paper"
            url = work.get("doi") or work.get("id") or api_url
            pub_year = work.get("publication_year")
            pub_date = work.get("publication_date") or (str(pub_year) if pub_year else None)
            cited_by = work.get("cited_by_count", 0)

            authors = [
                a.get("author", {}).get("display_name", "")
                for a in work.get("authorships", [])[:4]
                if a.get("author", {}).get("display_name")
            ]
            author_str = ", ".join(authors) if authors else "OpenAlex Author"

            abstract_text = self._reconstruct_abstract(work.get("abstract_inverted_index"))
            concepts = [c.get("display_name", "") for c in work.get("concepts", [])[:5] if c.get("display_name")]
            full_text = f"{abstract_text}\nTopik: {', '.join(concepts)} | Sitasi: {cited_by}".strip()

            is_uniq, fp = self.dedup.is_unique(url, title, full_text)
            if not is_uniq:
                continue

            rec = self.pipeline.process(
                id_record=f"openalex_{fp}",
                platform="openalex",
                category="research",
                title=title,
                url=url,
                raw_content=full_text,
                author=author_str,
                published_date=pub_date,
                preset_numeric=float(pub_year) if pub_year else None,
                preset_numeric_label=f"Tahun {pub_year} ({cited_by} sitasi)" if pub_year else f"{cited_by} sitasi",
                extra_metadata={"citations": cited_by, "year": pub_year}
            )
            results.append(rec)

        return results


class ArxivAdapter(BasePlatformAdapter):
    """Adapter untuk preprint ilmiah arXiv.org (Computer Science, Physics, Math, Quantitative Biology)."""

    def __init__(self, pipeline, lb, dedup):
        super().__init__("arxiv", "research", "export.arxiv.org", pipeline, lb, dedup)

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        q = query.strip() or "artificial intelligence"
        encoded_q = urllib.parse.quote(f"all:{q}")
        api_url = f"http://export.arxiv.org/api/query?search_query={encoded_q}&start=0&max_results={min(40, max_results)}&sortBy=submittedDate&sortOrder=descending"

        async def _fetch(worker: WorkerNode):
            def _sync_get():
                return cf_requests.get(
                    api_url,
                    headers={"User-Agent": worker.user_agent},
                    timeout=15
                )
            resp = await asyncio.to_thread(_sync_get)
            if resp.status_code != 200:
                raise RuntimeError(f"arXiv HTTP {resp.status_code}")
            return resp.text

        xml_text = await self.lb.execute_task(self.domain, _fetch)
        results: List[UniversalRecord] = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)

        for entry in root.findall("atom:entry", ns)[:max_results]:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip().replace("\n", " ")
            link = entry.findtext("atom:id", default="", namespaces=ns) or api_url
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
            pub_year = float(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None

            authors = [
                a.findtext("atom:name", default="", namespaces=ns)
                for a in entry.findall("atom:author", ns)[:4]
            ]
            author_str = ", ".join([a for a in authors if a])

            is_uniq, fp = self.dedup.is_unique(link, title, summary)
            if not is_uniq:
                continue

            rec = self.pipeline.process(
                id_record=f"arxiv_{fp}",
                platform="arxiv",
                category="research",
                title=title,
                url=link,
                raw_content=summary,
                author=author_str,
                published_date=published,
                preset_numeric=pub_year,
                preset_numeric_label=f"Tahun {int(pub_year)}" if pub_year else None
            )
            results.append(rec)

        return results


class WikipediaAdapter(BasePlatformAdapter):
    """Adapter untuk ensiklopedia & referensi pengetahuan Wikipedia (ID & EN)."""

    def __init__(self, pipeline, lb, dedup):
        super().__init__("wikipedia", "research", "id.wikipedia.org", pipeline, lb, dedup)

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        q = query.strip() or "Indonesia"
        encoded_q = urllib.parse.quote(q)
        api_url = f"https://id.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_q}&utf8=&format=json&srlimit={min(30, max_results)}"

        async def _fetch(worker: WorkerNode):
            def _sync_get():
                return cf_requests.get(
                    api_url,
                    headers={"User-Agent": worker.user_agent},
                    timeout=12
                )
            resp = await asyncio.to_thread(_sync_get)
            return resp.json()

        data = await self.lb.execute_task(self.domain, _fetch)
        results: List[UniversalRecord] = []

        for item in data.get("query", {}).get("search", [])[:max_results]:
            title = item.get("title", "")
            snippet_html = item.get("snippet", "")
            clean_snippet = BeautifulSoup(snippet_html, "html.parser").get_text(" ", strip=True)
            timestamp = (item.get("timestamp", "") or "")[:10]
            page_url = f"https://id.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"

            is_uniq, fp = self.dedup.is_unique(page_url, title, clean_snippet)
            if not is_uniq:
                continue

            rec = self.pipeline.process(
                id_record=f"wiki_{fp}",
                platform="wikipedia",
                category="research",
                title=title,
                url=page_url,
                raw_content=clean_snippet,
                author="Wikipedia Contributors",
                published_date=timestamp
            )
            results.append(rec)

        return results


class DuckDuckGoWebAdapter(BasePlatformAdapter):
    """Adapter Pencarian Web Universal menggunakan DuckDuckGo HTML dengan TLS Impersonation."""

    def __init__(self, pipeline, lb, dedup):
        super().__init__("duckduckgo", "web_search", "html.duckduckgo.com", pipeline, lb, dedup)

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        q = query.strip() or "berita teknologi terbaru"

        async def _fetch(worker: WorkerNode):
            def _sync_post():
                return cf_requests.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": q},
                    headers={
                        "User-Agent": worker.user_agent,
                        "Referer": "https://html.duckduckgo.com/"
                    },
                    impersonate="chrome124",
                    timeout=15
                )
            resp = await asyncio.to_thread(_sync_post)
            if resp.status_code != 200:
                raise RuntimeError(f"DuckDuckGo HTTP {resp.status_code}")
            return resp.text

        html_text = await self.lb.execute_task(self.domain, _fetch)
        soup = BeautifulSoup(html_text, "html.parser")
        results: List[UniversalRecord] = []

        for block in soup.find_all("div", class_="result"):
            if len(results) >= max_results:
                break
            title_el = block.find("a", class_="result__a")
            snippet_el = block.find("a", class_="result__snippet")
            url_el = block.find("a", class_="result__url")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            href = (url_el.get("href") if url_el else title_el.get("href")) or ""
            if href.startswith("//"):
                href = "https:" + href

            is_uniq, fp = self.dedup.is_unique(href, title, snippet)
            if not is_uniq:
                continue

            rec = self.pipeline.process(
                id_record=f"ddg_{fp}",
                platform="duckduckgo",
                category="web_search",
                title=title,
                url=href,
                raw_content=snippet
            )
            results.append(rec)

        return results


class RedditAdapter(BasePlatformAdapter):
    """Adapter Media Sosial & Komunitas Reddit (Public JSON Search Feed)."""

    def __init__(self, pipeline, lb, dedup):
        super().__init__("reddit", "social", "www.reddit.com", pipeline, lb, dedup)

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        q = query.strip() or "technology"
        encoded_q = urllib.parse.quote(q)
        api_url = f"https://www.reddit.com/search.json?q={encoded_q}&sort=new&limit={min(50, max_results)}"

        async def _fetch(worker: WorkerNode):
            def _sync_get():
                return cf_requests.get(
                    api_url,
                    headers={"User-Agent": worker.user_agent, "Accept": "application/json"},
                    impersonate="chrome124",
                    timeout=15
                )
            resp = await asyncio.to_thread(_sync_get)
            if resp.status_code != 200:
                raise RuntimeError(f"Reddit HTTP {resp.status_code}")
            return resp.json()

        data = await self.lb.execute_task(self.domain, _fetch)
        results: List[UniversalRecord] = []

        children = data.get("data", {}).get("children", [])
        for child in children[:max_results]:
            post = child.get("data", {})
            title = post.get("title", "")
            selftext = post.get("selftext", "") or title
            subreddit = post.get("subreddit_name_prefixed", "r/all")
            author = post.get("author", "redditor")
            permalink = f"https://www.reddit.com{post.get('permalink', '')}"
            ups = post.get("ups", 0)

            is_uniq, fp = self.dedup.is_unique(permalink, title, selftext)
            if not is_uniq:
                continue

            rec = self.pipeline.process(
                id_record=f"reddit_{fp}",
                platform="reddit",
                category="social",
                title=f"[{subreddit}] {title}",
                url=permalink,
                raw_content=selftext[:1200],
                author=f"u/{author}",
                preset_numeric=float(ups),
                preset_numeric_label=f"{ups} Upvotes"
            )
            results.append(rec)

        return results


class CustomUrlAdapter(BasePlatformAdapter):
    """Adapter Universal untuk mengekstrak konten, harga, email, dan nomor telepon dari URL kustom pilihan user."""

    def __init__(self, pipeline, lb, dedup):
        super().__init__("custom_url", "custom", "custom.local", pipeline, lb, dedup)

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        urls: List[str] = (extra_params or {}).get("custom_urls", [])
        if not urls and query.startswith("http"):
            urls = [u.strip() for u in query.split(",") if u.strip().startswith("http")]

        results: List[UniversalRecord] = []
        for target_url in urls[:max_results]:
            parsed_domain = urllib.parse.urlparse(target_url).netloc or "custom.local"

            async def _fetch(worker: WorkerNode, u=target_url):
                def _sync_get():
                    return cf_requests.get(
                        u,
                        headers={"User-Agent": worker.user_agent},
                        impersonate="chrome124",
                        timeout=15
                    )
                resp = await asyncio.to_thread(_sync_get)
                return resp.text

            try:
                html_text = await self.lb.execute_task(parsed_domain, _fetch)
                soup = BeautifulSoup(html_text, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                title = (soup.title.string if soup.title else target_url) or target_url
                body_text = soup.get_text(" ", strip=True)[:2500]

                is_uniq, fp = self.dedup.is_unique(target_url, title, body_text)
                if not is_uniq:
                    continue

                rec = self.pipeline.process(
                    id_record=f"url_{fp}",
                    platform="custom_url",
                    category="custom",
                    title=title.strip(),
                    url=target_url,
                    raw_content=body_text
                )
                results.append(rec)
            except Exception as e:
                continue

        return results


class ExistingScraperBridgeAdapter(BasePlatformAdapter):
    """
    Adapter Jembatan (Bridge Pattern) yang menghubungkan modul scraper spesifik
    (Direktori Kos, Mamikos, Threads, Facebook, Instagram, TikTok) ke dalam Universal Pipeline.
    """

    def __init__(self, platform_id: str, category: str, domain: str, pipeline, lb, dedup, headless: bool = True):
        super().__init__(platform_id, category, domain, pipeline, lb, dedup)
        self.headless = headless

    async def crawl(self, query: str, max_results: int = 20, extra_params: Optional[Dict[str, Any]] = None) -> List[UniversalRecord]:
        from scrapers.direct_kos_scraper import DirectKosScraper
        from scrapers.mamikos_scraper import MamikosScraper
        from scrapers.threads_scraper import ThreadsScraper
        from scrapers.fb_scraper import FacebookScraper
        from scrapers.ig_scraper import InstagramScraper
        from scrapers.tiktok_scraper import TikTokScraper

        async def _run_scraper(worker: WorkerNode):
            if self.platform_id == "direktori":
                s = DirectKosScraper()
            elif self.platform_id == "mamikos":
                s = MamikosScraper(headless=self.headless)
            elif self.platform_id == "threads":
                s = ThreadsScraper(headless=self.headless)
            elif self.platform_id == "facebook":
                s = FacebookScraper(headless=self.headless)
            elif self.platform_id == "instagram":
                s = InstagramScraper(headless=self.headless)
            elif self.platform_id == "tiktok":
                s = TikTokScraper(headless=self.headless)
            else:
                raise ValueError(f"Unsupported bridge platform: {self.platform_id}")
            return await s.scrape(max_results=max_results)

        legacy_items = await self.lb.execute_task(self.domain, _run_scraper, max_retries=1)
        results: List[UniversalRecord] = []

        for it in legacy_items:
            first_line = it.raw_text.split("\n")[0][:100] if it.raw_text else f"Listing {self.platform_id}"
            is_uniq, fp = self.dedup.is_unique(it.url_post, first_line, it.raw_text)
            if not is_uniq:
                continue

            rec = self.pipeline.process(
                id_record=it.id_post,
                platform=self.platform_id,
                category=self.category,
                title=first_line,
                url=it.url_post,
                raw_content=it.raw_text,
                author=it.author,
                published_date=it.tanggal_post,
                preset_numeric=float(it.harga_per_bulan) if it.harga_per_bulan else None,
                preset_numeric_label=f"Rp {it.harga_per_bulan:,}" if it.harga_per_bulan else None,
                extra_metadata={
                    "gender": it.gender,
                    "parkir": it.parkir_detail,
                    "air": it.air_detail,
                    "lokasi": it.lokasi_terdeteksi
                }
            )
            if it.kontak_wa and it.kontak_wa not in rec.contacts:
                rec.contacts.insert(0, str(it.kontak_wa))
            results.append(rec)

        return results


class AdapterFactory:
    """Factory Pattern untuk menginstansiasi Platform Adapter sesuai pilihan user."""

    @staticmethod
    def create(
        platform_id: str,
        pipeline: UniversalProcessingPipeline,
        lb: AdaptiveLoadBalancer,
        dedup: ContentDeduplicator,
        headless: bool = True
    ) -> BasePlatformAdapter:
        pid = platform_id.lower().strip()
        if pid == "openalex":
            return OpenAlexAdapter(pipeline, lb, dedup)
        if pid == "arxiv":
            return ArxivAdapter(pipeline, lb, dedup)
        if pid == "wikipedia":
            return WikipediaAdapter(pipeline, lb, dedup)
        if pid == "duckduckgo":
            return DuckDuckGoWebAdapter(pipeline, lb, dedup)
        if pid == "reddit":
            return RedditAdapter(pipeline, lb, dedup)
        if pid == "custom_url":
            return CustomUrlAdapter(pipeline, lb, dedup)
        if pid in ["direktori", "mamikos"]:
            return ExistingScraperBridgeAdapter(pid, "marketplace", f"{pid}.com", pipeline, lb, dedup, headless=headless)
        if pid in ["threads", "facebook", "instagram", "tiktok"]:
            return ExistingScraperBridgeAdapter(pid, "social", f"{pid}.com", pipeline, lb, dedup, headless=headless)
        raise ValueError(f"Adapter untuk platform '{platform_id}' belum terdaftar.")

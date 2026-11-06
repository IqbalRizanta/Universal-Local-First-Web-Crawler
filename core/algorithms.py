"""
Core Algorithms & Distributed Systems Patterns for Efficient Web Crawling:
1. TokenBucketRateLimiter: Per-domain rate limiting (Token Bucket Algorithm).
2. DomainCircuitBreaker: Fault tolerance & automatic failover (Circuit Breaker Pattern).
3. AdaptiveLoadBalancer: Least-Connections + Weighted Round-Robin worker scheduling & User-Agent rotation.
4. ContentDeduplicator: O(1) SHA-256 normalized fingerprinting to eliminate duplicates.
"""

import time
import math
import random
import hashlib
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple


USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


class CircuitState(str, Enum):
    CLOSED = "CLOSED"         # Normal: request diizinkan
    OPEN = "OPEN"             # Gangguan: request ditahan sementara
    HALF_OPEN = "HALF_OPEN"   # Uji pemulihan


@dataclass
class TokenBucket:
    rate: float               # Token yang ditambahkan per detik
    capacity: float           # Kapasitas maksimal ember
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    async def acquire(self, requested: float = 1.0) -> float:
        """Mengambil token; jika kurang, menunggu secara asinkron sesuai defisit waktu."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= requested:
            self.tokens -= requested
            return 0.0

        deficit = requested - self.tokens
        wait_time = deficit / self.rate
        self.tokens = 0.0
        self.last_refill = now + wait_time
        await asyncio.sleep(wait_time)
        return wait_time


class TokenBucketRateLimiter:
    """Mengelola Token Bucket per domain target agar tidak memicu HTTP 429 Too Many Requests."""

    def __init__(self, default_rate: float = 2.0, default_capacity: float = 4.0):
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._buckets: Dict[str, TokenBucket] = {}

    def get_bucket(self, domain: str) -> TokenBucket:
        if domain not in self._buckets:
            self._buckets[domain] = TokenBucket(rate=self.default_rate, capacity=self.default_capacity)
        return self._buckets[domain]

    async def throttle(self, domain: str) -> float:
        bucket = self.get_bucket(domain)
        return await bucket.acquire(1.0)


@dataclass
class CircuitBreakerMetrics:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0
    failure_threshold: int = 3
    recovery_timeout: float = 20.0


class DomainCircuitBreaker:
    """
    Circuit Breaker Pattern per platform/domain.
    Memutus koneksi sementara jika platform mengalami error beruntun,
    serta menerapkan Exponential Backoff with Full Jitter.
    """

    def __init__(self):
        self._circuits: Dict[str, CircuitBreakerMetrics] = {}

    def _get(self, domain: str) -> CircuitBreakerMetrics:
        if domain not in self._circuits:
            self._circuits[domain] = CircuitBreakerMetrics()
        return self._circuits[domain]

    def allow_request(self, domain: str) -> bool:
        cb = self._get(domain)
        if cb.state == CircuitState.CLOSED:
            return True
        if cb.state == CircuitState.OPEN:
            if (time.monotonic() - cb.last_failure_time) >= cb.recovery_timeout:
                cb.state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self, domain: str):
        cb = self._get(domain)
        cb.failures = 0
        cb.successes += 1
        cb.state = CircuitState.CLOSED

    def record_failure(self, domain: str):
        cb = self._get(domain)
        cb.failures += 1
        cb.last_failure_time = time.monotonic()
        if cb.failures >= cb.failure_threshold:
            cb.state = CircuitState.OPEN

    @staticmethod
    def compute_backoff_with_jitter(attempt: int, base_delay: float = 0.8, max_delay: float = 10.0) -> float:
        """Full Jitter Exponential Backoff: random(0, min(max_delay, base * 2^attempt))."""
        exp_delay = min(max_delay, base_delay * (2 ** attempt))
        return random.uniform(0.1, exp_delay)

    def get_states(self) -> Dict[str, str]:
        return {dom: m.state.value for dom, m in self._circuits.items()}


@dataclass
class WorkerNode:
    worker_id: str
    weight: int
    user_agent: str
    active_connections: int = 0
    completed_tasks: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return round(self.total_latency_ms / self.completed_tasks, 2) if self.completed_tasks > 0 else 0.0

    @property
    def load_ratio(self) -> float:
        """Rasio beban saat ini terhadap kapasitas bobot (Weighted Least-Connections)."""
        return self.active_connections / max(1, self.weight)


class AdaptiveLoadBalancer:
    """
    Algoritma Load Balancing Hibrida:
    - Weighted Least-Connections: Memilih worker node dengan rasio (active_connections / weight) terendah.
    - Tie-Breaker dengan Average Latency terendah & Round-Robin rotation.
    - Mengatur batas konkurensi global melalui asyncio.Semaphore.
    """

    def __init__(self, num_workers: int = 4, max_concurrency: int = 6):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.rate_limiter = TokenBucketRateLimiter(default_rate=2.5, default_capacity=5.0)
        self.circuit_breaker = DomainCircuitBreaker()
        self.workers: List[WorkerNode] = [
            WorkerNode(
                worker_id=f"worker-{i+1}",
                weight=(3 if i % 2 == 0 else 2),
                user_agent=USER_AGENT_POOL[i % len(USER_AGENT_POOL)]
            )
            for i in range(num_workers)
        ]
        self._rr_index = 0

    def select_worker(self) -> WorkerNode:
        """Memilih worker paling efisien menggunakan algoritma Weighted Least-Connections."""
        # Urutkan berdasarkan load_ratio terkecil, lalu avg_latency_ms terkecil
        sorted_workers = sorted(
            self.workers,
            key=lambda w: (w.load_ratio, w.avg_latency_ms)
        )
        chosen = sorted_workers[0]
        self._rr_index = (self._rr_index + 1) % len(self.workers)
        return chosen

    async def execute_task(
        self,
        domain: str,
        coro_factory: Callable[[WorkerNode], Any],
        max_retries: int = 2
    ) -> Any:
        """
        Menjalankan tugas scraping melalui Load Balancer, Rate Limiter, dan Circuit Breaker.
        """
        if not self.circuit_breaker.allow_request(domain):
            raise RuntimeError(f"Circuit Breaker OPEN untuk domain '{domain}' (terlalu banyak error sebelumnya).")

        await self.rate_limiter.throttle(domain)

        async with self.semaphore:
            worker = self.select_worker()
            worker.active_connections += 1
            start_ts = time.perf_counter()

            last_exc = None
            try:
                for attempt in range(max_retries + 1):
                    try:
                        result = await coro_factory(worker)
                        elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
                        worker.completed_tasks += 1
                        worker.total_latency_ms += elapsed_ms
                        self.circuit_breaker.record_success(domain)
                        return result
                    except Exception as e:
                        last_exc = e
                        if attempt < max_retries:
                            delay = self.circuit_breaker.compute_backoff_with_jitter(attempt)
                            await asyncio.sleep(delay)
                self.circuit_breaker.record_failure(domain)
                raise last_exc
            finally:
                worker.active_connections = max(0, worker.active_connections - 1)

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "workers": [
                {
                    "id": w.worker_id,
                    "weight": w.weight,
                    "active": w.active_connections,
                    "completed": w.completed_tasks,
                    "avg_latency_ms": w.avg_latency_ms
                }
                for w in self.workers
            ],
            "circuits": self.circuit_breaker.get_states()
        }


class ContentDeduplicator:
    """
    Algoritma Deduplikasi O(1) menggunakan SHA-256 Content & Canonical URL Fingerprinting.
    """

    def __init__(self):
        self._seen_hashes: set = set()
        self.duplicates_removed: int = 0

    @staticmethod
    def compute_fingerprint(url: str, title: str, content: str) -> str:
        norm_text = " ".join((title + " " + content[:240]).lower().split())
        raw_key = f"{url.split('?')[0].strip().lower()}||{norm_text[:160]}"
        return hashlib.sha256(raw_key.encode("utf-8", errors="ignore")).hexdigest()[:20]

    def is_unique(self, url: str, title: str, content: str) -> Tuple[bool, str]:
        fp = self.compute_fingerprint(url, title, content)
        if fp in self._seen_hashes:
            self.duplicates_removed += 1
            return False, fp
        self._seen_hashes.add(fp)
        return True, fp

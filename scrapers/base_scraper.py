"""
Base Scraper Abstract Class
"""

from abc import ABC, abstractmethod
from typing import List
from core.parser import KosItem, KosParser

class BaseScraper(ABC):
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.parser = KosParser()

    @abstractmethod
    async def scrape(self, max_results: int = 20) -> List[KosItem]:
        """Menjalankan proses scraping untuk platform tertentu"""
        pass

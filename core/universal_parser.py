"""
Universal Entity Extraction & Relevance Scoring Pipeline (Clean Architecture)
Menerapkan Chain of Responsibility Pattern dan algoritma BM25-Inspired Term Scoring
untuk memproses data dari platform apa saja (Research, Social Media, Search, Marketplace, Custom URL).
"""

import re
import math
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field


class UniversalFilterCriteria(BaseModel):
    query: str = ""
    must_include: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    custom_regex: Optional[str] = None
    min_score_threshold: int = 45


class UniversalRecord(BaseModel):
    id_record: str
    platform: str
    category: str                           # research | social | web_search | marketplace | custom
    title: str
    url: str
    author: Optional[str] = None
    published_date: Optional[str] = None
    raw_content: str

    # Hasil Ekstraksi Universal
    numeric_value: Optional[float] = None   # Harga (Rp/$), Tahun Publikasi, atau Jumlah Sitasi
    numeric_label: Optional[str] = None     # Format tampilan (misal: "Rp 600.000", "Tahun 2025", "42 Sitasi")
    contacts: List[str] = Field(default_factory=list)       # Nomor WA/Telp atau Email
    identifiers: List[str] = Field(default_factory=list)    # DOI, ArXiv ID, Hashtags
    matched_keywords: List[str] = Field(default_factory=list)
    custom_regex_matches: List[str] = Field(default_factory=list)

    # Skor Relevansi & Status Filter
    relevance_score: int = 0
    is_recommended: bool = False
    audit_notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UniversalProcessingPipeline:
    """
    Pipeline pemrosesan entitas universal & kalkulasi skor relevansi (BM25-inspired + Heuristic).
    """

    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    PHONE_REGEX = re.compile(r'(?:\+?62|08)[0-9\-\.\s]{8,14}')
    DOI_REGEX = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b')
    HASHTAG_REGEX = re.compile(r'#[a-zA-Z0-9_]{2,40}')
    YEAR_REGEX = re.compile(r'\b(19\d\d|20[0-3]\d)\b')

    def __init__(self, criteria: Optional[UniversalFilterCriteria] = None):
        self.criteria = criteria or UniversalFilterCriteria()

    @classmethod
    def extract_contacts(cls, text: str) -> List[str]:
        contacts = []
        for m in cls.PHONE_REGEX.findall(text):
            cleaned = re.sub(r'[\-\.\s]', '', m)
            if 10 <= len(cleaned) <= 15 and cleaned not in contacts:
                contacts.append(cleaned)
        for em in cls.EMAIL_REGEX.findall(text):
            if em not in contacts:
                contacts.append(em)
        return contacts[:5]

    @classmethod
    def extract_identifiers(cls, text: str) -> List[str]:
        ids = []
        for doi in cls.DOI_REGEX.findall(text):
            ids.append(f"DOI:{doi}")
        for tag in cls.HASHTAG_REGEX.findall(text):
            if tag.lower() not in [i.lower() for i in ids]:
                ids.append(tag)
        return ids[:8]

    @classmethod
    def extract_numeric_or_price(cls, text: str, category: str, default_val: Optional[float] = None) -> Tuple[Optional[float], Optional[str]]:
        if default_val is not None:
            if category == "research" and 1900 <= default_val <= 2100:
                return default_val, f"Tahun {int(default_val)}"
            if default_val >= 10000:
                return default_val, f"Rp {int(default_val):,}"
            return default_val, str(default_val)

        lower = text.lower()
        # 1. Cek format harga Indonesia (500rb, 650k, Rp 700.000)
        match_k = re.search(r'(?:rp\.?\s*)?(\d{2,4})\s*(?:rb|k|ribu)\b', lower)
        if match_k:
            val = float(match_k.group(1)) * 1000
            return val, f"Rp {int(val):,}"

        match_full = re.search(r'(?:rp\.?\s*)?(\d{1,3}(?:[\.,]\d{3}){1,2})\b', lower)
        if match_full:
            raw_digits = re.sub(r'[\.,]', '', match_full.group(1))
            if raw_digits.isdigit():
                val = float(raw_digits)
                if 50_000 <= val <= 500_000_000:
                    return val, f"Rp {int(val):,}"

        # 2. Jika kategori riset, ekstrak tahun publikasi
        if category == "research":
            years = cls.YEAR_REGEX.findall(text)
            if years:
                yr = float(years[0])
                return yr, f"Tahun {int(yr)}"

        return None, None

    def compute_bm25_term_score(self, text: str, query_terms: List[str], k1: float = 1.5, b: float = 0.75) -> float:
        """
        Menghitung skor relevansi teks terhadap kata kunci kueri menggunakan pendekatan saturasi frekuensi BM25.
        """
        if not query_terms:
            return 25.0

        words = re.findall(r'\w+', text.lower())
        doc_len = max(1, len(words))
        avg_doc_len = 80.0

        freq_map: Dict[str, int] = {}
        for w in words:
            freq_map[w] = freq_map.get(w, 0) + 1

        raw_score = 0.0
        for term in query_terms:
            t = term.lower().strip()
            if not t:
                continue
            tf = freq_map.get(t, 0)
            if tf == 0 and t in text.lower():
                tf = 1
            if tf > 0:
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (doc_len / avg_doc_len))
                raw_score += (numerator / denominator)

        max_possible = len(query_terms) * (k1 + 1.0)
        normalized = min(1.0, raw_score / max(1.0, max_possible * 0.65))
        return round(normalized * 45.0, 2)

    def process(
        self,
        id_record: str,
        platform: str,
        category: str,
        title: str,
        url: str,
        raw_content: str,
        author: Optional[str] = None,
        published_date: Optional[str] = None,
        preset_numeric: Optional[float] = None,
        preset_numeric_label: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> UniversalRecord:
        combined_text = f"{title}\n{raw_content}".strip()
        lower = combined_text.lower()
        notes: List[str] = []

        # 1. BM25 Query Relevance (Bobot maks 45 poin)
        query_terms = [t for t in re.split(r'\s+', self.criteria.query.strip()) if len(t) > 1]
        score = self.compute_bm25_term_score(combined_text, query_terms)
        if score >= 20:
            notes.append(f"Relevansi kueri tinggi (+{int(score)} pts)")

        # 2. Must-Include Keywords (Bobot maks 30 poin)
        matched_kw: List[str] = []
        if self.criteria.must_include:
            for kw in self.criteria.must_include:
                k_clean = kw.strip().lower()
                if k_clean and k_clean in lower:
                    matched_kw.append(kw.strip())
            ratio = len(matched_kw) / max(1, len(self.criteria.must_include))
            kw_points = round(ratio * 30.0)
            score += kw_points
            if matched_kw:
                notes.append(f"Keyword cocok: {', '.join(matched_kw)}")
        else:
            score += 20  # Jika user tidak membatasi must_include

        # 3. Exclude Keywords Disqualifier
        is_excluded = False
        for ex in self.criteria.exclude_keywords:
            ex_clean = ex.strip().lower()
            if ex_clean and ex_clean in lower:
                is_excluded = True
                score = max(0, score - 50)
                notes.append(f"Mengandung kata dikecualikan: '{ex.strip()}'")

        # 4. Ekstraksi Nilai Angka / Harga / Tahun (Bobot maks 20 poin)
        num_val, num_label = self.extract_numeric_or_price(combined_text, category, preset_numeric)
        if preset_numeric_label:
            num_label = preset_numeric_label

        numeric_ok = True
        if self.criteria.min_value is not None or self.criteria.max_value is not None:
            if num_val is not None:
                min_v = self.criteria.min_value if self.criteria.min_value is not None else -math.inf
                max_v = self.criteria.max_value if self.criteria.max_value is not None else math.inf
                if min_v <= num_val <= max_v:
                    score += 20
                    notes.append(f"Nilai sesuai rentang ({num_label})")
                else:
                    numeric_ok = False
                    score = max(0, score - 20)
                    notes.append(f"Nilai di luar rentang ({num_label})")
        else:
            score += 15

        # 5. Ekstraksi Kontak, Identifier & Custom Regex (Bobot bonus 5 poin)
        contacts = self.extract_contacts(combined_text)
        identifiers = self.extract_identifiers(combined_text)
        regex_matches: List[str] = []
        if self.criteria.custom_regex:
            try:
                regex_matches = [str(m) for m in re.findall(self.criteria.custom_regex, combined_text)[:5]]
                if regex_matches:
                    score += 5
                    notes.append(f"Custom Regex cocok ({len(regex_matches)})")
            except re.error:
                notes.append("Format Custom Regex tidak valid")

        if contacts or identifiers:
            score += 5

        final_score = int(min(100, max(0, round(score))))
        is_recommended = (
            not is_excluded
            and numeric_ok
            and final_score >= self.criteria.min_score_threshold
        )

        return UniversalRecord(
            id_record=id_record,
            platform=platform,
            category=category,
            title=title[:180] if title else (raw_content[:90] + "..."),
            url=url,
            author=author,
            published_date=published_date,
            raw_content=raw_content,
            numeric_value=num_val,
            numeric_label=num_label,
            contacts=contacts,
            identifiers=identifiers,
            matched_keywords=matched_kw,
            custom_regex_matches=regex_matches,
            relevance_score=final_score,
            is_recommended=is_recommended,
            audit_notes=notes,
            metadata=extra_metadata or {}
        )

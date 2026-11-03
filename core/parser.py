"""
Modul Parser dan Ekstraksi Entitas Teks Iklan Kos
Mengekstrak harga, gender, fasilitas (parkir & air), lokasi, dan nomor WhatsApp
dari teks caption media sosial yang tidak terstruktur.
"""

import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class KosItem(BaseModel):
    id_post: str
    platform: str
    url_post: str
    author: Optional[str] = None
    tanggal_post: Optional[str] = None
    raw_text: str
    
    # Hasil Ekstraksi
    nama_kos: Optional[str] = None
    harga_per_bulan: Optional[int] = None
    harga_raw: Optional[str] = None
    gender: str = "Tidak diketahui"  # Putri, Campur, Putra
    is_putri: bool = False
    
    # Lokasi
    lokasi_terdeteksi: List[str] = Field(default_factory=list)
    is_target_location: bool = False
    
    # Fasilitas & Lingkungan
    has_parkir: bool = False
    parkir_detail: Optional[str] = None
    has_air_bersih: bool = False
    air_detail: Optional[str] = None
    is_lingkungan_aman: bool = False
    
    # Kontak
    kontak_wa: Optional[str] = None
    
    # Skor Kesesuaian Kriteria (0 - 100%)
    match_score: int = 0
    is_fully_matched: bool = False
    catatan_filter: List[str] = Field(default_factory=list)


class KosParser:
    def __init__(self, criteria: Optional[Dict[str, Any]] = None):
        from config import FILTER_CRITERIA
        self.criteria = criteria or FILTER_CRITERIA

    def extract_phone_number(self, text: str) -> Optional[str]:
        """Ekstraksi nomor telepon / WhatsApp Indonesia"""
        pattern = r'(?:\+?62|08)[0-9\-\.\s]{8,15}'
        matches = re.findall(pattern, text)
        if matches:
            cleaned = re.sub(r'[\-\.\s]', '', matches[0])
            if 10 <= len(cleaned) <= 15:
                return cleaned
        return None

    def extract_price(self, text: str) -> (Optional[int], Optional[str]):
        """
        Mendeteksi harga per bulan dari teks postingan.
        Contoh: 600rb, 650.000, 500k, 700 ribu, Rp 650000
        """
        lower = text.lower()
        
        # Pola 1: Angka dengan k / rb / ribu (contoh: 600rb, 650k, 700 ribu)
        pattern_k = r'(?:rp\.?\s*)?(\d{2,4})\s*(?:rb|k|ribu)'
        match_k = re.search(pattern_k, lower)
        if match_k:
            num = int(match_k.group(1))
            price = num * 1000
            return price, f"{num}k/rb"

        # Pola 2: Angka jutaan / ratusan ribu penuh (contoh: 500.000, 650000, 700.000)
        pattern_full = r'(?:rp\.?\s*)?(\d{3})[\.,]?(\d{3})'
        match_full = re.search(pattern_full, lower)
        if match_full:
            full_val = int(match_full.group(1) + match_full.group(2))
            # Pastikan nilainya masuk akal untuk sewa kos per bulan (antara 300rb - 5jt)
            if 300_000 <= full_val <= 5_000_000:
                return full_val, f"Rp {full_val:,}"

        # Pola 3: Angka polos 3 digit diikuti konteks harga (contoh: sewa 600 / bln)
        pattern_context = r'(?:sewa|harga|tarif|biaya|hanya|cuma)\s*(?:rp\.?\s*)?(\d{3})(?!\d)'
        match_ctx = re.search(pattern_context, lower)
        if match_ctx:
            num = int(match_ctx.group(1))
            if 400 <= num <= 990:
                return num * 1000, f"{num} (konteks harga)"

        return None, None

    def analyze_post(self, id_post: str, platform: str, url_post: str, 
                     raw_text: str, author: Optional[str] = None, 
                     tanggal_post: Optional[str] = None) -> KosItem:
        """
        Menganalisis teks postingan dan memvalidasi terhadap kriteria:
        - Khusus Cewek / Putri
        - Range harga 500.000 - 700.000
        - Lokasi target (Gunung Anyar, UPN, UINSA, Tambak Sumur, dll)
        - Fasilitas Parkir & Air Bersih
        """
        lower = raw_text.lower()
        catatan = []
        score = 0

        # 1. Ekstraksi Kontak WA
        wa = self.extract_phone_number(raw_text)

        # 2. Ekstraksi Harga
        price, price_raw = self.extract_price(raw_text)
        price_matched = False
        if price:
            if self.criteria["price_min"] <= price <= self.criteria["price_max"]:
                price_matched = True
                score += 35
                catatan.append(f"Harga cocok ({price:,})")
            else:
                catatan.append(f"Harga di luar budget ({price:,})")
        else:
            catatan.append("Harga tidak tertera jelas")

        # 3. Analisis Gender
        is_excluded = any(ex in lower for ex in self.criteria["gender_excluded"])
        is_putri = any(kw in lower for kw in self.criteria["gender_allowed"])
        
        if is_excluded:
            gender = "Putra / Campur"
            catatan.append("Bukan kos putri (Putra/Campur)")
        elif is_putri:
            gender = "Putri / Mahasiswi"
            score += 25
            catatan.append("Khusus cewek/putri terkonfirmasi")
        else:
            gender = "Tidak disebutkan eksplisit"
            catatan.append("Gender tidak disebutkan")

        # 4. Analisis Lokasi Target
        lokasi_ditemukan = []
        for loc in self.criteria["locations_target"]:
            if loc in lower:
                lokasi_ditemukan.append(loc)
        
        is_target_loc = len(lokasi_ditemukan) > 0
        if is_target_loc:
            score += 20
            catatan.append(f"Lokasi sesuai ({', '.join(lokasi_ditemukan)})")
        else:
            catatan.append("Lokasi spesifik belum terdeteksi")

        # 5. Analisis Fasilitas Parkir
        has_parkir = any(p in lower for p in self.criteria["facilities_parking"])
        parkir_detail = None
        if has_parkir:
            score += 10
            if "mobil" in lower:
                parkir_detail = "Mobil & Motor"
            else:
                parkir_detail = "Parkir Motor"
            catatan.append("Ada lahan parkir")

        # 6. Analisis Fasilitas Air
        has_air = any(a in lower for a in self.criteria["facilities_water"])
        air_detail = None
        if has_air:
            score += 5
            if "pdam" in lower:
                air_detail = "PDAM"
            elif "sumur" in lower:
                air_detail = "Air Sumur / Jernih"
            else:
                air_detail = "Air Bersih Tersedia"
            catatan.append("Tersedia info air bersih")

        # 7. Analisis Lingkungan Aman
        is_aman = any(e in lower for e in self.criteria["environment_positive"])
        if is_aman:
            score += 5
            catatan.append("Disebutkan lingkungan aman / ada pagar / cctv")

        # Status Fully Matched (Memenuhi kriteria pokok: Khusus Putri + Range 500-700rb + Lokasi Target + Parkir)
        is_fully_matched = (
            (is_putri and not is_excluded) and
            price_matched and
            is_target_loc and
            has_parkir
        )

        return KosItem(
            id_post=id_post,
            platform=platform,
            url_post=url_post,
            author=author,
            tanggal_post=tanggal_post,
            raw_text=raw_text.strip(),
            harga_per_bulan=price,
            harga_raw=price_raw,
            gender=gender,
            is_putri=(is_putri and not is_excluded),
            lokasi_terdeteksi=lokasi_ditemukan,
            is_target_location=is_target_loc,
            has_parkir=has_parkir,
            parkir_detail=parkir_detail,
            has_air_bersih=has_air,
            air_detail=air_detail,
            is_lingkungan_aman=is_aman,
            kontak_wa=wa,
            match_score=min(score, 100),
            is_fully_matched=is_fully_matched,
            catatan_filter=catatan
        )

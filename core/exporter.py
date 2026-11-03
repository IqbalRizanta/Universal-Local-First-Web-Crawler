"""
Modul Export Data Hasil Scraping Kos
Menyimpan data hasil ekstraksi ke Excel (.xlsx), CSV, dan JSON.
"""

import json
from typing import List
from datetime import datetime
import pandas as pd
from config import RAW_DATA_DIR, FILTERED_DATA_DIR
from core.parser import KosItem

class KosExporter:
    @staticmethod
    def export(items: List[KosItem], filename_prefix: str = "hasil_kos") -> dict:
        """
        Export data ke 2 kategori:
        1. All Results (termasuk yang skor rendah untuk audit)
        2. Filtered Results (hanya yang lolos kriteria utama / skor >= 60%)
        """
        if not items:
            return {"status": "empty", "message": "Tidak ada data untuk diexport"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Convert items to list of dicts
        records = []
        for it in items:
            row = it.model_dump()
            # Format list to comma separated string for Excel/CSV readability
            row["lokasi_terdeteksi"] = ", ".join(row["lokasi_terdeteksi"])
            row["catatan_filter"] = " | ".join(row["catatan_filter"])
            records.append(row)

        df_all = pd.DataFrame(records)

        # 1. Simpan semua data ke folder raw
        raw_csv_path = RAW_DATA_DIR / f"{filename_prefix}_all_{timestamp}.csv"
        raw_json_path = RAW_DATA_DIR / f"{filename_prefix}_all_{timestamp}.json"
        
        df_all.to_csv(raw_csv_path, index=False, encoding="utf-8-sig")
        with open(raw_json_path, "w", encoding="utf-8") as f:
            json.dump([it.model_dump() for it in items], f, ensure_ascii=False, indent=2)

        # 2. Filter data yang lolos kriteria (Skor >= 60 atau is_fully_matched)
        df_filtered = df_all[
            (df_all["is_putri"] == True) & 
            (
                (df_all["harga_per_bulan"].isna()) | 
                ((df_all["harga_per_bulan"] >= 500_000) & (df_all["harga_per_bulan"] <= 700_000))
            ) &
            (df_all["match_score"] >= 50)
        ].copy()

        # Sortir berdasarkan skor kecocokan tertinggi
        if not df_filtered.empty:
            df_filtered.sort_values(by=["match_score", "is_fully_matched"], ascending=[False, False], inplace=True)

        filtered_xlsx_path = FILTERED_DATA_DIR / f"{filename_prefix}_rekomendasi_{timestamp}.xlsx"
        filtered_csv_path = FILTERED_DATA_DIR / f"{filename_prefix}_rekomendasi_{timestamp}.csv"

        df_filtered.to_excel(filtered_xlsx_path, index=False, engine="openpyxl")
        df_filtered.to_csv(filtered_csv_path, index=False, encoding="utf-8-sig")

        return {
            "status": "success",
            "total_scraped": len(df_all),
            "total_matched": len(df_filtered),
            "file_raw_csv": str(raw_csv_path),
            "file_filtered_excel": str(filtered_xlsx_path),
            "file_filtered_csv": str(filtered_csv_path)
        }

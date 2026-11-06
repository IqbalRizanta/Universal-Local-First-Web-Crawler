"""
Modul Export Data Universal & Spesifik
Menyimpan data hasil ekstraksi ke Excel (.xlsx), CSV, dan JSON,
serta mendukung Zero-Server Storage (in-memory stream via BytesIO) untuk Web UI.
"""

import io
import json
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
from config import RAW_DATA_DIR, FILTERED_DATA_DIR
from core.parser import KosItem


class KosExporter:
    @staticmethod
    def _prepare_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
        cleaned = []
        for r in records:
            row = {}
            for k, v in r.items():
                if isinstance(v, list):
                    row[k] = ", ".join(str(x) for x in v)
                elif isinstance(v, dict):
                    row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    row[k] = v
            cleaned.append(row)
        return pd.DataFrame(cleaned)

    @staticmethod
    def to_excel_bytes(records: List[Dict[str, Any]]) -> bytes:
        """Menghasilkan file Excel (.xlsx) di memori (BytesIO) tanpa menyimpan di disk server."""
        df = KosExporter._prepare_dataframe(records)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="OmniCrawl_Data")
        return output.getvalue()

    @staticmethod
    def to_csv_bytes(records: List[Dict[str, Any]]) -> bytes:
        """Menghasilkan file CSV di memori (BytesIO) tanpa menyimpan di disk server."""
        df = KosExporter._prepare_dataframe(records)
        return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

    @staticmethod
    def export(items: List[KosItem], filename_prefix: str = "hasil_kos") -> dict:
        if not items:
            return {"status": "empty", "message": "Tidak ada data untuk diexport"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        records = []
        for it in items:
            row = it.model_dump()
            row["lokasi_terdeteksi"] = ", ".join(row["lokasi_terdeteksi"])
            row["catatan_filter"] = " | ".join(row["catatan_filter"])
            records.append(row)

        df_all = pd.DataFrame(records)

        raw_csv_path = RAW_DATA_DIR / f"{filename_prefix}_all_{timestamp}.csv"
        raw_json_path = RAW_DATA_DIR / f"{filename_prefix}_all_{timestamp}.json"

        df_all.to_csv(raw_csv_path, index=False, encoding="utf-8-sig")
        with open(raw_json_path, "w", encoding="utf-8") as f:
            json.dump([it.model_dump() for it in items], f, ensure_ascii=False, indent=2)

        df_filtered = df_all[
            (df_all["is_putri"] == True) &
            (
                (df_all["harga_per_bulan"].isna()) |
                ((df_all["harga_per_bulan"] >= 500_000) & (df_all["harga_per_bulan"] <= 700_000))
            ) &
            (df_all["match_score"] >= 50)
        ].copy()

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

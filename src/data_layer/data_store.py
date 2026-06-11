from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from config.settings import PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from src.data_layer.models import (
    AdCampaignRecord,
    CompetitorKeyword,
    KeepaDailyRecord,
    Keyword,
    KeywordClassified,
    KeywordTrafficShare,
)


class DataStore:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.raw_dir = os.path.join(self.base_dir, "data", "raw")
        self.processed_dir = os.path.join(self.base_dir, "data", "processed")
        self.reports_dir = os.path.join(self.base_dir, "data", "reports")
        for d in [self.raw_dir, self.processed_dir, self.reports_dir]:
            os.makedirs(d, exist_ok=True)

    def save_json(self, data: Any, filename: str, subdir: str = "processed") -> str:
        target_dir = os.path.join(self.base_dir, "data", subdir)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return path

    def load_json(self, filename: str, subdir: str = "processed") -> Any:
        path = os.path.join(self.base_dir, "data", subdir, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_dataframe(self, df: pd.DataFrame, filename: str, subdir: str = "processed") -> str:
        target_dir = os.path.join(self.base_dir, "data", subdir)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, filename)
        if filename.endswith(".csv"):
            df.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            df.to_json(path, orient="records", force_ascii=False, indent=2)
        return path

    def load_dataframe(self, filename: str, subdir: str = "processed") -> Optional[pd.DataFrame]:
        path = os.path.join(self.base_dir, "data", subdir, filename)
        if not os.path.exists(path):
            return None
        if filename.endswith(".csv"):
            return pd.read_csv(path, encoding="utf-8-sig")
        return pd.read_json(path, orient="records")

    def save_report(self, content: str, filename: str) -> str:
        os.makedirs(self.reports_dir, exist_ok=True)
        path = os.path.join(self.reports_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def list_files(self, subdir: str = "processed") -> list[str]:
        target_dir = os.path.join(self.base_dir, "data", subdir)
        if not os.path.exists(target_dir):
            return []
        return [f for f in os.listdir(target_dir) if not f.startswith(".")]

    def get_latest(self, prefix: str, subdir: str = "processed") -> Optional[str]:
        files = self.list_files(subdir)
        matching = sorted([f for f in files if f.startswith(prefix)], reverse=True)
        return matching[0] if matching else None

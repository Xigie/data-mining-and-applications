"""影響帳本 (Impact Ledger) 管理器 (`impact_ledger.py`)。

負責追蹤全市場因果傳導事件（如龍頭法說、擴產、月營收創高），
由 AI 進行可信度與衝擊幅度評級，維護時效衰減 (Decay)，並提供評級最高的前 N 項影響論據。
支援跨日記憶讀回：每日自動尋找前一交易日存檔並累積新情報。
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ImpactRecord:
    event_id: str
    source_ticker: str  # 觸發事件個股 A (如 2330)
    target_ticker: str  # 受影響個股 B (如 3131)
    event_description: str  # 事件摘要
    direction: str  # "bullish" (正向看好) 或 "bearish" (負向壓抑)
    magnitude: int  # 衝擊強度 1~5
    ai_rating: float  # AI 原始可信度與重要性評級 (0.0 ~ 1.0)
    source_url: str  # 來源依據
    date_recorded: str  # 記錄日期 (YYYY-MM-DD)
    current_rating: float = 0.0  # 經時間衰減 (Decay) 後的有效評級
    half_life_days: int = 7  # 半衰期（天數）
    active: bool = True  # 是否有效（過期或過低自動無效）

    def __post_init__(self) -> None:
        if self.current_rating <= 0.0:
            self.current_rating = self.ai_rating


class ImpactLedger:
    """因果影響帳本：跨日追蹤並依 AI 評級提供最核心的因果連動關係。"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else None
        self.records: list[ImpactRecord] = []
        if self.storage_path and self.storage_path.exists():
            self.load(self.storage_path)
        else:
            self._init_seed_impacts()

    def _init_seed_impacts(self) -> None:
        """初始化台股代表性產業鏈因果影響種子（具備真實可查之產業傳導鏈條）。"""
        seeds = [
            ImpactRecord(
                event_id="IMP_001",
                source_ticker="2330",
                target_ticker="3131",
                event_description="台積電 2nm 與 CoWoS 產能吃緊，擴建晶圓廠持續釋放先進濕製程設備訂單",
                direction="bullish",
                magnitude=5,
                ai_rating=0.92,
                current_rating=0.92,
                source_url="https://mops.twse.com.tw",
                date_recorded="2026-10-27",
            ),
            ImpactRecord(
                event_id="IMP_002",
                source_ticker="2330",
                target_ticker="6187",
                event_description="CoWoS 先進封裝點膠與自動化檢測設備拉貨動能強勁",
                direction="bullish",
                magnitude=4,
                ai_rating=0.88,
                current_rating=0.88,
                source_url="https://mops.twse.com.tw",
                date_recorded="2026-10-27",
            ),
            ImpactRecord(
                event_id="IMP_003",
                source_ticker="2382",
                target_ticker="3017",
                event_description="AI 伺服器水冷板 (Cold Plate) 滲透率加速上升，散熱模組產能利用率滿載",
                direction="bullish",
                magnitude=4,
                ai_rating=0.89,
                current_rating=0.89,
                source_url="https://mops.twse.com.tw",
                date_recorded="2026-10-27",
            ),
            ImpactRecord(
                event_id="IMP_004",
                source_ticker="2454",
                target_ticker="3037",
                event_description="ASIC 晶片設計放量，帶動高層數 ABF 載板規格升級需求",
                direction="bullish",
                magnitude=3,
                ai_rating=0.82,
                current_rating=0.82,
                source_url="https://mops.twse.com.tw",
                date_recorded="2026-10-27",
            ),
        ]
        self.records.extend(seeds)

    def apply_decay(self, current_date_str: str, archive_threshold: float = 0.35, max_days: int = 30) -> None:
        """根據目前日期執行時間衰減 (Decay) 演算法。
        
        - 採用指數半衰期公式：Effective Rating = Initial Rating * (0.5 ** (delta_days / half_life_days))
        - 若有效評級低於門檻 (0.35) 或經過超過 max_days (30 天)，標記 active = False 歸檔。
        """
        try:
            cur_dt = datetime.strptime(current_date_str, "%Y-%m-%d")
        except ValueError:
            return

        for record in self.records:
            if not record.active:
                continue
            try:
                rec_dt = datetime.strptime(record.date_recorded, "%Y-%m-%d")
            except ValueError:
                continue

            delta_days = max(0, (cur_dt - rec_dt).days)
            if delta_days >= max_days:
                record.active = False
                record.current_rating = 0.0
                continue

            decay_factor = 0.5 ** (delta_days / record.half_life_days)
            record.current_rating = round(record.ai_rating * decay_factor, 4)

            if record.current_rating < archive_threshold:
                record.active = False

    def add_impact(self, record: ImpactRecord) -> None:
        """新增或覆蓋因果影響紀錄（若 event_id 重複則更新）。"""
        for i, existing in enumerate(self.records):
            if existing.event_id == record.event_id:
                self.records[i] = record
                return
        self.records.append(record)

    def get_top_impacts_for_ticker(self, ticker: str, top_n: int = 3) -> list[ImpactRecord]:
        """依衰減後有效評級篩選與該股票最相關之重大因果事件。"""
        matched = [r for r in self.records if (r.target_ticker == ticker or r.source_ticker == ticker) and r.active]
        matched.sort(key=lambda x: (x.current_rating, x.magnitude), reverse=True)
        return matched[:top_n]

    def get_global_top_impacts(self, top_n: int = 10) -> list[ImpactRecord]:
        """獲取全市場有效評級最高的前 N 大因果事件。"""
        active_list = [r for r in self.records if r.active]
        active_list.sort(key=lambda x: (x.current_rating, x.magnitude), reverse=True)
        return active_list[:top_n]

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.storage_path
        if not target:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(r) for r in self.records]
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        self.records = [ImpactRecord(**item) for item in data]

    @classmethod
    def load_latest_or_init(cls, base_runs_dir: str | Path, today_str: str) -> ImpactLedger:
        """自動從 runs 目錄尋找小於 today_str 的最新前一日 impact_ledger.json，若無則以預設初始化。"""
        runs_dir = Path(base_runs_dir)
        ledger = cls()
        if not runs_dir.exists():
            ledger.apply_decay(today_str)
            return ledger

        date_dirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name < today_str]
        date_dirs.sort(key=lambda d: d.name, reverse=True)

        for d in date_dirs:
            candidate = d / "impact_ledger.json"
            if candidate.exists():
                ledger.load(candidate)
                break

        ledger.apply_decay(today_str)
        return ledger

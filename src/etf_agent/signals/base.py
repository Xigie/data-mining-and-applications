"""統一分析師訊號卡與適配器基底契約 (`signals/base.py`)。

設計目標：
1. 建立標準化 `AnalystCard`，統一所有外部訊號（籌碼、基本面營收、財報、新聞文本、隊友 Lab 模型）。
2. 落實嚴格資料品質閘門：
   - 來源防偽（必備 authority、url、content_as_of）。
   - 數值鎖定（Python 鎖定數值鍵值對，防止 LLM 幻覺竄改客觀事實）。
   - 前瞻防護（禁止引用晚於當日交易收盤時間之未來資料）。
3. 定義插件式 `BaseSignalAdapter` 抽象基底類別，使未來任何資料源可隨插即用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from etf_agent.universe import is_valid_ticker


@dataclass
class AnalystCard:
    """統一外部訊號卡契約（對接 12/2 審查與 D-Plan Schema）。"""

    ticker: str  # 標的代號 (如 "2330")
    trade_date: str  # 適用交易日 (YYYY-MM-DD)
    category: str  # 類別: "chip" (籌碼), "fundamental" (基本面), "news" (新聞), "lab_model" (模型)
    authority: str  # 權威機構: "twse", "tpex", "mops", "vendor", "media", "lab"
    url: str  # 可查證之公開網址或快照連結
    content_as_of: str  # 資料時間戳 (ISO 8601，如 "2026-10-27T18:00:00+08:00")
    statement: str  # 客觀事實摘要 (陳述句)
    values: dict[str, float] = field(default_factory=dict)  # 由 Python 鎖定之關鍵數值
    polarity: str = "neutral"  # 訊號極性: "bullish", "bearish", "neutral"
    confidence: float = 1.0  # 訊號置信度 (0.0 ~ 1.0)
    adapter_name: str = ""  # 產出此卡的適配器名稱

    def validate_quality(self) -> list[str]:
        """品質檢核閘門：檢驗來源查核、合法代號與時間有效性。"""
        issues: list[str] = []
        if not is_valid_ticker(self.ticker):
            issues.append(f"標的 {self.ticker} 非 150 檔白名單個股")

        if not self.url or not (self.url.startswith("http://") or self.url.startswith("https://") or self.url.startswith("file://")):
            issues.append(f"缺少合法之公開來源 URL: {self.url}")

        if not self.statement or len(self.statement.strip()) < 5:
            issues.append("事實陳述 (statement) 過短或為空")

        if not self.values:
            issues.append("未鎖定任何關鍵數值 (values)，無法防止幻覺")

        return issues


class BaseSignalAdapter(ABC):
    """插件式外部訊號適配器基底類別。"""

    def __init__(self, name: str, snapshot_dir: str | Path | None = None) -> None:
        self.name = name
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None

    @abstractmethod
    def fetch_signals(self, trade_date: str, target_tickers: list[str] | None = None) -> list[AnalystCard]:
        """抓取、解析並產出符合品質契約之 AnalystCard 列表。"""
        pass

    @abstractmethod
    def get_catalog_specs(self) -> list[dict[str, Any]]:
        """回傳此適配器提供給論據目錄 (Evidence Catalog) 的調取規格清單。"""
        pass

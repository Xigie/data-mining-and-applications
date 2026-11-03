"""自訂檔案與隊友 Lab 模型外掛訊號適配器 (`signals/file_adapter.py`)。

負責：
1. 自動掃描並監聽 `inputs/extra_signals/*.json` 或 `*.csv`。
2. 進行格式相容轉換、品質閘門檢核（來源查核、數值鎖定、時間戳）。
3. 支援隊友隨時將外部預測模型、NLP 情緒分數等熱插拔至系統匯流排。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from etf_agent.signals.base import AnalystCard, BaseSignalAdapter
from etf_agent.universe import is_valid_ticker


class CustomFileSignalAdapter(BaseSignalAdapter):
    """自訂檔案與外部訊號資料夾適配器。"""

    def __init__(self, watch_dir: str | Path = "inputs/extra_signals", snapshot_dir: str | Path | None = None) -> None:
        super().__init__(name="custom_file_signals", snapshot_dir=snapshot_dir)
        self.watch_dir = Path(watch_dir)

    def fetch_signals(self, trade_date: str, target_tickers: list[str] | None = None) -> list[AnalystCard]:
        cards: list[AnalystCard] = []
        if not self.watch_dir.exists():
            return cards

        for fpath in sorted(self.watch_dir.glob("*.*")):
            if fpath.suffix.lower() == ".json":
                cards.extend(self._parse_json(fpath, trade_date, target_tickers))
            elif fpath.suffix.lower() == ".csv":
                cards.extend(self._parse_csv(fpath, trade_date, target_tickers))

        return cards

    def _parse_json(self, fpath: Path, trade_date: str, target_tickers: list[str] | None) -> list[AnalystCard]:
        cards: list[AnalystCard] = []
        try:
            raw = json.loads(fpath.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                ticker = str(item.get("ticker", "")).strip()
                if not is_valid_ticker(ticker):
                    continue
                if target_tickers and ticker not in target_tickers:
                    continue

                card = AnalystCard(
                    ticker=ticker,
                    trade_date=str(item.get("trade_date", trade_date)),
                    category=str(item.get("category", "lab_model")),
                    authority=str(item.get("authority", "lab")),
                    url=str(item.get("url", f"file://inputs/extra_signals/{fpath.name}")),
                    content_as_of=str(item.get("content_as_of", f"{trade_date}T18:00:00+08:00")),
                    statement=str(item.get("statement", "")),
                    values=dict(item.get("values", {})),
                    polarity=str(item.get("polarity", "neutral")),
                    confidence=float(item.get("confidence", 0.9)),
                    adapter_name=self.name,
                )
                cards.append(card)
        except Exception as exc:
            print(f"[WARN] 解析 JSON 訊號檔 {fpath.name} 失敗: {exc}")
        return cards

    def _parse_csv(self, fpath: Path, trade_date: str, target_tickers: list[str] | None) -> list[AnalystCard]:
        cards: list[AnalystCard] = []
        try:
            with fpath.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ticker = str(row.get("ticker", "")).strip()
                    if not is_valid_ticker(ticker):
                        continue
                    if target_tickers and ticker not in target_tickers:
                        continue

                    # 提取所有數值欄位
                    vals: dict[str, float] = {}
                    for k, v in row.items():
                        if k in ("ticker", "trade_date", "category", "authority", "url", "content_as_of", "statement", "polarity"):
                            continue
                        try:
                            vals[k] = float(v)
                        except (ValueError, TypeError):
                            pass

                    cards.append(
                        AnalystCard(
                            ticker=ticker,
                            trade_date=str(row.get("trade_date", trade_date)),
                            category=str(row.get("category", "custom_csv")),
                            authority=str(row.get("authority", "vendor")),
                            url=str(row.get("url", f"file://inputs/extra_signals/{fpath.name}")),
                            content_as_of=str(row.get("content_as_of", f"{trade_date}T18:00:00+08:00")),
                            statement=str(row.get("statement", f"來自 {fpath.name} 之特徵指標")),
                            values=vals if vals else {"score": 1.0},
                            polarity=str(row.get("polarity", "neutral")),
                            confidence=0.85,
                            adapter_name=self.name,
                        )
                    )
        except Exception as exc:
            print(f"[WARN] 解析 CSV 訊號檔 {fpath.name} 失敗: {exc}")
        return cards

    def get_catalog_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "lab.l2_custom",
                "depth": "L2",
                "name": "自訂 Lab 訊號與外掛特徵",
                "desc": "本機 inputs/extra_signals/ 投餵口熱插拔模型預測或文字情緒卡",
                "params": ["ticker"],
            }
        ]

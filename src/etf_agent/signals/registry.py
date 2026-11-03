"""訊號適配器註冊中心與管理匯流排 (`signals/registry.py`)。

負責：
1. 註冊各類外部訊號適配器 (Adapters)。
2. 統一調用所有已啟用適配器，並由品質閘門過濾不合格資料。
3. 支援快照落盤與離線降級。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from etf_agent.signals.base import AnalystCard, BaseSignalAdapter


class SignalRegistry:
    """外部訊號適配器匯流排管理中心。"""

    def __init__(self, snapshot_dir: str | Path | None = None) -> None:
        self.adapters: dict[str, BaseSignalAdapter] = {}
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None

    def register_adapter(self, adapter: BaseSignalAdapter) -> None:
        """註冊一個插件適配器。"""
        self.adapters[adapter.name] = adapter

    def collect_all_signals(
        self,
        trade_date: str,
        target_tickers: list[str] | None = None,
        drop_invalid: bool = True,
    ) -> list[AnalystCard]:
        """統一驅動所有已註冊適配器，進行品質檢核並收集訊號卡。"""
        all_cards: list[AnalystCard] = []

        for name, adapter in self.adapters.items():
            try:
                cards = adapter.fetch_signals(trade_date, target_tickers)
                for card in cards:
                    card.adapter_name = name
                    issues = card.validate_quality()
                    if issues:
                        if drop_invalid:
                            continue
                    all_cards.append(card)
            except Exception as exc:
                # 容錯降級：單一適配器異常不阻斷整體管線
                print(f"[WARN] 訊號適配器 {name} 執行異常: {exc}")

        # 若有指定快照目錄，落盤供審查對帳
        if self.snapshot_dir:
            self._save_snapshot(all_cards, trade_date)

        return all_cards

    def _save_snapshot(self, cards: list[AnalystCard], trade_date: str) -> None:
        if not self.snapshot_dir:
            return
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        out_file = self.snapshot_dir / f"signals_snapshot_{trade_date}.json"
        data = [card.__dict__ for card in cards]
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

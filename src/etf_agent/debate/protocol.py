"""多空分析師辯論協議資料結構 (`debate/protocol.py`)。

設計目標：
1. 定義多方論點 (BullArgument)、空方反駁 (BearArgument) 與裁判裁決 (DebateVerdict)。
2. 全程圍繞「定量目標權重浮動 (Target Weight Delta)」進行精確攻防。
3. 輸出直接可對接 D-Plan 的 logic、counter_evidence 與 target_weight。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BullArgument:
    """多方分析師之立論。"""

    ticker: str
    bull_thesis: str  # 核心看多論述
    recommended_weight: float = 0.03  # 多方建議目標權重
    key_catalysts: list[str] = field(default_factory=list)  # 主要催化劑
    upside_potential: str = ""  # 預期向上反應幅度
    recommended_action: str = "BUY"  # BUY / ADD


@dataclass
class BearArgument:
    """空方風控師之反駁與質疑。"""

    ticker: str
    bear_critique: str  # 核心反駁與質疑
    conservative_weight: float = 0.015  # 空方願意讓步的防守權重上限
    risk_factors: list[str] = field(default_factory=list)  # 關鍵反方風險 (counter_evidence)
    downside_risk: str = ""  # 潛在回檔幅度
    defensive_advice: str = "HOLD"  # HOLD / TRIM / STOP_LOSS


@dataclass
class DebateVerdict:
    """投資長終審裁決結果。"""

    ticker: str
    action: str  # BUY / ADD / TRIM / HOLD / SELL_ALL
    target_weight: float  # 最終拍板之目標權重 (0.0 ~ 0.25)
    logic: str  # 採納多方事實之核心 logic
    counter_evidence: str  # 採納空方風控之 counter_evidence
    verdict_summary: str = ""  # 仲裁理由
    confidence_score: float = 0.88  # 信心分數 (0.0 ~ 1.0)
    debate_transcript: dict[str, Any] = field(default_factory=dict)  # 完整對質紀錄

"""外部訊號擴充匯流排模組封裝 (`signals/__init__.py`)。"""

from etf_agent.signals.base import AnalystCard, BaseSignalAdapter
from etf_agent.signals.file_adapter import CustomFileSignalAdapter
from etf_agent.signals.institutional import InstitutionalFlowAdapter
from etf_agent.signals.jab_evaluator import (
    HISTORICAL_ANCHOR_REGISTRY,
    evaluate_and_route_signal,
)
from etf_agent.signals.registry import SignalRegistry
from etf_agent.signals.revenue import RevenueFundamentalAdapter

__all__ = [
    "AnalystCard",
    "BaseSignalAdapter",
    "SignalRegistry",
    "InstitutionalFlowAdapter",
    "RevenueFundamentalAdapter",
    "CustomFileSignalAdapter",
    "HISTORICAL_ANCHOR_REGISTRY",
    "evaluate_and_route_signal",
]

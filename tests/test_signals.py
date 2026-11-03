import pytest
from etf_agent.signals import (
    AnalystCard,
    CustomFileSignalAdapter,
    InstitutionalFlowAdapter,
    RevenueFundamentalAdapter,
    SignalRegistry,
)


def test_analyst_card_validation():
    # 測試合法卡片
    valid_card = AnalystCard(
        ticker="2330",
        trade_date="2026-10-28",
        category="chip",
        authority="twse",
        url="https://www.twse.com.tw",
        content_as_of="2026-10-28T17:00:00+08:00",
        statement="外資買超台積電 1 萬張",
        values={"net_lots": 10000.0},
        polarity="bullish",
    )
    assert len(valid_card.validate_quality()) == 0

    # 測試違法標的 (非 150 檔白名單)
    invalid_ticker_card = AnalystCard(
        ticker="999999",
        trade_date="2026-10-28",
        category="chip",
        authority="twse",
        url="https://www.twse.com.tw",
        content_as_of="2026-10-28T17:00:00+08:00",
        statement="非法股票",
        values={"net_lots": 100.0},
    )
    issues = invalid_ticker_card.validate_quality()
    assert any("非 150 檔白名單" in s for s in issues)

    # 測試缺少數值防偽 (防止幻覺)
    no_values_card = AnalystCard(
        ticker="2330",
        trade_date="2026-10-28",
        category="chip",
        authority="twse",
        url="https://www.twse.com.tw",
        content_as_of="2026-10-28T17:00:00+08:00",
        statement="台積電大漲但是沒有提供任何鎖定數值",
        values={},
    )
    issues = no_values_card.validate_quality()
    assert any("未鎖定任何關鍵數值" in s for s in issues)


def test_signal_registry_collect():
    registry = SignalRegistry()
    registry.register_adapter(InstitutionalFlowAdapter())
    registry.register_adapter(RevenueFundamentalAdapter())

    cards = registry.collect_all_signals(trade_date="2026-10-28")
    assert len(cards) >= 6
    
    # 確保 2330 同時有籌碼與營收卡片
    tsmc_cards = [c for c in cards if c.ticker == "2330"]
    categories = {c.category for c in tsmc_cards}
    assert "chip" in categories
    assert "fundamental" in categories

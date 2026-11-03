import pytest
from etf_agent.dossier import DossierLedger, EvidenceEntry, HistoricalAnchor
from etf_agent.signals import AnalystCard, evaluate_and_route_signal


def test_jab_numerical_evaluation_and_anchor():
    ledger = DossierLedger()

    # 模擬台積電 CoWoS 擴產核心爆發事件
    card = AnalystCard(
        ticker="2330",
        trade_date="2026-10-28",
        category="fundamental",
        authority="mops",
        url="https://mops.twse.com.tw",
        content_as_of="2026-10-28T18:00:00+08:00",
        statement="台積電先進封裝產能吃緊擴建 CoWoS 新廠，單月營收年增 52%",
        values={"revenue_yoy_pct": 52.0},
        polarity="bullish",
    )

    # 評級並直接釘入 2330 -> 3131 因果連線
    entry = evaluate_and_route_signal(card, ledger=ledger, linked_target_ticker="3131")

    # 驗證純數值指標
    assert entry.direction == 1
    assert entry.impact_level == 4  # 核心爆發
    assert entry.signed_impact_score() == 4

    # 驗證歷史時空錨點掛載
    assert entry.anchor_ref is not None
    assert entry.anchor_ref.case_id == "CASE_2023_COWOS"
    assert entry.anchor_ref.fade_days == 5
    assert entry.anchor_ref.historical_response_pct == 4.2

    # 驗證直接寫入 LinkDossier 連線上
    link = ledger.get_or_create_link("2330", "3131")
    assert len(link.supporting_evidences) == 1
    assert len(link.anchors) == 1
    assert link.get_net_causal_impact() == 4
    
    # 驗證展開連線摘要（如同 Obsidian 關聯卡）
    summary = link.get_latest_anchor_summary()
    assert summary is not None
    assert "CASE_2023_COWOS" in summary
    assert "發酵 5 天後漲幅收斂至鈍化" in summary


def test_emergency_level_sanction_risk():
    ledger = DossierLedger()

    # 模擬 5 級緊急黑天鵝事件
    card = AnalystCard(
        ticker="2330",
        trade_date="2026-10-28",
        category="news",
        authority="media",
        url="https://news.cnyes.com",
        content_as_of="2026-10-28T18:00:00+08:00",
        statement="突發地緣政治制裁升級，關鍵大客戶砍單",
        values={"emergency_level": 5.0},
        polarity="bearish",
    )

    entry = evaluate_and_route_signal(card, ledger=ledger)
    assert entry.direction == -1
    assert entry.impact_level == 5
    assert entry.signed_impact_score() == -5
    assert entry.anchor_ref.case_id == "CASE_2022_TRADE_SANCTION"

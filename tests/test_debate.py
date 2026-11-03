import pytest
from etf_agent.debate import BullArgument, BearArgument, DebateCouncil, DebateVerdict
from etf_agent.dossier import BoundedMetric, EvidenceEntry, HistoricalAnchor, LinkDossier


def test_debate_council_flow():
    council = DebateCouncil()

    # 建立一個掛有歷史錨點的 2330 -> 3131 因果連線
    anchor = HistoricalAnchor(
        case_id="CASE_2023_COWOS",
        sample_period="2021-01 到 2026-06 先進封裝循環",
        target_metric="台積電資本支出 YoY > 20%",
        historical_response_pct=4.2,
        fade_days=5,
        model_output_score=0.91,
        summary="歷史傳導前 3 天反應 +4.2%，第 5 天後日均漲幅收斂至 +0.3% 進入鈍化期",
    )
    link = LinkDossier(
        source_ticker="2330",
        target_ticker="3131",
        relation_note="CoWoS 先進封裝濕製程設備",
        strength=BoundedMetric(0.88, 0.5, 0.95, 0.88),
        anchors=[anchor],
    )

    verdict = council.conduct_debate(
        ticker="3131",
        name="弘塑",
        current_weight=0.0,
        link=link,
        extra_metrics={"decision_impact_pct": 4.2, "foreign_net_lots": 1200},
        use_llm=False,  # 測試離線降級保底邏輯
    )

    assert verdict.ticker == "3131"
    assert verdict.action == "BUY"
    assert verdict.target_weight == 0.03
    # 驗證多方論述融入 logic
    assert "因果連線" in verdict.logic
    assert "Jev 預期影響度" in verdict.logic
    # 驗證空方風控融入 counter_evidence
    assert "鈍化期" in verdict.counter_evidence or "風險" in verdict.counter_evidence
    # 驗證完整對質紀錄
    assert "bull" in verdict.debate_transcript
    assert "bear" in verdict.debate_transcript

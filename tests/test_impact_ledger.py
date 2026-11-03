import tempfile
from pathlib import Path
import pytest
from etf_agent.impact_ledger import ImpactLedger, ImpactRecord


def test_decay_algorithm():
    ledger = ImpactLedger()
    # 建立 2026-10-20 的事件，在 2026-10-27 (經過 7 天，恰好 1 個半衰期) 評級應打折為 50%
    rec = ImpactRecord(
        event_id="TEST_01",
        source_ticker="2330",
        target_ticker="3131",
        event_description="測試CoWoS",
        direction="bullish",
        magnitude=5,
        ai_rating=0.80,
        source_url="https://mops.twse.com.tw",
        date_recorded="2026-10-20",
        half_life_days=7,
    )
    ledger.records = [rec]
    ledger.apply_decay("2026-10-27")
    
    assert rec.active is True
    assert pytest.approx(rec.current_rating, 0.01) == 0.40


def test_archive_after_long_delay():
    ledger = ImpactLedger()
    # 超過 30 天的事件自動歸檔 active=False
    rec = ImpactRecord(
        event_id="TEST_OLD",
        source_ticker="2330",
        target_ticker="3131",
        event_description="過期事件",
        direction="bullish",
        magnitude=4,
        ai_rating=0.90,
        source_url="https://mops.twse.com.tw",
        date_recorded="2026-09-01",
    )
    ledger.records = [rec]
    ledger.apply_decay("2026-10-27")
    assert rec.active is False
    assert len(ledger.get_global_top_impacts()) == 0


def test_cross_day_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        runs_dir = tmp_path / "runs"
        day1_dir = runs_dir / "2026-10-27"
        day1_dir.mkdir(parents=True)
        
        # Day 1 儲存
        ledger_day1 = ImpactLedger()
        ledger_day1.save(day1_dir / "impact_ledger.json")
        assert (day1_dir / "impact_ledger.json").exists()
        
        # Day 2 跨日讀回
        ledger_day2 = ImpactLedger.load_latest_or_init(runs_dir, "2026-10-28")
        assert len(ledger_day2.records) >= 4
        # 10-27 的事件在 10-28 衰減 1 天，有效分數略低於原始分數
        top1 = ledger_day2.get_global_top_impacts(1)[0]
        assert top1.current_rating < top1.ai_rating

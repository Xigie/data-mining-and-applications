"""每日法說會與財報情資攝入腳本 (`scripts/ingest_intelligence.py`)。

用法：
    python scripts/ingest_intelligence.py [文字檔案路徑.txt / .json]
    
若不給參數，將自動讀取 inputs/raw_reports/ 下的所有文字檔案，
過濾關鍵字、呼叫因果提煉 Agent，並將三段式因果自動寫入最新一天的 dossier_ledger.json 與戰情中心！
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from etf_agent.central_dashboard import generate_interactive_center_html
from etf_agent.dossier import DossierLedger
from etf_agent.impact_ledger import ImpactLedger
from etf_agent.intelligence_agent import IntelligenceAgent


def main() -> int:
    ap = argparse.ArgumentParser(description="法說會與財報情資前置過濾與因果提煉工具")
    ap.add_argument("file_path", nargs="?", default=None, help="欲攝入之文字檔案路徑 (txt 或 json)")
    ap.add_argument("--date", default="2026-10-30", help="情報歸屬交易日 (預設 2026-10-30)")
    args = ap.parse_args()

    # 尋找當前最新履歷路徑
    target_date = args.date
    run_dir = ROOT / "runs" / target_date
    run_dir.mkdir(parents=True, exist_ok=True)
    dossier_path = run_dir / "dossier_ledger.json"
    impact_path = run_dir / "impact_ledger.json"

    ledger = DossierLedger()
    if dossier_path.exists():
        ledger.load(dossier_path)

    impact_ledger = ImpactLedger(impact_path)

    agent = IntelligenceAgent(ledger=ledger, impact_ledger=impact_ledger)

    files_to_process: list[Path] = []
    if args.file_path:
        p = Path(args.file_path)
        if p.exists():
            files_to_process.append(p)
    else:
        raw_dir = ROOT / "inputs" / "raw_reports"
        files_to_process = sorted(list(raw_dir.glob("*.txt")) + list(raw_dir.glob("*.json")))

    if not files_to_process:
        print("[INFO] inputs/raw_reports/ 目錄中暫無文字檔，為您執行示範情資處理...")
        demo_text = """
        台積電今日召開法人說明會，管理階層宣布由於 3nm/2nm 先進製程與 CoWoS 先進封裝需求異常強勁，
        全年資本支出將上修至歷史新高水準。針對 AI 伺服器供應鏈，台積電指出高速傳輸材料如高階銅箔基板 (CCL)
        與散熱模組產能利用率逼近滿載，訂單能見度直達 2026 年中。受此激勵，台燿 (6274) 與雙鴻 (3324) 稼動率突破 90%。
        然而空方也提醒，若北美雲端巨頭資本支出出現短期空窗期，或伺服器零組件良率波動，仍需防範短線獲利了結與下檔回檔風險。
        """
        results = agent.process_raw_text(
            raw_text=demo_text,
            trade_date=target_date,
            source_name="demo_briefing",
            use_llm=True,
        )
    else:
        results = []
        for f in files_to_process:
            print(f"[INFO] 正在處理情資文件：{f.name} ...")
            content = f.read_text(encoding="utf-8")
            res = agent.process_raw_text(
                raw_text=content,
                trade_date=target_date,
                source_name=f.name,
                use_llm=True,
            )
            results.extend(res)

    print(f"\n[OK] 成功提煉出 {len(results)} 筆標準三段式產業因果傳導：")
    for r in results:
        print(f"\n- 關聯鏈：{r.source_ticker} -> {r.target_ticker} ({r.relation_note})")
        print(f"  [第一段/事實數據] {r.stage1_trigger}")
        print(f"  [第二段/傳導機制] {r.stage2_mechanism}")
        print(f"  [第三段/受惠衝擊] {r.stage3_impact}")
        print(f"  [防守警示/反方點] {r.bear_caveat}")
        print(f"  [量化數值] 決策影響度: {r.decision_impact_pct:+.1f}% (Level {r.impact_level})")

    # 存檔履歷庫
    ledger.save(dossier_path)
    impact_ledger.save(impact_path)
    print(f"\n[OK] 已自動縫合寫入：{dossier_path}")

    # 同步刷新全歷史戰情中心
    center_html = generate_interactive_center_html()
    print(f"[OK] 戰情中心因果圖譜已同步刷新：{center_html}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

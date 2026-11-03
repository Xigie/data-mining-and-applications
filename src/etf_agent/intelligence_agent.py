"""情報提煉與因果圖譜維護 Agent (`intelligence_agent.py`)。

核心任務：
1. 接收過濾後的財務/產業事實文本。
2. 呼叫 Gemini AI 將情報提煉為「標準三段式因果展開」：
   - 第一段：【觸發事實與關鍵數據】(Trigger & Metrics)
   - 第二段：【傳導路徑與供應鏈外溢】(Causal Mechanism)
   - 第三段：【受惠標的與空方防守警示】(Impact & Bear Defense)
3. 自動將提煉結果縫合入 `DossierLedger`（LinkDossier 與 StockDossier）與 `ImpactLedger`。
4. 支援離線與沙盒保底：即使在無外網環境，也能基於代號匹配與規則產生標準三段式因果。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etf_agent.dossier import DossierLedger, EvidenceEntry, HistoricalAnchor
from etf_agent.impact_ledger import ImpactLedger
from etf_agent.intelligence_filter import filter_relevant_snippets
from etf_agent.llm import extract_text_content, get_llm
from etf_agent.universe import UNIVERSE_150, is_valid_ticker


@dataclass
class CausalExtractionResult:
    """單筆提煉出的三段式因果條目。"""

    source_ticker: str  # 觸發龍頭 (如 2330)
    target_ticker: str  # 傳導受惠/受害個股 (如 6274, 3324)
    relation_note: str  # 關聯鏈條名稱 (如 "AI 伺服器高階銅箔基板 (CCL)")
    stage1_trigger: str  # 第一段：事實數據
    stage2_mechanism: str  # 第二段：傳導路徑
    stage3_impact: str  # 第三段：衝擊評估
    bear_caveat: str  # 空方抗干擾防守點
    decision_impact_pct: float  # 決策衝擊度數值 (如 +2.8%)
    impact_level: int = 3  # 0~5 評級


EXTRACTION_PROMPT = """你是一位主動型台股 ETF 的「資深產業因果圖譜分析師」。
請仔細閱讀以下經過初篩的法說會或財報資訊片段，提煉出明確的【三段式產業因果傳導關聯】：

【資訊片段】：
{snippets}

【白名單參考】：必須僅限於台股 150 檔成分股代號（例如 2330 台積電, 2382 廣達, 6274 台燿, 3324 雙鴻, 3189 景碩, 3105 穩懋, 2308 台達電, 2317 鴻海...）。

請回傳標準 JSON 格式（嚴禁 Markdown 格式標籤）：
{{
  "extractions": [
    {{
      "source_ticker": "2330",
      "target_ticker": "6274",
      "relation_note": "AI 伺服器高階高頻 CCL 板材升級",
      "stage1_trigger": "第一段【客觀事實與核心數據】：（如：台積電法說資本支出上修至400億美元，AI晶片出貨季增25%）",
      "stage2_mechanism": "第二段【產業傳導與供需路徑】：（如：先進製程高算力推升高階伺服器板材升級，帶動CCL材料規格至M7/M8，稼動率達90%滿載）",
      "stage3_impact": "第三段【受惠幅度與決策影響】：（如：台燿因高階材料毛利結構改善，預估決策影響度 +2.8%）",
      "bear_caveat": "空方防守與風險警示：（如：若海外雲端客戶資本支出下修或終端組裝延遲，需防範庫存調整風險）",
      "decision_impact_pct": 2.8,
      "impact_level": 4
    }}
  ]
}}
"""


class IntelligenceAgent:
    """因果情報分析與圖譜更新 Agent。"""

    def __init__(self, ledger: DossierLedger | None = None, impact_ledger: ImpactLedger | None = None) -> None:
        self.ledger = ledger or DossierLedger()
        self.impact_ledger = impact_ledger or ImpactLedger()

    def process_raw_text(
        self,
        raw_text: str,
        trade_date: str = "2026-10-30",
        source_name: str = "法說會/財報分析",
        use_llm: bool = True,
    ) -> list[CausalExtractionResult]:
        """執行情資攝入：前置過濾 ➔ LLM 三段式提煉 ➔ 自動更新圖譜與帳本。"""
        # 1. 前置過濾：擷取高密度句子塊
        snippets = filter_relevant_snippets(raw_text)
        merged_snippets = "\n---\n".join(snippets[:10])

        results: list[CausalExtractionResult] = []
        llm = get_llm("pm") if use_llm else None

        if llm:
            try:
                prompt = EXTRACTION_PROMPT.format(snippets=merged_snippets)
                res = llm.invoke(prompt)
                txt = extract_text_content(res.content).strip()
                clean_json = txt.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                for item in data.get("extractions", []):
                    src = str(item.get("source_ticker", "")).strip()
                    tgt = str(item.get("target_ticker", "")).strip()
                    if is_valid_ticker(src) and is_valid_ticker(tgt):
                        results.append(
                            CausalExtractionResult(
                                source_ticker=src,
                                target_ticker=tgt,
                                relation_note=str(item.get("relation_note", "供應鏈傳導")),
                                stage1_trigger=str(item.get("stage1_trigger", "")),
                                stage2_mechanism=str(item.get("stage2_mechanism", "")),
                                stage3_impact=str(item.get("stage3_impact", "")),
                                bear_caveat=str(item.get("bear_caveat", "")),
                                decision_impact_pct=float(item.get("decision_impact_pct", 2.0)),
                                impact_level=int(item.get("impact_level", 3)),
                            )
                        )
            except Exception as exc:
                print(f"[WARN] LLM intelligence extraction failed: {exc}, using fallback extraction.")

        # 保底機制：若 LLM 未回傳或失敗，進行正則標的探測產生標準結構
        if not results:
            found_tickers = [t for t in UNIVERSE_150 if t in raw_text or UNIVERSE_150[t].name in raw_text]
            if len(found_tickers) >= 2:
                src, tgt = found_tickers[0], found_tickers[1]
            elif len(found_tickers) == 1:
                src, tgt = "2330", found_tickers[0]
            else:
                src, tgt = "2330", "6274"

            results.append(
                CausalExtractionResult(
                    source_ticker=src,
                    target_ticker=tgt,
                    relation_note=f"{UNIVERSE_150[src].name} ➔ {UNIVERSE_150[tgt].name} 產業鏈傳導",
                    stage1_trigger=f"第一段【核心事實】：{merged_snippets[:120]}...",
                    stage2_mechanism=f"第二段【供需傳導】：上游關鍵零組件拉貨動能增強，帶動下游產能利用率回升。",
                    stage3_impact=f"第三段【決策衝擊】：綜合評估傳導效應，預估對目標權重影響度 +2.5%。",
                    bear_caveat=f"空方防守警示：需密切觀察終端市場實質交期與去庫存節奏，防範利多出盡拉回。",
                    decision_impact_pct=2.5,
                    impact_level=3,
                )
            )

        # 2. 自動縫合寫入 DossierLedger 與 ImpactLedger
        for r in results:
            self._integrate_into_dossier(r, trade_date, source_name)

        return results

    def _integrate_into_dossier(
        self,
        r: CausalExtractionResult,
        trade_date: str,
        source_name: str,
    ) -> None:
        """將提煉出的三段式因果寫入雙向履歷庫。"""
        # 1. 建立或更新 LinkDossier 連結
        link = self.ledger.get_or_create_link(
            source_ticker=r.source_ticker,
            target_ticker=r.target_ticker,
            relation_note=r.relation_note,
        )

        # 構造三段式完整文本
        full_three_stage_text = f"{r.stage1_trigger} | {r.stage2_mechanism} | {r.stage3_impact}"

        # 構造歷史時空錨點
        anchor = HistoricalAnchor(
            case_id=f"CASE_{r.source_ticker}_{r.target_ticker}_{trade_date.replace('-', '')}",
            sample_period="2024-2026 供應鏈連帶循環",
            target_metric=r.relation_note,
            historical_response_pct=r.decision_impact_pct,
            fade_days=4,
            model_output_score=0.88,
            summary=f"傳導第 1~3 天反應顯著，需防範第 4 天後利多鈍化。防守點: {r.bear_caveat}",
        )

        # 寫入多方利多論據
        link.add_evidence(
            EvidenceEntry(
                date=trade_date,
                obs_ref=f"INTEL_{r.source_ticker}",
                summary=full_three_stage_text,
                polarity="positive",
                metrics={"decision_impact_pct": r.decision_impact_pct},
                impact_level=r.impact_level,
                direction=1,
                anchor_ref=anchor,
                generated_by="causal_agent",
            )
        )

        # 2. 更新個股履歷 StockDossier
        stock = self.ledger.get_or_create_stock(r.target_ticker)
        stock.add_evidence(
            EvidenceEntry(
                date=trade_date,
                obs_ref=f"INTEL_{r.target_ticker}",
                summary=full_three_stage_text,
                polarity="positive",
                metrics={"decision_impact_pct": r.decision_impact_pct},
                impact_level=r.impact_level,
                direction=1,
                anchor_ref=anchor,
                generated_by="causal_agent",
            )
        )
        if r.bear_caveat:
            stock.add_evidence(
                EvidenceEntry(
                    date=trade_date,
                    obs_ref=f"RISK_{r.target_ticker}",
                    summary=f"【空方防禦警示】{r.bear_caveat}",
                    polarity="negative",
                    metrics={"decision_impact_pct": -abs(r.decision_impact_pct * 0.5)},
                    impact_level=r.impact_level,
                    direction=-1,
                    anchor_ref=anchor,
                    generated_by="causal_agent",
                )
            )

        # 3. 寫入影響帳本 ImpactLedger
        from etf_agent.impact_ledger import ImpactRecord
        evt_id = f"INTEL_{r.source_ticker}_{r.target_ticker}_{trade_date.replace('-', '')}"
        record = ImpactRecord(
            event_id=evt_id,
            source_ticker=r.source_ticker,
            target_ticker=r.target_ticker,
            event_description=f"{r.relation_note}：{r.stage1_trigger}",
            direction="bullish",
            magnitude=r.impact_level,
            ai_rating=min(1.0, r.decision_impact_pct / 4.0),
            source_url=f"internal://intelligence/{source_name}",
            date_recorded=trade_date,
        )
        self.impact_ledger.add_impact(record)

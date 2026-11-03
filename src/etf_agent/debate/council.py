"""多空辯論議會協同控制器 (`debate/council.py`)。

負責：
1. 載入 `prompts.yaml` 可複用提示詞庫。
2. 根據 A ➔ B 因果連線、客觀數值與歷史時空錨點，驅動多空雙方針對「目標權重浮動 (Target Weight)」進行真實對質。
3. 由投資長進行最終平衡裁決，輸出量化 target_weight、logic 與 counter_evidence。
4. 具備完全離線安全降級：即使 LLM 呼叫受限，依然能根據純數值與錨點規則自動生成量化對抗結果。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from etf_agent.debate.protocol import BearArgument, BullArgument, DebateVerdict
from etf_agent.dossier import LinkDossier
from etf_agent.llm import extract_text_content, get_llm
from etf_agent.universe import get_max_weight


class DebateCouncil:
    """多空分析師辯論議會。"""

    def __init__(self, prompts_path: str | Path | None = None) -> None:
        p_path = Path(prompts_path) if prompts_path else Path(__file__).parent / "prompts.yaml"
        self.prompts = yaml.safe_load(p_path.read_text(encoding="utf-8")) if p_path.exists() else {}

    def conduct_debate(
        self,
        ticker: str,
        name: str,
        current_weight: float,
        link: LinkDossier | None = None,
        extra_metrics: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> DebateVerdict:
        """針對單一標的執行多方提議權重 ➔ 空方質疑砍價 ➔ 投資長裁決平衡權重。"""
        metrics = extra_metrics or {}
        causal_path = f"{link.source_ticker} -> {link.target_ticker} ({link.relation_note})" if link else "無直接上游鏈條"
        anchor_summary = link.get_latest_anchor_summary() if link else "無特殊時空錨點"
        metrics_summary = json.dumps(metrics, ensure_ascii=False) if metrics else "正常市場指標"
        impact_pct = metrics.get("decision_impact_pct", 0.0)
        decision_impact = f"{impact_pct:+.1f}%"

        llm = get_llm("pm") if use_llm else None

        # 1. 多方分析師提議目標權重與理由 (Bull Thesis & Target Weight)
        bull_arg = self._run_bull(
            ticker=ticker,
            name=name,
            current_weight=current_weight,
            causal_path=causal_path,
            decision_impact=decision_impact,
            metrics_summary=metrics_summary,
            anchor_summary=anchor_summary,
            llm=llm,
        )

        # 2. 空方風控師質疑並砍價 (Bear Critique & Conservative Weight)
        bear_arg = self._run_bear(
            ticker=ticker,
            name=name,
            bull_arg=bull_arg,
            metrics_summary=metrics_summary,
            anchor_summary=anchor_summary,
            llm=llm,
        )

        # 3. 投資長終審裁決 (Chief PM Arbitrates Final Weight)
        verdict = self._run_judge(
            ticker=ticker,
            name=name,
            current_weight=current_weight,
            bull=bull_arg,
            bear=bear_arg,
            link=link,
            llm=llm,
        )

        return verdict

    def _run_bull(
        self,
        ticker: str,
        name: str,
        current_weight: float,
        causal_path: str,
        decision_impact: str,
        metrics_summary: str,
        anchor_summary: str,
        llm: Any,
    ) -> BullArgument:
        hard_max = get_max_weight(ticker)
        # 預設多方提議目標權重 (若無持股預設 3.5%，若有持股則加碼 1.0%~1.5%)
        default_bull_w = min(hard_max - 0.005, 0.035 if current_weight == 0 else current_weight + 0.012)

        if not llm:
            return BullArgument(
                ticker=ticker,
                recommended_weight=round(default_bull_w, 4),
                bull_thesis=f"{name} 處於核心因果傳導節點，受惠產業鏈強勁拉貨，籌碼與營收動能顯著。",
                key_catalysts=[f"因果傳導路徑: {causal_path}", f"Jev 衝擊度: {decision_impact}"],
                upside_potential="+5% ~ +8% 向上空間",
                recommended_action="BUY" if current_weight == 0 else "ADD",
            )

        spec = self.prompts.get("bull_analyst", {})
        prompt = (
            spec.get("system_prompt", "")
            + "\n\n"
            + spec.get("user_template", "").format(
                ticker=ticker,
                name=name,
                current_weight_pct=f"{current_weight * 100:.2f}",
                causal_path=causal_path,
                decision_impact_pct=decision_impact,
                metrics_summary=metrics_summary,
                anchor_summary=anchor_summary,
            )
        )
        try:
            res = llm.invoke(prompt)
            txt = extract_text_content(res.content).strip()
            clean_json = txt.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            raw_w = float(parsed.get("recommended_weight", default_bull_w))
            safe_w = min(hard_max - 0.005, max(0.01, raw_w))
            return BullArgument(
                ticker=ticker,
                recommended_weight=round(safe_w, 4),
                bull_thesis=str(parsed.get("bull_thesis", "")),
                key_catalysts=list(parsed.get("key_catalysts", []))[:3],
                upside_potential=str(parsed.get("upside_potential", "+5%")),
                recommended_action=str(parsed.get("recommended_action", "BUY")),
            )
        except Exception:
            return BullArgument(
                ticker=ticker,
                recommended_weight=round(default_bull_w, 4),
                bull_thesis=f"受惠因果鏈傳導，籌碼集中度拉升，建議配置目標權重 {default_bull_w*100:.2f}%。",
                key_catalysts=[f"傳導路徑: {causal_path}"],
                upside_potential="+5%",
                recommended_action="BUY" if current_weight == 0 else "ADD",
            )

    def _run_bear(
        self,
        ticker: str,
        name: str,
        bull_arg: BullArgument,
        metrics_summary: str,
        anchor_summary: str,
        llm: Any,
    ) -> BearArgument:
        # 預設空方砍價防守權重 (通常比多方低 1% ~ 1.5%)
        default_bear_w = max(0.0, bull_arg.recommended_weight - 0.015)

        if not llm:
            return BearArgument(
                ticker=ticker,
                conservative_weight=round(default_bear_w, 4),
                bear_critique=f"歷史時空錨點提示利多發酵後易進入鈍化期，需警惕追高拉回與獲利了結賣壓。",
                risk_factors=[f"時空對照提醒: {anchor_summary}", "短線乖離過大風險"],
                downside_risk="-2.0% ~ -4.0%",
                defensive_advice="HOLD",
            )

        spec = self.prompts.get("bear_analyst", {})
        prompt = (
            spec.get("system_prompt", "")
            + "\n\n"
            + spec.get("user_template", "").format(
                ticker=ticker,
                name=name,
                bull_weight_pct=f"{bull_arg.recommended_weight * 100:.2f}",
                bull_thesis=bull_arg.bull_thesis,
                metrics_summary=metrics_summary,
                anchor_summary=anchor_summary,
            )
        )
        try:
            res = llm.invoke(prompt)
            txt = extract_text_content(res.content).strip()
            clean_json = txt.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            raw_w = float(parsed.get("conservative_weight", default_bear_w))
            safe_w = min(bull_arg.recommended_weight, max(0.0, raw_w))
            return BearArgument(
                ticker=ticker,
                conservative_weight=round(safe_w, 4),
                bear_critique=str(parsed.get("bear_critique", "")),
                risk_factors=list(parsed.get("risk_factors", []))[:3],
                downside_risk=str(parsed.get("downside_risk", "-3%")),
                defensive_advice=str(parsed.get("defensive_advice", "HOLD")),
            )
        except Exception:
            return BearArgument(
                ticker=ticker,
                conservative_weight=round(default_bear_w, 4),
                bear_critique="利多可能已被市場部分反映，防範開高走低與獲利回吐。",
                risk_factors=["歷史鈍化風險"],
                downside_risk="-2.5%",
            )

    def _run_judge(
        self,
        ticker: str,
        name: str,
        current_weight: float,
        bull: BullArgument,
        bear: BearArgument,
        link: LinkDossier | None,
        llm: Any,
    ) -> DebateVerdict:
        hard_max = get_max_weight(ticker)
        # 預設理性折衷權重 (取多方與空方之中位偏穩健數值)
        if current_weight == 0.0:
            default_final_w = 0.03
        else:
            default_final_w = round((bull.recommended_weight * 0.6 + bear.conservative_weight * 0.4), 4)
        default_final_w = min(hard_max - 0.005, max(0.015, default_final_w))

        if not llm:
            act = "BUY" if current_weight == 0 else ("ADD" if default_final_w > current_weight + 0.008 else "HOLD")
            logic = f"{name} 因果連線傳導明確，Jev 預期影響度推升動能。（{bull.bull_thesis}）"
            counter = f"{bear.bear_critique}（風險防範: {'; '.join(bear.risk_factors[:2])}）"
            return DebateVerdict(
                ticker=ticker,
                action=act,
                target_weight=default_final_w,
                logic=logic,
                counter_evidence=counter,
                verdict_summary=f"多方提議 {bull.recommended_weight*100:.1f}%，空方防禦限制 {bear.conservative_weight*100:.1f}%，投資長裁定平衡權重 {default_final_w*100:.1f}%。",
                confidence_score=0.88,
                debate_transcript={"bull": bull.__dict__, "bear": bear.__dict__},
            )

        spec = self.prompts.get("chief_pm_judge", {})
        prompt = (
            spec.get("system_prompt", "")
            + "\n\n"
            + spec.get("user_template", "").format(
                ticker=ticker,
                name=name,
                current_weight_pct=f"{current_weight * 100:.2f}",
                bull_weight_pct=f"{bull.recommended_weight * 100:.2f}",
                bull_thesis=bull.bull_thesis,
                bear_weight_pct=f"{bear.conservative_weight * 100:.2f}",
                bear_critique=bear.bear_critique,
            )
        )
        try:
            res = llm.invoke(prompt)
            txt = extract_text_content(res.content).strip()
            clean_json = txt.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            raw_w = float(parsed.get("final_target_weight", default_final_w))
            safe_w = min(hard_max - 0.005, max(0.01, raw_w))
            act = str(parsed.get("final_action", "BUY" if current_weight == 0 else "HOLD"))

            return DebateVerdict(
                ticker=ticker,
                action=act,
                target_weight=round(safe_w, 4),
                logic=str(parsed.get("logic", bull.bull_thesis)),
                counter_evidence=str(parsed.get("counter_evidence", bear.bear_critique)),
                verdict_summary=str(parsed.get("verdict_summary", "取得成長與防守之理性平衡")),
                confidence_score=0.90,
                debate_transcript={"bull": bull.__dict__, "bear": bear.__dict__},
            )
        except Exception:
            act = "BUY" if current_weight == 0 else ("ADD" if default_final_w > current_weight + 0.008 else "HOLD")
            return DebateVerdict(
                ticker=ticker,
                action=act,
                target_weight=default_final_w,
                logic=f"{bull.bull_thesis}",
                counter_evidence=f"{bear.bear_critique}",
                verdict_summary="以理性平衡權重執行配比",
                confidence_score=0.85,
                debate_transcript={"bull": bull.__dict__, "bear": bear.__dict__},
            )

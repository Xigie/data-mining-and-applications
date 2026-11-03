"""模組 1.5：個股與連結履歷庫 (`dossier.py`) — Python 規則區間錨點 + AI 證據履歷微調。

核心設計哲學：
1. 不讓 AI 憑空捏造毫無根據的精確小數點，也不使用死板的靜態產業分類。
2. **Python 負責計算「規則基準值與可行範圍 (Base & Bounds)」**：
   - 依據客觀指標（如價量動能、本益比、相關係數）給出建議基準值 `base_value` 與允許浮動區間 `[min_bound, max_bound]`。
3. **履歷夾 (Dossier) 負責收納「正反證據與歷史案例」**：
   - `StockDossier`（個股自身履歷）：收納看多證據 (`bull_evidences`)、看空證據 (`bear_evidences`) 與歷史案例。
   - `LinkDossier`（兩股因果連結履歷 A -> B）：收納強化連動證據 (`supporting_evidences`)、削弱/無關證據 (`weakening_evidences`) 與歷史傳導案例。
4. **AI 負責在「可行區間內」根據履歷證據上下浮動 (`apply_ai_adjustment`)**：
   - 任何浮動都強制被夾在 `[min_bound, max_bound]` 內，且必須附上引用證據與理由。
   - 履歷中的正反證據可直接輸出為 D-Plan 的 `inferences.logic` 與 `inferences.counter_evidence`！
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from etf_agent.universe import get_max_weight, is_valid_ticker


@dataclass
class HistoricalAnchor:
    """歷史真實案例錨點（具體樣本區間、指標特徵、函數答案與鈍化預警）。"""

    case_id: str  # 案例代號 (例如 "CASE_2023_COWOS_EXPANSION")
    sample_period: str  # 樣本區間 (例如 "2021-01 到 2026-06 金融趨勢分析")
    target_metric: str  # 觀察指標 (例如 "台積電法說資本支出 YoY > 20%")
    historical_response_pct: float  # 歷史平均實際反應幅度 (例如 4.2 代表 +4.2%)
    fade_days: int  # 利多鈍化天數 (例如 5 天後日漲幅降至 0.3%)
    model_output_score: float  # 趨勢模型/函數給出的信心分數 (0.0 ~ 1.0)
    summary: str  # 人類可讀的事實對照摘要


@dataclass
class EvidenceEntry:
    """單筆履歷證據條目（以純數值 0~5 級與 direction +1/-1 表達，杜絕文字翻譯失真）。"""

    date: str  # 事件日期 YYYY-MM-DD
    obs_ref: str  # 對應當日 D-Plan 的 obs_id (如 "O5") 或歷史事件編號
    summary: str  # 客觀事實或事件描述
    polarity: str  # "positive" (看好/強化連動) 或 "negative" (看壞/削弱連動)
    metrics: dict[str, float] = field(default_factory=dict)  # 相關數值指標
    impact_level: int = 2  # 0~5 級純數值評級 (0:雜訊, 1:微弱, 2:中度, 3:顯著, 4:核心爆發, 5:緊急黑天鵝)
    direction: int = 0  # 純數值方向 (+1:看多/強化, -1:看空/削弱, 0:中性)
    anchor_ref: HistoricalAnchor | None = None  # 掛載之歷史錨點 (若有匹配)
    generated_by: str = "jev_ai"  # 來源標記: "jev_ai" (由 Jev AI 模型產出) 或 "python_fallback" (降級純規則產出)
    needs_recalc: bool = False  # 是否標記為需於下一輪連網時由 AI 重新追蹤運算

    def __post_init__(self) -> None:
        # 若未手動指定 direction，自動依據 polarity 同步
        if self.direction == 0:
            if self.polarity == "positive":
                self.direction = 1
            elif self.polarity == "negative":
                self.direction = -1

    def signed_impact_score(self) -> int:
        """綜合衝擊純數值 [-5 ~ +5]。"""
        return self.direction * self.impact_level


@dataclass
class BoundedMetric:
    """由 Python 定錨可行範圍、供 AI 在範圍內上下浮動的數值結構。"""

    base_value: float  # Python 依量化指標算出的基準建議值
    min_bound: float  # Python 鎖定的下限
    max_bound: float  # Python 鎖定的上限
    current_value: float  # 經 AI 根據履歷微調後的當前值
    last_reason: str = "Python 初始基準值"

    def clamp_and_set(self, proposed_value: float, reason: str) -> float:
        """讓 AI 提出調整值，強制約束在 [min_bound, max_bound] 內並記錄理由。"""
        clamped = max(self.min_bound, min(self.max_bound, round(proposed_value, 4)))
        self.current_value = clamped
        self.last_reason = reason
        return clamped


@dataclass
class StockDossier:
    """單一股票的價值與事件履歷。"""

    ticker: str
    # 建議目標權重區間 (由 Python 依動能/估值初始化，AI 依履歷在區間內微調)
    weight_guide: BoundedMetric
    bull_evidences: list[EvidenceEntry] = field(default_factory=list)
    bear_evidences: list[EvidenceEntry] = field(default_factory=list)
    historical_cases: list[str] = field(default_factory=list)

    def add_evidence(self, entry: EvidenceEntry) -> None:
        if entry.polarity == "positive":
            self.bull_evidences.append(entry)
        else:
            self.bear_evidences.append(entry)


@dataclass
class LinkDossier:
    """股票 A 對 股票 B 的連帶因果履歷 (A -> B)，如同 Obsidian 雙向關聯筆記之連線實體。"""

    source_ticker: str  # 起點股票 A (例如 "2330" 台積電)
    target_ticker: str  # 受影響股票 B (例如 "3131" 弘塑)
    relation_note: str  # 關聯背景說明 (例如 "CoWoS 先進封裝濕製程設備供應")
    # 連結強度區間 [0.0 ~ 1.0]：Python 依歷史連動率給初值與範圍，AI 依當下事件性質上下浮動
    strength: BoundedMetric
    supporting_evidences: list[EvidenceEntry] = field(default_factory=list)  # 🟢 看多/強化傳導之數值論據
    weakening_evidences: list[EvidenceEntry] = field(default_factory=list)  # 🔴 看空/削弱連動之數值論據
    historical_cases: list[str] = field(default_factory=list)  # 傳統字串案例相容
    anchors: list[HistoricalAnchor] = field(default_factory=list)  # 具備具體區間與函數答案之歷史時空錨點

    def add_evidence(self, entry: EvidenceEntry) -> None:
        if entry.direction > 0 or entry.polarity == "positive":
            self.supporting_evidences.append(entry)
        else:
            self.weakening_evidences.append(entry)
        if entry.anchor_ref and entry.anchor_ref not in self.anchors:
            self.anchors.append(entry.anchor_ref)

    def get_net_causal_impact(self) -> int:
        """計算這條連線上的淨因果衝擊強度 (加總所有生效證據的 Signed Impact Score)。"""
        return sum(e.signed_impact_score() for e in self.supporting_evidences) + sum(
            e.signed_impact_score() for e in self.weakening_evidences
        )

    def get_latest_anchor_summary(self) -> str | None:
        """取得掛載在此連線上最新歷史時空錨點的事實與鈍化預警。"""
        if not self.anchors:
            return None
        latest = self.anchors[-1]
        return (
            f"【歷史對照錨點 {latest.case_id} ({latest.sample_period})】"
            f"歷史平均反應 +{latest.historical_response_pct:.1f}%，發酵 {latest.fade_days} 天後漲幅收斂至鈍化。"
            f"模型信心度 {latest.model_output_score:.2f}：{latest.summary}"
        )


def propose_stock_weight_bounds(
    ticker: str,
    chg_pct: float = 0.0,
    vol_ratio: float = 1.0,
    is_current_holding: bool = False,
    current_weight: float = 0.0,
) -> BoundedMetric:
    """【Python 量化錨點規則】：根據客觀價量指標，為個股計算合理的權重可行範圍。

    - 台積電 (2330) 硬上限 0.25，一般建議區間 [0.10, 0.22]。
    - 其餘個股硬上限 0.10，一般核心/衛星建議區間落在 [0.015, 0.075]。
    """
    hard_max = get_max_weight(ticker)
    if ticker == "2330":
        base = current_weight if is_current_holding and current_weight > 0 else 0.15
        if chg_pct > 1.5 and vol_ratio > 1.2:
            base = min(0.20, base + 0.02)
        return BoundedMetric(
            base_value=round(base, 4),
            min_bound=0.08,
            max_bound=min(0.22, hard_max),
            current_value=round(base, 4),
        )

    # 非 2330 之一般個股
    base = current_weight if (is_current_holding and current_weight > 0) else 0.035
    if chg_pct > 2.0 and vol_ratio > 1.2:
        base += 0.008  # 價量齊揚微幅調升基準
    elif chg_pct < -2.5:
        base -= 0.008  # 走弱微幅調降基準

    base = max(0.02, min(0.065, base))
    min_b = max(0.0, round(base - 0.02, 4))
    max_b = min(hard_max - 0.01, round(base + 0.025, 4))  # 預留 1% 安全緩衝防漲停超標
    return BoundedMetric(
        base_value=round(base, 4),
        min_bound=min_b,
        max_bound=max_b,
        current_value=round(base, 4),
    )


def propose_link_strength_bounds(
    price_corr_20d: float = 0.5,
    has_direct_revenue_tie: bool = True,
) -> BoundedMetric:
    """【Python 量化錨點規則】：根據兩股近期報酬相關性與業務關聯，給出連結強度可行範圍 [min, max]。"""
    corr_clamped = max(0.0, min(1.0, price_corr_20d))
    base = 0.5 * corr_clamped + (0.3 if has_direct_revenue_tie else 0.1)
    base = max(0.1, min(0.85, round(base, 2)))
    min_b = max(0.0, round(base - 0.25, 2))
    max_b = min(1.0, round(base + 0.25, 2))
    return BoundedMetric(
        base_value=base,
        min_bound=min_b,
        max_bound=max_b,
        current_value=base,
    )


class DossierLedger:
    """管理全市場 150 檔個股履歷與跨股連結履歷的儲存庫。"""

    def __init__(self) -> None:
        self.stocks: dict[str, StockDossier] = {}
        self.links: dict[tuple[str, str], LinkDossier] = {}

    def get_or_create_stock(
        self,
        ticker: str,
        chg_pct: float = 0.0,
        vol_ratio: float = 1.0,
        is_current_holding: bool = False,
        current_weight: float = 0.0,
    ) -> StockDossier:
        if not is_valid_ticker(ticker):
            raise KeyError(f"非 150 檔白名單個股：{ticker}")
        if ticker not in self.stocks:
            bounds = propose_stock_weight_bounds(
                ticker, chg_pct, vol_ratio, is_current_holding, current_weight
            )
            self.stocks[ticker] = StockDossier(ticker=ticker, weight_guide=bounds)
        return self.stocks[ticker]

    def get_or_create_link(
        self,
        source_ticker: str,
        target_ticker: str,
        relation_note: str = "",
        price_corr_20d: float = 0.5,
        has_direct_revenue_tie: bool = True,
    ) -> LinkDossier:
        if not (is_valid_ticker(source_ticker) and is_valid_ticker(target_ticker)):
            raise KeyError(f"連結股票必須皆在 150 檔白名單內：{source_ticker} -> {target_ticker}")
        key = (source_ticker, target_ticker)
        if key not in self.links:
            bounds = propose_link_strength_bounds(price_corr_20d, has_direct_revenue_tie)
            self.links[key] = LinkDossier(
                source_ticker=source_ticker,
                target_ticker=target_ticker,
                relation_note=relation_note,
                strength=bounds,
            )
        return self.links[key]

    def get_link(self, source_ticker: str, target_ticker: str) -> LinkDossier | None:
        """安全取得既有連結，若不存在則回傳 None。"""
        return self.links.get((source_ticker, target_ticker))

    def propagate_signal(self, source_ticker: str, source_signal: float) -> dict[str, float]:
        """當起點股票 A 發生強度為 source_signal 的事件時，依目前各連結履歷的 current_value 計算對下游 B 的連帶分數。"""
        impacts: dict[str, float] = {}
        for (src, tgt), link in self.links.items():
            if src == source_ticker and link.strength.current_value > 0:
                impacts[tgt] = round(source_signal * link.strength.current_value, 4)
        return impacts

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "stocks": {k: asdict(v) for k, v in self.stocks.items()},
            "links": {f"{k[0]}->{k[1]}": asdict(v) for k, v in self.links.items()},
        }
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        for ticker, sdata in data.get("stocks", {}).items():
            if not is_valid_ticker(ticker):
                continue
            wg = BoundedMetric(**sdata["weight_guide"])
            bulls = []
            for e in sdata.get("bull_evidences", []):
                e_copy = dict(e)
                anchor_dict = e_copy.pop("anchor_ref", None)
                anchor = HistoricalAnchor(**anchor_dict) if anchor_dict else None
                bulls.append(EvidenceEntry(anchor_ref=anchor, **e_copy))
            bears = []
            for e in sdata.get("bear_evidences", []):
                e_copy = dict(e)
                anchor_dict = e_copy.pop("anchor_ref", None)
                anchor = HistoricalAnchor(**anchor_dict) if anchor_dict else None
                bears.append(EvidenceEntry(anchor_ref=anchor, **e_copy))

            self.stocks[ticker] = StockDossier(
                ticker=ticker,
                weight_guide=wg,
                bull_evidences=bulls,
                bear_evidences=bears,
                historical_cases=sdata.get("historical_cases", []),
            )
        for link_str, ldata in data.get("links", {}).items():
            parts = link_str.split("->")
            if len(parts) == 2 and is_valid_ticker(parts[0]) and is_valid_ticker(parts[1]):
                strength = BoundedMetric(**ldata["strength"])
                supps = []
                for e in ldata.get("supporting_evidences", []):
                    e_copy = dict(e)
                    anchor_dict = e_copy.pop("anchor_ref", None)
                    anchor = HistoricalAnchor(**anchor_dict) if anchor_dict else None
                    supps.append(EvidenceEntry(anchor_ref=anchor, **e_copy))
                weaks = []
                for e in ldata.get("weakening_evidences", []):
                    e_copy = dict(e)
                    anchor_dict = e_copy.pop("anchor_ref", None)
                    anchor = HistoricalAnchor(**anchor_dict) if anchor_dict else None
                    weaks.append(EvidenceEntry(anchor_ref=anchor, **e_copy))
                anchors_list = [HistoricalAnchor(**a) for a in ldata.get("anchors", [])]

                self.links[(parts[0], parts[1])] = LinkDossier(
                    source_ticker=parts[0],
                    target_ticker=parts[1],
                    relation_note=ldata.get("relation_note", ""),
                    strength=strength,
                    supporting_evidences=supps,
                    weakening_evidences=weaks,
                    historical_cases=ldata.get("historical_cases", []),
                    anchors=anchors_list,
                )

    @classmethod
    def load_latest_or_init(cls, base_runs_dir: str | Path, today_str: str) -> DossierLedger:
        """自動從 runs 目錄尋找小於 today_str 的最新前一日 dossier_ledger.json。"""
        runs_dir = Path(base_runs_dir)
        ledger = cls()
        if not runs_dir.exists():
            return ledger

        date_dirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name < today_str]
        date_dirs.sort(key=lambda d: d.name, reverse=True)

        for d in date_dirs:
            candidate = d / "dossier_ledger.json"
            if candidate.exists():
                ledger.load(candidate)
                break

        return ledger


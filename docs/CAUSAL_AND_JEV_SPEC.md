# 因果鏈結實體化與 Jev 結構化決策評審規範 (Causal & Jev Specification)

> **版本**：v1.0 (2026-10-28)  
> **適用專案**：AI CUP 2026 玉山人工智慧挑戰賽 — Agent 基金經理人 (Team 11715)  
> **核心目標**：透過 OpenRouter Decisions API (Jev 模型) 實現極速、極低成本且純數值化的事件因果影響度評審，並直接將證據釘入雙向因果連線 (`LinkDossier`) 圖譜。

---

## 1. Jev 決策模型架構 (OpenRouter Decisions API)

傳統 LLM 生成散文容易產生幻覺、數值飄移且消耗過多 Token。本專案引入 TypeSafe 的 **Jev 結構化決策模型** (`typesafe/jev-1.13`)，專門負責「問答選擇題評分與概率分佈」。

### 1.1 API 呼叫規範
- **端點 (Endpoint)**：`POST https://openrouter.ai/api/alpha/decisions`
- **金鑰儲存**：本機 `.env` 之 `OPENROUTER_API_KEY`
- **核心問答原語 (Decision Primitives)**：
  1. **`choice`（分類選擇）**：判定事件方向（`bullish` / `bearish` / `neutral`），回傳各選項精確概率（如 `bullish: 0.99`）與整體信心度。
  2. **`score`（有序標尺評級）**：在給定的 0~3 衝擊梯度標尺上，輸出機率加權的純數值（如 `score: 2.08`）。

### 1.2 呼叫成本與耗時實測
- **單次呼叫耗時**：約 0.8 ~ 1.2 秒
- **單次呼叫成本**：約 `\$0.000021`（約新台幣 0.0007 元），成本不到傳統大模型的 1/100！

---

## 2. 決策影響度純數值化對照 (Signed Impact & Amplitude)

為避免多次語言文字轉譯導致資訊丟失，Jev 評審結果統一轉化為**純數值與百分比衝擊幅度**：

| Jev 標尺等級 | 數值名稱 | 數值化預期衝擊幅度 (Amplitude) | 適用場景 |
|:---:|:---|:---:|:---|
| **0** | 微弱無感 / 雜訊 | $\pm 0.1\% \sim \pm 0.5\%$ | 傳聞、無直接營收關聯之公關發稿 |
| **1** | 常規溫和傳導 | $\pm 0.5\% \sim \pm 1.5\%$ | 例行月度小幅增長、常規零組件採購 |
| **2** | 顯著動能拉抬 | $\pm 1.5\% \sim \pm 3.5\%$ | 先進封裝擴產釋單、外資法人連續買超重押 |
| **3** | 核心爆發 / 換代 | $> \pm 3.5\% \quad (\text{如 } +4.5\%)$ | 全新架構規格換代量產、單月營收年增破 50% |

- **方向符號數值化**：$\text{direction} \in \{+1, -1, 0\}$
- **最終決策影響度 (Decision Impact %)**：
  $$\text{Impact \%} = \text{direction} \times \text{預期衝擊幅度 (例如 } +2.5\% \text{ 或 } -1.2\%)$$

---

## 3. 雙向因果連線實體化 (`LinkDossier`)

打分後的事件與證據**唯一歸宿**為更新雙向因果連線 (`LinkDossier`)，具備類似 Obsidian 雙向筆記關聯視圖之結構：

```
節點 A (2330 台積電) ============= [因果連線 LinkDossier] =============> 節點 B (3131 弘塑)
                                  ├─ 關聯機制：CoWoS 濕製程設備主力供應
                                  ├─ 連結強度：0.88
                                  ├─ Jev 決策影響度：+2.8% (信心度 98%)
                                  ├─ 🟢 supporting_evidences: [法人連買, 擴產新單]
                                  ├─ 🔴 weakening_evidences: []
                                  └─ 📚 掛載歷史錨點：CASE_2023_COWOS (5天鈍化預警)
```

### 3.1 歷史時空錨點結構 (`HistoricalAnchor`)
拒絕空泛概念，定義具體金融分析區間與數值答案：
- `case_id`: 歷史對照代號（如 `CASE_2023_COWOS`）
- `sample_period`: 統計樣本區間（如 `2021-01 到 2026-06 金融趨勢分析`）
- `target_metric`: 觀察特徵指標（如 `台積電資本支出 YoY > 20%`）
- `historical_response_pct`: 歷史平均實際反應幅度（如 `+4.2%`）
- `fade_days`: 利多鈍化天數（如 `5` 天後日漲幅降至 0.3%）
- `model_output_score`: 模型置信度（`0.0 ~ 1.0`）

---

## 4. 前台視覺化儀表板 (Dashboard) 查核規範

- **透明可解釋性 (Transparency)**：前台網頁 (`dashboard_<date>.html`) 增設「**因果鏈關聯圖譜與證據視圖**」，點開連線即可直接查閱 Jev 影響度數值、客觀數據與歷史時空對照。
- **自主決策鐵律 (Read-Only)**：儀表板僅供經理人與評審檢視推論脈絡與對帳，**嚴禁從場外手動干擾或篡改下單指令**，100% 維護 AI CUP 自主決策賽規。

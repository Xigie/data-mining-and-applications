# 專案交接與無縫接軌狀態卡 (Project Handoff State)

> **產生時間**：2026-10-28 00:15  
> **專案定位**：AI CUP 2026 玉山人工智慧挑戰賽 — Agent 基金經理人 (Team 11715)  
> **工作目錄**：`d:\etf-agent` (Git Remote: `origin/main`)  
> **使用模型**：Google Gemini 3.8 Flash (金鑰已設於 `.env`)  

---

## 1. 目前完成狀態總結 (Current Milestone)
* **Sprint 1 (閉環 MVP)**：已 100% 完工並通過 24 項自動化單元測試 (`pytest -q` 全部綠燈)。
* **Day 1 (2026-10-27 首日建倉)**：已成功執行，24 檔 BUY 全數成交，0 違規，D-Plan 與 HTML 儀表板已產出。
* **Day 2 (2026-10-28 日常調倉)**：已成功執行，展現 AI 汰弱留強 (出清 5880 合庫金，買進 3081 聯亞)，沙盒八大鐵律 100% 通過。
* **階段 A (AI 自主提案權與論據目錄)**：已落地！
  - `src/etf_agent/catalog.yaml` & `catalog.py`：論據目錄 (L1 預載，L2/L3 按需展開)。
  - `src/etf_agent/impact_ledger.py`：重大因果鏈影響帳本。
* **階段 B (因果記憶跨日接軌與時效半衰期衰減)**：已落地！
  - 自動跨日搜尋最新前一日紀錄，半衰期衰減引擎 (7 天打對折，30 天過期歸檔)。
* **階段 C (外部訊號適配匯流排 Signal Adapter Bus)**：已落地！
  - `src/etf_agent/signals/`：建立防偽品質閘門、三大法人籌碼、MOPS 月營收與本機自訂檔案熱插拔匯流排。
* **階段 D (JAB 0~5 級數值化評級與因果鏈連線實體化)**：進行中！
  - 將訊號事件純數值化 (0~5 級、方向 +1/-1)，直接掛載寫入 A ➔ B 因果連線 (`LinkDossier`)，預留真實歷史時空錨點 (`HistoricalAnchor`) 插槽。

---

## 2. 檔案目錄結構與核心職責
* `inputs/datapacks/`：大會每日下載之 `DataPack_..._YYYY-MM-DD.json`（自動選取最新）。
* `inputs/extra_signals/`：外部訊號與隊友模型熱插拔投餵口 (JSON/CSV)。
* `inputs/etf_benchmarks.json`：30 檔主動 ETF 成分股基準庫。
* `src/etf_agent/universe.py`：150 檔個股白名單、權重上限 (2330 25%，其餘 10%)。
* `src/etf_agent/collectors.py`：TWSE/TPEx OpenAPI 150 檔收盤行情抓取。
* `src/etf_agent/signals/`：外部訊號適配匯流排、防偽品質閘門與 JAB 評審器。
* `src/etf_agent/dossier.py`：個股履歷夾 (`StockDossier`) 與因果鏈連線網 (`LinkDossier`)。
* `src/etf_agent/impact_ledger.py`：全市場重大因果事件與半衰期衰減。
* `src/etf_agent/funnel.py`：S1..Sn / O1..On 連續編號器、昨日持倉 100% 保留漏斗。
* `src/etf_agent/pm_agent.py`：Gemini 3.8 Flash 自主提案核心 (BUY/ADD/TRIM/SELL_ALL/HOLD)。
* `src/etf_agent/sandbox.py`：沙盒守門員 (千股反推、現金比率、檔數、Active Share 檢核)。
* `src/etf_agent/dashboard.py`：產出人類可讀的 HTML 戰情儀表板。
* `scripts/run_daily.py`：每日一鍵執行入口 (`python scripts/run_daily.py`)。

---

## 3. 下一步迭代計畫 (Next Steps - 階段 D)
對應規格書：`docs/AI_AGENT_PLAN.md` & `docs/SYSTEM_BLUEPRINT.md`
1. **實作 JAB 0~5 級純數值評級器與歷史時空錨點**：
   - 杜絕多次語言文字轉譯導致的資訊丟失，以純數值 `[-5, +5]` 與具體樣本區間(如 2021-2026)函數答案掛載於因果連線上。
2. **多空分析師辯論議會 (Bull vs. Bear Debate Council)**：
   - 多方與空方分析師各自從 `LinkDossier` 連線上提取 `supporting_evidences` 與 `weakening_evidences` 進行對質與裁決。

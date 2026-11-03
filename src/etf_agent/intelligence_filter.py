"""情資前置過濾工具 (Python Keyword & Sentence Extractor)。

設計依據：參考作業一文本前置過濾原理
1. 針對台股 150 檔成分股的關鍵詞庫（營收、毛利、資本支出、CoWoS、GB200、CCL、水冷散熱、稼動率、交期等）。
2. 在萬字法說會逐字稿或長篇報告中，精準擷取含有核心財務指標與產業動態的前後上下文 (Snippets)。
3. 過濾掉客套話、致謝、免責宣告等雜訊（縮減約 80%~90% 文本長度），大幅節省 Token 並提升 AI 提煉專注度。
"""

from __future__ import annotations

import re
from typing import Any

# 核心金融、產業傳導與供需關鍵字庫
KEYWORD_PATTERNS = [
    # 核心財務與擴產
    r"資本支出",
    r"營收(?:年增|月增|創高|不如預期)?",
    r"毛利率?",
    r"稼動率",
    r"產能利用率",
    r"擴產",
    r"單月營收",
    r"季報",
    r"法說會?",
    # 先進封裝與 AI 伺服器
    r"CoWoS",
    r"SoIC",
    r"先進封裝",
    r"GB200",
    r"B200",
    r"H100",
    r"AI\s*伺服器",
    r"水冷(?:板|散熱)?",
    r"散熱模組",
    r"銅箔基板",
    r"CCL",
    r"ABF\s*載板",
    r"矽光子",
    r"CPO",
    # 供需與風險警示
    r"供不應求",
    r"缺貨",
    r"滿載",
    r"訂單能見度",
    r"交期遞延",
    r"庫存調整",
    r"下修",
    r"砍單",
]

COMPILED_PATTERN = re.compile("|".join(KEYWORD_PATTERNS), re.IGNORECASE)


def filter_relevant_snippets(text: str, max_sentences_context: int = 2) -> list[str]:
    """將長文本切成句子，過濾出包含關鍵字句的前後上下文區塊。"""
    # 粗切段落與句子
    raw_sentences = re.split(r"[。！？\n]+", text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) >= 5]

    matched_indices = set()
    for idx, sentence in enumerate(sentences):
        if COMPILED_PATTERN.search(sentence):
            # 取前後 max_sentences_context 句
            start = max(0, idx - max_sentences_context)
            end = min(len(sentences), idx + max_sentences_context + 1)
            for i in range(start, end):
                matched_indices.add(i)

    if not matched_indices:
        # 若未精確匹配關鍵字，回傳前 500 字保底
        return [text[:800]]

    # 合併相鄰句子區塊
    sorted_indices = sorted(list(matched_indices))
    blocks: list[str] = []
    current_block: list[str] = []
    prev_idx = -1

    for idx in sorted_indices:
        if prev_idx != -1 and idx > prev_idx + 1:
            if current_block:
                blocks.append("。".join(current_block) + "。")
                current_block = []
        current_block.append(sentences[idx])
        prev_idx = idx

    if current_block:
        blocks.append("。".join(current_block) + "。")

    return blocks

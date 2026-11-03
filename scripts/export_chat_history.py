"""將對話紀錄與 AI 歷程轉成易讀的 HTML 閱讀器腳本。"""

import json
from pathlib import Path

ROOT = Path("C:/Users/User/.gemini/antigravity/brain/ffa917da-2f23-4385-b1b5-4a89792f1918")
TRANSCRIPT_PATH = ROOT / ".system_generated" / "logs" / "transcript.jsonl"
OUT_HTML = Path("D:/etf-agent/runs/conversation_history.html")

def build_chat_history_html():
    if not TRANSCRIPT_PATH.exists():
        print("Transcript not found")
        return

    items = []
    with TRANSCRIPT_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                stype = data.get("type", "")
                content = data.get("content", "")
                created = data.get("created_at", "")
                
                # 只保留使用者輸入與助理回覆
                if stype in ("USER_INPUT", "PLANNER_RESPONSE"):
                    role = "user" if stype == "USER_INPUT" else "assistant"
                    # 若是 assistant 但 content 為空，可能是純 tool call
                    if not content and data.get("tool_calls"):
                        tool_names = [tc.get("toolSummary") or tc.get("name") or "工具調用" for tc in data.get("tool_calls")]
                        content = f"<i>[執行系統指令/工具: {', '.join(tool_names)}]</i>"
                    if content:
                        items.append({
                            "role": role,
                            "content": content,
                            "time": created,
                            "index": data.get("step_index", 0)
                        })
            except Exception:
                pass

    chat_rows = ""
    for it in items:
        is_user = it["role"] == "user"
        box_class = "msg-user" if is_user else "msg-ai"
        sender_label = "👤 您 (User)" if is_user else "🤖 Antigravity AI"
        time_label = it["time"].replace("T", " ")[:19] if it["time"] else ""
        
        # 簡易 Markdown 換行處理
        formatted_content = it["content"].replace("\n", "<br>")
        
        chat_rows += f"""
        <div class="msg-container {box_class}">
            <div class="msg-header">
                <strong>{sender_label}</strong>
                <span class="msg-time">{time_label} (Step {it['index']})</span>
            </div>
            <div class="msg-body">{formatted_content}</div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>ETF Agent 協作對話完整歷史記錄</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 24px;
            max-width: 960px;
            margin: 0 auto;
        }}
        h1 {{
            color: #38bdf8;
            font-size: 1.5rem;
            margin-bottom: 8px;
        }}
        p.subtitle {{
            color: #94a3b8;
            font-size: 0.9rem;
            margin-bottom: 24px;
        }}
        .msg-container {{
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            line-height: 1.6;
            font-size: 0.95rem;
        }}
        .msg-user {{
            background: #1e293b;
            border-left: 4px solid #38bdf8;
        }}
        .msg-ai {{
            background: #1e293b;
            border-left: 4px solid #34d399;
        }}
        .msg-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.85rem;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            padding-bottom: 4px;
        }}
        .msg-time {{
            color: #64748b;
        }}
        .msg-body {{
            word-break: break-word;
        }}
        pre, code {{
            background: rgba(0,0,0,0.3);
            padding: 2px 4px;
            border-radius: 4px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <h1>📜 ETF Agent 完整協作對話記錄</h1>
    <p class="subtitle">自動從對話日誌彙整，共收錄 {len(items)} 則完整互動訊息</p>
    <div class="chat-thread">
        {chat_rows}
    </div>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"[OK] 歷史對話網頁已產出: {OUT_HTML}")

if __name__ == "__main__":
    build_chat_history_html()

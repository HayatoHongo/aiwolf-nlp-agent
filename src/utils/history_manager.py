from collections import deque
from typing import Deque, List
import tiktoken
import openai
import os
from dotenv import load_dotenv
from pathlib import Path


# --------------- 設定 -----------------
ENC = tiktoken.encoding_for_model("gpt-4o-mini")
TOKEN_LIMIT = 5000
# .env をロードして環境変数からキーを取得
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# API クライアント初期化時にも明示的に api_key を渡す
client = openai.Client(api_key=openai.api_key)
# --------------------------------------


class HistoryBuffer:
    """会話履歴を管理し、長くなったら要約に置き換える。"""

    def __init__(self) -> None:
        self.raw: Deque[str] = deque()
        self.summaries: List[str] = []

    # ----- 公開 API -----
    def add(self, line: str) -> None:
        """会話文を追加し、必要なら要約する。"""
        self.raw.append(line)
        if self._token_len(self.raw) > TOKEN_LIMIT:
            self._summarize()

    def get_context(self) -> str:
        """LLM に渡す履歴全文（summary + current raw）"""
        return "\n".join(self.summaries + list(self.raw))

    # ----- 内部 -----
    def _summarize(self) -> None:
        prompt = [
            {
                "role": "system",
                "content": "以下の会話を日本語で100字以内にまとめてください。箇条書き可。",
            },
            {"role": "user", "content": "\n".join(self.raw)},
        ]
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=prompt)
        summary = resp.choices[0].message.content.strip()
        self.summaries.append(summary)
        self.raw.clear()

    @staticmethod
    def _token_len(lines) -> int:
        return sum(len(ENC.encode(l)) for l in lines)

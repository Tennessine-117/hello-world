"""簡易な意味検索Webアプリ。
- 起動時に問題文を数値ベクトル化して保持
- 検索文も同じ方法でベクトル化
- コサイン類似度で近い順に上位10件を返す
"""

from __future__ import annotations

import hashlib
import json
import math
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlparse

# -----------------------------
# 設定値（最小構成）
# -----------------------------
DATA_PATH = Path("data/problems.json")
INDEX_PATH = Path("static/index.html")
VECTOR_SIZE = 128  # 「意味を表す数字の列」の長さ（固定長）
TOP_K = 10
HOST = "0.0.0.0"
PORT = 8000


# -----------------------------
# テキスト -> 数値ベクトル 変換
# -----------------------------

def _normalize_text(text: str) -> str:
    """前処理：空白などを軽く整える（日本語向けに簡易対応）"""
    # 全角/半角や記号の細かな処理は省略し、最低限で動かす
    return "".join(text.lower().split())


def _char_bigrams(text: str) -> List[str]:
    """文字2-gramを作る（日本語でも最低限の意味手がかりになる）"""
    if len(text) < 2:
        return [text]
    return [text[i : i + 2] for i in range(len(text) - 1)]


def _hash_to_index(token: str) -> int:
    """トークンを固定長ベクトルのインデックスへ（再現性のあるハッシュ）"""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    # 先頭4バイトを整数化して次元に割り当て
    value = int.from_bytes(digest[:4], "little")
    return value % VECTOR_SIZE


def text_to_vector(text: str) -> List[float]:
    """テキストを「意味を表す数字の列」に変換"""
    normalized = _normalize_text(text)
    bigrams = _char_bigrams(normalized)

    # ハッシュ化した出現回数ベクトル
    vec = [0.0] * VECTOR_SIZE
    for token in bigrams:
        vec[_hash_to_index(token)] += 1.0

    # L2正規化（コサイン類似度用）
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """コサイン類似度（内積）"""
    return sum(a * b for a, b in zip(vec_a, vec_b))


# -----------------------------
# 起動時に問題文を読み込み＆ベクトル化
# -----------------------------
with DATA_PATH.open("r", encoding="utf-8") as f:
    PROBLEMS = json.load(f)

PROBLEM_VECTORS = [
    {
        "id": item["id"],
        "text": item["text"],
        "vector": text_to_vector(item["text"]),
    }
    for item in PROBLEMS
]


# -----------------------------
# HTTPハンドラ
# -----------------------------
class AppHandler(BaseHTTPRequestHandler):
    """最小のHTTPハンドラ"""

    def _send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str, status=HTTPStatus.OK):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandlerのAPIに合わせる)
        parsed = urlparse(self.path)

        # ルートは検索ページ
        if parsed.path == "/" or parsed.path == "/index.html":
            html = INDEX_PATH.read_text(encoding="utf-8")
            self._send_html(html)
            return

        # 検索API
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not query:
                self._send_json([])
                return

            query_vec = text_to_vector(query)

            # 類似度計算して上位を抽出
            scored = [
                {
                    "id": item["id"],
                    "text": item["text"],
                    "score": cosine_similarity(query_vec, item["vector"]),
                }
                for item in PROBLEM_VECTORS
            ]
            scored.sort(key=lambda x: x["score"], reverse=True)
            self._send_json(scored[:TOP_K])
            return

        # それ以外は404
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)


def run():
    """サーバ起動"""
    server = HTTPServer((HOST, PORT), AppHandler)
    print(f"Serving on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()

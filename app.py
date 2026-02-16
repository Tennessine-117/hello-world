"""簡易な意味検索Webアプリ。
- 起動時に問題文を数値ベクトル化して保持
- 検索文も同じ方法でベクトル化
- コサイン類似度で近い順に上位10件を返す
- 問題詳細ページで選択肢/答え表示のトグルに対応
"""

from __future__ import annotations

import hashlib
import json
import math
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, unquote, urlparse

# -----------------------------
# 設定値（最小構成）
# -----------------------------
DATA_PATH = Path("data/problems.json")
INDEX_PATH = Path("static/index.html")
PROBLEM_PAGE_PATH = Path("static/problem.html")
VECTOR_SIZE = 128  # 「意味を表す数字の列」の長さ（固定長）
TOP_K = 10
HOST = "0.0.0.0"
PORT = 8000


# -----------------------------
# テキスト -> 数値ベクトル 変換
# -----------------------------
def _normalize_text(text: str) -> str:
    """前処理：空白などを軽く整える（日本語向けに簡易対応）"""
    return "".join((text or "").lower().split())


def _char_bigrams(text: str) -> List[str]:
    """文字2-gramを作る（日本語でも最低限の意味手がかりになる）"""
    if len(text) < 2:
        return [text]
    return [text[i : i + 2] for i in range(len(text) - 1)]


def _hash_to_index(token: str) -> int:
    """トークンを固定長ベクトルのインデックスへ（再現性のあるハッシュ）"""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "little")
    return value % VECTOR_SIZE


def text_to_vector(text: str) -> List[float]:
    """テキストを「意味を表す数字の列」に変換"""
    normalized = _normalize_text(text)
    bigrams = _char_bigrams(normalized)

    vec = [0.0] * VECTOR_SIZE
    for token in bigrams:
        vec[_hash_to_index(token)] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """コサイン類似度（内積）"""
    return sum(a * b for a, b in zip(vec_a, vec_b))


def build_problem_search_text(problem: Dict) -> str:
    """検索用テキストを構築。

    精度改善は次PRとして、ここでは既存ロジックに寄せたシンプル構成。
    """
    title = str(problem.get("title", ""))
    statement = str(problem.get("statement", ""))
    tags = " ".join(problem.get("tags") or [])
    concepts = " ".join(problem.get("concepts") or [])
    return " ".join([title, statement, tags, concepts]).strip()


# -----------------------------
# 起動時に問題文を読み込み＆ベクトル化
# -----------------------------
with DATA_PATH.open("r", encoding="utf-8") as f:
    PROBLEMS: List[Dict] = json.load(f)

PROBLEMS_BY_ID: Dict[str, Dict] = {str(item.get("id", "")): item for item in PROBLEMS}

PROBLEM_VECTORS = [
    {"id": item.get("id"), "vector": text_to_vector(build_problem_search_text(item))}
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
            self._send_html(INDEX_PATH.read_text(encoding="utf-8"))
            return

        # 問題詳細ページ
        if parsed.path.startswith("/problems/"):
            self._send_html(PROBLEM_PAGE_PATH.read_text(encoding="utf-8"))
            return

        # 検索API
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not query:
                self._send_json([])
                return

            query_vec = text_to_vector(query)

            scored = []
            for item in PROBLEM_VECTORS:
                problem = PROBLEMS_BY_ID.get(str(item.get("id")), {})
                scored.append(
                    {
                        "id": problem.get("id", ""),
                        "title": problem.get("title", "(無題)"),
                        "tags": problem.get("tags") or [],
                        "score": cosine_similarity(query_vec, item["vector"]),
                    }
                )

            scored.sort(key=lambda x: x["score"], reverse=True)
            self._send_json(scored[:TOP_K])
            return

        # 問題詳細API
        if parsed.path.startswith("/api/problems/"):
            problem_id = unquote(parsed.path.replace("/api/problems/", "", 1)).strip()
            problem = PROBLEMS_BY_ID.get(problem_id)
            if not problem:
                self._send_json({"error": "problem not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(problem)
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

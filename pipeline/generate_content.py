"""
無課金AI社員パイプライン(雛形)

構成:
1. 無料RSSフィードから記事ネタを収集する
2. Gemini API無料枠で要約・下書き記事を生成する
3. 結果を drafts/ 配下にファイル出力する(公開は人間が手動で行う)

必要なもの(すべて無料):
- Gemini APIキー(環境変数 GEMINI_API_KEY として設定。Google AI Studioで無料登録して取得)
- Python 3.10+ , `pip install google-genai feedparser`

このスクリプトはGitHub Actionsの無料枠(cronスケジュール)で日次実行することを想定している。
ワークフロー定義は .github/workflows/daily-content.yml を参照。
"""

import os
import time
import datetime
import feedparser
from google import genai
from google.genai import errors as genai_errors

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+%E5%89%AF%E6%A5%AD&hl=ja&gl=JP&ceid=JP:ja",
]

DRAFT_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts")


def fetch_topics(limit: int = 5) -> list[str]:
    topics = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            topics.append(entry.title)
    return topics


def generate_draft(topics: list[str]) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)

    prompt = (
        "以下のニュース見出しを参考に、AI副業に関心がある読者向けの短い記事下書きを作成してください。"
        "誇張表現(稼げる、誰でも、不労所得など)は絶対に使わないでください。"
        "事実ベースで、AIができること・できないことを正直に書いてください。\n\n"
        + "\n".join(f"- {t}" for t in topics)
    )

    last_error = None
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt,
            )
            return response.text
        except genai_errors.ServerError as e:
            last_error = e
            wait_seconds = 30 * (attempt + 1)
            print(f"サーバー混雑のため失敗(試行{attempt + 1}/5)。{wait_seconds}秒待って再試行します: {e}")
            time.sleep(wait_seconds)

    raise last_error


def main() -> None:
    os.makedirs(DRAFT_DIR, exist_ok=True)
    topics = fetch_topics()
    draft = generate_draft(topics)

    today = datetime.date.today().isoformat()
    out_path = os.path.join(DRAFT_DIR, f"{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {today} 下書き(AI生成・未公開)\n\n")
        f.write(draft)

    print(f"下書きを生成しました: {out_path}")
    print("この下書きは自動公開されません。内容を確認し、compliance/red-flags-checklist.md に照らしてから手動で投稿してください。")


if __name__ == "__main__":
    main()

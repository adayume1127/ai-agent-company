"""
無課金AI社員パイプライン(雛形)

構成:
1. 無料RSSフィードから記事ネタを収集する
2. Gemini API無料枠で要約・下書き記事を生成する
3. 結果を drafts/ 配下にファイル出力する(公開は人間が手動で行う)
4. その日AIが何を選び、どう判断したかを decisions/ 配下にログとして残す
5. 生成物に誇張・断定表現が混入していないか自動チェックする

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

MODEL_NAME = "gemini-flash-lite-latest"

# compliance/red-flags-checklist.md に対応する禁止ワード。
# ここに引っかかった場合、下書きは自動公開せず「要確認」マークを付けて人間の目視を促す。
BANNED_PHRASES = [
    "稼げる", "誰でも稼げる", "誰でも", "不労所得", "絶対", "必ず儲かる",
    "保証します", "確実に", "リスクなし", "簡単に稼", "月収100万",
]

DRAFT_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts")
DECISIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "decisions")


def fetch_topics(limit: int = 5) -> list[str]:
    topics = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            topics.append(entry.title)
    return topics


def check_compliance(text: str) -> list[str]:
    """禁止ワードが含まれていないか確認し、見つかったものを返す"""
    return [phrase for phrase in BANNED_PHRASES if phrase in text]


def generate_draft(topics: list[str]) -> tuple[str, int]:
    """下書き本文と、生成に要した試行回数を返す"""
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
                model=MODEL_NAME,
                contents=prompt,
            )
            return response.text, attempt + 1
        except genai_errors.ServerError as e:
            last_error = e
            wait_seconds = 30 * (attempt + 1)
            print(f"サーバー混雑のため失敗(試行{attempt + 1}/5)。{wait_seconds}秒待って再試行します: {e}")
            time.sleep(wait_seconds)

    raise last_error


def write_decision_log(today: str, topics: list[str], attempts: int, flagged: list[str]) -> str:
    """その日AIが何を選び、どう判断したかを正直に記録する(Xでの発信素材にも使う)"""
    os.makedirs(DECISIONS_DIR, exist_ok=True)
    out_path = os.path.join(DECISIONS_DIR, f"{today}.md")

    lines = [
        f"# {today} AI意思決定ログ",
        "",
        f"- 使用モデル: {MODEL_NAME}",
        f"- 生成に要した試行回数: {attempts}回" + ("(1回で成功)" if attempts == 1 else "(サーバー混雑のためリトライ発生)"),
        f"- 参照したニュース見出し数: {len(topics)}件",
    ]
    if topics:
        lines.append("- 選んだ見出し:")
        lines.extend(f"  - {t}" for t in topics)
    if flagged:
        lines.append(f"- ⚠️ 禁止ワード検出: {', '.join(flagged)}(該当下書きは公開前に必ず人間が修正すること)")
    else:
        lines.append("- 禁止ワードチェック: 問題なし")

    content = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def main() -> None:
    os.makedirs(DRAFT_DIR, exist_ok=True)
    topics = fetch_topics()
    draft, attempts = generate_draft(topics)
    flagged = check_compliance(draft)

    today = datetime.date.today().isoformat()
    out_path = os.path.join(DRAFT_DIR, f"{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        header = f"# {today} 下書き(AI生成・未公開)\n\n"
        if flagged:
            header += f"**⚠️ 要確認: 禁止ワード({', '.join(flagged)})が検出されました。公開前に必ず修正してください。**\n\n"
        f.write(header)
        f.write(draft)

    log_path = write_decision_log(today, topics, attempts, flagged)

    print(f"下書きを生成しました: {out_path}")
    print(f"意思決定ログを記録しました: {log_path}")
    if flagged:
        print(f"警告: 禁止ワードが検出されました → {flagged}")
    print("この下書きは自動公開されません。内容を確認し、compliance/red-flags-checklist.md に照らしてから手動で投稿してください。")


if __name__ == "__main__":
    main()

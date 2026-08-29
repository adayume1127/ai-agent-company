"""
GEMINI_API_KEYが有効かどうかだけを確認するテストスクリプト。
キーの中身は一切表示しない。

使い方:
  cd ai-agent-company/pipeline
  pip install -r requirements.txt python-dotenv
  python test_key.py
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

key = os.environ.get("GEMINI_API_KEY", "")

if not key:
    print("NG: .envにGEMINI_API_KEYが見つかりません")
    raise SystemExit(1)

print(f"読み込んだキーの先頭6文字: {key[:6]}... (長さ: {len(key)}文字)")

try:
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents="OK とだけ返してください",
    )
    print("OK: APIキーは有効です")
    print("応答:", response.text)
except Exception as e:
    print("NG: APIキーが無効か、リクエストが失敗しました")
    print("エラー内容:", e)

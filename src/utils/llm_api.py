"""DeepSeek LLM API 工具模块"""

import os
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


def call_deepseek_llm(prompt, temperature=0.7, max_tokens=128, model="deepseek-chat"):
    """调用 DeepSeek LLM API"""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(
            DEEPSEEK_API_URL, headers=headers, json=payload, timeout=20
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        # 返回详细错误信息
        return f"DeepSeek API 调用失败: {e}"
    except KeyError as e:
        # 返回详细响应格式错误
        return f"DeepSeek API 响应格式错误: {e}"


"""OpenAI LLM API 工具模块"""
# 仮想環境で openai ライブラリと python-dotenv をインストールしてください
import os
import openai
from dotenv import load_dotenv

# .env から環境変数を読み込む
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY が設定されていません。.env ファイルをご確認ください。"
    )

openai.api_key = OPENAI_API_KEY


def call_openai_llm(
    prompt: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.7,
    max_tokens: int = 128,
    system_prompt: str = None,
) -> str:
    """
    OpenAI Chat API (v1.0.0+) を呼び出す汎用関数。

    Args:
        prompt: ユーザーからの入力文字列
        model: 使用するモデル名 (例: "gpt-4o-mini", "gpt-3.5-turbo" など)
        temperature: ランダム性の制御値 (0.0～2.0)
        max_tokens: 生成する最大トークン数
        system_prompt: システムプロンプトを設定したい場合に指定

    Returns:
        モデルが生成したレスポンス文字列（エラー時は詳細を含むメッセージ）
    """
    # メッセージ列を組み立て
    messages = []
    if system_prompt is not None:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        # モデルによって max_tokens / max_completion_tokens を使い分け
        if model.startswith("gpt-4o"):
            resp = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
        else:
            resp = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return resp.choices[0].message.content.strip()

    except openai.OpenAIError as e:
        # エラー詳細を返す
        return f"OpenAI API 呼び出し中にエラー発生: {e}"

    except (KeyError, IndexError) as e:
        # レスポンス解析エラーの詳細を返す
        return f"OpenAI API レスポンス解析中にエラー発生: {e}"


# 動作確認用サンプル
if __name__ == "__main__":
    answer = call_openai_llm(
        prompt="こんにちは、今日の天気を教えてください。",
        model="gpt-3.5-turbo",  # "gpt-4.1"
    )
    print(answer)

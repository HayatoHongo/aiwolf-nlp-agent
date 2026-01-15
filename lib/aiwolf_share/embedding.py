from openai import OpenAI  # type: ignore
import openai  # type: ignore
import os
import numpy as np
import pandas as pd

# APIキーを環境変数として設定
openai.api_key = os.environ["OPENAI_API_KEY"]

client = OpenAI()


def get_embedding(text, model="text-embedding-3-small"):  # small or large
    result = client.embeddings.create(input=[text], model=model).data[0].embedding
    return np.array(result)


def cos_sim(a, b):
    try:
        # 入力を numpy 配列に変換
        a = np.array(a)
        b = np.array(b)

        # 1次元配列にフラット化
        a = a.flatten()
        b = b.flatten()

        # ゼロベクトルチェック
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return np.dot(a, b) / (norm_a * norm_b)
    except Exception as e:
        print(f"[DEBUG] cos_sim error:  returning 0.0")
        return 0.0

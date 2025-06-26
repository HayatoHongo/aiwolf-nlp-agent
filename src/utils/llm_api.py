"""DeepSeek LLM API 工具模块"""

import os
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

def call_deepseek_llm(prompt, temperature=0.7, max_tokens=128):
    """调用 DeepSeek LLM API"""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        print(f"DeepSeek API 调用失败: {e}")
        return "API调用失败，使用默认回复"
    except KeyError as e:
        print(f"DeepSeek API 响应格式错误: {e}")
        return "API响应格式错误，使用默认回复" 
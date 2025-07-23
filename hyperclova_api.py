import os
import requests
from functools import lru_cache

API_KEY = os.getenv("HCX_API_KEY")            # your HyperCLOVA X API key
BASE_URL = "https://clovastudio.stream.ntruss.com/v1"

def _get_headers():
    if not API_KEY:
        raise ValueError("HCX_API_KEY 환경변수를 설정해주세요.")
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

@lru_cache(maxsize=128)
def classify_content(text: str) -> dict:
    """
    TODO: Implement /completions or /router or embedding-based tagging.
    """
    return {"risk": "중립", "themes": [], "period": "장기"}

@lru_cache(maxsize=128)
def summarize_text(text: str, max_length: int = 200) -> str:
    """
    TODO: Implement /summarize endpoint.
    """
    return text[:max_length] + "..."

def chat_completion(prompt: str) -> str:
    """
    Calls HyperCLOVA X Chat Completions v3 to answer the user's question.
    """
    headers = _get_headers()
    payload = {
        "model": "hyperclova-x-seed-14b",   # pick the appropriate seed/model
        "messages": [
            {"role": "system", "content":
             "당신은 금융투자 전문가 AI입니다. "
             "사용자의 투자 성향과 추천 상품 정보를 참고해 친절하게 설명해 주세요."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }
    try:
        res = requests.post(f"{BASE_URL}/chat/completions",
                            json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        # OpenAI‑style response parsing
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # In demo mode, fallback to an error‐friendly message
        return f"[에러: {e}]"


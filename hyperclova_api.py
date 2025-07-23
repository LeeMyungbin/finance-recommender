# hyperclova_api.py
import os
import requests
from functools import lru_cache

API_KEY = os.getenv("HCX_API_KEY")
BASE_URL = "https://clovastudio.stream.ntruss.com"  # CLOVA Studio Chat Completions v3 엔드포인트

def _get_headers():
    """
    HCX_API_KEY 환경변수를 읽어서 CLOVA Studio 호출용 헤더를 만든다.
    """
    if not API_KEY:
        raise ValueError("HCX_API_KEY 환경변수를 설정해주세요.")
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

@lru_cache(maxsize=128)
def classify_content(text: str) -> dict:
    """
    TODO: 실제 HyperCLOVA X 콘텐츠 분류 API 호출 부분으로 교체
    """
    # 예시:
    # payload = {"model":"hyperclova-x-seed-14b", "messages":[
    #     {"role":"system","content":"금융 뉴스의 테마, 위험도, 투자기간을 분류해줘."},
    #     {"role":"user","content": text}
    # ]}
    # r = requests.post(f"{BASE_URL}/v3/chat/completions", headers=_get_headers(), json=payload)
    # r.raise_for_status()
    # data = r.json()
    # message = data["result"]["choices"][0]["message"]["content"]
    # return json.loads(message)
    return {"risk": "중립", "themes": [], "period": "중기"}

@lru_cache(maxsize=128)
def summarize_text(text: str, max_length: int = 200) -> str:
    """
    TODO: 실제 HyperCLOVA X 요약 API 호출 부분으로 교체
    """
    # 예시:
    # payload = {"model":"hyperclova-x-seed-14b", "messages":[
    #     {"role":"system","content":f"아래 텍스트를 {max_length}자 이내로 요약해줘:"},
    #     {"role":"user","content": text}
    # ]}
    # r = requests.post(f"{BASE_URL}/v3/chat/completions", headers=_get_headers(), json=payload)
    # r.raise_for_status()
    # data = r.json()
    # return data["result"]["choices"][0]["message"]["content"]
    return text[:max_length] + "..."

def chat_completion(prompt: str) -> str:
    """
    실제 HyperCLOVA X Chat Completions v3 API 호출 부분.
    사용자 prompt 를 그대로 전달하고, 모델의 응답을 텍스트로 리턴한다.
    """
    headers = _get_headers()
    payload = {
        "model": "hyperclova-x-seed-14b",    # 사용하실 모델로 변경 가능
        "messages": [
            {"role": "system", "content": "당신은 금융 투자 어드바이저 AI입니다. 사용자 질문에 맞춰 답해주세요."},
            {"role": "user",   "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        resp = requests.post(f"{BASE_URL}/v3/chat/completions",
                             headers=headers,
                             json=payload,
                             timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        # 네트워크 에러 또는 비정상 응답 시
        return f"[Error] HyperCLOVA 호출 실패: {e}"

    data = resp.json()
    try:
        return data["result"]["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return "[Error] 응답 형식이 예상과 다릅니다."


import os, json, hashlib, requests
from datetime import datetime
from collections import Counter
from typing import List, Tuple

import streamlit as st
from hyperclova_api import classify_content, summarize_text, chat_completion

# ─── 환경설정 ───────────────────────────────────────────────
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
NEWS_DB_PATH  = "news_data.json"

# ─── 공통 유틸 ──────────────────────────────────────────────
def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def make_hash(title: str, link: str) -> str:
    return hashlib.md5((title + link).encode("utf-8")).hexdigest()

def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(obj: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# ─── 네이버 뉴스 수집 ───────────────────────────────────────
def get_news(query: str) -> list:
    """네이버 뉴스 20건 최신순 반환(오류 시 빈 리스트)."""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    try:
        r = requests.get(
            url,
            headers=headers,
            params={"query": query, "display": 20, "sort": "date"},
            timeout=5
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception:
        return []

def crawl_today_news(keywords: List[str]) -> None:
    """금일 키워드별 뉴스를 DB(json)에 누적 저장."""
    db = load_json(NEWS_DB_PATH)
    d  = today_str()
    db.setdefault(d, [])
    seen = {make_hash(n["title"], n["link"]) for n in db[d]}

    for kw in keywords:
        for it in get_news(kw):
            h = make_hash(it["title"], it["link"])
            if h not in seen:
                db[d].append(
                    {
                        "title":       it["title"],
                        "description": it["description"],
                        "pubDate":     it["pubDate"],
                        "link":        it["link"],
                        "query":       kw
                    }
                )
                seen.add(h)

    save_json(db, NEWS_DB_PATH)

# ─── 투자자 성향 설문 ───────────────────────────────────────
st.sidebar.header("📋 투자자 성향 설문")

q1 = st.sidebar.radio("투자 가능 기간은?",   ["1년 이하", "1~5년", "5년 이상"])
q2 = st.sidebar.radio("원금 손실 가능성 있다면?", ["절대 불가", "감수 가능", "고수익이면 감수"])
q3 = st.sidebar.radio("투자 시 가장 중요 요소는?", ["안정", "균형", "고수익"])
q4 = st.sidebar.radio("투자 경험은?",        ["예금·적금", "펀드 소액", "직접 주식"])
q5 = st.sidebar.radio("투자 가능 비율은?",    ["10% 이하", "10~30%", "30% 이상"])
q6 = st.sidebar.radio("선호 투자 상황은?",    ["3% 안정", "10% 수익/5% 손실", "20% 수익/손실"])

# 관심 테마 / 뉴스 키워드
interests = st.sidebar.multiselect(
    "관심 분야",
    ["인프라", "ETF", "TDF", "EMP", "프리IPO", "구조화상품", "AI"]
)
kws = st.sidebar.multiselect(
    "뉴스 키워드",
    ["금리", "인프라", "AI", "프리IPO", "채권", "ETF", "구조화상품"],
    default=["금리", "ETF"]
)

# ─── 성향 분류 로직 (점수 기반) ─────────────────────────────
def classify_investor(
    period: str,  # q1
    answers: Tuple[str, str, str, str, str]  # q2~q6
) -> Tuple[str, float]:
    """
    질문별 점수를 합산해 -8~+8 스코어 → 0~1 실수 변환.
      * score ≥ 4  → 공격형
      * score ≤ -4 → 안정형
      * else      → 중립형
    """

    # 각 문항별 가중치 테이블
    score_map = {
        # q2
        "절대 불가": -2,
        "감수 가능":  0,
        "고수익이면 감수": +2,
        # q3
        "안정": -2,
        "균형":  0,
        "고수익": +2,
        # q4
        "예금·적금": -1,
        "펀드 소액":  0,
        "직접 주식": +1,
        # q5
        "10% 이하":  -2,
        "10~30%":    -1,
        "30% 이상":  +2,
        # q6
        "3% 안정":            -2,
        "10% 수익/5% 손실":   +1,
        "20% 수익/손실":     +2,
    }

    raw_score = sum(score_map.get(a, 0) for a in answers)
    # -8~+8 → 0~1 정규화
    risk_score = (raw_score + 8) / 16

    if raw_score >= 4:
        label = "공격형 투자자"
    elif raw_score <= -4:
        label = "안정형 투자자"
    else:
        label = "중립형 투자자"

    return label, round(risk_score, 2)

def generate_investor_profile(
    label: str,
    risk_score: float,
    period_label: str,
    interests: List[str]
) -> dict:

    horizon_map = {"1년 이하": 1, "1~5년": 3, "5년 이상": 5}
    return {
        "investor_label": label,
        "risk_score": risk_score,          # 0.0(보수) ~ 1.0(공격)
        "horizon_years": horizon_map.get(period_label, 3),
        "interest_tags": interests
    }

# ─── 설문 완료 처리 ────────────────────────────────────────
if st.sidebar.button("설문 완료 & 추천 시작"):
    answers = (q2, q3, q4, q5, q6)
    label, risk = classify_investor(q1, answers)
    profile = generate_investor_profile(label, risk, q1, interests)

    st.session_state["profile"]  = profile
    st.session_state["keywords"] = kws
    st.sidebar.success(f"{label}로 분류되었습니다!")

# ─── 메인 화면 ─────────────────────────────────────────────
st.set_page_config(page_title="HyperCLOVA 금융추천", layout="wide")
st.title("HyperCLOVA X 기반 맞춤형 금융상품 추천")

if "profile" in st.session_state:
    prof = st.session_state["profile"]
    kws  = st.session_state["keywords"]

    # 1) 오늘 뉴스 수집 (캐싱)
    if "news_db" not in st.session_state:
        crawl_today_news(kws)
        st.session_state["news_db"] = load_json(NEWS_DB_PATH)

    news_db = st.session_state["news_db"]
    today   = max(news_db.keys())
    items   = news_db[today][:10]

    # 2) 뉴스 요약 & 태그
    st.subheader("뉴스 요약 & 태그")
    tags_accum: List[str] = []
    for it in items:
        cnt     = f"{it['title']}\n{it['description']}"
        summary = summarize_text(cnt)
        tags    = classify_content(cnt).get("themes", [])
        tags_accum.extend(tags)

        with st.expander(it["title"]):
            st.write(summary)
            st.caption("태그: " + ", ".join(tags) if tags else "태그 없음")
            st.markdown(f"[원문 보기]({it['link']})")

    # 3) 상품 추천
    market_themes = list(set(kws + tags_accum))
    PRODUCTS_DB = [
        {"name": "EMP 분산 펀드", "risk": 0.5, "themes": ["자산배분", "ETF"], "description": "여러 ETF로 글로벌 분산투자"},
        {"name": "TDF 2045",    "risk": 0.3, "themes": ["장기", "채권"],   "description": "은퇴 목표 시점에 맞춰 자동 리밸런싱"},
        {"name": "글로벌 리츠",   "risk": 0.4, "themes": ["리츠", "부동산"], "description": "안정적 임대 수익형 부동산 포트폴리오"},
        {"name": "고정쿠폰 ELS",  "risk": 0.8, "themes": ["구조화상품"],     "description": "조건부 조기상환형 ELS"},
        {"name": "Pre-IPO 펀드", "risk": 0.9, "themes": ["프리IPO"],       "description": "미상장 혁신기업 성장 투자"},
        {"name": "인프라 ETF",   "risk": 0.6, "themes": ["인프라"],         "description": "도로·데이터센터 등 글로벌 인프라"},
        {"name": "AI 스마트베타","risk": 0.6, "themes": ["AI"],            "description": "AI 팩터 기반 스마트베타 ETF"},
    ]

    def recommend_products(profile: dict, themes: List[str]) -> List[dict]:
        scored = []
        for p in PRODUCTS_DB:
            # ① 위험 적합도(60%) ② 테마 적합도(40%)
            rs = 1 - abs(profile["risk_score"] - p["risk"])
            ts = len(set(profile["interest_tags"] + themes) & set(p["themes"])) / (len(p["themes"]) + 1e-5)
            scored.append((0.6 * rs + 0.4 * ts, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:3]]

    recs = recommend_products(prof, market_themes)

    # 4) 추천 결과
    st.subheader("추천 상품")
    for p in recs:
        st.markdown(f"### {p['name']}  (위험도 {p['risk']})")
        st.write(p["description"])
        st.caption("테마: " + ", ".join(p["themes"]))

    # 5) 챗봇 Q&A
    st.subheader("챗봇 Q&A")
    q = st.text_input("궁금한 내용을 입력하세요")
    if q:
        prompt = (
            f"사용자 프로필: {prof}\n"
            f"추천 상품: {[x['name'] for x in recs]}\n"
            f"질문: {q}"
        )
        answer = chat_completion(prompt)
        st.info(answer)

import os, json, hashlib, requests
from datetime import datetime
from collections import Counter
import streamlit as st
from hyperclova_api import classify_content, summarize_text, chat_completion

# ─── 설정 ─────────────────────────────────────────────────
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
NEWS_DB_PATH  = "news_data.json"

# ─── 유틸 함수 ───────────────────────────────────────────────
def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def make_hash(title, link):
    return hashlib.md5((title + link).encode("utf-8")).hexdigest()

def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# ─── 뉴스 크롤러 ────────────────────────────────────────────
def get_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    try:
        r = requests.get(url, headers=headers,
                         params={"query": query, "display": 20, "sort": "date"},
                         timeout=5)
        r.raise_for_status()
        return r.json().get("items", [])
    except:
        return []

def crawl_today_news(keywords):
    db = load_json(NEWS_DB_PATH)
    d = today_str()
    db.setdefault(d, [])
    seen = {make_hash(n["title"], n["link"]) for n in db[d]}
    for kw in keywords:
        for it in get_news(kw):
            h = make_hash(it["title"], it["link"])
            if h not in seen:
                db[d].append({
                    "title": it["title"],
                    "description": it["description"],
                    "pubDate": it["pubDate"],
                    "link": it["link"],
                    "query": kw
                })
                seen.add(h)
    save_json(db, NEWS_DB_PATH)

# ─── 투자자 성향 설문 & 분류 ─────────────────────────────────
st.sidebar.header("📋 투자자 성향 설문")

q1 = st.sidebar.radio(
    "투자 가능 기간은?",
    ["1년 이하", "1~5년", "5년 이상"]
)

q2 = st.sidebar.radio(
    "원금 손실 가능성 있다면?",
    ["절대 불가", "감수 가능", "고수익이면 감수"]
)

q3 = st.sidebar.radio(
    "투자 시 가장 중요 요소는?",
    ["안정", "균형", "고수익"]
)

q4 = st.sidebar.radio(
    "투자 경험은?",
    ["예금·적금", "펀드 소액", "직접 주식"]
)

q5 = st.sidebar.radio(
    "투자 가능 비율은?",
    ["10% 이하", "10~30%", "30% 이상"]
)

q6 = st.sidebar.radio(
    "선호 투자 상황은?",
    ["3% 안정", "10% 수익/5% 손실", "20% 수익/손실"]
)

# 관심 분야 (별도 유지)
interests = st.sidebar.multiselect(
    "관심 분야",
    ["인프라","ETF","TDF","EMP","프리IPO","구조화상품","AI"]
)

# 뉴스 키워드 (별도 유지)
kws = st.sidebar.multiselect(
    "뉴스 키워드",
    ["금리","인프라","AI","프리IPO","채권","ETF","구조화상품"],
    default=["금리","ETF"]
)

# 성향 분류 로직 (A/B/C 문항→ 공격/중립/안정 + 기본 risk score)
def classify_investor(answers):
    cnt = {"안정":0, "균형":0, "고수익":0}
    # q2~q6: ['절대 불가'→안정,'감수 가능'→균형,'고수익이면 감수'→고수익], ...
    # 간단히 mapping: 순서대로 안정/균형/고수익
    mapping = {
        "절대 불가":"안정", "감수 가능":"균형", "고수익이면 감수":"고수익",
        "안정":"안정",     "균형":"균형",     "고수익":"고수익"
    }
    for a in answers:
        key = mapping.get(a, None)
        if key: cnt[key] += 1

    if cnt["고수익"] >= 4:
        return "공격형 투자자", 0.7
    elif cnt["안정"] >= 4:
        return "안정형 투자자", 0.3
    else:
        return "중립형 투자자", 0.5

# 프로필 생성 함수: classify_investor 결과 + horizon mapping
def generate_investor_profile(label, risk_score, period_label, interests):
    # horizon: 1년 이하→1, 1~5년→3, 5년 이상→5
    horizon_map = {"1년 이하":1, "1~5년":3, "5년 이상":5}
    return {
        "investor_label": label,
        "risk_score": risk_score,
        "horizon_years": horizon_map.get(period_label, 3),
        "interest_tags": interests
    }

# 버튼 클릭 시 프로필 생성해서 세션에 저장
if st.sidebar.button("설문 완료 & 추천 시작"):
    answers = [q2, q3, q4, q5, q6]
    label, base_risk = classify_investor(answers)
    profile = generate_investor_profile(label, base_risk, q1, interests)
    st.sidebar.success(f"{label}으로 분류되었습니다!")
    st.session_state["profile"] = profile
    st.session_state["keywords"] = kws

# ─── 메인 화면 ─────────────────────────────────────────────
st.set_page_config(page_title="HyperCLOVA 금융추천", layout="wide")
st.title("HyperCLOVA X 기반 맞춤형 금융상품 추천")

if "profile" in st.session_state:
    prof = st.session_state["profile"]
    kws  = st.session_state["keywords"]

    # 1) 오늘 뉴스 크롤링
    crawl_today_news(kws)
    news_db = load_json(NEWS_DB_PATH)
    today   = max(news_db.keys())
    items   = news_db[today][:10]

    # 2) 뉴스 요약 & 태그
    st.subheader("뉴스 요약 & 태그")
    tags_accum = []
    for it in items:
        cnt     = it["title"] + "\n" + it["description"]
        summary = summarize_text(cnt)
        tags    = classify_content(cnt).get("themes", [])
        tags_accum += tags

        with st.expander(it["title"]):
            st.write(summary)
            st.caption("태그: " + ", ".join(tags))
            st.markdown(f"[원문 보기]({it['link']})")

    # 3) 테마 병합 후 추천
    market_themes = list(set(kws + tags_accum))
    # 상품 DB 예시
    PRODUCTS_DB = [
        {"name":"EMP 분산 펀드","risk":0.5,"themes":["자산배분","ETF"],"description":"여러 ETF 분산투자"},
        {"name":"TDF 2045","risk":0.3,"themes":["장기","채권"],"description":"은퇴 타깃 리밸런싱"},
        {"name":"글로벌 리츠","risk":0.4,"themes":["리츠","부동산"],"description":"안정적 부동산 배당"},
        {"name":"고정쿠폰 ELS","risk":0.8,"themes":["구조화상품"],"description":"조기상환형 ELS"},
        {"name":"Pre-IPO 펀드","risk":0.9,"themes":["프리IPO"],"description":"미상장 스타트업 투자"},
        {"name":"인프라 ETF","risk":0.6,"themes":["인프라"],"description":"도로·데이터센터 투자"},
        {"name":"AI 스마트베타","risk":0.6,"themes":["AI"],"description":"AI 팩터 기반 ETF"}
    ]

    def recommend_products(profile, themes):
        scored=[]
        for p in PRODUCTS_DB:
            rs = 1 - abs(profile["risk_score"] - p["risk"])
            ts = len(set(profile["interest_tags"] + themes) & set(p["themes"])) \
                 / (len(p["themes"]) + 1e-5)
            scored.append((0.6*rs + 0.4*ts, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:3]]

    recs = recommend_products(prof, market_themes)

    # 4) 추천 상품 표시
    st.subheader("추천 상품")
    for p in recs:
        st.markdown(f"### {p['name']} （위험도 {p['risk']}）")
        st.write(p["description"])
        st.write("테마:", ", ".join(p["themes"]))

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

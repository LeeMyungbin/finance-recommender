import os, json, hashlib, requests
from datetime import datetime
from collections import Counter
import streamlit as st
from hyperclova_api import classify_content, summarize_text, chat_completion

# — 환경변수 읽기
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
NEWS_DB_PATH  = "news_data.json"

# — 유틸
def today_str(): return datetime.now().strftime("%Y-%m-%d")
def make_hash(t, l): return hashlib.md5((t+l).encode()).hexdigest()
def load_json(p): return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
def save_json(o,p): json.dump(o, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

# — 뉴스 크롤링
def get_news(q):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id":CLIENT_ID, "X-Naver-Client-Secret":CLIENT_SECRET}
    try:
        r=requests.get(url, headers=headers, params={"query":q,"display":20,"sort":"date"},timeout=5)
        r.raise_for_status()
        return r.json().get("items",[])
    except:
        return []

def crawl_today_news(keywords):
    db = load_json(NEWS_DB_PATH)
    d = today_str()
    db.setdefault(d, [])
    seen = {make_hash(n["title"],n["link"]) for n in db[d]}
    for kw in keywords:
        for it in get_news(kw):
            h = make_hash(it["title"], it["link"])
            if h not in seen:
                db[d].append({
                    "title":it["title"], "description":it["description"],
                    "pubDate":it["pubDate"], "link":it["link"], "query":kw})
                seen.add(h)
    save_json(db, NEWS_DB_PATH)

# — 프로필 생성
def generate_investor_profile(r):
    rm={"매우 보수적":0.1,"보수적":0.3,"중립":0.5,"공격적":0.7,"매우 공격적":0.9}
    hm={"단기":1,"중기":3,"장기":5}
    return {"risk_score":rm[r["risk_level"]],"horizon_years":hm[r["horizon"]],"interest_tags":r["interests"]}

# — 상품 DB
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
        rs = 1 - abs(profile["risk_score"]-p["risk"])
        ts = len(set(profile["interest_tags"]+themes)&set(p["themes"]))/(len(p["themes"])+1e-5)
        scored.append((0.6*rs + 0.4*ts, p))
    scored.sort(key=lambda x:x[0], reverse=True)
    return [p for _,p in scored[:3]]

# — Streamlit UI
st.set_page_config(page_title="HyperCLOVA 금융추천", layout="wide")
st.title("HyperCLOVA X 기반 맞춤형 금융상품 추천")

with st.sidebar:
    st.header("투자 성향 설문")
    age       = st.slider("연령대",20,60,30)
    risk      = st.selectbox("위험 성향",["매우 보수적","보수적","중립","공격적","매우 공격적"])
    horizon   = st.selectbox("투자 기간",["단기","중기","장기"])
    interests = st.multiselect("관심 분야",["인프라","ETF","TDF","EMP","프리IPO","구조화"])
    kws       = st.multiselect("뉴스 키워드",["금리", "ETF", "인프라", "AI", "프리IPO", "채권"], default=["금리", "ETF"])

    if st.button("프로필 생성"):
        prof = generate_investor_profile({"risk_level":risk,"horizon":horizon,"interests":interests})
        st.session_state.profile  = prof
        st.session_state.keywords = kws

if "profile" in st.session_state:
    prof = st.session_state.profile
    kws  = st.session_state.keywords
    crawl_today_news(kws)
    db    = load_json(NEWS_DB_PATH)
    today = max(db.keys())
    items = db[today][:10]

    st.subheader("뉴스 요약 & 태그")
    tags_accum=[]
    for it in items:
        cnt     = it["title"]+"\n"+it["description"]
        summary = summarize_text(cnt)
        tags    = classify_content(cnt).get("themes", [])
        tags_accum += tags
        with st.expander(it["title"]):
            st.write(summary)
            st.caption("태그: "+", ".join(tags))
            st.markdown(f"[원문]({it['link']})")

    market_themes = list(set(kws + tags_accum))
    recs = recommend_products(prof, market_themes)

    st.subheader("추천 상품")
    for p in recs:
        st.markdown(f"### {p['name']} ({p['risk']})")
        st.write(p["description"])
        st.write("테마:", ", ".join(p["themes"]))

    st.subheader("챗봇 Q&A")
    q = st.text_input("궁금한 내용을 입력하세요")
    if q:
        # 프로필·추천 리스트를 문자열로 직렬화
        prompt = (
            f"사용자 프로필: {prof}\n"
            f"추천 상품: {[p['name'] for p in recs]}\n"
            f"질문: {q}"
        )
        answer = chat_completion(prompt)
        st.info(answer)
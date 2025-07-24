#익스플로어어에 있는거롤 요약해보기
# -*- coding: utf-8 -*-
import streamlit as st
import requests
import json
import re
import urllib.parse
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import uuid

# ------------------------------
# 페이지 설정
# ------------------------------
st.set_page_config(page_title="투자자 성향 분석 및 금융뉴스 요약", layout="centered")
st.title("📊 투자자 성향 분석 & 금융 뉴스 요약 추천")

# ------------------------------
# 1단계: 투자자 성향 설문
# ------------------------------
questions = [
    ("1️⃣ 투자 가능 기간은?", {"A": "1년 이하", "B": "1~3년", "C": "3년 이상"}),
    ("2️⃣ 원금 손실 가능성?", {"A": "절대 불가", "B": "감수 가능", "C": "고수익이면 감수"}),
    ("3️⃣ 가장 중요한 요소는?", {"A": "안정성", "B": "균형", "C": "수익성"}),
    ("4️⃣ 관심 키워드?", {"A": "금리, 채권", "B": "ETF, 지수", "C": "기술주, AI"}),
    ("5️⃣ 투자 경험?", {"A": "예적금", "B": "ETF·펀드", "C": "직접 주식/코인"}),
    ("6️⃣ 투자 자산 비율?", {"A": "10% 이하", "B": "10~30%", "C": "30% 이상"}),
    ("7️⃣ 선호 투자 방식?", {"A": "3% 확정 수익", "B": "10% 기대 수익", "C": "20% 기대, 손실 감수"})
]
answers = [st.radio(q, list(opts), format_func=lambda x, opts=opts: opts[x], key=f"q{i}") for i, (q, opts) in enumerate(questions)]

def classify_investor(ans):
    count = {"A": ans.count("A"), "B": ans.count("B"), "C": ans.count("C")}
    return "🟦 안정형 투자자" if count["A"] >= 4 else ("🟥 공격형 투자자" if count["C"] >= 4 else "🟨 중립형 투자자")

if st.button("✅ 투자 성향 분석하기"):
    investor_type = classify_investor(answers)
    st.success(f"당신은 **{investor_type}** 입니다!")

# ------------------------------
# 2단계: 관심 키워드 선택
# ------------------------------
st.markdown("---")
st.markdown("### 🔍 관심 있는 경제 키워드를 선택하세요")
default_keywords = ["금리", "ETF", "채권", "주식", "TDF", "물가", "경기침체", "환율", "연준", "인플레이션"]
selected_keywords = st.multiselect("키워드 선택 (최대 3개)", default_keywords, max_selections=3)

# ------------------------------
# API KEY 설정
# ------------------------------
CLIENT_ID = "r9LA_NX9CVuHhnhhoVOg"
CLIENT_SECRET = "kQWtIytPZX"
CLOVA_API_KEY = "nv-5e40cb6c29fc4a809841fab999de0e3dbe4f"

# ------------------------------
# 뉴스 수집 및 필터링
# ------------------------------
def clean_text(text):
    return re.sub(r"<[^>]+>|&[^;\s]+;", "", text)

def get_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    encoded_query = urllib.parse.quote(query)
    url_with_query = f"{url}?query={encoded_query}&display=20&sort=date"
    res = requests.get(url_with_query, headers=headers)
    return res.json().get("items", []) if res.status_code == 200 else []

def filter_recent_news(items, days=2):
    today = datetime.now().date()
    threshold = today - timedelta(days=days)
    filtered = []
    for item in items:
        try:
            news_date = parsedate_to_datetime(item["pubDate"]).date()
            if threshold <= news_date <= today:
                filtered.append(item)
        except:
            continue
    return filtered

def is_relevant_news(item, keywords):
    title = item.get("title", "").lower()
    desc = item.get("description", "").lower()
    for kw in keywords:
        if kw.lower() in title or kw.lower() in desc:
            return True
    return False

def crawl_news(queries, keywords):
    results = []
    for q in queries:
        for item in filter_recent_news(get_news(q)):
            if is_relevant_news(item, keywords):
                results.append({
                    "title": clean_text(item["title"]),
                    "description": clean_text(item["description"]),
                    "pubDate": item["pubDate"],
                    "link": item["link"],
                    "query": q
                })
    return results

# ------------------------------
# 요약 API 호출
# ------------------------------
def summarize_text(text, api_key=CLOVA_API_KEY):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4())
    }
    data = {
        "texts": [text],
        "autoSentenceSplitter": True,
        "segCount": -1,
        "segMaxSize": 1000,
        "segMinSize": 300,
        "includeAiFilters": False
    }
    url = "https://clovastudio.stream.ntruss.com/v1/api-tools/summarization/v2"
    res = requests.post(url, headers=headers, json=data)
    if res.status_code == 200:
        return res.json()["result"]["text"]
    else:
        return f"❌ 요약 실패: {res.text}"

# ------------------------------
# 3단계: 뉴스 수집 및 요약 실행
# ------------------------------
if selected_keywords:
    st.markdown("### 📰 추천 뉴스 목록")
    news_list = crawl_news(selected_keywords, selected_keywords)

    if news_list:
        for i, news in enumerate(news_list):
            with st.expander(f"🔎 {i+1}. {news['title']}"):
                st.markdown(f"- 🕒 {news['pubDate']}")
                st.markdown(f"- 📄 {news['description']}")
                st.markdown(f"[📰 원문 링크]({news['link']})")

                if st.button(f"이 뉴스 요약하기", key=f"sum_{i}"):
                    with st.spinner("요약 중..."):
                        summary = summarize_text(news["title"] + " " + news["description"])
                        st.success("📌 요약 결과")
                        st.write(summary)
    else:
        st.info("🔍 최근 뉴스가 없거나 키워드와 관련된 뉴스가 없습니다.")

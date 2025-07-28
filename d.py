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
# API KEY 설정
# ------------------------------
CLIENT_ID = "r9LA_NX9CVuHhnhhoVOg"
CLIENT_SECRET = "kQWtIytPZX"
CLOVA_API_KEY = "nv-5e40cb6c29fc4a809841fab999de0e3dbe4f"

# ------------------------------
# 페이지 설정
# ------------------------------
st.set_page_config(page_title="투자자 성향 분석 및 뉴스 기반 추천", layout="centered")
st.title("\U0001F4CA 투자자 성향 분석 & Clova X 기반 금융상품 추천")

# ------------------------------
# 투자자 성향 설문
# ------------------------------
questions = [
    ("1\u20e3\ufe0f 투자 가능 기간은?", {"A": "1년 이하", "B": "1~3년", "C": "3년 이상"}),
    ("2\u20e3\ufe0f 원금 손실 가능성?", {"A": "절대 불가", "B": "감수 가능", "C": "고수익이면 감수"}),
    ("3\u20e3\ufe0f 가장 중요한 요소는?", {"A": "안정성", "B": "균형", "C": "수익성"}),
    ("4\u20e3\ufe0f 관심 키워드?", {"A": "금리, 채권", "B": "ETF, 지수", "C": "기술주, AI"}),
    ("5\u20e3\ufe0f 투자 경험?", {"A": "예적금", "B": "ETF·펀드", "C": "직접 주식/코인"}),
    ("6\u20e3\ufe0f 투자 자산 비율?", {"A": "10% 이하", "B": "10~30%", "C": "30% 이상"}),
    ("7\u20e3\ufe0f 선호 투자 방식?", {"A": "3% 확정 수익", "B": "10% 기대 수익", "C": "20% 기대, 손실 감수"})
]
answers = [st.radio(q, list(opts), format_func=lambda x, opts=opts: opts[x], key=f"q{i}") for i, (q, opts) in enumerate(questions)]


def classify_investor(ans):
    count = {"A": ans.count("A"), "B": ans.count("B"), "C": ans.count("C")}
    if count["A"] >= 4:
        return "\U0001F7E6 안정형 투자자"
    elif count["C"] >= 4:
        return "\U0001F7E5 공격형 투자자"
    else:
        return "\U0001F7E8 중립형 투자자"

if st.button("✅ 투자 성향 분석하기"):
    investor_type = classify_investor(answers)
    st.session_state.investor_type = investor_type
    st.success(f"당신은 **{investor_type}** 입니다!")

# ------------------------------
# 관심 키워드 선택
# ------------------------------
st.markdown("---")
st.markdown("### \U0001F50D 관심 있는 경제 키워드를 선택하세요")
default_keywords = ["금리", "ETF", "채권", "주식", "TDF", "물가", "경기침체", "환율", "연준", "인플레이션"]
selected_keywords = st.multiselect("키워드 선택 (최대 3개)", default_keywords, max_selections=3)

# ------------------------------
# 뉴스 수집 및 정제
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
    return [item for item in items if 'pubDate' in item and parsedate_to_datetime(item["pubDate"]).date() >= threshold]

def is_relevant_news(item, keywords):
    title = item.get("title", "").lower()
    desc = item.get("description", "").lower()
    return any(kw.lower() in title or kw.lower() in desc for kw in keywords)

def crawl_news(queries, keywords):
    results = []
    for q in queries:
        for item in filter_recent_news(get_news(q), days=2):
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
# Clova Prompt 개선: 뉴스 기반 영향 분석 + 성향 기반 추천
# ------------------------------
def get_clova_contextual_recommendation(news_summary, investor_profile):
    url = "https://clovastudio.stream.ntruss.com/testapp/v1/chat-completions/HCX-DASH-001"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLOVA_API_KEY}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4())
    }
    prompt = f"""
당신은 금융시장 분석과 맞춤형 투자 추천을 제공하는 AI 금융 어드바이저입니다.

[뉴스 내용]
{news_summary}

[투자자 성향]
{investor_profile}

[요청]
1. 위 뉴스가 금융시장에 미칠 영향을 2~3줄로 요약
2. 이 뉴스가 해당 투자자의 포트폴리오에 어떤 위험/기회를 줄 수 있는지 설명
3. 이 상황에서 투자자에게 적절한 금융상품 2~3개를 추천하고, 각각의 추천 사유를 뉴스 및 투자 성향과 연계하여 설명
"""
    data = {
        "messages": [
            {"role": "system", "content": "당신은 금융시장 기반 추천을 제공하는 AI 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        "topP": 0.9,
        "topK": 0,
        "temperature": 0.7,
        "maxTokens": 1200
    }
    res = requests.post(url, headers=headers, json=data)
    if res.status_code == 200:
        return res.json()["result"]["message"]["content"]
    else:
        return f"\u274c 추천 실패: {res.text}"

# ------------------------------
# 3단계: 뉴스 출력 및 Clova 호출 실행
# ------------------------------
if selected_keywords:
    st.markdown("### \U0001F4F0 추천 뉴스 목록")
    news_list = crawl_news(selected_keywords, selected_keywords)

    if news_list:
        for i, news in enumerate(news_list):
            with st.expander(f"\U0001F50E {i+1}. {news['title']}"):
                st.markdown(f"- \U0001F552 {news['pubDate']}")
                st.markdown(f"- \U0001F4C4 {news['description']}")
                st.markdown(f"[\U0001F4F0 원문 링크]({news['link']})")

                if st.button(f"\U0001F916 뉴스 분석 기반 추천 받기", key=f"clova_{i}"):
                    if "investor_type" not in st.session_state:
                        st.warning("먼저 투자 성향 분석을 진행해주세요.")
                    else:
                        with st.spinner("Clova AI가 요약 및 추천 중..."):
                            summary_input = news['title'] + ". " + news['description']
                            profile = st.session_state.investor_type
                            result = get_clova_contextual_recommendation(summary_input, profile)
                            st.success("\U0001F4DD 분석 및 추천 결과")
                            st.markdown(result)
    else:
        st.info("\U0001F50D 최근 뉴스가 없거나 키워드와 관련된 뉴스가 없습니다.")

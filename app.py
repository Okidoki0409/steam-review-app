import streamlit as st
import requests
import csv
import time
from datetime import datetime, date
from io import StringIO

# -----------------------
# 게임 리스트 (이름 → App ID 매핑)
# -----------------------
game_options = {
    "inZOI": "2456740",
    "Dinkum": "1062520",
    "Subnautica 2": "1962700",
    "PUBG: Blindspot": "3143710"
}

# -----------------------
# Streamlit UI
# -----------------------
st.title("🎮 Steam Review Collector")

selected_game = st.selectbox("Select a game", list(game_options.keys()))
language = st.selectbox("Select a language", [
    "all", "english", "koreana", "schinese", "japanese",
    "german", "french", "spanish", "brazilian", "italian", "polish"
])
date_range = st.date_input("Select date range", [date(2025, 3, 1), date.today()])
sentiment = st.radio("Recommendation filter", ["All", "Positive only", "Negative only"])

run = st.button("Start review collection")

if run:
    app_id = game_options[selected_game]
    API_URL = f"https://store.steampowered.com/appreviews/{app_id}"

    params = {
        "json": 1,
        "language": language,
        "filter": "recent",
        "num_per_page": 100,
        "cursor": "*",
        "purchase_type": "all"
    }

    all_reviews = []
    seen_keys = set()

    st.write("🚀 Collecting reviews...")
    progress = st.progress(0)
    count = 0

    while True:
        response = requests.get(API_URL, params=params, timeout=10)
        data = response.json()

        reviews = data.get("reviews", [])
        if not reviews:
            break

        for review in reviews:
            steamid = review["author"]["steamid"]
            timestamp = review["timestamp_created"]
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            language_code = review["language"]
            key = f"{steamid}_{timestamp}"

            if key in seen_keys:
                continue
            seen_keys.add(key)

            # 필터 적용
            review_date = datetime.fromtimestamp(timestamp).date()
            if not (date_range[0] <= review_date <= date_range[1]):
                continue

            if sentiment == "Positive only" and not review["voted_up"]:
                continue
            if sentiment == "Negative only" and review["voted_up"]:
                continue

            all_reviews.append({
                "Votes Up": review.get("votes_up", 0),
                "Author": steamid,
                "Recommended": "👍" if review["voted_up"] else "👎",
                "Review": review["review"].replace("\n", " ").strip(),
                "Posted At": date_str,
                "Language": language_code
            })

        count += len(reviews)
        progress.progress(min((count % 1000) / 1000, 1.0))
        params["cursor"] = data.get("cursor")
        time.sleep(0.2)

    st.success(f"✅ Collected {len(all_reviews)} reviews!")

    # 리뷰 요약 표시
    from collections import Counter
    import pandas as pd

    # 긍정/부정 리뷰 추출
    positive_reviews = [r for r in all_reviews if r["Recommended"] == "👍"]
    negative_reviews = [r for r in all_reviews if r["Recommended"] == "👎"]
    
    def get_top_reviews(reviews, n=3):
        return sorted(
            reviews,
            key=lambda r: r.get("Votes Up", 0),
            reverse=True
        )[:n]

    # 간단 요약 생성 함수
    def summarize(text, max_words=30):
        words = text.split()
        return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")
    st.subheader("📊 Review Summary")
    total = len(all_reviews)
    positives = sum(1 for r in all_reviews if r["Recommended"] == "👍")
    negatives = total - positives
    lang_counts = {}
    for r in all_reviews:
        lang = r["Language"]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    st.markdown(f"**Total Reviews:** {total}")
    st.markdown(f"**👍 Positive:** {positives}")
    st.markdown(f"**👎 Negative:** {negatives}")

    st.markdown("**Language Distribution:**")
    for lang, count in lang_counts.items():
        st.markdown(f"- {lang}: {count}")

    # 날짜별 리뷰 수 시각화
    
    date_counts = Counter(r["Posted At"][:10] for r in all_reviews)
    date_df = pd.DataFrame(sorted(date_counts.items()), columns=["Date", "Count"])
    st.bar_chart(date_df.set_index("Date"))

    
    # 주요 리뷰 표시
    st.markdown("**🔍 Most Notable Positive Reviews:**")
    for r in get_top_reviews(positive_reviews):
        st.markdown(f"- {summarize(r['Review'])}")

    st.markdown("**🔍 Most Notable Negative Reviews:**")
    for r in get_top_reviews(negative_reviews):
        st.markdown(f"- {summarize(r['Review'])}")

    # CSV 변환
    if all_reviews:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=all_reviews[0].keys())
        writer.writeheader()
        writer.writerows(all_reviews)
        st.download_button(
            label="📥 Download CSV file",
            data=output.getvalue().encode("utf-8"),
            file_name=f"{selected_game}_reviews.csv",
            mime="text/csv"
        )

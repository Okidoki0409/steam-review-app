import streamlit as st
import requests
import csv
import time
from datetime import datetime, date
from io import StringIO, BytesIO
import pandas as pd
import xlsxwriter  # ✅ 추가: Excel 저장용 엔진 필요

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

selected_game = st.selectbox("**Select a game**", list(game_options.keys()))
language = st.selectbox("**Select a language**", [
    "all", "english", "koreana", "schinese", "japanese",
    "german", "french", "spanish", "brazilian", "italian", "polish"
])
date_range = st.date_input("**Select date range**", [date(2025, 3, 1), date.today()])
sentiment = st.radio("**Filter**", ["All", "Positive only", "Negative only"])

playtime_filter = st.checkbox("Only include reviews with ≥ 1hr playtime")
purchased_filter = st.checkbox("Only include reviews from purchased users")
votes_range = st.slider("**Votes Up Range (100+ included)**",
    min_value=0,
    max_value=100,
    value=(0, 100),
    step=1
)

run = st.button("**🚀 Start Review Collection**", type="primary")

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

            playtime_hrs = review['author'].get('playtime_at_review', 0) / 60
            purchased = review.get("steam_purchase")
            votes_up = review.get("votes_up", 0)

            if playtime_filter and playtime_hrs < 1.0:
                continue
            if purchased_filter and not purchased:
                continue
            if votes_up < votes_range[0]:
                continue
            seen_keys.add(key)

            review_date = datetime.fromtimestamp(timestamp).date()
            if not (date_range[0] <= review_date <= date_range[1]):
                continue

            if sentiment == "Positive only" and not review["voted_up"]:
                continue
            if sentiment == "Negative only" and review["voted_up"]:
                continue

            all_reviews.append({
                "Votes Up": votes_up,
                "Playtime (hrs)": "{:.1f} hrs".format(playtime_hrs),
                "Purchased": "✅" if purchased else "❌",
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

    from collections import Counter

    def get_top_reviews(reviews, n=3):
        return sorted(
            reviews,
            key=lambda r: r.get("Votes Up", 0),
            reverse=True
        )[:n]

    def summarize(text, max_words=30):
        words = text.split()
        return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")

    # ➕ 긍정/부정 리뷰 리스트 만들기
    positive_reviews = [r for r in all_reviews if r["Recommended"] == "👍"]
    negative_reviews = [r for r in all_reviews if r["Recommended"] == "👎"]

    st.subheader("📊 Review Summary")
    total = len(all_reviews)
    positives = len(positive_reviews)
    negatives = len(negative_reviews)

    lang_counts = {}
    for r in all_reviews:
        lang = r["Language"]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    def get_review_grade(positive_ratio, total_reviews):
        if total_reviews < 50:
            return "Not enough data"
        if total_reviews >= 500:
            if positive_ratio >= 0.95:
                return "Overwhelmingly Positive"
            elif positive_ratio <= 0.05:
                return "Overwhelmingly Negative"
        if positive_ratio >= 0.80:
            return "Very Positive"
        elif positive_ratio >= 0.70:
            return "Mostly Positive"
        elif positive_ratio >= 0.40:
            return "Mixed"
        elif positive_ratio >= 0.20:
            return "Mostly Negative"
        elif positive_ratio >= 0.05:
            return "Very Negative"
        else:
            return "Overwhelmingly Negative"

    review_grade = get_review_grade(positives / total, total)
    st.markdown(f"**🔎 Overall Review Rating:** _{review_grade}_")

    st.markdown(f"**Total Reviews:** {total}")
    st.markdown(f"**👍 Positive:** {positives}")
    st.markdown(f"**👎 Negative:** {negatives}")

    purchased_count = sum(1 for r in all_reviews if r["Purchased"] == "✅")
    st.markdown(f"**🛒 Purchased Users:** {purchased_count} / {total} ({purchased_count / total:.1%})")

    def parse_hrs(text):
        try:
            return float(text.replace(" hrs", ""))
        except:
            return 0

    avg_playtime = sum(parse_hrs(r["Playtime (hrs)"]) for r in all_reviews) / total
    st.markdown(f"**⏱ Average Playtime:** {avg_playtime:.1f} hrs")

    short_reviews = sum(1 for r in all_reviews if parse_hrs(r["Playtime (hrs)"]) < 1.0)
    st.markdown(f"**⚠️ Reviews under 1 hour:** {short_reviews} ({short_reviews / total:.1%})")

    st.markdown("**Language Distribution:**")
    for lang, count in lang_counts.items():
        st.markdown(f"- {lang}: {count}")

    date_counts = Counter(r["Posted At"][:10] for r in all_reviews)
    date_df = pd.DataFrame(sorted(date_counts.items()), columns=["Date", "Count"])
    st.bar_chart(date_df.set_index("Date"))

    st.markdown("**🔍 Most Notable Positive Reviews:**")
    for r in get_top_reviews(positive_reviews):
        st.markdown(f"- {summarize(r['Review'])}")

    st.markdown("**🔍 Most Notable Negative Reviews:**")
    for r in get_top_reviews(negative_reviews):
        st.markdown(f"- {summarize(r['Review'])}")

    if all_reviews:
        # CSV 다운로드
        output_csv = StringIO()
        writer = csv.DictWriter(output_csv, fieldnames=all_reviews[0].keys())
        writer.writeheader()
        writer.writerows(all_reviews)
        st.download_button(
            label="📥 Download CSV file",
            data=output_csv.getvalue().encode("utf-8"),
            file_name=f"{selected_game}_reviews.csv",
            mime="text/csv"
        )

        # Excel 다운로드
        df = pd.DataFrame(all_reviews)
        output_excel = BytesIO()
        writer = pd.ExcelWriter(output_excel, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Reviews')
        writer.close()
        st.download_button(
            label="📥 Download Excel file",
            data=output_excel.getvalue(),
            file_name=f"{selected_game}_reviews.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

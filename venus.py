import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
from astro_analysis import (
    parse_uploaded_files,
    filter_matching_tickers,
    get_user_aspect_config,
    render_aspect_table,
    render_aspect_heatmap
)
from PIL import Image

# Load and display logo
try:
    logo = Image.open("FullLogo_NoBuffer.jpg")
    st.image(logo, width=300)
except FileNotFoundError:
    st.title("🌕 Luna Lira: The Oracle")

st.title("🌌 Luna Lira: Finviz-Filtered IPO Analyzer")
st.markdown("Upload your IPO and Finviz files to begin.")

ipo_file = st.file_uploader("📥 Upload IPO CSV File", type=["csv"])
finviz_file = st.file_uploader("📥 Upload Finviz Export CSV", type=["csv"])

# 🔮 Core Aspect Calculation Functions

def generate_datetimes(start_date, end_date, time_start, time_end, step_minutes=30):
    current_date = start_date
    while current_date <= end_date:
        dt_start = datetime.combine(current_date, time_start)
        dt_end = datetime.combine(current_date, time_end)
        current_dt = dt_start
        while current_dt <= dt_end:
            yield current_dt
            current_dt += timedelta(minutes=step_minutes)
        current_date += timedelta(days=1)

def calculate_aspects_at_datetime(ticker, dt, matched_df, aspect_config):
    """
    PLACEHOLDER: Replace with your real aspect logic.
    This should return a DataFrame of aspects at this datetime.
    """
    # Example structure
    return pd.DataFrame([{
        "Ticker": ticker,
        "Source": "IPO",
        "Planet1": "Sun",
        "Planet2": "Moon",
        "Aspect": "Conjunction",
        "Score": aspect_config.get("Conjunction", {}).get("score", 5),
        "Datetime": dt
    }])

def calculate_aspects_for_ticker(ticker, matched_df, start_date, end_date, time_start, time_end, aspect_config):
    all_results = []

    for dt in generate_datetimes(start_date, end_date, time_start, time_end):
        try:
            aspects_df = calculate_aspects_at_datetime(ticker, dt, matched_df, aspect_config)
            aspects_df["Datetime"] = dt
            all_results.append(aspects_df)
        except Exception as e:
            print(f"⚠️ Error at {dt} for {ticker}: {e}")

    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

# 🧠 Main App Logic

if ipo_file and finviz_file:
    ipo_df, finviz_df = parse_uploaded_files(ipo_file, finviz_file)
    st.success("✅ IPO File Sample:")
    st.write(ipo_df.head())
    st.success("✅ Finviz File Sample:")
    st.write(finviz_df.head())

    matched_df = filter_matching_tickers(ipo_df, finviz_df)
    st.success("✅ Matching IPOs with Finviz tickers:")
    st.write(matched_df)

    ticker_options = matched_df["Ticker"].unique().tolist()
    selected_tickers = st.multiselect("🎯 Select tickers to analyze", ticker_options)

    with st.sidebar:
        start_date, end_date = st.date_input(
            "📅 Select date range",
            value=(datetime.today().date(), datetime.today().date())
        )
        time_start, time_end = st.slider(
            "⏰ Time of day range",
            min_value=time(0, 0),
            max_value=time(23, 59),
            value=(time(9, 30), time(16, 0)),
            step=timedelta(minutes=15)
        )

        st.subheader("🔧 Aspect Configuration")
        aspect_scores = {}
        aspect_orbs = {}

        aspect_types = ['Conjunction', 'Opposition', 'Trine', 'Sextile', 'Square',
                        'Quincunx', 'Semisextile', 'Semisquare', 'Sesquisquare']

        default_scores = {
            'Conjunction': 5, 'Opposition': -5, 'Trine': 3, 'Sextile': 2,
            'Square': -3, 'Quincunx': -1, 'Semisextile': 1,
            'Semisquare': -1, 'Sesquisquare': -1
        }

        default_orbs = {
            'Conjunction': 5, 'Opposition': 5, 'Trine': 3, 'Sextile': 3,
            'Square': 3, 'Quincunx': 2, 'Semisextile': 2,
            'Semisquare': 2, 'Sesquisquare': 2
        }

        for aspect in aspect_types:
            aspect_scores[aspect] = st.slider(
                f"{aspect} Score", -5, 5, default_scores[aspect]
            )
        for aspect in aspect_types:
            aspect_orbs[aspect] = st.slider(
                f"{aspect} Orb ±°", 1, 10, default_orbs[aspect]
            )

    aspect_config = get_user_aspect_config(aspect_orbs, aspect_scores)
    min_score = st.slider("🔍 Filters: Minimum Aspect Score", -5, 5, -5)

    if st.button("🔮 Run Analysis"):
        for ticker in selected_tickers:
            st.markdown(f"### 🔮 Aspect Analysis for {ticker}")
            try:
                result_df = calculate_aspects_for_ticker(
                    ticker=ticker,
                    matched_df=matched_df,
                    start_date=start_date,
                    end_date=end_date,
                    time_start=time_start,
                    time_end=time_end,
                    aspect_config=aspect_config
                )
                result_df = result_df[result_df["Score"] >= min_score]

                ipo_aspects = result_df[result_df["Source"] == "IPO"]
                nyse_aspects = result_df[result_df["Source"] == "NYSE"]
                transit_aspects = result_df[result_df["Source"] == "Transit"]

                st.markdown("#### 🌱 IPO Aspects")
                render_aspect_table(ipo_aspects)

                st.markdown("#### 🏛️ NYSE Aspects")
                render_aspect_table(nyse_aspects)

                st.markdown("#### 🌌 Transit-to-Transit Aspects")
                render_aspect_table(transit_aspects)

                st.markdown("#### 📈 Aspect Score Summary")
                render_aspect_heatmap(result_df)

            except Exception as e:
                st.error(f"Error analyzing {ticker}: {e}")

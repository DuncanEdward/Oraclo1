import streamlit as st
import pandas as pd
from datetime import datetime, time
from astro_analysis import (
    parse_uploaded_files,
    filter_matching_tickers,
    get_user_aspect_config,
    calculate_aspects_for_ticker,
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

# --- Helper to manage multiple time inputs in the UI ---
def ensure_default_times():
    if "times_of_day" not in st.session_state:
        # Sensible defaults for market open/close checks
        st.session_state.times_of_day = [time(9, 30), time(16, 0)]

def render_time_inputs():
    ensure_default_times()
    st.subheader("🕒 Times of day")
    st.caption("Add one or more times to evaluate (e.g., 09:30 and 16:00).")
    # Show current times with editable inputs
    new_times = []
    for idx, t in enumerate(st.session_state.times_of_day):
        new_t = st.time_input(f"Time #{idx+1}", value=t, key=f"time_input_{idx}")
        new_times.append(new_t)

    cols = st.columns(2)
    with cols[0]:
        if st.button("➕ Add time"):
            new_times.append(time(10, 0))  # quick default
    with cols[1]:
        if len(new_times) > 1 and st.button("➖ Remove last time"):
            new_times = new_times[:-1]

    st.session_state.times_of_day = new_times
    return st.session_state.times_of_day

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
        start_date = st.date_input("📅 Start date", datetime.today())
        end_date = st.date_input("📅 End date", datetime.today())
        # Replaced single time input with multi-time UI (shown in main area)
        st.markdown("Times are configured in the main panel ↓")

    # --- Aspect configuration ---
    st.subheader("🔧 Aspect Configuration")
    aspect_scores = {}
    aspect_orbs = {}

    aspect_types = [
        'Conjunction', 'Opposition', 'Trine', 'Sextile', 'Square',
        'Quincunx', 'Semisextile', 'Semisquare', 'Sesquisquare'
    ]

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

    # NEW: multi-time selection UI
    times_of_day = render_time_inputs()

    if st.button("🔮 Run Analysis"):
        if not selected_tickers:
            st.info("Select at least one ticker to analyze.")
        else:
            for ticker in selected_tickers:
                st.markdown(f"## 🔮 Aspect Analysis for **{ticker}**")

                try:
                    all_results = []

                    # Run analysis for EACH requested time of day
                    for t in times_of_day:
                        result_df = calculate_aspects_for_ticker(
                            ticker, matched_df, start_date, end_date, t, aspect_config
                        )
                        # Tag which time this run corresponds to (for filtering/heatmaps)
                        result_df = result_df.copy()
                        result_df["Time"] = t.strftime("%H:%M")
                        all_results.append(result_df)

                    # Combine all time slices
                    result_df = pd.concat(all_results, ignore_index=True)

                    # Apply min score filter
                    result_df = result_df[result_df["Score"] >= min_score]

                    # Keep a clean Date column if not present
                    if "Date" not in result_df.columns:
                        # If your calculate_aspects_for_ticker returns a datetime column, adjust below:
                        # result_df["Date"] = pd.to_datetime(result_df["Datetime"]).dt.date
                        result_df["Date"] = pd.to_datetime(result_df["Timestamp"]).dt.date if "Timestamp" in result_df.columns else None

                    # Split per source as before
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

                    # --- NEW: Date × Time heatmap-style pivot (quick glance) ---
                    st.markdown("#### 🗺️ Heatmap by Date × Time")
                    # Aggregate (sum) scores for each Date/Time; adapt if you prefer mean/max
                    if "Date" in result_df.columns:
                        pivot = (
                            result_df
                            .groupby(["Date", "Time"], as_index=False)["Score"]
                            .sum()
                            .pivot(index="Date", columns="Time", values="Score")
                            .sort_index()
                        )
                        # Show with basic gradient styling for quick readability
                        try:
                            st.dataframe(
                                pivot.style.background_gradient(axis=None)
                            )
                        except Exception:
                            st.dataframe(pivot)
                    else:
                        st.info("No Date column found to render Date × Time pivot.")

                except Exception as e:
                    st.error(f"Error analyzing {ticker}: {e}")

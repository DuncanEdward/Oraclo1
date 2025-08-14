import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
from collections import defaultdict

from astro_analysis import (
    parse_uploaded_files,
    filter_matching_tickers,
    get_user_aspect_config,
    calculate_aspects_for_ticker,
    render_aspect_table,
    render_aspect_heatmap
)

st.title("🌌 Luna Lira: Finviz-Filtered IPO Analyzer")
st.markdown("Upload your IPO and Finviz files to begin.")

# ---------- Uploads ----------
ipo_file = st.file_uploader("📥 Upload IPO CSV File", type=["csv"])
finviz_file = st.file_uploader("📥 Upload Finviz Export CSV", type=["csv"])

# ---------- Helpers ----------
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def dates_between(start_d: datetime.date, end_d: datetime.date):
    d = start_d
    while d <= end_d:
        yield d
        d += timedelta(days=1)

def build_date_to_time_map(start_d, end_d, weekday_time_map):
    """
    Return dict[date -> time] picking the correct time for each date's weekday
    Only dates present in [start_d, end_d] are included.
    """
    out = {}
    for d in dates_between(start_d, end_d):
        wd = d.weekday()  # Monday=0..Sunday=6
        t = weekday_time_map.get(wd)
        if t is not None:
            out[d] = t
    return out

def run_calculations_per_time(
    ticker: str,
    matched_df: pd.DataFrame,
    date_to_time: dict,
    aspect_config: dict
) -> pd.DataFrame:
    """
    Group dates by chosen time, call your existing calculate_aspects_for_ticker
    once per unique time (re-using [min(date_group), max(date_group)]), then
    filter rows to only the exact dates in the group to ensure accuracy.
    """
    if not date_to_time:
        return pd.DataFrame()

    # Group dates by time
    time_groups = defaultdict(list)
    for d, t in date_to_time.items():
        time_groups[t].append(d)

    parts = []
    for t, dates_list in time_groups.items():
        start_d = min(dates_list)
        end_d = max(dates_list)

        # Call existing function with the *group's* time
        df = calculate_aspects_for_ticker(
            ticker=ticker,
            matched_df=matched_df,
            start_date=start_d,
            end_date=end_d,
            time_of_day=t,
            aspect_config=aspect_config
        )

        # Keep only rows whose date is in dates_list (string-safe)
        keep_dates = set(pd.to_datetime(dates_list))
        # Assuming your result has a datetime column named "Datetime" or "Timestamp".
        # Try both gracefully; adjust if your column name differs.
        datetime_col = None
        for candidate in ("Datetime", "Timestamp", "DateTime", "dt", "date_time"):
            if candidate in df.columns:
                datetime_col = candidate
                break
        if datetime_col is None:
            # Fallback: if you already output a "Date" column
            if "Date" in df.columns:
                df["_result_date"] = pd.to_datetime(df["Date"]).dt.normalize()
            else:
                # Last resort: try to coerce the first datetime-like column
                for c in df.columns:
                    try:
                        _tmp = pd.to_datetime(df[c], errors="raise")
                        datetime_col = c
                        break
                    except Exception:
                        pass
                if datetime_col is None:
                    # If we truly can't identify, just append as-is
                    parts.append(df)
                    continue

        if datetime_col is not None:
            dt_series = pd.to_datetime(df[datetime_col])
            df = df[dt_series.dt.normalize().isin(keep_dates)]

        parts.append(df)

    if parts:
        return pd.concat(parts, ignore_index=True)
    return pd.DataFrame()

# ---------- Main ----------
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

        st.markdown("### ⏰ Time selection mode")
        mode = st.radio(
            "How do you want to set times?",
            ["Same time every day", "Different time per weekday"],
            horizontal=False
        )

        if mode == "Same time every day":
            same_time = st.time_input("⏰ Time of day", time(10, 0))
            weekday_time_map = {i: same_time for i in range(7)}
        else:
            st.caption("Pick a time for each weekday (leave blank to skip that day).")
            weekday_time_map = {}
            cols = st.columns(2)
            defaults = {
                0: time(10, 0),
                1: time(10, 0),
                2: time(10, 0),
                3: time(10, 0),
                4: time(10, 0),
                5: None,  # weekend default off
                6: None,  # weekend default off
            }
            for i, name in enumerate(WEEKDAYS):
                container = cols[i % 2]
                with container:
                    enabled = st.checkbox(f"{name}", value=(defaults[i] is not None), key=f"wd_enabled_{i}")
                    if enabled:
                        default_time = defaults[i] or time(10, 0)
                        weekday_time_map[i] = st.time_input(f"{name} time", default_time, key=f"wd_time_{i}")
                    else:
                        # explicitly mark as skipped
                        weekday_time_map[i] = None

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
    min_score = st.slider("🔍 Filters: Minimum Aspect Score", -5, 5, 1)

    # ---------- Analysis Button ----------
    if st.button("🔮 Run Analysis"):
        # Build a date -> time map from the chosen mode
        normalized_wtm = {k: v for k, v in weekday_time_map.items() if v is not None}
        date_to_time = build_date_to_time_map(start_date, end_date, normalized_wtm)

        if not date_to_time:
            st.warning("No days selected (or no times set). Please enable at least one weekday/time.")
        else:
            for ticker in selected_tickers:
                st.markdown(f"### 🔮 Aspect Analysis for {ticker}")
                try:
                    # NEW: run in batches per unique time and merge
                    result_df = run_calculations_per_time(
                        ticker=ticker,
                        matched_df=matched_df,
                        date_to_time=date_to_time,
                        aspect_config=aspect_config
                    )

                    if result_df.empty:
                        st.info("No aspects found for the selected dates/times.")
                        continue

                    result_df = result_df[result_df["Score"] >= min_score]

                    ipo_aspects = result_df[result_df["Source"] == "IPO"]
                    nyse_aspects = result_df[result_df["Source"] == "NYSE"]

                    st.markdown("#### IPO Aspects")
                    render_aspect_table(ipo_aspects)

                    st.markdown("#### NYSE Aspects")
                    render_aspect_table(nyse_aspects)

                    st.markdown("#### 📈 Aspect Score Summary")
                    render_aspect_heatmap(result_df)

                except Exception as e:
                    st.error(f"Error analyzing {ticker}: {e}")

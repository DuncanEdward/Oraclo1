import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
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

import pandas as pd
from datetime import datetime, timedelta
import swisseph as swe
import pytz
swe.set_topo(-74.011389, 40.706667, 0)  # NYSE location: 40°42′24″N, 74°00′41″W
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

# Constants
TRANSIT_BODIES = {
    'sun': swe.SUN,
    'moon': swe.MOON,
    'mercury': swe.MERCURY,
    'venus': swe.VENUS,
    'mars': swe.MARS,
    'jupiter': swe.JUPITER,
    'saturn': swe.SATURN,
    'uranus': swe.URANUS,
    'neptune': swe.NEPTUNE,
    'pluto': swe.PLUTO
}

NYSE_NATAL_POSITIONS = {
    'ASC': 103.85,
    'MC': 353.33,
    'Neptune': 207.7,
    'Mars': 228.72
}

ASPECT_ANGLES = {
    'Conjunction': 0,
    'Opposition': 180,
    'Trine': 120,
    'Sextile': 60,
    'Square': 90,
    'Quincunx': 150,
    'Semisextile': 30,
    'Semisquare': 45,
    'Sesquisquare': 135
}

def parse_uploaded_files(ipo_file, finviz_file):
    ipo_df = pd.read_csv(ipo_file)
    finviz_df = pd.read_csv(finviz_file)
    return ipo_df, finviz_df

def filter_matching_tickers(ipo_df, finviz_df):
    ipo_df['Ticker'] = ipo_df['Ticker'].str.upper().str.strip()
    finviz_df['Ticker'] = finviz_df['Ticker'].str.upper().str.strip()
    return ipo_df[ipo_df['Ticker'].isin(finviz_df['Ticker'])]

def get_user_aspect_config(aspect_orbs, aspect_scores):
    return {
        k: {'angle': ASPECT_ANGLES[k], 'orb': aspect_orbs[k], 'score': aspect_scores[k]}
        for k in aspect_orbs
    }

def normalize_angle(deg):
    return deg % 360

def angular_diff(a, b):
    return min(abs(normalize_angle(a - b)), abs(normalize_angle(b - a)), 360 - abs(normalize_angle(a - b)))

def determine_aspect(diff, aspect_config):
    for name, cfg in aspect_config.items():
        if abs(diff - cfg['angle']) <= cfg['orb']:
            return name, abs(diff - cfg['angle']), cfg['score']
    return None, None, None


def get_planet_longitudes_swe(date_dt):
    eastern = pytz.timezone("America/New_York")
    local_dt = eastern.localize(date_dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)

    jd = swe.julday(date_dt.year, date_dt.month, date_dt.day, date_dt.hour + date_dt.minute/60.0)
    positions = {}
    for name, planet_id in TRANSIT_BODIES.items():
        result = swe.calc_ut(jd, planet_id)
        lon = result[0][0]  # Extract longitude
        positions[name.capitalize()] = lon
    return positions

def calculate_aspects_for_ticker(ticker, df_ipo, start_date, end_date, time_of_day, aspect_config):
    ipo_row = df_ipo[df_ipo['Ticker'] == ticker]
    if ipo_row.empty:
        return pd.DataFrame(columns=['Date', 'Ticker', 'Aspect', 'Score', 'Source'])

    # Ensure correct date range
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    ipo_date = pd.to_datetime(ipo_row.iloc[0]['Date'])
    ipo_datetime = datetime.combine(ipo_date, time_of_day)
    ipo_positions = get_planet_longitudes_swe(ipo_datetime)

    results = []
    prev_orbs = {}

    current_date = start_date
    while current_date <= end_date:
        dt = datetime.combine(current_date, time_of_day)
        transit_positions = get_planet_longitudes_swe(dt)

        for transit_name, transit_deg in transit_positions.items():
            for natal_name, natal_deg in ipo_positions.items():
                diff = angular_diff(transit_deg, natal_deg)
                aspect, orb_diff, score = determine_aspect(diff, aspect_config)
                if aspect:
                    key = ("IPO", transit_name, natal_name, aspect)
                    if key not in prev_orbs or orb_diff < prev_orbs[key]:
                        results.append({
                            'Date': current_date.strftime('%Y-%m-%d'),
                            'Ticker': ticker,
                            'Aspect': f"{transit_name} {aspect} IPO {natal_name} ({orb_diff:.1f}°, Score: {score:+.1f})",
                            'Score': score,
                            'Source': 'IPO'
                        })
                    prev_orbs[key] = orb_diff

            for nyse_name, nyse_deg in NYSE_NATAL_POSITIONS.items():
                diff = angular_diff(transit_deg, nyse_deg)
                aspect, orb_diff, score = determine_aspect(diff, aspect_config)
                if aspect:
                    key = ("NYSE", transit_name, nyse_name, aspect)
                    if key not in prev_orbs or orb_diff < prev_orbs[key]:
                        results.append({
                            'Date': current_date.strftime('%Y-%m-%d'),
                            'Ticker': ticker,
                            'Aspect': f"{transit_name} {aspect} NYSE {nyse_name} ({orb_diff:.1f}°, Score: {score:+.1f})",
                            'Score': score,
                            'Source': 'NYSE'
                        })
                    prev_orbs[key] = orb_diff

        # Transit-to-Transit aspects
        transit_bodies = list(transit_positions.items())
        for i in range(len(transit_bodies)):
            for j in range(i + 1, len(transit_bodies)):
                name1, deg1 = transit_bodies[i]
                name2, deg2 = transit_bodies[j]
                diff = angular_diff(deg1, deg2)
                aspect, orb_diff, score = determine_aspect(diff, aspect_config)
                if aspect:
                    key = ("Transit", name1, name2, aspect)
                    if key not in prev_orbs or orb_diff < prev_orbs[key]:
                        results.append({
                            'Date': current_date.strftime('%Y-%m-%d'),
                            'Ticker': ticker,
                            'Aspect': f"{name1} {aspect} {name2} ({orb_diff:.1f}°, Score: {score:+.1f})",
                            'Score': score,
                            'Source': 'Transit'
                        })
                    prev_orbs[key] = orb_diff

        current_date += timedelta(days=1)

    return pd.DataFrame(results, columns=['Date', 'Ticker', 'Aspect', 'Score', 'Source'])

import streamlit as st

def render_aspect_table(df):
    st.dataframe(df)

def render_aspect_heatmap(df):
    import seaborn as sns
    import matplotlib.pyplot as plt

    if df.empty:
        st.write("No data to visualize.")
        return

    pivot = df.pivot_table(index='Date', columns='Source', values='Score', aggfunc='sum')
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.heatmap(pivot.fillna(0), annot=True, fmt=".1f", cmap="RdYlGn", center=0, ax=ax)
    st.pyplot(fig)

def get_best_ticker_per_day(summary_df: pd.DataFrame) -> pd.DataFrame:
    return summary_df.loc[summary_df.groupby("Date")["TotalScore"].idxmax()]

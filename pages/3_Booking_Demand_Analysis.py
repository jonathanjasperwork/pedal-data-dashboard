
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.preprocessing import load_padel_data


st.set_page_config(
    page_title="Playing-Time Analysis",
    page_icon="🎾",
    layout="wide",
)

st.title("Playing-Time & Demand Proxy Analysis")
st.caption(
    "Analyze listed prices and scheduled time slots. "
    "This page does not measure actual bookings."
)

try:
    courts, slots = load_padel_data()
except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
    st.error(f"Unable to load data: {error}")
    st.stop()


# --------------------------------------------------
# 1. Prepare data
# --------------------------------------------------

opened_ids = (
    courts.loc[
        courts["published"].eq("opened"), "court_id"
    ]
    .dropna()
    .astype(str)
    .unique()
)

df = slots[
    slots["court_id"].astype(str).isin(opened_ids)
].copy()

df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["duration_minutes"] = pd.to_numeric(
    df["duration_minutes"], errors="coerce"
)
df["start_hour"] = pd.to_numeric(
    df["start_hour"], errors="coerce"
)
df["date"] = pd.to_datetime(df["date"], errors="coerce")

df = df[
    (df["price"] > 0)
    & (df["duration_minutes"] > 0)
    & df["start_hour"].between(0, 23)
].copy()

df["price_per_hour"] = (
    df["price"] / df["duration_minutes"] * 60
)

# Normalize common Indonesian day names.
day_mapping = {
    "Senin": "Monday",
    "Selasa": "Tuesday",
    "Rabu": "Wednesday",
    "Kamis": "Thursday",
    "Jumat": "Friday",
    "Sabtu": "Saturday",
    "Minggu": "Sunday",
}

df["day_name"] = df["day_name"].replace(day_mapping)

day_order = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

df["day_name"] = pd.Categorical(
    df["day_name"],
    categories=day_order,
    ordered=True,
)

# --------------------------------------------------
# 2. Filters
# --------------------------------------------------

st.sidebar.header("Analysis Filters")

provinces = sorted(df["province"].dropna().unique())

selected_provinces = st.sidebar.multiselect(
    "Province",
    provinces,
    default=provinces,
)

tiers = ["budget", "standard", "premium"]

selected_tiers = st.sidebar.multiselect(
    "Tier",
    tiers,
    default=tiers,
)

df = df[
    df["province"].isin(selected_provinces)
    & df["tier"].isin(selected_tiers)
].copy()

if df.empty:
    st.warning("No time-slot records match these filters.")
    st.stop()

# --------------------------------------------------
# 3. Overview metrics
# --------------------------------------------------

st.header("Schedule Overview")

col1, col2, col3 = st.columns(3)

col1.metric("Listed time slots", f"{len(df):,}")
col2.metric(
    "Courts represented",
    f"{df['court_id'].nunique():,}",
)
col3.metric(
    "Median hourly price",
    f"Rp {df['price_per_hour'].median():,.0f}",
)

st.info(
    "A listed slot is not necessarily available or booked. "
    "These metrics describe the schedule data only."
)

# --------------------------------------------------
# 4. Price attractiveness by hour
# --------------------------------------------------

st.header("Playing-Time Price Analysis")

hourly = (
    df.groupby("start_hour", as_index=False)
    .agg(
        median_price=("price_per_hour", "median"),
        average_price=("price_per_hour", "mean"),
        slot_count=("price_per_hour", "size"),
        court_count=("court_id", "nunique"),
    )
    .sort_values("start_hour")
)

fig_hour = px.line(
    hourly,
    x="start_hour",
    y="median_price",
    markers=True,
    title="Median Listed Price by Start Hour",
    labels={
        "start_hour": "Start hour",
        "median_price": "Median price per hour (IDR)",
    },
)

st.plotly_chart(fig_hour, use_container_width=True)

st.subheader("Price Comparison by Day and Hour")

heatmap = df.pivot_table(
    index="day_name",
    columns="start_hour",
    values="price_per_hour",
    aggfunc="median",
    observed=False,
)

fig_heatmap = px.imshow(
    heatmap,
    aspect="auto",
    color_continuous_scale="YlOrRd",
    labels={
        "x": "Start hour",
        "y": "Day",
        "color": "Median IDR/hour",
    },
    title="Median Listed Price: Day vs Start Hour",
)

st.plotly_chart(fig_heatmap, use_container_width=True)

# --------------------------------------------------
# 5. Relative affordability
# --------------------------------------------------

st.header("Relative Price Attractiveness")

st.caption(
    "Lower prices relative to other observed slots receive "
    "higher affordability scores. This is not a demand score."
)

global_median = df["price_per_hour"].median()

hourly["affordability_score"] = (
    global_median / hourly["median_price"]
).mul(100)

hourly["affordability_score"] = (
    hourly["affordability_score"].clip(upper=100)
)

fig_affordability = px.bar(
    hourly,
    x="start_hour",
    y="affordability_score",
    title="Relative Affordability by Start Hour",
    labels={
        "start_hour": "Start hour",
        "affordability_score": "Affordability score",
    },
)

st.plotly_chart(
    fig_affordability,
    use_container_width=True,
)

# --------------------------------------------------
# 6. Schedule coverage by day and hour
# --------------------------------------------------

st.header("Schedule Coverage")

st.caption(
    "Coverage counts the number of listed schedule records. "
    "It does not indicate bookings, availability, or demand."
)

coverage = df.pivot_table(
    index="day_name",
    columns="start_hour",
    values="court_id",
    aggfunc="count",
    observed=False,
)

fig_coverage = px.imshow(
    coverage,
    aspect="auto",
    color_continuous_scale="Blues",
    labels={
        "x": "Start hour",
        "y": "Day",
        "color": "Listed slot records",
    },
    title="Listed Schedule Records by Day and Hour",
)

st.plotly_chart(fig_coverage, use_container_width=True)

# --------------------------------------------------
# 7. Detailed table
# --------------------------------------------------

st.header("Hourly Analysis Table")

st.dataframe(
    hourly.round(2),
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Download hourly analysis CSV",
    data=hourly.to_csv(index=False).encode("utf-8"),
    file_name="padel_hourly_analysis.csv",
    mime="text/csv",
)

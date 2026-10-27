
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.preprocessing import load_padel_data


st.set_page_config(
    page_title="Geographic Analysis",
    page_icon="🎾",
    layout="wide",
)

st.title("Geographic Padel Court Analysis")
st.caption(
    "Explore court distribution, pricing, ratings, and "
    "market coverage by province and city."
)

try:
    courts, slots = load_padel_data()
except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
    st.error(f"Unable to load data: {error}")
    st.stop()


# --------------------------------------------------
# 1. Prepare court-level data
# --------------------------------------------------

courts = courts.copy()
courts["rating"] = pd.to_numeric(courts["rating"], errors="coerce")

# One record per court ID for geographic counts.
courts = courts.drop_duplicates("court_id", keep="first")

# Prepare valid slot prices.
slots = slots.copy()
slots["price"] = pd.to_numeric(slots["price"], errors="coerce")
slots["duration_minutes"] = pd.to_numeric(
    slots["duration_minutes"], errors="coerce"
)

slots = slots[
    (slots["price"] > 0)
    & (slots["duration_minutes"] > 0)
].copy()

slots["price_per_hour"] = (
    slots["price"] / slots["duration_minutes"] * 60
)

# Only opened courts are included in price comparisons.
opened_ids = set(
    courts.loc[
        courts["published"].eq("opened"), "court_id"
    ].dropna().astype(str)
)

slots["court_id"] = slots["court_id"].astype(str)

opened_slots = slots[
    slots["court_id"].isin(opened_ids)
].copy()

# Attach geographic information from the court table.
location_columns = [
    "court_id", "city", "province", "tier", "published"
]

opened_slots = opened_slots.drop(
    columns=["city", "province", "tier", "published"],
    errors="ignore",
).merge(
    courts[location_columns].assign(
        court_id=lambda x: x["court_id"].astype(str)
    ),
    on="court_id",
    how="left",
    validate="many_to_one",
)

# --------------------------------------------------
# 2. Filters
# --------------------------------------------------

st.sidebar.header("Geographic Filters")

province_options = sorted(
    courts["province"].dropna().unique().tolist()
)

selected_provinces = st.sidebar.multiselect(
    "Province",
    province_options,
    default=province_options,
)

filtered = courts[
    courts["province"].isin(selected_provinces)
].copy()

city_options = sorted(
    filtered["city"].dropna().unique().tolist()
)

selected_cities = st.sidebar.multiselect(
    "City",
    city_options,
    default=city_options,
)

filtered = filtered[
    filtered["city"].isin(selected_cities)
].copy()

selected_ids = set(filtered["court_id"].dropna().astype(str))

filtered_slots = opened_slots[
    opened_slots["court_id"].isin(selected_ids)
].copy()

# --------------------------------------------------
# 3. Geographic overview
# --------------------------------------------------

st.header("Geographic Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Unique courts",
    f"{filtered['court_id'].nunique():,}",
)

col2.metric(
    "Provinces",
    f"{filtered['province'].nunique():,}",
)

col3.metric(
    "Cities",
    f"{filtered['city'].nunique():,}",
)

col4.metric(
    "Opened courts",
    f"{filtered['published'].eq('opened').sum():,}",
)

# --------------------------------------------------
# 4. Court distribution by province
# --------------------------------------------------

st.subheader("Court Distribution by Province")

province_summary = (
    filtered.groupby("province", dropna=False)
    .agg(
        court_count=("court_id", "nunique"),
        average_rating=("rating", "mean"),
    )
    .reset_index()
    .sort_values("court_count", ascending=False)
)

fig_province = px.bar(
    province_summary,
    x="province",
    y="court_count",
    color="court_count",
    title="Unique Padel Courts by Province",
    labels={
        "province": "Province",
        "court_count": "Unique courts",
    },
)

fig_province.update_layout(xaxis_tickangle=-45)

st.plotly_chart(fig_province, use_container_width=True)

st.dataframe(
    province_summary,
    use_container_width=True,
    hide_index=True,
)

# --------------------------------------------------
# 5. City-level distribution
# --------------------------------------------------

st.subheader("City-Level Distribution")

city_summary = (
    filtered.groupby(
        ["province", "city"], dropna=False
    )
    .agg(
        court_count=("court_id", "nunique"),
        average_rating=("rating", "mean"),
    )
    .reset_index()
    .sort_values("court_count", ascending=False)
)

fig_city = px.bar(
    city_summary.head(25),
    x="city",
    y="court_count",
    color="province",
    title="Top 25 Cities by Unique Court Count",
    labels={
        "city": "City",
        "court_count": "Unique courts",
    },
)

fig_city.update_layout(xaxis_tickangle=-45)

st.plotly_chart(fig_city, use_container_width=True)

# --------------------------------------------------
# 6. Regional price comparisons
# --------------------------------------------------

st.header("Regional Price Comparison")

if filtered_slots.empty:
    st.info("No valid prices for the selected locations.")
else:
    regional_prices = (
        filtered_slots.groupby(
            ["province", "city"], dropna=False
        )
        .agg(
            median_price_hour=("price_per_hour", "median"),
            average_price_hour=("price_per_hour", "mean"),
            priced_courts=("court_id", "nunique"),
            listed_slots=("price_per_hour", "size"),
        )
        .reset_index()
        .sort_values("median_price_hour")
    )

    fig_regional = px.bar(
        regional_prices.sort_values(
            "median_price_hour", ascending=False
        ).head(25),
        x="median_price_hour",
        y="city",
        color="province",
        orientation="h",
        title="25 Highest-Median-Price Cities",
        labels={
            "median_price_hour": "Median price per hour (IDR)",
            "city": "City",
        },
    )

    st.plotly_chart(fig_regional, use_container_width=True)

    st.dataframe(
        regional_prices,
        use_container_width=True,
        hide_index=True,
    )

# --------------------------------------------------
# 7. Tier distribution by province
# --------------------------------------------------

st.header("Regional Market Structure")

tier_counts = (
    filtered.groupby(
        ["province", "tier"], dropna=False
    )
    .size()
    .reset_index(name="court_count")
)

fig_tier = px.bar(
    tier_counts,
    x="province",
    y="court_count",
    color="tier",
    barmode="stack",
    title="Court Tier Distribution by Province",
    labels={
        "province": "Province",
        "court_count": "Unique court records",
        "tier": "Tier",
    },
)

fig_tier.update_layout(xaxis_tickangle=-45)

st.plotly_chart(fig_tier, use_container_width=True)

# --------------------------------------------------
# 8. Publication status by province
# --------------------------------------------------

st.subheader("Publication Status by Province")

status_counts = (
    filtered.groupby(
        ["province", "published"], dropna=False
    )
    .size()
    .reset_index(name="court_count")
)

fig_status = px.bar(
    status_counts,
    x="province",
    y="court_count",
    color="published",
    barmode="stack",
    title="Publication Status by Province",
    labels={
        "province": "Province",
        "court_count": "Court records",
        "published": "Publication status",
    },
)

fig_status.update_layout(xaxis_tickangle=-45)

st.plotly_chart(fig_status, use_container_width=True)

# --------------------------------------------------
# 9. Export
# --------------------------------------------------

st.header("Export Geographic Results")

st.download_button(
    "Download province summary",
    data=province_summary.to_csv(index=False).encode("utf-8"),
    file_name="padel_province_summary.csv",
    mime="text/csv",
)

st.download_button(
    "Download city summary",
    data=city_summary.to_csv(index=False).encode("utf-8"),
    file_name="padel_city_summary.csv",
    mime="text/csv",
)

st.download_button(
    "Download regional prices",
    data=(
        regional_prices.to_csv(index=False).encode("utf-8")
        if not filtered_slots.empty
        else b""
    ),
    file_name="padel_regional_prices.csv",
    mime="text/csv",
    disabled=filtered_slots.empty,
)

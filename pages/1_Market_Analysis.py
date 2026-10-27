
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.preprocessing import load_padel_data


st.set_page_config(
    page_title="Padel Analytics",
    page_icon="🎾",
    layout="wide",
)

st.title("Padel Court Analytics")
st.caption("Market overview and pricing analysis")

try:
    courts, slots = load_padel_data()
except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
    st.error(f"Unable to load data: {error}")
    st.stop()


# -------------------------
# 1. Sidebar filters
# -------------------------

st.sidebar.header("Filters")

tiers = sorted(courts["tier"].dropna().unique().tolist())
statuses = sorted(
    courts["published"].dropna().unique().tolist()
)
provinces = sorted(
    courts["province"].dropna().unique().tolist()
)

selected_tiers = st.sidebar.multiselect(
    "Court tier",
    tiers,
    default=tiers,
)

selected_statuses = st.sidebar.multiselect(
    "Publication status",
    statuses,
    default=statuses,
)

selected_provinces = st.sidebar.multiselect(
    "Province",
    provinces,
    default=provinces,
)

filtered_courts = courts[
    courts["tier"].isin(selected_tiers)
    & courts["published"].isin(selected_statuses)
    & courts["province"].isin(selected_provinces)
].copy()

filtered_slots = slots[
    slots["court_id"].isin(filtered_courts["court_id"])
].copy()


# -------------------------
# 2. Overview metrics
# -------------------------

st.header("Market Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Court records",
    f"{len(filtered_courts):,}",
)

col2.metric(
    "Unique court IDs",
    f"{filtered_courts['court_id'].nunique():,}",
)

opened_count = (
    filtered_courts["published"] == "opened"
).sum()

col3.metric(
    "Opened courts",
    f"{opened_count:,}",
)

col4.metric(
    "Cities",
    f"{filtered_courts['city'].nunique():,}",
)


# -------------------------
# 3. Publication status
# -------------------------

st.subheader("Publication Status")

status_counts = (
    filtered_courts["published"]
    .fillna("Unknown")
    .value_counts()
    .rename_axis("Status")
    .reset_index(name="Courts")
)

fig_status = px.pie(
    status_counts,
    names="Status",
    values="Courts",
    hole=0.45,
    title="Court Status Distribution",
)

st.plotly_chart(fig_status, use_container_width=True)


# -------------------------
# 4. Tier distribution
# -------------------------

st.subheader("Court Tier Distribution")

tier_counts = (
    filtered_courts["tier"]
    .fillna("Unknown")
    .value_counts()
    .rename_axis("Tier")
    .reset_index(name="Courts")
)

fig_tier = px.bar(
    tier_counts,
    x="Tier",
    y="Courts",
    color="Tier",
    title="Number of Courts by Tier",
)

st.plotly_chart(fig_tier, use_container_width=True)


# -------------------------
# 5. Geographic analysis
# -------------------------

st.subheader("Geographic Distribution")

province_counts = (
    filtered_courts.groupby("province", dropna=False)
    .agg(
        court_records=("court_id", "size"),
        unique_courts=("court_id", "nunique"),
    )
    .reset_index()
    .sort_values("unique_courts", ascending=False)
)

fig_province = px.bar(
    province_counts.head(20),
    x="province",
    y="unique_courts",
    title="Top 20 Provinces by Unique Courts",
    labels={
        "province": "Province",
        "unique_courts": "Unique courts",
    },
)

fig_province.update_layout(xaxis_tickangle=-45)

st.plotly_chart(fig_province, use_container_width=True)

st.subheader("City Comparison")

city_counts = (
    filtered_courts.groupby(
        ["province", "city"], dropna=False
    )
    .agg(
        unique_courts=("court_id", "nunique"),
    )
    .reset_index()
    .sort_values("unique_courts", ascending=False)
)

st.dataframe(
    city_counts.head(50),
    use_container_width=True,
)


# -------------------------
# 6. Price analysis
# -------------------------

st.header("Pricing Analysis")

opened_ids = filtered_courts.loc[
    filtered_courts["published"] == "opened",
    "court_id",
]

price_data = filtered_slots[
    filtered_slots["court_id"].isin(opened_ids)
    & (filtered_slots["price"] > 0)
    & (filtered_slots["duration_minutes"] > 0)
].copy()

if price_data.empty:
    st.warning("No valid prices available for the selected filters.")
else:
    price_col1, price_col2, price_col3 = st.columns(3)

    price_col1.metric(
        "Average price / hour",
        f"Rp {price_data['price_per_hour'].mean():,.0f}",
    )

    price_col2.metric(
        "Median price / hour",
        f"Rp {price_data['price_per_hour'].median():,.0f}",
    )

    price_col3.metric(
        "Courts with valid prices",
        f"{price_data['court_id'].nunique():,}",
    )

    fig_price_tier = px.box(
        price_data.dropna(subset=["tier"]),
        x="tier",
        y="price_per_hour",
        color="tier",
        title="Hourly Price Distribution by Tier",
        labels={
            "tier": "Court tier",
            "price_per_hour": "Price per hour (IDR)",
        },
    )

    st.plotly_chart(
        fig_price_tier,
        use_container_width=True,
    )

    # Hourly pricing patterns
    hourly_prices = (
        price_data.dropna(subset=["start_hour"])
        .groupby("start_hour", as_index=False)
        .agg(
            average_price=("price_per_hour", "mean"),
            median_price=("price_per_hour", "median"),
            slot_count=("price_per_hour", "size"),
        )
    )

    fig_hourly = px.line(
        hourly_prices,
        x="start_hour",
        y=["average_price", "median_price"],
        markers=True,
        title="Listed Price by Start Hour",
        labels={
            "start_hour": "Start hour",
            "value": "Price per hour (IDR)",
            "variable": "Statistic",
        },
    )

    st.plotly_chart(
        fig_hourly,
        use_container_width=True,
    )

    # Day and hour heatmap
    heatmap_data = price_data.dropna(
        subset=["day_name", "start_hour"]
    )

    if not heatmap_data.empty:
        heatmap = heatmap_data.pivot_table(
            index="day_name",
            columns="start_hour",
            values="price_per_hour",
            aggfunc="mean",
        )

        fig_heatmap = px.imshow(
            heatmap,
            aspect="auto",
            color_continuous_scale="YlOrRd",
            labels={
                "x": "Start hour",
                "y": "Day",
                "color": "Price / hour",
            },
            title="Average Hourly Price by Day and Start Hour",
        )

        st.plotly_chart(
            fig_heatmap,
            use_container_width=True,
        )

    # Discounts
    discount_data = price_data.dropna(
        subset=["discount_pct"]
    )

    discount_data = discount_data[
        (discount_data["strike_price"] > 0)
        & (discount_data["discount_pct"] >= 0)
        & (discount_data["discount_pct"] <= 100)
    ]

    st.subheader("Listed Discounts")

    if discount_data.empty:
        st.info("No valid strike-price comparisons found.")
    else:
        st.metric(
            "Average listed discount",
            f"{discount_data['discount_pct'].mean():.1f}%",
        )

        fig_discount = px.histogram(
            discount_data,
            x="discount_pct",
            nbins=20,
            title="Distribution of Listed Discounts",
            labels={"discount_pct": "Discount (%)"},
        )

        st.plotly_chart(
            fig_discount,
            use_container_width=True,
        )


# -------------------------
# 7. Data table
# -------------------------

st.header("Filtered Court Data")

st.dataframe(
    filtered_courts,
    use_container_width=True,
)

st.download_button(
    "Download filtered courts as CSV",
    data=filtered_courts.to_csv(index=False).encode("utf-8"),
    file_name="filtered_padel_courts.csv",
    mime="text/csv",
)

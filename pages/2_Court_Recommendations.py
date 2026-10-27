
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.preprocessing import load_padel_data


st.set_page_config(
    page_title="Court Recommendations",
    page_icon="🎾",
    layout="wide",
)

st.title("Best Padel Court Recommendations")
st.caption(
    "Rank opened courts using listed prices, ratings, "
    "tier preferences, and location."
)

try:
    courts, slots = load_padel_data()
except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
    st.error(f"Unable to load data: {error}")
    st.stop()


# --------------------------------------------------
# 1. Prepare opened courts and their price summaries
# --------------------------------------------------

opened = courts[
    (courts["published"] == "opened")
    & courts["court_id"].notna()
].copy()

# Deduplicate court metadata by ID.
opened = opened.drop_duplicates("court_id", keep="first")

valid_slots = slots[
    (slots["published"] == "opened")
    & (slots["price"] > 0)
    & (slots["duration_minutes"] > 0)
].copy()

valid_slots["price_per_hour"] = (
    valid_slots["price"]
    / valid_slots["duration_minutes"]
    * 60
)

# Summarize the schedule prices for each court.
price_summary = (
    valid_slots.groupby("court_id")
    .agg(
        median_price_hour=("price_per_hour", "median"),
        min_price_hour=("price_per_hour", "min"),
        max_price_hour=("price_per_hour", "max"),
        valid_slot_count=("price_per_hour", "size"),
    )
    .reset_index()
)

data = opened.merge(
    price_summary,
    on="court_id",
    how="left",
    validate="one_to_one",
)

data["rating"] = pd.to_numeric(data["rating"], errors="coerce")

# Exclude invalid prices and ratings from scoring.
data["city"] = data["city"].fillna("Unknown")
data["province"] = data["province"].fillna("Unknown")
data["tier"] = data["tier"].fillna("Unknown")

# --------------------------------------------------
# 2. User filters
# --------------------------------------------------

st.sidebar.header("Recommendation Filters")

provinces = sorted(
    data.loc[data["province"] != "Unknown", "province"].unique()
)

selected_province = st.sidebar.selectbox(
    "Province",
    ["All provinces"] + provinces,
)

if selected_province == "All provinces":
    location_data = data.copy()
else:
    location_data = data[
        data["province"] == selected_province
    ].copy()

cities = sorted(
    location_data.loc[
        location_data["city"] != "Unknown", "city"
    ].unique()
)

selected_city = st.sidebar.selectbox(
    "City",
    ["All cities"] + cities,
)

if selected_city != "All cities":
    location_data = location_data[
        location_data["city"] == selected_city
    ].copy()

available_tiers = [
    tier for tier in ["budget", "standard", "premium"]
    if tier in location_data["tier"].values
]

selected_tiers = st.sidebar.multiselect(
    "Tier",
    available_tiers,
    default=available_tiers,
)

location_data = location_data[
    location_data["tier"].isin(selected_tiers)
].copy()

valid_ratings = location_data["rating"].dropna()

if not valid_ratings.empty:
    min_rating = st.sidebar.slider(
        "Minimum rating",
        min_value=0.0,
        max_value=5.0,
        value=0.0,
        step=0.1,
    )
    location_data = location_data[
        location_data["rating"] >= min_rating
    ].copy()

valid_prices = location_data["median_price_hour"].dropna()

if not valid_prices.empty:
    max_budget = st.sidebar.number_input(
        "Maximum median price per hour (IDR)",
        min_value=0,
        max_value=max(1, int(valid_prices.max())),
        value=int(valid_prices.max()),
        step=25000,
    )

    location_data = location_data[
        location_data["median_price_hour"].notna()
        & (location_data["median_price_hour"] <= max_budget)
    ].copy()

# --------------------------------------------------
# 3. Recommendation preferences
# --------------------------------------------------

st.subheader("Scoring Preferences")

col1, col2, col3 = st.columns(3)

with col1:
    price_weight = st.slider(
        "Price importance",
        min_value=0,
        max_value=100,
        value=40,
        step=5,
    )

with col2:
    rating_weight = st.slider(
        "Rating importance",
        min_value=0,
        max_value=100,
        value=40,
        step=5,
    )

with col3:
    tier_weight = st.slider(
        "Tier preference importance",
        min_value=0,
        max_value=100,
        value=20,
        step=5,
    )

weight_total = price_weight + rating_weight + tier_weight

if weight_total == 0:
    st.warning("Set at least one scoring weight above zero.")
    st.stop()

# --------------------------------------------------
# 4. Calculate recommendation scores
# --------------------------------------------------

ranked = location_data.copy()

# Normalize affordability:
# lowest median price gets 100; highest gets 0.
# If all prices are identical, all receive 100.
price_min = ranked["median_price_hour"].min()
price_max = ranked["median_price_hour"].max()

if pd.isna(price_min):
    ranked["price_score"] = float("nan")
elif price_max == price_min:
    ranked["price_score"] = 100.0
else:
    ranked["price_score"] = (
        (price_max - ranked["median_price_hour"])
        / (price_max - price_min)
        * 100
    )

# Normalize ratings to a 0-100 scale.
ranked["rating_score"] = (
    ranked["rating"].clip(lower=0, upper=5) / 5 * 100
)

# Tier preference is explicitly defined by category.
tier_scores = {
    "budget": 100,
    "standard": 70,
    "premium": 40,
}

ranked["tier_score"] = ranked["tier"].map(tier_scores)

# Renormalize weights among available score components.
components = [
    ("price_score", price_weight),
    ("rating_score", rating_weight),
    ("tier_score", tier_weight),
]

numerator = pd.Series(0.0, index=ranked.index)
denominator = pd.Series(0.0, index=ranked.index)

for column, weight in components:
    if weight > 0:
        available = ranked[column].notna()
        numerator.loc[available] += (
            ranked.loc[available, column] * weight
        )
        denominator.loc[available] += weight

ranked["recommendation_score"] = (
    numerator / denominator.replace(0, float("nan"))
)

ranked = ranked.sort_values(
    ["recommendation_score", "rating", "median_price_hour"],
    ascending=[False, False, True],
    na_position="last",
)

# --------------------------------------------------
# 5. Display recommendations
# --------------------------------------------------

st.subheader("Recommended Courts")

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Eligible courts", f"{len(ranked):,}")

metric2.metric(
    "Courts with prices",
    f"{ranked['median_price_hour'].notna().sum():,}",
)

metric3.metric(
    "Courts with ratings",
    f"{ranked['rating'].notna().sum():,}",
)

if ranked.empty:
    st.info("No courts match your selected filters.")
else:
    st.caption(
        "Scores are relative to the currently filtered courts. "
        "They are recommendation scores, not predicted outcomes."
    )

    top_n = st.selectbox(
        "Number of recommendations",
        [10, 20, 50, 100],
        index=1,
    )

    display = ranked.head(top_n).copy()

    display["median_price_hour"] = display[
        "median_price_hour"
    ].round(0)

    display["min_price_hour"] = display[
        "min_price_hour"
    ].round(0)

    display["max_price_hour"] = display[
        "max_price_hour"
    ].round(0)

    display["recommendation_score"] = display[
        "recommendation_score"
    ].round(1)

    st.dataframe(
        display[
            [
                "name",
                "city",
                "province",
                "tier",
                "rating",
                "median_price_hour",
                "min_price_hour",
                "max_price_hour",
                "recommendation_score",
                "link",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "median_price_hour": st.column_config.NumberColumn(
                "Median hourly price",
                format="Rp %.0f",
            ),
            "min_price_hour": st.column_config.NumberColumn(
                "Minimum hourly price",
                format="Rp %.0f",
            ),
            "max_price_hour": st.column_config.NumberColumn(
                "Maximum hourly price",
                format="Rp %.0f",
            ),
            "recommendation_score": st.column_config.ProgressColumn(
                "Recommendation score",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "link": st.column_config.LinkColumn("Court link"),
        },
    )

    fig = px.scatter(
        ranked.dropna(
            subset=["median_price_hour", "rating"]
        ),
        x="median_price_hour",
        y="rating",
        color="tier",
        hover_name="name",
        hover_data=["city", "province", "recommendation_score"],
        title="Court Price vs Rating",
        labels={
            "median_price_hour": "Median hourly price (IDR)",
            "rating": "Rating",
        },
    )

    st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        "Download recommendations as CSV",
        data=ranked.to_csv(index=False).encode("utf-8"),
        file_name="padel_recommendations.csv",
        mime="text/csv",
    )

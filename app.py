
import streamlit as st

st.set_page_config(
    page_title="Padel Court Analytics",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎾 Padel Court Analytics")
st.subheader("Explore Indonesia's Padel Court Market")

st.markdown(
    """
    Welcome to Padel Court Analytics, a data analysis dashboard
    for exploring padel courts across Indonesia.

    Use the pages in the sidebar to explore court pricing,
    recommendations, schedule patterns, and geographic
    market distribution.
    """
)

st.divider()

st.subheader("Explore the Dashboard")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 1. Market Analysis")
    st.write(
        "Explore court distribution, publication status, "
        "ratings, and listed prices."
    )

    st.page_link(
        "pages/1_Market_Analysis.py",
        label="Open Market Analysis",
        icon="📊",
    )

    st.markdown("### 3. Court Recommendations")
    st.write(
        "Compare courts using price, rating, tier, "
        "and location preferences."
    )

    st.page_link(
        "pages/2_Court_Recommendations.py",
        label="Find the Best Court",
        icon="🏆",
    )

with col2:
    st.markdown("### 2. Playing-Time Analysis")
    st.write(
        "Explore listed prices and schedule patterns "
        "by day and starting hour."
    )

    st.page_link(
        "pages/3_Booking_Demand_Analysis.py",
        label="Explore Playing Times",
        icon="🕒",
    )

    st.markdown("### 4. Geographic Analysis")
    st.write(
        "Compare court distribution and listed prices "
        "across provinces and cities."
    )

    st.page_link(
        "pages/4_Geographic_Analysis.py",
        label="Explore Geographic Data",
        icon="📍",
    )

st.divider()

st.caption(
    "Data snapshot analysis. Prices and schedule patterns "
    "reflect the collected dataset, not live booking availability "
    "or future price predictions."
)

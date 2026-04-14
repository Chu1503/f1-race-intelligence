import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="F1 Race Intelligence",
    page_icon="🏎️",
    layout="wide"
)

API_URL = "http://localhost:8000"

DRIVER_NAMES = {
    1: "Verstappen", 11: "Perez", 44: "Hamilton", 63: "Russell",
    16: "Leclerc", 55: "Sainz", 4: "Norris", 81: "Piastri",
    14: "Alonso", 18: "Stroll", 10: "Gasly", 31: "Ocon",
    23: "Albon", 2: "Sargeant", 77: "Bottas", 24: "Zhou",
    20: "Magnussen", 27: "Hulkenberg", 3: "Ricciardo", 22: "Tsunoda"
}

st.title("🏎️ F1 Race Intelligence System")
st.caption("Real-time strategy analysis powered by Spark + CrewAI + RAG")

# Sidebar
st.sidebar.header("Data Source")
year = st.sidebar.selectbox("Season", [2024, 2023], index=0)
round_num = st.sidebar.selectbox("Round", list(range(1, 24)), index=0)

# Load data
@st.cache_data
def load_race_data(year, round_num):
    path = f"data/spark_output/historical/{year}_round{round_num}"
    if not os.path.exists(path):
        return None
    return pd.read_parquet(path)

df = load_race_data(year, round_num)

if df is None:
    st.warning(f"No data found for {year} Round {round_num}. Run the batch processor first.")
    st.stop()

df["driver_name"] = df["driver_number"].map(DRIVER_NAMES).fillna(df["driver_number"].astype(str))

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Race Overview", "🔍 Driver Deep Dive", "🤖 AI Strategy", "💬 Commentary"])

with tab1:
    st.subheader("Lap Time Comparison")
    selected_drivers = st.multiselect(
        "Select Drivers",
        options=sorted(df["driver_number"].unique()),
        default=sorted(df["driver_number"].unique())[:5],
        format_func=lambda x: DRIVER_NAMES.get(x, str(x))
    )
    if selected_drivers:
        filtered = df[df["driver_number"].isin(selected_drivers)]
        fig = px.line(
            filtered, x="lap_number", y="lap_duration",
            color="driver_name", title="Lap Times by Driver",
            labels={"lap_duration": "Lap Time (s)", "lap_number": "Lap"}
        )
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Tyre Degradation Rates")
        deg_summary = df.groupby("driver_name")["tyre_degradation_rate"].mean().sort_values()
        fig2 = px.bar(
            deg_summary, orientation="h",
            title="Avg Degradation Rate (s/lap)",
            labels={"value": "Deg Rate (s/lap)", "index": "Driver"}
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("Pit Stop Flags")
        pit_counts = df.groupby("driver_name")["should_pit_soon"].sum().sort_values(ascending=False)
        fig3 = px.bar(pit_counts, title="Laps Flagged 'Should Pit Soon'")
        st.plotly_chart(fig3, use_container_width=True)

with tab2:
    st.subheader("Driver Deep Dive")
    driver_num = st.selectbox(
        "Select Driver",
        options=sorted(df["driver_number"].unique()),
        format_func=lambda x: DRIVER_NAMES.get(x, str(x))
    )
    driver_df = df[df["driver_number"] == driver_num].sort_values("lap_number")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Laps", len(driver_df))
    col2.metric("Fastest Lap", f"{driver_df['lap_duration'].min():.3f}s")
    col3.metric("Avg Deg Rate", f"{driver_df['tyre_degradation_rate'].mean():.4f}s/lap")
    col4.metric("Laps to Pit", int(driver_df['should_pit_soon'].sum()))

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=driver_df["lap_number"], y=driver_df["lap_duration"],
        name="Lap Time", line=dict(color="blue")
    ))
    fig4.add_trace(go.Scatter(
        x=driver_df["lap_number"], y=driver_df["rolling_avg_lap_time"],
        name="Rolling Avg (5 lap)", line=dict(color="orange", dash="dash")
    ))
    pit_laps = driver_df[driver_df["should_pit_soon"] == True]
    fig4.add_trace(go.Scatter(
        x=pit_laps["lap_number"], y=pit_laps["lap_duration"],
        mode="markers", name="Should Pit",
        marker=dict(color="red", size=10, symbol="x")
    ))
    fig4.update_layout(title=f"{DRIVER_NAMES.get(driver_num, driver_num)} — Lap Times & Pit Flags")
    st.plotly_chart(fig4, use_container_width=True)

    fig5 = px.line(
        driver_df, x="lap_number", y="tyre_degradation_rate",
        title="Tyre Degradation Rate Over Race",
        labels={"tyre_degradation_rate": "Deg Rate (s/lap)"}
    )
    fig5.add_hline(y=0.15, line_dash="dash", line_color="red", annotation_text="Pit threshold")
    st.plotly_chart(fig5, use_container_width=True)

with tab3:
    st.subheader("🤖 AI Strategy Recommendation")
    st.caption("Uses the Strategy Agent + RAG pipeline")

    driver_num = st.selectbox(
        "Driver", options=sorted(df["driver_number"].unique()),
        format_func=lambda x: DRIVER_NAMES.get(x, str(x)), key="strat_driver"
    )
    driver_df = df[df["driver_number"] == driver_num].sort_values("lap_number")

    lap_num = st.slider("Lap", int(driver_df["lap_number"].min()), int(driver_df["lap_number"].max()),
                         int(driver_df["lap_number"].median()))
    lap_row = driver_df[driver_df["lap_number"] == lap_num]

    if not lap_row.empty:
        row = lap_row.iloc[0]
        st.json({
            "lap_time": f"{row['lap_duration']:.3f}s",
            "tyre": f"{row.get('tyre_compound', 'N/A')} ({int(row.get('tyre_age_laps', 0))} laps)",
            "degradation_rate": f"{row['tyre_degradation_rate']:.4f}s/lap",
            "should_pit_soon": bool(row["should_pit_soon"])
        })

        if st.button("🤖 Get Strategy Recommendation"):
            with st.spinner("Consulting Strategy Agent..."):
                payload = {
                    "driver_number": int(row["driver_number"]),
                    "lap_number": int(row["lap_number"]),
                    "lap_duration": float(row["lap_duration"]),
                    "tyre_compound": str(row.get("tyre_compound", "UNKNOWN")),
                    "tyre_age_laps": int(row.get("tyre_age_laps", 0)),
                    "tyre_degradation_rate": float(row["tyre_degradation_rate"]),
                    "rolling_avg_lap_time": float(row["rolling_avg_lap_time"]),
                    "lap_delta": float(row["lap_delta"]),
                    "should_pit_soon": bool(row["should_pit_soon"]),
                    "estimated_laps_to_pit": float(row["estimated_laps_to_pit"]),
                    "circuit_name": "Bahrain",
                    "total_race_laps": 57
                }
                try:
                    resp = requests.post(f"{API_URL}/strategy", json=payload, timeout=60)
                    st.success("Strategy recommendation:")
                    st.markdown(resp.json()["recommendation"])
                except Exception as e:
                    st.error(f"API error: {e}")

with tab4:
    st.subheader("💬 Live Race Commentary")
    driver_num = st.selectbox(
        "Driver", options=sorted(df["driver_number"].unique()),
        format_func=lambda x: DRIVER_NAMES.get(x, str(x)), key="comm_driver"
    )
    driver_df = df[df["driver_number"] == driver_num].sort_values("lap_number")
    lap_num = st.slider("Lap", int(driver_df["lap_number"].min()), int(driver_df["lap_number"].max()),
                         int(driver_df["lap_number"].median()), key="comm_lap")
    lap_row = driver_df[driver_df["lap_number"] == lap_num]

    if not lap_row.empty and st.button("🎙️ Generate Commentary"):
        row = lap_row.iloc[0]
        with st.spinner("Commentator warming up..."):
            payload = {
                "driver_name": DRIVER_NAMES.get(int(row["driver_number"]), f"Driver {int(row['driver_number'])}"),
                "driver_number": int(row["driver_number"]),
                "lap_number": int(row["lap_number"]),
                "lap_duration": float(row["lap_duration"]),
                "tyre_compound": str(row.get("tyre_compound", "UNKNOWN")),
                "tyre_age_laps": int(row.get("tyre_age_laps", 0)),
                "should_pit_soon": bool(row["should_pit_soon"]),
                "tyre_degradation_rate": float(row["tyre_degradation_rate"]),
            }
            try:
                resp = requests.post(f"{API_URL}/commentary", json=payload, timeout=60)
                st.info(f"🎙️ {resp.json()['commentary']}")
            except Exception as e:
                st.error(f"API error: {e}")
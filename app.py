"""
DB Delay Predictor - Live Prediction Demo

Portfolio-ready Streamlit app demonstrating:
- Real-time DB API integration
- ML model inference
- Prediction logging & monitoring
- Feature transparency
"""

import logging
from datetime import date, datetime

import pandas as pd
import streamlit as st

from src.predictor import DelayPredictor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="DB Delay Predictor",
    page_icon="🚂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better visuals
st.markdown(
    """
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #EC0016;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .prediction-success {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .prediction-warning {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .prediction-danger {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Station list (matching training data)
STATIONS = [
    "Frankfurt (Main) Hbf",
    "Berlin Hauptbahnhof",
    "München Hbf",
    "Hannover Hbf",
    "Hamburg Hbf",
    "Nürnberg Hbf",
    "Berlin-Spandau",
    "Köln Hbf",
    "Kassel-Wilhelmshöhe",
    "Düsseldorf Hbf",
]


@st.cache_resource
def load_predictor():
    """Load predictor (cached for performance)."""
    try:
        return DelayPredictor("models/xgb_weather.joblib")
    except Exception as e:
        st.error(f"Failed to load model: {e}")
        return None


def render_header():
    """Render app header."""
    st.markdown(
        '<div class="main-header">🚂 DB Delay Predictor</div>', unsafe_allow_html=True
    )
    st.markdown(
        """
        <p style='text-align: center; color: #666; font-size: 1.1rem;'>
        Real-time Deutsche Bahn delay predictions using machine learning
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")


def render_sidebar():
    """Render sidebar with info."""
    with st.sidebar:
        st.header("ℹ️ About")
        st.write(
            """
        This app predicts whether a Deutsche Bahn ICE train will be delayed
        (>5 minutes) using:

        - **Real-time data** from DB Timetables API
        - **Historical patterns** from 750K+ observations
        - **XGBoost model** (74.7% accuracy)
        """
        )

        st.header("📊 Model Info")
        st.metric("Accuracy", "74.7%")
        st.metric("Training Data", "750K rows")
        st.metric("Time Period", "2024-07 to 2025-11")

        st.header("🔑 Features Used")
        st.write(
            """
        - Hour of day, day of week
        - Rush hour indicator
        - Historical delay rate
        - Train frequency
        - Weather conditions
        - German public holidays
        """
        )

        st.markdown("---")
        st.caption("Data © Deutsche Bahn AG (CC BY 4.0)")
        st.caption("Weather © DWD (CC BY 4.0)")


def render_input_form(predictor: DelayPredictor):
    """Render input form and return values."""
    st.header("🔍 Make a Prediction")

    col1, col2 = st.columns(2)

    with col1:
        station = st.selectbox(
            "Station",
            options=STATIONS,
            key="station",
            help="Select the station where you want to check the train",
        )

    with col2:
        query_date = st.date_input(
            "Date",
            value=date.today(),
            key="query_date",
            help="Date to check (default: today)",
        )

    col3, col4 = st.columns(2)

    with col3:
        current_hour = datetime.now().hour
        hour = st.slider(
            "Hour",
            min_value=0,
            max_value=23,
            value=current_hour,
            key="hour",
            help="Hour to check (default: current hour)",
        )

    with col4:
        selection_key = f"{station}|{query_date}|{hour}"
        if st.session_state.get("_last_selection") != selection_key:
            st.session_state["_available_trains"] = None
            st.session_state["_last_selection"] = selection_key

        if st.session_state.get("_available_trains") is None:
            trains = predictor.get_available_trains(station, query_date, hour)
            st.session_state["_available_trains"] = trains if trains else ["No ICE trains found"]

        train_number = st.selectbox(
            "ICE Train Number",
            options=st.session_state["_available_trains"],
            key="train_number",
            help="Select an ICE train running at this station and time",
        )

        if st.button("🔄 Refresh Trains", use_container_width=True):
            st.session_state["_available_trains"] = None
            st.rerun()

    predict_button = st.button(
        "🚀 Predict Delay", type="primary", use_container_width=True
    )

    return station, train_number, query_date, hour, predict_button


def render_prediction_result(result: dict):
    """Render prediction results."""
    st.header("📈 Prediction Results")

    if "error" in result:
        st.error(f"❌ {result['error']}")
        return

    # Real-time status banner (if available)
    has_rt = result.get("has_realtime_data", False)
    if has_rt:
        arr_delay = result.get("actual_arrival_delay_min")
        dep_delay = result.get("actual_departure_delay_min")
        rt_parts = []
        if arr_delay is not None:
            rt_parts.append(f"Arrived {arr_delay:+.0f} min")
        if dep_delay is not None:
            rt_parts.append(f"Departing {dep_delay:+.0f} min")
        rt_text = " | ".join(rt_parts)

        if arr_delay is not None and arr_delay > 5:
            st.warning(f"🔴 LIVE: {rt_text}")
        elif arr_delay is not None and arr_delay > 0:
            st.info(f"🟡 LIVE: {rt_text}")
        else:
            st.success(f"🟢 LIVE: {rt_text}")
    else:
        st.info("ℹ️ No real-time delay data available — prediction based on historical patterns")

    # Main prediction card
    delayed = result.get("delayed")
    probability = result.get("probability")
    confidence = result.get("confidence")

    if delayed is None:
        st.error("Prediction failed - please try again")
        return

    # Color-coded result card
    if delayed:
        card_class = "prediction-danger" if probability > 0.7 else "prediction-warning"
        emoji = "⚠️"
        verdict = "LIKELY DELAYED"
    else:
        card_class = "prediction-success"
        emoji = "✅"
        verdict = "LIKELY ON TIME"

    st.markdown(
        f"""
        <div class="{card_class}">
            <h2 style='margin: 0;'>{emoji} {verdict}</h2>
            <p style='font-size: 1.2rem; margin: 0.5rem 0;'>
                Delay probability: <strong>{probability * 100:.1f}%</strong>
            </p>
            <p style='margin: 0;'>Confidence: <strong>{confidence.upper()}</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Delay Probability", f"{probability * 100:.1f}%")

    with col2:
        st.metric("Confidence", confidence.upper())

    with col3:
        arr_delay = result.get("actual_arrival_delay_min")
        if arr_delay is not None:
            delta = f"{arr_delay:+.0f} min"
            st.metric("Actual Arrival", f"{arr_delay:.0f} min", delta=delta)
        else:
            st.metric("Actual Arrival", "N/A")

    with col4:
        dep_delay = result.get("actual_departure_delay_min")
        if dep_delay is not None:
            delta = f"{dep_delay:+.0f} min"
            st.metric("Actual Departure", f"{dep_delay:.0f} min", delta=delta)
        else:
            st.metric("Actual Departure", "N/A")

    # Probability gauge
    st.subheader("📊 Probability Breakdown")
    prob_on_time = 1 - probability
    col1, col2 = st.columns(2)

    with col1:
        st.metric("On Time", f"{prob_on_time * 100:.1f}%")
        st.progress(prob_on_time)

    with col2:
        st.metric("Delayed", f"{probability * 100:.1f}%")
        st.progress(probability)


def render_feature_transparency(result: dict):
    """Render feature values used for prediction."""
    if "features" not in result:
        return

    st.header("🔬 Feature Transparency")
    st.write("Values used by the model for this prediction:")

    features = result["features"]

    # Group features by category
    time_features = {
        "Hour": features.get("hour"),
        "Day of Week": features.get("day_of_week"),
        "Month": features.get("month"),
        "Season": features.get("season"),
        "Is Weekend": "Yes" if features.get("is_weekend") else "No",
        "Is Rush Hour": "Yes" if features.get("is_rush_hour") else "No",
        "Is Holiday": "Yes" if features.get("is_holiday") else "No",
    }

    historical_features = {
        "Historical Delay Rate": f"{features.get('hist_delay_rate', 0) * 100:.1f}%",
        "Train Count at Station": features.get("train_count", "N/A"),
        "Previous Delay (min)": features.get("prev_delay_min", "N/A"),
    }

    # Display in columns
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⏰ Time Features")
        for key, value in time_features.items():
            st.text(f"{key}: {value}")

    with col2:
        st.subheader("📊 Historical Features")
        for key, value in historical_features.items():
            st.text(f"{key}: {value}")

    # Weather features (if available)
    weather_features = {
        "Temperature (°C)": features.get("temperature_c"),
        "Precipitation (mm)": features.get("precipitation_mm"),
        "Wind Speed (m/s)": features.get("wind_speed_ms"),
        "Humidity (%)": features.get("humidity_pct"),
    }

    # Check if any weather data is available
    if any(v is not None for v in weather_features.values()):
        st.subheader("🌤️ Weather Features")
        for key, value in weather_features.items():
            if value is not None:
                st.text(f"{key}: {value:.1f}")
            else:
                st.text(f"{key}: N/A")
    else:
        st.info("ℹ️ Weather data not available for this prediction")


def render_similar_patterns(predictor: DelayPredictor, result: dict):
    """Render similar historical patterns."""
    st.header("📚 Similar Historical Patterns")

    station = result.get("station_name")
    hour = result.get("hour")

    if not station or hour is None:
        return

    # Query similar patterns from historical data
    try:
        from src.database import engine

        query = f"""
        SELECT
            DATE(time) as date,
            train_number,
            delay_in_min,
            CASE WHEN delay_in_min > 5 THEN 'Delayed' ELSE 'On Time' END as status
        FROM train_delays
        WHERE station_name = '{station}'
        AND EXTRACT(HOUR FROM time AT TIME ZONE 'Europe/Berlin') = {hour}
        ORDER BY time DESC
        LIMIT 10
        """
        similar = pd.read_sql(query, engine)

        if len(similar) > 0:
            st.write(
                f"Recent trains at **{station}** around **{hour}:00** (last 10 observations):"
            )

            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                delayed_count = (similar["status"] == "Delayed").sum()
                st.metric("Delayed", f"{delayed_count}/10")
            with col2:
                avg_delay = similar["delay_in_min"].mean()
                st.metric("Avg Delay", f"{avg_delay:.1f} min")
            with col3:
                max_delay = similar["delay_in_min"].max()
                st.metric("Max Delay", f"{max_delay:.0f} min")

            # Show table
            st.dataframe(
                similar,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No recent historical data available for this station and time.")

    except Exception as e:
        st.warning(f"Could not load historical patterns: {e}")


def render_prediction_history(predictor: DelayPredictor):
    """Render recent predictions from database."""
    st.header("📜 Recent Predictions")

    recent = predictor.get_recent_predictions(limit=20)

    if len(recent) == 0:
        st.info("No predictions logged yet. Make your first prediction above!")
        return

    st.write(f"Showing last {len(recent)} predictions:")

    # Format for display
    display_df = recent.copy()
    display_df["created_at"] = pd.to_datetime(display_df["created_at"]).dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    display_df["Probability"] = (display_df["predicted_prob"] * 100).round(1).astype(
        str
    ) + "%"
    display_df["Prediction"] = display_df["predicted_delay"].map(
        {True: "Delayed", False: "On Time"}
    )

    # Select columns
    display_df = display_df[
        ["created_at", "station_name", "train_number", "Prediction", "Probability"]
    ]
    display_df.columns = ["Timestamp", "Station", "Train", "Prediction", "Probability"]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # Summary metrics
    st.subheader("📊 Prediction Summary")
    col1, col2, col3 = st.columns(3)

    with col1:
        total = len(recent)
        st.metric("Total Predictions", total)

    with col2:
        delayed = recent["predicted_delay"].sum()
        st.metric("Predicted Delays", f"{delayed}/{total}")

    with col3:
        avg_prob = recent["predicted_prob"].mean()
        st.metric("Avg Delay Probability", f"{avg_prob * 100:.1f}%")


def main():
    """Main app logic."""
    # Header
    render_header()

    # Sidebar
    render_sidebar()

    # Load predictor
    predictor = load_predictor()
    if not predictor:
        st.error("Failed to load prediction model. Please check model file exists.")
        return

    # Input form
    station, train_number, query_date, hour, predict_button = render_input_form(predictor)

    # Make prediction when button clicked
    if predict_button:
        if not train_number or train_number == "No ICE trains found":
            st.error("No valid train selected")
            return

        with st.spinner("🔄 Fetching live data and making prediction..."):
            try:
                result = predictor.predict_and_log(
                    station_name=station,
                    train_number=train_number,
                    query_date=query_date,
                    hour=hour,
                )

                # Show results
                render_prediction_result(result)

                # Feature transparency
                render_feature_transparency(result)

                # Similar historical patterns
                render_similar_patterns(predictor, result)

            except Exception as e:
                st.error(f"Prediction failed: {e}")
                logger.exception("Prediction error")

    st.markdown("---")

    # Prediction history
    render_prediction_history(predictor)

    # Footer
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 2rem;'>
            <p>Built with ❤️ for portfolio demonstration</p>
            <p>Data: Deutsche Bahn (CC BY 4.0) | Weather: DWD (CC BY 4.0)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

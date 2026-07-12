import json
import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.predictor import DelayPredictor
from components.styles import inject_css, ACCENT, TEXT, MUTED, CARD, CARD2, GREEN
from components.sidebar import render_sidebar
from components.hero import render_prediction_card
from components.cards import kpi_card, render_kpi_row, render_feature_grid, recommendation_box
from components.charts import (
    probability_gauge, confidence_radar, feature_importance_bar,
    model_comparison_chart, delay_distribution,
    historical_trend_line, confusion_matrix_heatmap, roc_curve_chart,
)
from components.tables import render_history_table, render_model_comparison_table

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="DB Delay Predictor",
    page_icon="🚂",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

STATIONS = [
    "Frankfurt (Main) Hbf", "Berlin Hauptbahnhof", "München Hbf",
    "Hannover Hbf", "Hamburg Hbf", "Nürnberg Hbf", "Berlin-Spandau",
    "Köln Hbf", "Kassel-Wilhelmshöhe", "Düsseldorf Hbf",
]


@st.cache_resource
def load_predictor():
    try:
        return DelayPredictor("models/xgb_weather.joblib")
    except Exception as e:
        st.error(f"Failed to load model: {e}")
        return None


def render_top_nav():
    st.markdown(f"""
    <div class="top-nav">
        <div class="nav-left">
            <div class="nav-logo">🚂</div>
            <div>
                <div class="nav-title">DB Delay Predictor</div>
                <div class="nav-subtitle">Real-time ICE Train Delay Analytics</div>
            </div>
        </div>
        <div class="nav-right">
            <div style="display:flex; align-items:center; gap:6px; font-size:0.7rem; color:{MUTED};">
                <span style="width:6px; height:6px; border-radius:50%; background:{GREEN};"></span>
                System Online
            </div>
            <div class="nav-time">{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def predict_tab(predictor):
    st.markdown('<div class="section-title">🔍 Make a Prediction</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        station = st.selectbox("Station", options=STATIONS, key="station",
                               help="Select the station where you want to check the train")
    with col2:
        query_date = st.date_input("Date", value=date.today(), key="query_date")
    with col3:
        current_hour = datetime.now().hour
        hour = st.slider("Hour", 0, 23, value=current_hour, key="hour",
                         help="Hour to check (default: current hour)")

    col_a, col_b = st.columns([4, 1])
    with col_a:
        selection_key = f"{station}|{query_date}|{hour}"
        if st.session_state.get("_last_selection") != selection_key:
            st.session_state["_available_trains"] = None
            st.session_state["_last_selection"] = selection_key

        if st.session_state.get("_available_trains") is None:
            with st.spinner("Loading available trains..."):
                trains = predictor.get_available_trains(station, query_date, hour)
                st.session_state["_available_trains"] = trains if trains else ["No ICE trains found"]

        train_number = st.selectbox(
            "ICE Train Number",
            options=st.session_state["_available_trains"],
            key="train_number",
            help="Select an ICE train running at this station and time",
        )
    with col_b:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state["_available_trains"] = None
            st.rerun()

    if st.button("🚀 Predict Delay", type="primary", use_container_width=True):
        if not train_number or train_number == "No ICE trains found":
            st.error("No valid train selected")
            return

        with st.spinner("🔄 Fetching live data & predicting..."):
            try:
                result = predictor.predict_and_log(station, train_number, query_date, hour)
                st.session_state["_last_result"] = result
            except Exception as e:
                st.error(f"Prediction failed: {e}")
                logger.exception("Prediction error")

    # Show result if available
    if "_last_result" in st.session_state:
        result = st.session_state["_last_result"]
        if "error" not in result:
            render_prediction_hero(predictor, result)
        else:
            st.error(f"❌ {result['error']}")

    st.markdown("---")
    render_recent_predictions(predictor)


def render_prediction_hero(predictor, result):
    st.markdown('<div class="section-title">📋 Prediction Results</div>', unsafe_allow_html=True)

    # Main hero area
    col_main, col_side = st.columns([3, 2])
    with col_main:
        render_prediction_card(result)

    with col_side:
        probability = result.get("probability", 0)
        confidence = result.get("confidence", "low")
        confidence_score = result.get("confidence_score", 0)

        st.markdown("---")
        st.markdown("**📊 Probability Distribution**")
        dist_fig = delay_distribution(probability)
        st.plotly_chart(dist_fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("---")
        st.markdown("**🛡️ Confidence Profile**")
        radar_fig = confidence_radar(confidence_score, confidence)
        st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})

    # KPI row
    probability = result.get("probability", 0)
    confidence = result.get("confidence", "low")
    arr_delay = result.get("actual_arrival_delay_min")
    status = ("🔴 Delayed" if result.get("delayed") else "🟢 On Time")
    status_accent = "red" if result.get("delayed") else "green"

    if arr_delay is not None:
        trend = f"{arr_delay:+d} min"
        trend_dir = "down" if arr_delay > 0 else "up"
    else:
        trend = "Schedule"
        trend_dir = "neutral"

    render_kpi_row(
        f"{probability*100:.1f}%", "Delay Probability", "🎯", "blue", "blue",
        confidence.upper(), "Confidence Level", "📈",
        {"high": "green", "medium": "orange", "low": "red"}.get(confidence, "blue"),
        {"high": "green", "medium": "orange", "low": "red"}.get(confidence, "blue"),
        f"{arr_delay:+d} min" if arr_delay is not None else "—", "Expected Delay", "⏱️", "orange", "orange",
        status, "Train Status", "🚄", status_accent, status_accent.split("-")[0] if "-" in status_accent else status_accent,
    )

    # Charts row
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown("---")
        st.markdown("**🎯 Probability Gauge**")
        gauge_fig = probability_gauge(probability)
        st.plotly_chart(gauge_fig, use_container_width=True, config={"displayModeBar": False})

    with col_c2:
        fi = predictor.get_feature_importance()
        if fi:
            st.markdown("---")
            st.markdown("**🔬 Feature Importance**")
            fi_fig = feature_importance_bar(fi)
            st.plotly_chart(fi_fig, use_container_width=True, config={"displayModeBar": False})

    # Feature transparency
    if "features" in result:
        st.markdown(f'<div style="font-size:0.9rem; font-weight:600; color:{TEXT}; margin-top:1.5rem;">🔬 Features Used by Model</div>', unsafe_allow_html=True)
        features = result["features"]
        time_keys = {"Hour": "hour", "Day of Week": "day_of_week", "Month": "month",
                      "Season": "season", "Weekend": "is_weekend", "Rush Hour": "is_rush_hour",
                      "Holiday": "is_holiday"}
        hist_keys = {"Hist. Delay Rate": "hist_delay_rate", "Train Count": "train_count",
                      "Prev Delay": "prev_delay_min", "Prev Delayed": "prev_delayed",
                      "Dwell (min)": "planned_dwell_minutes", "First Stop": "is_first_stop"}
        weather_keys = {"Temperature": "temperature_c", "Precipitation": "precipitation_mm",
                        "Wind Speed": "wind_speed_ms", "Humidity": "humidity_pct"}
        render_feature_grid(features, time_keys, hist_keys, weather_keys)


def render_recent_predictions(predictor):
    st.markdown(f'<div class="section-title">📜 Recent Predictions</div>', unsafe_allow_html=True)
    recent = predictor.get_recent_predictions(limit=50)
    if len(recent) == 0:
        st.info("No predictions logged yet.")
        return

    total, delayed_count, avg_prob = render_history_table(recent)

    # KPI summary
    if total and total > 0:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="kpi-card accent-blue" style="padding:0.75rem 1rem;">
                <div class="kpi-card-label">Total</div>
                <div class="kpi-card-value" style="font-size:1.2rem;">{total}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="kpi-card accent-red" style="padding:0.75rem 1rem;">
                <div class="kpi-card-label">Predicted Delays</div>
                <div class="kpi-card-value" style="font-size:1.2rem; color:#EF4444;">{delayed_count}/{total}</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="kpi-card accent-orange" style="padding:0.75rem 1rem;">
                <div class="kpi-card-label">Avg Probability</div>
                <div class="kpi-card-value" style="font-size:1.2rem;">{avg_prob*100:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # Historical trend chart
    if len(recent) >= 3:
        st.markdown("---")
        st.markdown("**📈 Prediction History Trend**")
        trend_fig = historical_trend_line(recent)
        if trend_fig:
            st.plotly_chart(trend_fig, use_container_width=True, config={"displayModeBar": False})


def model_tab(predictor):
    st.markdown('<div class="section-title">📊 Model Performance</div>', unsafe_allow_html=True)

    metrics = predictor.get_model_metrics()
    if not metrics:
        st.info("No saved model metrics found. Run `python src/train.py` to generate them.")
        return

    # Prefer the artifact used by live inference; selection metadata may name
    # a comparison-only fallback model.
    best = metrics.get("_serving_model", metrics.get("_best_model", "N/A"))
    rows = metrics.get("_training_rows", "N/A")
    split = metrics.get("_split_date", "N/A")

    # Summary chips
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card accent-db" style="padding:0.75rem 1rem;">
            <div class="kpi-card-label">Best Model</div>
            <div class="kpi-card-value" style="font-size:1.1rem;">{best}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card accent-blue" style="padding:0.75rem 1rem;">
            <div class="kpi-card-label">Training Rows</div>
            <div class="kpi-card-value" style="font-size:1.1rem;">{rows:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card accent-green" style="padding:0.75rem 1rem;">
            <div class="kpi-card-label">Split Date</div>
            <div class="kpi-card-value" style="font-size:1.1rem;">{split}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        acc = metrics.get(best, {}).get("accuracy", 0)
        st.markdown(f"""
        <div class="kpi-card accent-orange" style="padding:0.75rem 1rem;">
            <div class="kpi-card-label">Accuracy</div>
            <div class="kpi-card-value" style="font-size:1.1rem;">{acc*100:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    # Model comparison
    models = {k: v for k, v in metrics.items() if not k.startswith("_")}
    if models:
        st.markdown('<div class="section-title">📋 Model Comparison</div>', unsafe_allow_html=True)
        render_model_comparison_table(models)

        # Metric comparison chart
        comp = pd.DataFrame(models).T.round(4)
        comp.index.name = "Model"
        chart_fig = model_comparison_chart(comp)
        if chart_fig:
            st.markdown("---")
            st.markdown("**📊 Metric Comparison**")
            st.plotly_chart(chart_fig, use_container_width=True, config={"displayModeBar": False})

    # Feature importance
    fi = metrics.get("_feature_importance")
    if fi:
        st.markdown('<div class="section-title">🔬 Feature Importance</div>', unsafe_allow_html=True)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("---")
            st.markdown("**📊 Importance Weights**")
            fi_fig = feature_importance_bar(fi)
            st.plotly_chart(fi_fig, use_container_width=True, config={"displayModeBar": False})
        with col_f2:
            # Additional metrics from best model
            best_metrics = metrics.get(best, {})
            cm = {
                "tn": best_metrics.get("tn", 0),
                "fp": best_metrics.get("fp", 0),
                "fn": best_metrics.get("fn", 0),
                "tp": best_metrics.get("tp", 0),
            }
            if any(cm.values()):
                st.markdown("---")
                st.markdown("**📊 Confusion Matrix**")
                cm_fig = confusion_matrix_heatmap(cm)
                st.plotly_chart(cm_fig, use_container_width=True, config={"displayModeBar": False})

            auc = best_metrics.get("roc_auc", 0)
            if auc:
                st.markdown("---")
                st.markdown(f"**📈 ROC Curve** (AUC={auc:.3f})")
                roc_fig = roc_curve_chart(auc)
                st.plotly_chart(roc_fig, use_container_width=True, config={"displayModeBar": False})

    # Training details
    st.markdown('<div class="section-title">📋 Training Configuration</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="prediction-card" style="padding:1rem 1.25rem;">
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem;">
            <div>
                <div style="font-size:0.65rem; color:{MUTED}; text-transform:uppercase; letter-spacing:0.3px;">Best Model</div>
                <div style="font-size:0.95rem; font-weight:600; color:{TEXT}; margin-top:2px;">{metrics.get("_best_model", "N/A")}</div>
            </div>
            <div>
                <div style="font-size:0.65rem; color:{MUTED}; text-transform:uppercase; letter-spacing:0.3px;">Training Date</div>
                <div style="font-size:0.95rem; font-weight:600; color:{TEXT}; margin-top:2px;">{metrics.get("_training_date", "N/A")}</div>
            </div>
            <div>
                <div style="font-size:0.65rem; color:{MUTED}; text-transform:uppercase; letter-spacing:0.3px;">Split Date</div>
                <div style="font-size:0.95rem; font-weight:600; color:{TEXT}; margin-top:2px;">{metrics.get("_split_date", "N/A")}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def about_tab():
    st.markdown('<div class="section-title">ℹ️ About This Project</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown(f"""
        <div class="prediction-card" style="padding:1.5rem;">
            <h3 style="color:{TEXT}; font-weight:700; margin-bottom:1rem;">How it works</h3>
            <ol style="color:{MUTED}; line-height:1.8; padding-left:1.2rem;">
                <li><strong style="color:{TEXT};">Live API</strong> — Fetches real-time ICE train schedules from the
                    DB Timetables API. Actual delay data is merged from the changes endpoint.</li>
                <li><strong style="color:{TEXT};">Feature Engineering</strong> — Converts raw timetable + weather data into
                    ML features: time patterns, historical delay rates, cascading delay
                    from live arrival data, and DWD weather conditions.</li>
                <li><strong style="color:{TEXT};">XGBoost Model</strong> — Gradient-boosted decision tree trained on 750K+
                    historical observations (Jul 2024 – Nov 2025) across Germany's top 10
                    ICE stations. The model achieves ~74.7% accuracy in predicting
                    delays &gt;5 minutes.</li>
                <li><strong style="color:{TEXT};">Live Feedback</strong> — When real-time delay data is available from the
                    API, the model uses the actual arrival delay as a cascading feature,
                    dramatically improving prediction accuracy.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="prediction-card" style="padding:1.5rem; margin-top:1rem;">
            <h3 style="color:{TEXT}; font-weight:700; margin-bottom:1rem;">Data Sources</h3>
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <th style="text-align:left; color:{MUTED}; padding:0.5rem 0; font-weight:600;">Source</th>
                    <th style="text-align:left; color:{MUTED}; padding:0.5rem 0; font-weight:600;">Data</th>
                    <th style="text-align:left; color:{MUTED}; padding:0.5rem 0; font-weight:600;">License</th>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                    <td style="padding:0.5rem 0; color:{TEXT};">DB Timetables API</td>
                    <td style="padding:0.5rem 0; color:{MUTED};">Live train schedules & delays</td>
                    <td style="padding:0.5rem 0; color:{MUTED};">CC BY 4.0</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                    <td style="padding:0.5rem 0; color:{TEXT};">DWD Open Data</td>
                    <td style="padding:0.5rem 0; color:{MUTED};">Hourly weather (temp, precip, wind, humidity)</td>
                    <td style="padding:0.5rem 0; color:{MUTED};">CC BY 4.0</td>
                </tr>
                <tr>
                    <td style="padding:0.5rem 0; color:{TEXT};">DB Historical Data</td>
                    <td style="padding:0.5rem 0; color:{MUTED};">750K+ ICE delay records (2024-2025)</td>
                    <td style="padding:0.5rem 0; color:{MUTED};">CC BY 4.0</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="prediction-card" style="padding:1.5rem;">
            <h3 style="color:{TEXT}; font-weight:700; margin-bottom:1rem;">Tech Stack</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem;">
                <div style="background:{CARD2}; border-radius:10px; padding:0.6rem 0.8rem; text-align:center;">
                    <div style="font-size:0.65rem; color:{MUTED};">Frontend</div>
                    <div style="font-size:0.85rem; font-weight:600; color:{TEXT};">Streamlit</div>
                </div>
                <div style="background:{CARD2}; border-radius:10px; padding:0.6rem 0.8rem; text-align:center;">
                    <div style="font-size:0.65rem; color:{MUTED};">Model</div>
                    <div style="font-size:0.85rem; font-weight:600; color:{TEXT};">XGBoost</div>
                </div>
                <div style="background:{CARD2}; border-radius:10px; padding:0.6rem 0.8rem; text-align:center;">
                    <div style="font-size:0.65rem; color:{MUTED};">Database</div>
                    <div style="font-size:0.85rem; font-weight:600; color:{TEXT};">Supabase</div>
                </div>
                <div style="background:{CARD2}; border-radius:10px; padding:0.6rem 0.8rem; text-align:center;">
                    <div style="font-size:0.65rem; color:{MUTED};">API</div>
                    <div style="font-size:0.85rem; font-weight:600; color:{TEXT};">DB Timetables</div>
                </div>
                <div style="background:{CARD2}; border-radius:10px; padding:0.6rem 0.8rem; text-align:center;">
                    <div style="font-size:0.65rem; color:{MUTED};">Weather</div>
                    <div style="font-size:0.85rem; font-weight:600; color:{TEXT};">DWD</div>
                </div>
                <div style="background:{CARD2}; border-radius:10px; padding:0.6rem 0.8rem; text-align:center;">
                    <div style="font-size:0.65rem; color:{MUTED};">Charts</div>
                    <div style="font-size:0.85rem; font-weight:600; color:{TEXT};">Plotly</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="prediction-card" style="padding:1.5rem; margin-top:1rem;">
            <h3 style="color:{TEXT}; font-weight:700; margin-bottom:1rem;">Key Features</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.4rem;">
                {''.join(f'<div style="display:flex; align-items:center; gap:6px; font-size:0.8rem; color:{MUTED}; padding:0.3rem 0;"><span style="color:{TEXT};">•</span> {f}</div>' for f in [
                    'Real-time API integration', 'Cascading delay awareness',
                    'Weather-enriched predictions', 'Feature transparency',
                    'Live delay monitoring', 'Prediction logging',
                ])}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="text-align:center; padding:1.5rem 0; color:{MUTED}; font-size:0.8rem;">
            Built with ❤️ for portfolio demonstration
        </div>
        """, unsafe_allow_html=True)


def main():
    predictor = load_predictor()
    if not predictor:
        st.error("Failed to load model. Check that `models/xgb_weather.joblib` exists.")
        return

    selected = render_sidebar(predictor)

    render_top_nav()

    if selected == "Predict":
        predict_tab(predictor)
    elif selected == "Model Performance":
        model_tab(predictor)
    elif selected == "About":
        about_tab()

    st.markdown(f"""
    <div style="text-align:center; color:{MUTED}; padding:1rem 0; font-size:0.75rem;">
        Data © Deutsche Bahn AG (CC BY 4.0) · Weather © DWD (CC BY 4.0)
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

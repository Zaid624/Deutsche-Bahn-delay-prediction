import streamlit as st
from components.styles import CARD, CARD2, TEXT, MUTED, GREEN, ORANGE, RED

def kpi_card(icon: str, icon_bg: str, label: str, value: str,
             accent: str, trend: str = "", trend_dir: str = "neutral"):
    st.markdown(f"""
    <div class="kpi-card accent-{accent}">
        <div class="kpi-card-icon {icon_bg}">{icon}</div>
        <div class="kpi-card-label">{label}</div>
        <div class="kpi-card-value">{value}</div>
        {"<div class='kpi-card-trend " + trend_dir + "'>" + trend + "</div>" if trend else ""}
    </div>
    """, unsafe_allow_html=True)

def render_kpi_row(col1_val, col1_label, col1_icon, col1_accent, col1_icon_bg,
                   col2_val, col2_label, col2_icon, col2_accent, col2_icon_bg,
                   col3_val, col3_label, col3_icon, col3_accent, col3_icon_bg,
                   col4_val, col4_label, col4_icon, col4_accent, col4_icon_bg):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(col1_icon, col1_icon_bg, col1_label, col1_val, col1_accent)
    with c2:
        kpi_card(col2_icon, col2_icon_bg, col2_label, col2_val, col2_accent)
    with c3:
        kpi_card(col3_icon, col3_icon_bg, col3_label, col3_val, col3_accent)
    with c4:
        kpi_card(col4_icon, col4_icon_bg, col4_label, col4_val, col4_accent)

BOOLEAN_FEATURES = {"Weekend", "Rush Hour", "Holiday", "First Stop", "Prev Delayed"}

def render_feature_grid(features: dict, time_keys: dict, hist_keys: dict, weather_keys: dict):
    items_html = ""
    for section_label, keys in [("⏰ Time", time_keys), ("📊 Historical", hist_keys), ("🌤️ Weather", weather_keys)]:
        for k, v in keys.items():
            val = features.get(v)
            if isinstance(val, int) and k in BOOLEAN_FEATURES:
                val = "Yes" if val else "No"
            elif isinstance(val, float):
                val = f"{val:.2f}" if abs(val) < 10 else f"{val:.1f}"
            elif val is None:
                val = "N/A"
            items_html += f"""
            <div class="feature-item">
                <div class="feature-item-label">{k}</div>
                <div class="feature-item-value">{val}</div>
            </div>"""

    st.markdown(f'<div class="feature-grid">{items_html}</div>', unsafe_allow_html=True)

def recommendation_box(message: str, emoji: str = "📌"):
    st.markdown(f"""
    <div class="rec-box">
        <div class="rec-box-title">{emoji} Recommendation</div>
        <div class="rec-box-text">{message}</div>
    </div>
    """, unsafe_allow_html=True)

from datetime import datetime
import streamlit as st
from streamlit_option_menu import option_menu
from components.styles import DB_RED, TEXT, MUTED, CARD, CARD2, BG

def render_sidebar(predictor):
    with st.sidebar:
        # Logo + Brand
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:12px; padding:0.5rem 0 0.5rem 0;">
            <div style="width:40px; height:40px; background:linear-gradient(135deg, {DB_RED}, #ff4d4d);
                        border-radius:12px; display:flex; align-items:center; justify-content:center;
                        font-size:1.2rem; font-weight:900; color:white; box-shadow:0 2px 8px rgba(236,0,22,0.4);">
                🚂
            </div>
            <div>
                <div style="font-size:1.1rem; font-weight:700; color:{TEXT}; letter-spacing:-0.3px;">DB Predictor</div>
                <div style="font-size:0.7rem; color:{MUTED};">Real-time Delay Analytics</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<hr style='border-color:rgba(255,255,255,0.06); margin:0.75rem 0;'>", unsafe_allow_html=True)

        # Navigation
        selected = option_menu(
            menu_title=None,
            options=["Predict", "Model Performance", "About"],
            icons=["speedometer2", "bar-chart", "info-circle"],
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": MUTED, "font-size": "14px"},
                "nav-link": {
                    "font-size": "13px", "font-weight": "500",
                    "padding": "8px 12px", "border-radius": "10px",
                    "color": MUTED, "margin": "2px 0",
                },
                "nav-link-selected": {
                    "background": f"linear-gradient(135deg, {DB_RED}, #cc0012)",
                    "color": "white", "font-weight": "600",
                },
            },
        )

        st.markdown(f"<hr style='border-color:rgba(255,255,255,0.06); margin:1rem 0;'>", unsafe_allow_html=True)

        # Model Performance Card
        metrics = predictor.get_model_metrics() if predictor else {}
        best = metrics.get("_best_model", "XGBoost + Weather")
        acc = metrics.get(best, {}).get("accuracy", 0.747)
        auc = metrics.get(best, {}).get("roc_auc", 0)

        st.markdown(f"""
        <div style="background:{CARD}; border:1px solid rgba(255,255,255,0.06); border-radius:16px;
                    padding:1rem 1.25rem; margin-bottom:1rem;">
            <div style="font-size:0.7rem; font-weight:600; color:{MUTED}; text-transform:uppercase;
                        letter-spacing:0.5px; margin-bottom:0.75rem;">📊 Model Performance</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                <div style="font-size:0.75rem; color:{MUTED};">Accuracy</div>
                <div style="font-size:1.1rem; font-weight:700; color:{TEXT};">{acc*100:.1f}%</div>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <div style="font-size:0.75rem; color:{MUTED};">ROC-AUC</div>
                <div style="font-size:1.1rem; font-weight:700; color:{TEXT};">{('%.3f' % auc) if auc else 'N/A'}</div>
            </div>
            <div style="margin-top:0.5rem; font-size:0.65rem; color:{MUTED};">
                Best: {best}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Key Features Card
        st.markdown(f"""
        <div style="background:{CARD}; border:1px solid rgba(255,255,255,0.06); border-radius:16px;
                    padding:1rem 1.25rem; margin-bottom:1rem;">
            <div style="font-size:0.7rem; font-weight:600; color:{MUTED}; text-transform:uppercase;
                        letter-spacing:0.5px; margin-bottom:0.75rem;">🔑 ML Features</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; font-size:0.75rem;">
                <div style="color:{MUTED};">⏰ Hour, DOW, Month</div>
                <div style="color:{MUTED};">📅 Season, Holiday</div>
                <div style="color:{MUTED};">🚄 Rush Hour Ind.</div>
                <div style="color:{MUTED};">📊 Hist. Delay Rate</div>
                <div style="color:{MUTED};">🔄 Cascading Delay</div>
                <div style="color:{MUTED};">🌤️ Weather Data</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Status Footer
        st.markdown(f"""
        <div style="margin-top:auto; padding-top:1rem;">
            <div style="display:flex; align-items:center; gap:6px; font-size:0.7rem; color:{MUTED};">
                <span style="width:7px; height:7px; border-radius:50%; background:#22C55E; animation:pulse 2s infinite;"></span>
                System Online
            </div>
            <div style="font-size:0.65rem; color:{MUTED}; margin-top:4px;">
                {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
            <div style="font-size:0.6rem; color:{MUTED}; margin-top:8px;">
                Data: DB AG (CC BY 4.0) · DWD (CC BY 4.0)
            </div>
        </div>
        <style>
            @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
        </style>
        """, unsafe_allow_html=True)

    return selected

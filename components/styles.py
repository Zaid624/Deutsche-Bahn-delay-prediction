BG = "#0C0D0E"
CARD = "#1A1C1E"
CARD2 = "#2B2D30"
TEXT = "#EDEEF0"
MUTED = "#868A91"
ACCENT = "#3B82F6"
GREEN = "#22C55E"
ORANGE = "#EAB308"
RED = "#EF4444"
FONT_SANS = "Inter"
FONT_MONO = "JetBrains Mono"
SPACING = (4, 8, 12, 16, 24, 32, 48)
RADIUS_SM = "4px"
RADIUS_LG = "8px"

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

* {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}

.stApp {{
    background-color: {BG};
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: #475569; }}

/* ── Top Navigation ── */
.top-nav {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.5rem;
    background: {CARD};
    border: 1px solid {CARD2};
    border-radius: {RADIUS_LG};
    margin-bottom: 1.5rem;
}}
.nav-left {{ display: flex; align-items: center; gap: 12px; }}
.nav-logo {{
    width: 32px; height: 32px;
    background: {ACCENT};
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; font-weight: 700; color: white;
}}
.nav-title {{ font-size: 1.15rem; font-weight: 700; color: {TEXT}; letter-spacing: -0.3px; }}
.nav-subtitle {{ font-size: 0.7rem; color: {MUTED}; }}
.nav-right {{ display: flex; align-items: center; gap: 16px; }}
.nav-time {{ font-size: 0.75rem; color: {MUTED}; font-family: '{FONT_MONO}'; }}

/* ── Hero Section ── */
.hero-container {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1rem;
    margin-bottom: 1.5rem;
}}
.hero-main {{
    background: {CARD};
    border: 1px solid {CARD2};
    border-radius: {RADIUS_LG};
    padding: 1.75rem;
}}
.hero-side {{
    display: flex;
    flex-direction: column;
    gap: 1rem;
}}

/* ── Prediction Result Card ── */
.prediction-card {{
    background: {CARD};
    border: 1px solid {CARD2};
    border-radius: {RADIUS_LG};
    padding: 1.75rem;
}}

/* ── Probability Ring ── */
.prob-ring-container {{
    display: flex; flex-direction: column; align-items: center;
    justify-content: center;
    padding: 1rem;
}}
.prob-ring-svg {{
    width: 130px; height: 130px;
    transform: rotate(-90deg);
}}
.prob-ring-bg {{ fill: none; stroke: #1e293b; stroke-width: 8; }}
.prob-ring-fg {{ fill: none; stroke-width: 8; stroke-linecap: round; transition: stroke-dashoffset 0.8s ease; }}
.prob-ring-text {{
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    font-size: 1.8rem; font-weight: 800;
}}
.prob-ring-label {{
    font-size: 0.7rem; color: {MUTED}; text-align: center; margin-top: 0.25rem;
}}

/* ── KPI Cards ── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}}
.kpi-card {{
    background: {CARD};
    border: 1px solid {CARD2};
    border-radius: {RADIUS_LG};
    padding: 1rem 1.25rem;
}}
.kpi-card.accent-blue {{ border-top: 3px solid {ACCENT}; }}
.kpi-card.accent-green {{ border-top: 3px solid {GREEN}; }}
.kpi-card.accent-orange {{ border-top: 3px solid {ORANGE}; }}
.kpi-card.accent-red {{ border-top: 3px solid {RED}; }}
.kpi-card.accent-db {{ border-top: 3px solid {ACCENT}; }}

.kpi-card-icon {{
    width: 36px; height: 36px;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; margin-bottom: 0.5rem;
}}
.kpi-card-icon.blue {{ background: rgba(59,130,246,0.12); }}
.kpi-card-icon.green {{ background: rgba(34,197,94,0.12); }}
.kpi-card-icon.orange {{ background: rgba(217,119,6,0.12); }}
.kpi-card-icon.red {{ background: rgba(239,68,68,0.12); }}

.kpi-card-label {{ font-size: 0.7rem; color: {MUTED}; font-weight: 500; margin-bottom: 0.2rem; }}
.kpi-card-value {{ font-size: 1.4rem; font-weight: 700; color: {TEXT}; letter-spacing: -0.3px; font-family: '{FONT_MONO}'; }}
.kpi-card-trend {{ font-size: 0.7rem; font-weight: 600; display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: {RADIUS_SM}; margin-top: 0.4rem; }}
.kpi-card-trend.up {{ color: {GREEN}; background: rgba(34,197,94,0.1); }}
.kpi-card-trend.down {{ color: {RED}; background: rgba(239,68,68,0.1); }}
.kpi-card-trend.neutral {{ color: {MUTED}; background: rgba(148,163,184,0.1); }}

/* ── Feature Box ── */
.feature-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.6rem;
    margin-top: 0.5rem;
}}
.feature-item {{
    background: {CARD2};
    border: 1px solid transparent;
    border-radius: {RADIUS_SM};
    padding: 0.5rem 0.75rem;
}}
.feature-item-label {{ font-size: 0.65rem; color: {MUTED}; letter-spacing: 0.3px; }}
.feature-item-value {{ font-size: 0.85rem; font-weight: 600; color: {TEXT}; font-family: '{FONT_MONO}'; }}

/* ── Live Banner ── */
.live-banner {{
    padding: 0.6rem 1rem;
    border-radius: 6px;
    font-weight: 500; font-size: 0.8rem;
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 1rem;
    border: 1px solid {CARD2};
}}
.live-banner.green {{ background: rgba(34,197,94,0.1); color: {GREEN}; border-color: rgba(34,197,94,0.2); }}
.live-banner.yellow {{ background: rgba(245,158,11,0.1); color: {ORANGE}; border-color: rgba(245,158,11,0.2); }}
.live-banner.red {{ background: rgba(239,68,68,0.1); color: {RED}; border-color: rgba(239,68,68,0.2); }}
.live-banner.blue {{ background: rgba(59,130,246,0.1); color: {ACCENT}; border-color: rgba(59,130,246,0.2); }}

/* ── Route Bar ── */
.route-bar {{
    display: flex; align-items: center; gap: 6px;
    overflow-x: auto; padding: 0.6rem 0; flex-wrap: wrap;
}}
.route-stop {{
    background: {CARD2};
    border: 1px solid {CARD2};
    border-radius: {RADIUS_SM};
    padding: 3px 10px;
    font-size: 0.75rem; font-weight: 500; color: {MUTED};
    white-space: nowrap;
}}
.route-stop.current {{
    background: {ACCENT} !important;
    color: white !important;
    font-weight: 700;
    border-color: {ACCENT} !important;
}}
.route-arrow {{ color: #475569; font-size: 0.7rem; }}

/* ── Section Title ── */
.section-title {{
    font-size: 1rem; font-weight: 600; color: {TEXT};
    margin: 1.5rem 0 1rem 0;
}}

/* ── Form Controls ── */
.stSelectbox label, .stDateInput label, .stSlider label {{
    color: {MUTED} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}}
div[data-baseweb="select"] > div {{
    background-color: {CARD2} !important;
    border: 1px solid {CARD2} !important;
    border-radius: {RADIUS_SM} !important;
    color: {TEXT} !important;
}}
div[data-baseweb="select"] > div > div {{
    color: {TEXT} !important;
}}
.stDateInput > div > div > input {{
    background-color: {CARD2} !important;
    border: 1px solid {CARD2} !important;
    border-radius: {RADIUS_SM} !important;
    color: {TEXT} !important;
}}
.stSlider > div > div {{
    color: {TEXT} !important;
}}
div[data-baseweb="slider"] > div > div[data-testid="stSliderTrack"] {{
    background: {ACCENT} !important;
}}
div[data-baseweb="slider"] [data-testid="stTickBar"],
div[data-baseweb="slider"] [data-testid="stTickBar"] > div {{
    background: transparent !important;
    color: {MUTED} !important;
}}
.stSlider .st-bn {{
    color: {TEXT} !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
}}

/* ── Buttons ── */
.stButton > button {{
    font-weight: 600 !important;
    border-radius: 6px !important;
    border: 1px solid {ACCENT} !important;
    background: {ACCENT} !important;
    color: white !important;
    padding: 0.4rem 1.25rem !important;
    cursor: pointer !important;
}}
.stButton > button:hover {{
    background: #2563EB !important;
    border-color: #2563EB !important;
}}
div.stButton > button:first-child {{ width: 100%; }}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 2px;
    background: {CARD};
    border-radius: {RADIUS_LG};
    padding: 3px;
    border: 1px solid {CARD2};
    margin-bottom: 1.5rem;
}}
.stTabs [data-baseweb="tab"] {{
    color: {MUTED} !important;
    font-weight: 500 !important;
    font-size: 0.8rem !important;
    border-radius: {RADIUS_SM} !important;
    padding: 0.4rem 0.9rem !important;
    border: none !important;
}}
.stTabs [aria-selected="true"] {{
    background: {ACCENT} !important;
    color: white !important;
}}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {{
    color: {TEXT} !important;
    background: rgba(255,255,255,0.04) !important;
}}

/* ── Metrics ── */
div[data-testid="stMetric"] {{
    background: transparent !important;
    padding: 0 !important;
    border-radius: 0 !important;
}}
div[data-testid="stMetric"] > div {{
    color: {TEXT} !important;
}}
div[data-testid="stMetric"] label {{
    color: {MUTED} !important;
}}

/* ── DataFrames ── */
.stDataFrame {{
    color: {TEXT} !important;
}}
.stDataFrame [data-testid="StyledDataFrameDataTable"] {{
    background: {CARD} !important;
    border-radius: {RADIUS_LG} !important;
    border: 1px solid {CARD2} !important;
}}

/* ── Info / Error / Success boxes ── */
.stAlert {{
    background: {CARD2} !important;
    color: {TEXT} !important;
    border-radius: {RADIUS_LG} !important;
    border: 1px solid {CARD2} !important;
}}

/* ── Spinner ── */
.stSpinner > div > div {{
    border-color: {ACCENT} transparent transparent transparent !important;
}}

/* ── Expander ── */
.streamlit-expanderHeader {{
    color: {TEXT} !important;
    font-weight: 600 !important;
    background: {CARD} !important;
    border-radius: {RADIUS_LG} !important;
    border: 1px solid {CARD2} !important;
}}

/* ── Footer ── */
footer {{ display: none; }}

/* ── Global text fixes ── */
p, li, span, h1, h2, h3, h4, h5, h6, .stMarkdown {{
    color: {TEXT};
}}
a {{
    color: {ACCENT};
}}

/* ── Recommendation Box ── */
.rec-box {{
    background: {CARD};
    border: 1px solid {CARD2};
    border-radius: {RADIUS_LG};
    padding: 1rem 1.25rem;
    margin-top: 0.75rem;
}}
.rec-box-title {{
    font-size: 0.7rem; font-weight: 600; color: {MUTED};
    margin-bottom: 0.3rem;
}}
.rec-box-text {{
    font-size: 0.9rem; font-weight: 500; color: {TEXT};
    line-height: 1.4;
}}

/* ── Confidence Badge ── */
.conf-badge {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 10px; border-radius: {RADIUS_SM};
    font-size: 0.7rem; font-weight: 600;
}}
.conf-badge.high {{ background: rgba(34,197,94,0.15); color: {GREEN}; }}
.conf-badge.medium {{ background: rgba(245,158,11,0.15); color: {ORANGE}; }}
.conf-badge.low {{ background: rgba(239,68,68,0.15); color: {RED}; }}

/* ── Glass panels ── */
.glass {{
    background: {CARD};
    border: 1px solid {CARD2};
}}

/* ── Responsive ── */
@media (max-width: 1200px) {{
    .hero-container {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .feature-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media (max-width: 768px) {{
    .kpi-grid {{ grid-template-columns: 1fr; }}
    .feature-grid {{ grid-template-columns: 1fr; }}
    .top-nav {{ flex-direction: column; gap: 8px; padding: 0.75rem 1rem; }}
    .nav-right {{ width: 100%; justify-content: center; }}
}}
"""

def inject_css():
    import streamlit as st
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

BG = "#0B1220"
CARD = "#111827"
CARD2 = "#1E293B"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
DB_RED = "#EC0016"
GREEN = "#22C55E"
ORANGE = "#F59E0B"
RED = "#EF4444"
BLUE = "#3B82F6"

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

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
    background: linear-gradient(135deg, {CARD} 0%, #151E33 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}}
.nav-left {{ display: flex; align-items: center; gap: 12px; }}
.nav-logo {{
    width: 36px; height: 36px;
    background: linear-gradient(135deg, {DB_RED}, #ff4d4d);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; font-weight: 900; color: white;
    box-shadow: 0 2px 8px rgba({DB_RED},0.4);
}}
.nav-title {{ font-size: 1.15rem; font-weight: 700; color: {TEXT}; letter-spacing: -0.3px; }}
.nav-subtitle {{ font-size: 0.75rem; color: {MUTED}; }}
.nav-right {{ display: flex; align-items: center; gap: 16px; }}
.nav-status {{
    display: flex; align-items: center; gap: 6px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.75rem; font-weight: 500;
}}
.nav-status.online {{ background: rgba(34,197,94,0.15); color: {GREEN}; }}
.nav-status.dot {{ width: 7px; height: 7px; border-radius: 50%; background: {GREEN}; animation: pulse 2s infinite; }}
.nav-time {{ font-size: 0.75rem; color: {MUTED}; }}

@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.3; }}
}}

/* ── Hero Section ── */
.hero-container {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1.25rem;
    margin-bottom: 1.5rem;
}}
.hero-main {{
    background: linear-gradient(145deg, {CARD} 0%, #141d33 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 22px;
    padding: 1.75rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.25);
    position: relative;
    overflow: hidden;
}}
.hero-main::before {{
    content: '';
    position: absolute;
    top: -50%; right: -50%;
    width: 100%; height: 100%;
    background: radial-gradient(circle, rgba({DB_RED.replace('#','')},0.03) 0%, transparent 70%);
    pointer-events: none;
}}
.hero-side {{
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}}

/* ── Prediction Result Card ── */
.prediction-card {{
    background: {CARD};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 22px;
    padding: 1.75rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.25);
    transition: transform 0.2s, box-shadow 0.2s;
}}
.prediction-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.35);
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
    gap: 1.25rem;
    margin-bottom: 1.5rem;
}}
.kpi-card {{
    background: linear-gradient(145deg, {CARD} 0%, #141d33 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
    cursor: default;
}}
.kpi-card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    border-color: rgba(255,255,255,0.12);
}}
.kpi-card::after {{
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 3px;
}}
.kpi-card.accent-blue::after {{ background: linear-gradient(90deg, {BLUE}, #60A5FA); }}
.kpi-card.accent-green::after {{ background: linear-gradient(90deg, {GREEN}, #4ADE80); }}
.kpi-card.accent-orange::after {{ background: linear-gradient(90deg, {ORANGE}, #FBBF24); }}
.kpi-card.accent-red::after {{ background: linear-gradient(90deg, {RED}, #F87171); }}
.kpi-card.accent-db::after {{ background: linear-gradient(90deg, {DB_RED}, #ff4d4d); }}

.kpi-card-icon {{
    width: 40px; height: 40px;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; margin-bottom: 0.75rem;
}}
.kpi-card-icon.blue {{ background: rgba(59,130,246,0.15); }}
.kpi-card-icon.green {{ background: rgba(34,197,94,0.15); }}
.kpi-card-icon.orange {{ background: rgba(245,158,11,0.15); }}
.kpi-card-icon.red {{ background: rgba(239,68,68,0.15); }}

.kpi-card-label {{ font-size: 0.75rem; color: {MUTED}; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.3rem; }}
.kpi-card-value {{ font-size: 1.6rem; font-weight: 800; color: {TEXT}; letter-spacing: -0.5px; }}
.kpi-card-trend {{ font-size: 0.7rem; font-weight: 600; display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: 10px; margin-top: 0.4rem; }}
.kpi-card-trend.up {{ color: {GREEN}; background: rgba(34,197,94,0.1); }}
.kpi-card-trend.down {{ color: {RED}; background: rgba(239,68,68,0.1); }}
.kpi-card-trend.neutral {{ color: {MUTED}; background: rgba(148,163,184,0.1); }}

/* ── Chart Cards ── */
.chart-card {{
    background: linear-gradient(145deg, {CARD} 0%, #141d33 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 1.25rem 1.25rem 0.75rem 1.25rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    transition: all 0.25s ease;
    height: 100%;
}}
.chart-card:hover {{
    border-color: rgba(255,255,255,0.12);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}}
.chart-card-title {{
    font-size: 0.85rem; font-weight: 600; color: {TEXT};
    margin-bottom: 0.75rem; display: flex; align-items: center; gap: 8px;
}}
.chart-card-title .badge {{
    font-size: 0.6rem; font-weight: 600; padding: 2px 8px;
    border-radius: 6px; background: rgba(236,0,22,0.12); color: {DB_RED};
    text-transform: uppercase; letter-spacing: 0.3px;
}}

/* ── Feature Box ── */
.feature-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.6rem;
    margin-top: 0.5rem;
}}
.feature-item {{
    background: {CARD2};
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 10px;
    padding: 0.5rem 0.75rem;
    transition: all 0.2s;
}}
.feature-item:hover {{
    background: rgba(255,255,255,0.04);
    border-color: rgba(255,255,255,0.08);
}}
.feature-item-label {{ font-size: 0.65rem; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.3px; }}
.feature-item-value {{ font-size: 0.85rem; font-weight: 600; color: {TEXT}; }}

/* ── Live Banner ── */
.live-banner {{
    padding: 0.7rem 1.2rem;
    border-radius: 12px;
    font-weight: 600; font-size: 0.85rem;
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 1rem;
    border: 1px solid rgba(255,255,255,0.06);
}}
.live-banner.green {{ background: rgba(34,197,94,0.1); color: {GREEN}; border-color: rgba(34,197,94,0.2); }}
.live-banner.yellow {{ background: rgba(245,158,11,0.1); color: {ORANGE}; border-color: rgba(245,158,11,0.2); }}
.live-banner.red {{ background: rgba(239,68,68,0.1); color: {RED}; border-color: rgba(239,68,68,0.2); }}
.live-banner.blue {{ background: rgba(59,130,246,0.1); color: {BLUE}; border-color: rgba(59,130,246,0.2); }}

/* ── Route Bar ── */
.route-bar {{
    display: flex; align-items: center; gap: 6px;
    overflow-x: auto; padding: 0.6rem 0; flex-wrap: wrap;
}}
.route-stop {{
    background: {CARD2};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 3px 12px;
    font-size: 0.75rem; font-weight: 500; color: {MUTED};
    white-space: nowrap;
    transition: all 0.2s;
}}
.route-stop:hover {{ border-color: rgba(255,255,255,0.15); color: {TEXT}; }}
.route-stop.current {{
    background: {DB_RED} !important;
    color: white !important;
    font-weight: 700;
    border-color: {DB_RED} !important;
    box-shadow: 0 2px 8px rgba(236,0,22,0.3);
}}
.route-arrow {{ color: #475569; font-size: 0.7rem; }}

/* ── Section Title ── */
.section-title {{
    font-size: 1.15rem; font-weight: 700; color: {TEXT};
    margin: 1.5rem 0 1rem 0;
    letter-spacing: -0.3px;
}}

/* ── Form Controls ── */
.stSelectbox label, .stDateInput label, .stSlider label {{
    color: {MUTED} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}}
div[data-baseweb="select"] > div {{
    background-color: {CARD2} !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    color: {TEXT} !important;
}}
div[data-baseweb="select"]:hover > div {{
    border-color: rgba(255,255,255,0.2) !important;
}}
div[data-baseweb="select"] > div > div {{
    color: {TEXT} !important;
}}
.stDateInput > div > div > input {{
    background-color: {CARD2} !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    color: {TEXT} !important;
}}
.stSlider > div > div {{
    color: {TEXT} !important;
}}
div[data-baseweb="slider"] > div > div[data-testid="stSliderTrack"] {{
    background: {DB_RED} !important;
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
    border-radius: 12px !important;
    border: none !important;
    background: linear-gradient(135deg, {DB_RED}, #ff4d4d) !important;
    color: white !important;
    box-shadow: 0 4px 16px rgba(236,0,22,0.25) !important;
    transition: all 0.25s ease !important;
    padding: 0.5rem 1.5rem !important;
}}
.stButton > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px rgba(236,0,22,0.4) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
}}
div.stButton > button:first-child {{ width: 100%; }}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    background: {CARD};
    border-radius: 14px;
    padding: 4px;
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 1.5rem;
}}
.stTabs [data-baseweb="tab"] {{
    color: {MUTED} !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    border-radius: 10px !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s !important;
    border: none !important;
}}
.stTabs [aria-selected="true"] {{
    background: {DB_RED} !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(236,0,22,0.3) !important;
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
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
}}

/* ── Info / Error / Success boxes ── */
.stAlert {{
    background: {CARD2} !important;
    color: {TEXT} !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
}}

/* ── Spinner ── */
.stSpinner > div > div {{
    border-color: {DB_RED} transparent transparent transparent !important;
}}

/* ── Expander ── */
.streamlit-expanderHeader {{
    color: {TEXT} !important;
    font-weight: 600 !important;
    background: {CARD} !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
}}

/* ── Footer ── */
footer {{ display: none; }}

/* ── Global text fixes ── */
p, li, span, h1, h2, h3, h4, h5, h6, .stMarkdown {{
    color: {TEXT};
}}
a {{
    color: {BLUE};
}}

/* ── Recommendation Box ── */
.rec-box {{
    background: linear-gradient(135deg, rgba(236,0,22,0.08), rgba(236,0,22,0.02));
    border: 1px solid rgba(236,0,22,0.15);
    border-radius: 14px;
    padding: 1rem 1.25rem;
    margin-top: 0.75rem;
}}
.rec-box-title {{
    font-size: 0.75rem; font-weight: 600; color: {MUTED};
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 0.3rem;
}}
.rec-box-text {{
    font-size: 0.9rem; font-weight: 500; color: {TEXT};
    line-height: 1.4;
}}

/* ── Confidence Badge ── */
.conf-badge {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 12px; border-radius: 20px;
    font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.3px;
}}
.conf-badge.high {{ background: rgba(34,197,94,0.15); color: {GREEN}; }}
.conf-badge.medium {{ background: rgba(245,158,11,0.15); color: {ORANGE}; }}
.conf-badge.low {{ background: rgba(239,68,68,0.15); color: {RED}; }}

/* ── Glass panels ── */
.glass {{
    background: rgba(17,24,39,0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.06);
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

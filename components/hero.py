import streamlit as st
from components.styles import TEXT, MUTED, CARD, CARD2, GREEN, ORANGE, RED

def render_probability_ring(prob: float, size: int = 130, stroke: int = 8):
    color = GREEN if prob < 0.4 else ORANGE if prob < 0.7 else RED
    r = (size - stroke) / 2
    circumference = 2 * 3.14159 * r
    offset = circumference * (1 - prob)
    center = size / 2

    st.markdown(f"""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:0.5rem; position:relative;">
        <svg width="{size}" height="{size}" style="transform:rotate(-90deg);">
            <circle cx="{center}" cy="{center}" r="{r}" fill="none"
                    stroke="#1e293b" stroke-width="{stroke}"/>
            <circle cx="{center}" cy="{center}" r="{r}" fill="none"
                    stroke="{color}" stroke-width="{stroke}" stroke-linecap="round"
                    stroke-dasharray="{circumference}"
                    stroke-dashoffset="{offset}"
                    style="transition: stroke-dashoffset 0.8s ease;"/>
        </svg>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);
                    font-size:1.8rem; font-weight:800; color:{TEXT};">{prob*100:.0f}%</div>
        <div style="font-size:0.65rem; color:{MUTED}; text-align:center; margin-top:0.2rem;">DELAY PROBABILITY</div>
    </div>
    """, unsafe_allow_html=True)

def render_confidence_badge(confidence: str):
    color_map = {"high": GREEN, "medium": ORANGE, "low": RED}
    c = color_map.get(confidence, MUTED)
    st.markdown(f"""
    <span style="display:inline-flex; align-items:center; gap:5px; padding:3px 12px; border-radius:20px;
                 font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.3px;
                 background:rgba({','.join(str(int(c[i+1:i+3],16)) for i in (0,2,4))},0.15);
                 color:{c};">{confidence}</span>
    """, unsafe_allow_html=True)

def render_prediction_card(result: dict):
    has_rt = result.get("has_realtime_data", False)
    delayed = result.get("delayed")
    probability = result.get("probability", 0)
    confidence = result.get("confidence", "low")

    if delayed is None:
        return

    # Live banner
    if has_rt:
        arr = result.get("actual_arrival_delay_min")
        dep = result.get("actual_departure_delay_min")
        parts = []
        if arr is not None:
            parts.append(f"Arrived {arr:+.0f} min")
        if dep is not None:
            parts.append(f"Departing {dep:+.0f} min")
        live_text = " | ".join(parts) if parts else "On time"

        if arr is not None and arr > 5:
            banner_class, icon = "red", "🔴"
        elif arr is not None and arr > 0:
            banner_class, icon = "yellow", "🟡"
        else:
            banner_class, icon = "green", "🟢"
    else:
        banner_class, icon = "blue", "ℹ️"
        live_text = "No live delay data — prediction based on historical patterns"

    st.markdown(f'<div class="live-banner {banner_class}">{icon} LIVE · {live_text}</div>',
                unsafe_allow_html=True)

    # Main prediction area
    verdict = "LIKELY DELAYED" if delayed else "LIKELY ON TIME"
    verdict_color = RED if delayed else GREEN
    subtitle = "Delay probability exceeds threshold" if delayed else "Train is expected to run on schedule"

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown(f"""
        <div style="font-size:2rem; font-weight:900; color:{verdict_color}; letter-spacing:-0.5px;
                    margin-bottom:0.25rem;">{'⚠️' if delayed else '✅'} {verdict}</div>
        <div style="font-size:0.85rem; color:{MUTED}; margin-bottom:1rem;">{subtitle}</div>
        """, unsafe_allow_html=True)

        # Train info chips
        chips = []
        chips.append(("🚄", f"ICE {result.get('train_number', '')}"))
        chips.append(("📍", result.get("station_name", "").split(" (")[0]))
        origin = result.get("origin") or "?"
        dest = result.get("destination") or "?"
        chips.append(("🔄", f"{origin} → {dest}"))
        t = result.get("scheduled_time_display") or "?"
        chips.append(("⏰", t))

        chip_html = '<div style="display:flex; gap:8px; flex-wrap:wrap;">'
        for icon, text in chips:
            chip_html += f"""
            <div style="background:{CARD}; border:1px solid rgba(255,255,255,0.06); border-radius:10px;
                        padding:4px 12px; font-size:0.8rem; color:{TEXT}; display:flex; align-items:center; gap:5px;">
                {icon} {text}
            </div>"""
        chip_html += "</div>"
        st.markdown(chip_html, unsafe_allow_html=True)

    with col_right:
        render_probability_ring(probability)

    # Recommendation
    if delayed:
        if probability > 0.8:
            msg = "High delay risk. Consider alternative connections. Check DB Navigator for updates."
            emoji = "⚠️"
        else:
            msg = "Moderate delay risk. Monitor live departure boards for changes."
            emoji = "👀"
    else:
        msg = "Train expected on schedule. Enjoy your journey!"
        emoji = "✅"

    st.markdown(f"""
    <div class="rec-box">
        <div class="rec-box-title">{emoji} Recommendation</div>
        <div class="rec-box-text">{msg}</div>
    </div>
    """, unsafe_allow_html=True)

    # Route stops
    route_stops = result.get("route_stops", [])
    station_name = result.get("station_name", "")
    if route_stops:
        station_short = station_name.split(" (")[0]
        st.markdown(f'<div style="font-size:0.8rem; font-weight:600; color:{MUTED}; margin-top:0.75rem; margin-bottom:0.3rem;">🛤️ Route</div>', unsafe_allow_html=True)
        html = '<div class="route-bar">'
        for stop in route_stops:
            is_current = station_short.lower() in stop.lower() or station_name.lower() in stop.lower()
            cls = "route-stop current" if is_current else "route-stop"
            html += f'<span class="{cls}">{stop}</span>'
            if stop != route_stops[-1]:
                html += '<span class="route-arrow">›</span>'
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    # Time comparison mini row
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        arr = result.get("actual_arrival_delay_min")
        if arr is not None:
            st.metric("Arrival Delay", f"{arr:+.0f} min", delta=f"{arr:+.0f}")
        else:
            st.metric("Arrival Delay", "N/A")
    with mc2:
        dep = result.get("actual_departure_delay_min")
        if dep is not None:
            st.metric("Departure Delay", f"{dep:+.0f} min", delta=f"{dep:+.0f}")
        else:
            st.metric("Departure Delay", "N/A")
    with mc3:
        plat = result.get("arrival_platform") or result.get("departure_platform")
        st.metric("Platform", plat if plat else "—")
    with mc4:
        sch = result.get("scheduled_time_display")
        act = result.get("actual_arrival_time") or result.get("actual_departure_time")
        if sch and act:
            st.metric("Sched → Actual", f"{sch} → {act}")
        elif sch:
            st.metric("Scheduled", sch)


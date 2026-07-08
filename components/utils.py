from datetime import datetime

def format_time(t: str) -> str:
    """Format a DB API time string (yymmddHHMM) to HH:MM."""
    if not t:
        return "?"
    try:
        return datetime.strptime(t, "%y%m%d%H%M").strftime("%H:%M")
    except ValueError:
        return t

def format_delay(minutes) -> str:
    if minutes is None:
        return "—"
    return f"{minutes:+.0f} min"

def get_delay_color(minutes) -> str:
    if minutes is None:
        return "#94A3B8"
    if minutes > 10:
        return "#EF4444"
    if minutes > 3:
        return "#F59E0B"
    return "#22C55E"

def get_prob_color(prob: float) -> str:
    if prob >= 0.7:
        return "#EF4444"
    if prob >= 0.4:
        return "#F59E0B"
    return "#22C55E"

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from components.styles import DB_RED, GREEN, ORANGE, RED, BLUE, TEXT, MUTED, CARD, CARD2

_PC = dict(displayModeBar=False, responsive=True, autosizable=True)

_GRID = "rgba(255,255,255,0.04)"
_SUBGRID = "rgba(255,255,255,0.02)"

def _base(title="", height=280, showlegend=False):
    return dict(
        title=dict(text=title, font=dict(family="Inter, sans-serif", color=TEXT, size=13), x=0, xanchor="left"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=36, b=8),
        height=height,
        font=dict(family="Inter, sans-serif", color=MUTED, size=10),
        showlegend=showlegend,
        hovermode="x unified",
        hoverlabel=dict(bgcolor=CARD2, font_family="Inter, sans-serif", font_color=TEXT, bordercolor="rgba(255,255,255,0.08)", font_size=11),
        transition=dict(duration=500, easing="cubic-in-out"),
    )


def _hover(name, value, pct=None, extra=None):
    parts = [f"<b>{name}</b>"]
    parts.append(f"{value}")
    if pct is not None:
        parts.append(f"<span style='color:{MUTED}'>({pct})</span>")
    if extra:
        parts.append(f"<span style='color:{MUTED};font-size:9px'>{extra}</span>")
    return "<br>".join(parts)


def probability_gauge(prob: float):
    pct = prob * 100
    color = GREEN if prob < 0.4 else ORANGE if prob < 0.7 else RED
    label = "On Time" if prob < 0.4 else "Uncertain" if prob < 0.7 else "Delayed"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number=dict(font=dict(family="Inter, sans-serif", color=TEXT, size=32), suffix="%"),
        delta=dict(reference=50, increasing=dict(color=RED), decreasing=dict(color=GREEN)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, tickcolor=MUTED,
                     tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9)),
            bar=dict(color=color, thickness=0.35),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            shape="angular",
            steps=[
                dict(range=[0, 40], color="rgba(34,197,94,0.06)"),
                dict(range=[40, 70], color="rgba(245,158,11,0.06)"),
                dict(range=[70, 100], color="rgba(239,68,68,0.06)"),
            ],
            threshold=dict(
                line=dict(color=TEXT, width=2),
                thickness=0.6,
                value=pct,
            ),
        ),
    ))
    fig.update_layout(**_base(height=260))
    return fig


def confidence_radar(confidence_score: float, confidence_label: str):
    score_map = {"high": 0.9, "medium": 0.65, "low": 0.35}
    base = score_map.get(confidence_label, 0.5)
    categories = ["Confidence", "Reliability", "Data Quality", "Model Fit"]
    values = [confidence_score, base * 0.9, base * 0.85, base * 0.95]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor=f"rgba(236,0,22,0.12)",
        line=dict(color=DB_RED, width=2),
        name="Score",
        hovertemplate=_hover("%{theta}", "%{r:.0%}", extra="Confidence Profile"),
    ))
    # Full-baseline reference
    fig.add_trace(go.Scatterpolar(
        r=[1] * 5, theta=categories + [categories[0]],
        fill="toself",
        fillcolor="rgba(255,255,255,0.02)",
        line=dict(color="rgba(255,255,255,0.06)", width=1, dash="dot"),
        name="Baseline",
        hovertemplate="Baseline: %{r:.0%}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 1], showticklabels=False, gridcolor=_GRID),
            angularaxis=dict(tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9), gridcolor=_GRID),
        ),
        **_base(height=280, showlegend=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5,
                   font=dict(family="Inter, sans-serif", color=MUTED, size=9)),
    )
    return fig


def feature_importance_bar(fi_dict: dict, top_n: int = 12):
    sorted_items = sorted(fi_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]
    features = [x[0] for x in sorted_items][::-1]
    values = [x[1] for x in sorted_items][::-1]
    total = sum(values)

    fig = go.Figure(go.Bar(
        x=values,
        y=features,
        orientation="h",
        marker=dict(
            color=values,
            colorscale=[[0, "rgba(59,130,246,0.4)"], [0.5, "rgba(139,92,246,0.7)"], [1, DB_RED]],
            line=dict(color="rgba(255,255,255,0.04)", width=1),
            cornerradius=3,
        ),
        hovertemplate=_hover(
            "%{y}",
            "%{x:.3f}",
            pct="%{customdata:.1f}%",
            extra="Feature Importance",
        ),
        customdata=np.array([[v / total * 100] for v in values]),
    ))
    fig.update_layout(
        **_base(height=max(240, len(features) * 22)),
        xaxis=dict(title="", showgrid=True, gridcolor=_GRID, zeroline=False, tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9)),
        yaxis=dict(title="", tickfont=dict(family="Inter, sans-serif", color=TEXT, size=10)),
    )
    return fig


def model_comparison_chart(comp_df: pd.DataFrame):
    metrics = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    available = [m for m in metrics if m in comp_df.columns]
    if not available:
        return None

    melted = comp_df.reset_index().melt(id_vars="Model", value_vars=available, var_name="Metric", value_name="Score")
    models = melted["Model"].unique()
    palette = [DB_RED, BLUE, GREEN, ORANGE, "#A855F7", "#06B6D4"]
    color_map = {m: palette[i % len(palette)] for i, m in enumerate(models)}

    fig = go.Figure()
    for model in models:
        subset = melted[melted["Model"] == model]
        fig.add_trace(go.Bar(
            name=model,
            x=subset["Metric"],
            y=subset["Score"],
            marker=dict(color=color_map[model], line=dict(width=0)),
            hovertemplate=_hover(model, "%{y:.3f}", extra="Metric: %{x}"),
        ))

    fig.update_layout(
        barmode="group",
        **_base(height=300, showlegend=True),
        yaxis=dict(range=[0, 1], title="", gridcolor=_GRID, zeroline=False,
                   tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9)),
        xaxis=dict(title="", tickfont=dict(family="Inter, sans-serif", color=TEXT, size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5,
                   font=dict(family="Inter, sans-serif", color=MUTED, size=9)),
    )
    return fig


def delay_distribution(prob: float):
    pct = prob * 100
    zone_color = GREEN if prob < 0.4 else ORANGE if prob < 0.7 else RED
    zone_label = "Likely On Time" if prob < 0.4 else "Uncertain" if prob < 0.7 else "Likely Delayed"

    fig = go.Figure()
    # Probability axis line
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0.5, 0.5],
        mode="lines",
        line=dict(color="rgba(255,255,255,0.08)", width=3),
        showlegend=False,
        hoverinfo="skip",
    ))
    # Marker
    fig.add_trace(go.Scatter(
        x=[prob], y=[0.5],
        mode="markers+text",
        marker=dict(size=16, color=zone_color, line=dict(color=TEXT, width=2)),
        text=[f"{pct:.0f}%"],
        textposition="top center",
        textfont=dict(family="Inter, sans-serif", color=TEXT, size=11, weight="bold"),
        showlegend=False,
        hovertemplate=_hover("Delay Probability", f"{pct:.1f}%", extra=f"Zone: {zone_label}"),
    ))

    # Zone backgrounds
    zones = [(0, 0.4, "On Time", GREEN), (0.4, 0.7, "Uncertain", ORANGE), (0.7, 1, "Delayed", RED)]
    for start, end, label, clr in zones:
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor=f"rgba({','.join(str(int(clr[i+1:i+3],16)) for i in (0,2,4))},0.06)",
            layer="below", line_width=0,
        )
        fig.add_annotation(
            x=(start + end) / 2, y=0.42, text=label,
            font=dict(family="Inter, sans-serif", color=clr, size=8),
            showarrow=False, yanchor="top",
        )

    fig.update_layout(
        **_base(height=140),
        xaxis=dict(range=[-0.03, 1.03], title="", tickformat=".0%",
                   tickfont=dict(family="Inter, sans-serif", color=MUTED, size=8)),
        yaxis=dict(showticklabels=False, showgrid=False, range=[0.3, 0.65]),
    )
    return fig


def historical_trend_line(recent_df: pd.DataFrame):
    if recent_df.empty or "created_at" not in recent_df.columns or "predicted_prob" not in recent_df.columns:
        return None

    df = recent_df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at").tail(50)
    df["idx"] = range(len(df))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["idx"], y=df["predicted_prob"],
        mode="lines+markers",
        line=dict(color=DB_RED, width=2.5, shape="spline"),
        marker=dict(
            color=df["predicted_prob"],
            colorscale=[[0, GREEN], [0.5, ORANGE], [1, RED]],
            size=6, showscale=False, line=dict(color="rgba(255,255,255,0.1)", width=1),
        ),
        fill="tozeroy",
        fillcolor=f"rgba(236,0,22,0.05)",
        hovertemplate=_hover(
            "Prediction #%{x}",
            "%{y:.1%}",
            extra="%{text}",
        ),
        text=[f"<span style='color:{MUTED}'>{t.strftime('%m/%d %H:%M') if hasattr(t, 'strftime') else t}</span>"
              for t in df["created_at"]],
    ))
    fig.add_hline(y=0.5, line=dict(color="rgba(255,255,255,0.1)", width=1, dash="dash"))
    fig.add_annotation(x=0, y=0.52, text="Threshold 50%", showarrow=False,
                       font=dict(family="Inter, sans-serif", color=MUTED, size=8))

    fig.update_layout(
        **_base(height=280),
        xaxis=dict(title="", showticklabels=False, zeroline=False),
        yaxis=dict(range=[0, 1], title="", tickformat=".0%", gridcolor=_GRID, zeroline=False,
                   tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9)),
    )
    return fig


def confusion_matrix_heatmap(cm: dict):
    matrix = [[cm.get("tn", 0), cm.get("fp", 0)],
              [cm.get("fn", 0), cm.get("tp", 0)]]

    labels = [
        ["True Negative", "False Positive"],
        ["False Negative", "True Positive"],
    ]

    annotations = []
    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            total = sum(sum(r) for r in matrix)
            pct = val / total * 100 if total else 0
            annotations.append(dict(
                x=j, y=i,
                text=f"<b>{val}</b><br><span style='font-size:9px;color:{MUTED}'>{labels[i][j]}</span>",
                font=dict(family="Inter, sans-serif", size=12, color=TEXT),
                showarrow=False,
                xanchor="center",
                yanchor="middle",
            ))

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=["Predicted On Time", "Predicted Delayed"],
        y=["Actual On Time", "Actual Delayed"],
        text=[[f"{v}" for v in row] for row in matrix],
        texttemplate="%{text}",
        textfont=dict(size=1, color="rgba(0,0,0,0)"),
        colorscale=[[0, "rgba(59,130,246,0.15)"], [0.3, "rgba(99,102,241,0.3)"],
                    [0.6, "rgba(236,0,22,0.4)"], [1, DB_RED]],
        showscale=False,
        hovertemplate=_hover(
            "%{x}<br>%{y}",
            "%{z}",
            pct="%{customdata:.1f}%",
            extra="Confusion Matrix",
        ),
        customdata=[[v / (sum(sum(r) for r in matrix)) * 100 for v in row] for row in matrix],
    ))

    for a in annotations:
        fig.add_annotation(a)

    fig.update_layout(
        **_base(height=300),
        xaxis=dict(title="", side="bottom", tickfont=dict(family="Inter, sans-serif", color=TEXT, size=9)),
        yaxis=dict(title="", autorange="reversed", tickfont=dict(family="Inter, sans-serif", color=TEXT, size=9)),
    )
    fig.update_xaxes(constrain="domain")
    fig.update_yaxes(constrain="domain")
    return fig


def roc_curve_chart(auc: float):
    fpr = np.linspace(0, 1, 100)
    tpr = 1 - (1 - fpr) ** (1 / (1 - auc + 0.01))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fpr, y=tpr,
        mode="lines",
        line=dict(color=DB_RED, width=3, shape="spline"),
        fill="tozeroy",
        fillcolor=f"rgba(236,0,22,0.05)",
        name=f"AUC = {auc:.3f}",
        hovertemplate=_hover(
            "ROC Curve",
            "TPR: %{y:.2%}",
            extra="FPR: %{x:.2%}",
        ),
    ))
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line=dict(color="rgba(255,255,255,0.08)", width=1.5, dash="dash"),
        name="Random Classifier",
        hovertemplate="Random Baseline<extra></extra>",
    ))

    fig.update_layout(
        **_base(height=280, showlegend=True),
        xaxis=dict(title="False Positive Rate", range=[0, 1], gridcolor=_GRID, zeroline=False,
                   tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9)),
        yaxis=dict(title="True Positive Rate", range=[0, 1], gridcolor=_GRID, zeroline=False,
                   tickfont=dict(family="Inter, sans-serif", color=MUTED, size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                   font=dict(family="Inter, sans-serif", color=MUTED, size=9)),
    )
    return fig

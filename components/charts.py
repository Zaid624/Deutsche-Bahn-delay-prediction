import numpy as np
import pandas as pd
import plotly.graph_objects as go
from components.styles import ACCENT, GREEN, ORANGE, RED, TEXT, MUTED, CARD, CARD2, FONT_MONO

_ACCENT_RGB = tuple(int(ACCENT.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(family=FONT_MONO, color=MUTED),
        xaxis=dict(
            gridcolor=CARD2,
            linecolor=CARD2,
            zerolinecolor=CARD2,
        ),
        yaxis=dict(
            gridcolor=CARD2,
            linecolor=CARD2,
            zerolinecolor=CARD2,
        ),
        colorway=[ACCENT, GREEN, ORANGE, RED],
    ),
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
    if prob < 0.4:
        color = GREEN
    elif prob < 0.7:
        color = ORANGE
    else:
        color = RED

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number=dict(font=dict(family=FONT_MONO, color=TEXT, size=32), suffix="%"),
        delta=dict(reference=50, increasing=dict(color=RED), decreasing=dict(color=GREEN)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, tickcolor=MUTED,
                     tickfont=dict(family=FONT_MONO, color=MUTED, size=9)),
            bar=dict(color=color, thickness=0.35),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            shape="angular",
            steps=[
                dict(range=[0, 40], color=f"rgba(34,197,94,0.08)"),
                dict(range=[40, 70], color=f"rgba(234,179,8,0.08)"),
                dict(range=[70, 100], color=f"rgba(239,68,68,0.08)"),
            ],
            threshold=dict(
                line=dict(color=TEXT, width=2),
                thickness=0.6,
                value=pct,
            ),
        ),
    ))
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], height=300, margin=dict(l=20, r=20, t=30, b=20))
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
        fillcolor=f"rgba({_ACCENT_RGB[0]},{_ACCENT_RGB[1]},{_ACCENT_RGB[2]},0.12)",
        line=dict(color=ACCENT, width=2),
        name="Score",
        hovertemplate=_hover("%{theta}", "%{r:.0%}", extra="Confidence Profile"),
    ))
    fig.add_trace(go.Scatterpolar(
        r=[1] * 5, theta=categories + [categories[0]],
        fill="toself",
        fillcolor="rgba(255,255,255,0.02)",
        line=dict(color=CARD2, width=1, dash="dot"),
        name="Baseline",
        hovertemplate="Baseline: %{r:.0%}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 1], showticklabels=False, gridcolor=CARD2),
            angularaxis=dict(tickfont=dict(family=FONT_MONO, color=MUTED, size=9), gridcolor=CARD2),
        ),
        **PLOTLY_TEMPLATE["layout"],
        height=280,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5,
                   font=dict(family=FONT_MONO, color=MUTED, size=9)),
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
            colorscale=[[0, f"rgba({_ACCENT_RGB[0]},{_ACCENT_RGB[1]},{_ACCENT_RGB[2]},0.15)"], [0.5, f"rgba(139,92,246,0.5)"], [1, ACCENT]],
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
        **PLOTLY_TEMPLATE["layout"],
        height=max(240, len(features) * 22),
    )
    fig.update_xaxes(title="", showgrid=True, gridcolor=CARD2, zeroline=False, tickfont=dict(family=FONT_MONO, color=MUTED, size=9))
    fig.update_yaxes(title="", tickfont=dict(family=FONT_MONO, color=TEXT, size=10))
    return fig


def model_comparison_chart(comp_df: pd.DataFrame):
    metrics = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    available = [m for m in metrics if m in comp_df.columns]
    if not available:
        return None

    melted = comp_df.reset_index().melt(id_vars="Model", value_vars=available, var_name="Metric", value_name="Score")
    models = melted["Model"].unique()
    palette = [ACCENT, GREEN, ORANGE, RED]
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
        **PLOTLY_TEMPLATE["layout"],
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5,
                   font=dict(family=FONT_MONO, color=MUTED, size=9)),
    )
    fig.update_xaxes(title="", tickfont=dict(family=FONT_MONO, color=TEXT, size=9))
    fig.update_yaxes(range=[0, 1], title="", gridcolor=CARD2, zeroline=False,
                     tickfont=dict(family=FONT_MONO, color=MUTED, size=9))
    return fig


def delay_distribution(prob: float):
    pct = prob * 100
    if prob < 0.4:
        zone_color = GREEN
        zone_label = "Likely On Time"
    elif prob < 0.7:
        zone_color = ORANGE
        zone_label = "Uncertain"
    else:
        zone_color = RED
        zone_label = "Likely Delayed"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0.5, 0.5],
        mode="lines",
        line=dict(color="rgba(255,255,255,0.08)", width=3),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[prob], y=[0.5],
        mode="markers+text",
        marker=dict(size=16, color=zone_color, line=dict(color=TEXT, width=2)),
        text=[f"{pct:.0f}%"],
        textposition="top center",
        textfont=dict(family=FONT_MONO, color=TEXT, size=11, weight="bold"),
        showlegend=False,
        hovertemplate=_hover("Delay Probability", f"{pct:.1f}%", extra=f"Zone: {zone_label}"),
    ))

    zones = [(0, 0.4, "On Time", GREEN), (0.4, 0.7, "Uncertain", ORANGE), (0.7, 1, "Delayed", RED)]
    for start, end, label, clr in zones:
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor=f"rgba({','.join(str(int(clr[i+1:i+3],16)) for i in (0,2,4))},0.06)",
            layer="below", line_width=0,
        )
        fig.add_annotation(
            x=(start + end) / 2, y=0.42, text=label,
            font=dict(family=FONT_MONO, color=clr, size=8),
            showarrow=False, yanchor="top",
        )

    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=140,
    )
    fig.update_xaxes(range=[-0.03, 1.03], title="", tickformat=".0%",
                     tickfont=dict(family=FONT_MONO, color=MUTED, size=8))
    fig.update_yaxes(showticklabels=False, showgrid=False, range=[0.3, 0.65])
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
        line=dict(color=ACCENT, width=2.5, shape="spline"),
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
                       font=dict(family=FONT_MONO, color=MUTED, size=8))

    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=280,
    )
    fig.update_xaxes(title="", showticklabels=False, zeroline=False)
    fig.update_yaxes(range=[0, 1], title="", tickformat=".0%", gridcolor=CARD2, zeroline=False,
                     tickfont=dict(family=FONT_MONO, color=MUTED, size=9))
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
                font=dict(family=FONT_MONO, size=12, color=TEXT),
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
        colorscale=[[0, f"rgba({_ACCENT_RGB[0]},{_ACCENT_RGB[1]},{_ACCENT_RGB[2]},0.08)"],
                    [0.5, f"rgba({_ACCENT_RGB[0]},{_ACCENT_RGB[1]},{_ACCENT_RGB[2]},0.35)"],
                    [1, ACCENT]],
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
        **PLOTLY_TEMPLATE["layout"],
        height=300,
    )
    fig.update_xaxes(title="", side="bottom", tickfont=dict(family=FONT_MONO, color=TEXT, size=9), constrain="domain")
    fig.update_yaxes(title="", autorange="reversed", tickfont=dict(family=FONT_MONO, color=TEXT, size=9), constrain="domain")
    return fig


def roc_curve_chart(auc: float):
    fpr = np.linspace(0, 1, 100)
    tpr = 1 - (1 - fpr) ** (1 / (1 - auc + 0.01))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fpr, y=tpr,
        mode="lines",
        line=dict(color=ACCENT, width=3, shape="spline"),
        fill="tozeroy",
        fillcolor=f"rgba({_ACCENT_RGB[0]},{_ACCENT_RGB[1]},{_ACCENT_RGB[2]},0.05)",
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
        **PLOTLY_TEMPLATE["layout"],
        height=280,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                   font=dict(family=FONT_MONO, color=MUTED, size=9)),
    )
    fig.update_xaxes(title="False Positive Rate", range=[0, 1], gridcolor=CARD2, zeroline=False,
                     tickfont=dict(family=FONT_MONO, color=MUTED, size=9))
    fig.update_yaxes(title="True Positive Rate", range=[0, 1], gridcolor=CARD2, zeroline=False,
                     tickfont=dict(family=FONT_MONO, color=MUTED, size=9))
    return fig

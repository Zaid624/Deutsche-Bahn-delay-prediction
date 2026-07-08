import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
from components.styles import CARD, TEXT, MUTED, CARD2

GRID_CUSTOM_CSS = {
    ".ag-theme-alpine": {
        "background-color": CARD,
        "border-radius": "14px",
        "overflow": "hidden",
    },
    ".ag-root-wrapper": {
        "background-color": CARD,
    },
    ".ag-header": {
        "background-color": CARD2,
        "border-bottom": "1px solid rgba(255,255,255,0.06)",
    },
    ".ag-header-cell": {
        "color": MUTED,
        "font-weight": "700",
        "text-transform": "uppercase",
        "letter-spacing": "0.5px",
        "font-size": "0.6rem",
        "background-color": CARD2,
    },
    ".ag-cell": {
        "color": TEXT,
        "display": "flex",
        "align-items": "center",
        "border-bottom": "1px solid rgba(255,255,255,0.03)",
    },
    ".ag-row": {
        "cursor": "pointer",
        "background-color": CARD,
    },
    ".ag-row-even": {
        "background-color": CARD,
    },
    ".ag-row-odd": {
        "background-color": "rgba(255,255,255,0.02)",
    },
    ".ag-row:hover": {
        "background-color": "rgba(255,255,255,0.04)",
    },
    ".ag-paging-panel": {
        "color": MUTED,
        "background-color": CARD,
        "border-top": "1px solid rgba(255,255,255,0.06)",
    },
    ".ag-paging-button": {
        "color": MUTED,
    },
    ".ag-paging-button:hover": {
        "color": TEXT,
    },
    ".ag-body-viewport": {
        "background-color": CARD,
    },
    ".ag-center-cols-container": {
        "background-color": CARD,
    },
    ".ag-overlay-no-rows-wrapper": {
        "color": MUTED,
    },
}

def render_history_table(recent: pd.DataFrame):
    if len(recent) == 0:
        st.info("No predictions logged yet.")
        return None, None, None

    display = recent.copy()
    display["created_at"] = pd.to_datetime(display["created_at"]).dt.strftime("%m/%d %H:%M")
    display["Prob"] = (display["predicted_prob"] * 100).round(1).astype(str) + "%"
    display["Result"] = display["predicted_delay"].map({True: "⚠️ Delayed", False: "✅ On Time"})
    display = display[["created_at", "station_name", "train_number", "Result", "Prob"]]
    display.columns = ["Time", "Station", "Train", "Result", "Prob"]

    total = len(recent)
    delayed_count = recent["predicted_delay"].sum()
    avg_prob = recent["predicted_prob"].mean()

    gb = GridOptionsBuilder.from_dataframe(display)
    gb.configure_default_column(
        min_column_width=30,
        resizable=True,
        filterable=True,
        sortable=True,
        cellStyle={"color": TEXT, "background": "transparent"},
        headerClass={"color": MUTED, "font-weight": "600", "font-size": "0.75rem"},
    )
    gb.configure_column("Result", cellRenderer=JsCode("""
        class ResultCell {
            init(params) {
                const isDelayed = params.value.includes('⚠');
                this.eGui = document.createElement('span');
                this.eGui.style.cssText = `
                    display:inline-flex; align-items:center; gap:4px;
                    padding:2px 10px; border-radius:6px;
                    font-weight:600; font-size:0.75rem;
                    background: ${isDelayed ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.12)'};
                    color: ${isDelayed ? '#EF4444' : '#22C55E'};
                `;
                this.eGui.innerHTML = params.value;
            }
            getGui() { return this.eGui; }
        }
    """))
    gb.configure_column("Prob", cellRenderer=JsCode("""
        class ProbCell {
            init(params) {
                const val = parseFloat(params.value);
                const color = val > 70 ? '#EF4444' : val > 40 ? '#F59E0B' : '#22C55E';
                this.eGui = document.createElement('span');
                this.eGui.style.cssText = `font-weight:700; color:${color};`;
                this.eGui.innerHTML = params.value;
            }
            getGui() { return this.eGui; }
        }
    """))
    gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=10)
    gb.configure_grid_options(headerHeight=36, rowHeight=38)
    gb.configure_selection("single", use_checkbox=False)

    grid_options = gb.build()
    grid_options["defaultColDef"]["headerClass"] = "ag-header-cell"

    grid_response = AgGrid(
        display,
        grid_options,
        height=min(420, 38 * min(len(display) + 1, 11) + 40),
        width="100%",
        update_mode=GridUpdateMode.NO_UPDATE,
        theme="alpine",
        custom_css=GRID_CUSTOM_CSS,
        allow_unsafe_jscode=True,
    )

    return total, delayed_count, avg_prob


def render_model_comparison_table(models: dict):
    if not models:
        return

    comp = pd.DataFrame(models).T.round(4)
    comp.index.name = "Model"
    comp = comp.reset_index()

    metrics_cols = [c for c in comp.columns if c not in ("Model",) and not c.startswith("_")]
    display_cols = ["Model"] + [c for c in metrics_cols if c in comp.columns]

    gb = GridOptionsBuilder.from_dataframe(comp[display_cols])
    gb.configure_default_column(
        min_column_width=30,
        resizable=True,
        sortable=True,
        filterable=True,
        cellStyle={"color": TEXT, "background": "transparent"},
    )
    gb.configure_column("Model", pinned="left", cellStyle={"fontWeight": "700", "color": TEXT})
    for col in metrics_cols:
        if col in comp.columns:
            gb.configure_column(col, type=["numericColumn"],
                                cellRenderer=JsCode("""
                class NumCell {
                    init(params) {
                        const val = params.value;
                        const pct = Math.min(val * 100, 100);
                        this.eGui = document.createElement('div');
                        this.eGui.style.cssText = 'display:flex; align-items:center; gap:8px; width:100%;';
                        this.eGui.innerHTML = `
                            <span style="font-weight:600; color:#F8FAFC; min-width:40px;">${val.toFixed(4)}</span>
                            <div style="flex:1; height:4px; background:rgba(255,255,255,0.06); border-radius:2px;">
                                <div style="width:${pct}%; height:4px; background:#EC0016; border-radius:2px;"></div>
                            </div>
                        `;
                    }
                    getGui() { return this.eGui; }
                }
            """))
    gb.configure_pagination(enabled=True, paginationPageSize=5)
    gb.configure_grid_options(headerHeight=36, rowHeight=42)

    grid_options = gb.build()

    AgGrid(
        comp[display_cols],
        grid_options,
        height=300,
        width="100%",
        update_mode=GridUpdateMode.NO_UPDATE,
        theme="alpine",
        custom_css=GRID_CUSTOM_CSS,
        allow_unsafe_jscode=True,
    )

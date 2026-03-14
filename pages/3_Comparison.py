"""Page 3: Comparison — variance analysis across different dimensions."""
import streamlit as st
import pandas as pd
from src.db import FeeIncomeDB
from src.queries import (
    get_ytd_comparison, get_fy_comparison,
    get_prior_snapshot_comparison, get_yoy_comparison, get_snapshot_n_value,
)

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

@st.cache_resource
def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def show_comparison_table(data, col_a, col_b, label_a, label_b):
    if not data:
        st.info("No data available for this comparison.")
        return
    df = pd.DataFrame(data)
    df["variance"] = df[col_a] - df[col_b]
    df["var_abs"] = df["variance"].abs()
    df = df.sort_values("var_abs", ascending=False)

    df_display = pd.DataFrame({
        "Project": df["project_name"], "Platform": df["platform"],
        label_a: (df[col_a] / 1e6).round(1), label_b: (df[col_b] / 1e6).round(1),
        "Variance": (df["variance"] / 1e6).round(1),
    })

    totals = pd.DataFrame([{
        "Project": "Grand Total", "Platform": "",
        label_a: df_display[label_a].sum().round(1),
        label_b: df_display[label_b].sum().round(1),
        "Variance": df_display["Variance"].sum().round(1),
    }])
    df_display = pd.concat([df_display, totals], ignore_index=True)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

def main():
    st.title("Comparison")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded.")
        return

    latest = db.get_latest_snapshot()
    selected = st.selectbox("Snapshot", snapshots,
        index=snapshots.index(latest) if latest in snapshots else 0)

    n = get_snapshot_n_value(selected)
    month_name = MONTH_NAMES.get(n, str(n))

    mode = st.radio("Comparison Mode", [
        f"YTD {month_name} Act vs YTD {month_name} Bud",
        "FY26 Fcst vs FY26 Bud",
        "FY26 Fcst vs Prior Month Fcst",
        "YoY (FY26 vs FY25)",
    ], horizontal=True)

    if "YTD" in mode:
        data = get_ytd_comparison(db, selected)
        show_comparison_table(data, "ytd_act", "ytd_bud", f"YTD {month_name} Act", f"YTD {month_name} Bud")
    elif "Fcst vs FY26 Bud" in mode:
        data = get_fy_comparison(db, selected)
        show_comparison_table(data, "fy_fcst", "fy_bud", "FY26 Fcst", "FY26 Bud")
    elif "Prior Month" in mode:
        data = get_prior_snapshot_comparison(db, selected)
        if data is None:
            st.warning(f"Prior snapshot not found in database. Need snapshot with N={n-1}.")
        else:
            show_comparison_table(data, "current_fcst", "prior_fcst",
                                  f"Current ({selected})", f"Prior ({n-1}+{13-n})")
    elif "YoY" in mode:
        data = get_yoy_comparison(db, selected)
        show_comparison_table(data, "fy26", "fy25", "FY26 Fcst", "FY25 Act")

main()

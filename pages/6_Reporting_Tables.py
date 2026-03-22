"""Page 4b: Reporting Tables — variance tables with copy & paste for monthly reporting."""
import streamlit as st
import pandas as pd
import io
from src.db import FeeIncomeDB
from src.queries import (
    get_mtd_comparison, get_ytd_comparison, get_fy_comparison, get_yoy_comparison,
    get_snapshot_n_value,
)

MONTH_NAMES = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
               7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
HEADER_COLOR = "#4a5568"


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def format_millions(value: float) -> str:
    return f"{value / 1_000_000:.1f}"

def export_button(df, filename="export.xlsx", key=None):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(label="Export to Excel", data=buf.getvalue(),
                        file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=key)

def copy_html_button(html_content, key="copy", title=""):
    import streamlit.components.v1 as components
    import base64
    title_html = f'<h3 style="font-family:Calibri,sans-serif; color:#2d3748;">{title}</h3>' if title else ""
    full_content = title_html + html_content
    b64 = base64.b64encode(full_content.encode("utf-8")).decode("ascii")
    components.html(f"""
    <button onclick="copyTable()" style="background:#4a5568; color:white; border:none; padding:6px 16px;
        border-radius:4px; cursor:pointer; font-size:13px; font-family:Calibri,sans-serif;">Copy Table</button>
    <span id="msg_{key}" style="margin-left:8px; font-size:12px; color:#38a169;"></span>
    <script>
    function copyTable() {{
        const b64 = "{b64}";
        const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
        const html = new TextDecoder('utf-8').decode(bytes);
        const blob = new Blob([html], {{type: 'text/html'}});
        const item = new ClipboardItem({{'text/html': blob}});
        navigator.clipboard.write([item]).then(() => {{
            document.getElementById('msg_{key}').innerText = 'Copied!';
            setTimeout(() => document.getElementById('msg_{key}').innerText = '', 2000);
        }});
    }}
    </script>
    """, height=40)


def main():
    st.title("Reporting Tables for Copy & Paste")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded. Go to Data Management to upload.")
        return

    latest = db.get_latest_snapshot()
    selected = st.selectbox("Snapshot", snapshots,
        index=snapshots.index(latest) if latest in snapshots else 0)

    n = get_snapshot_n_value(selected)
    month_name = MONTH_NAMES.get(n, str(n))
    snapshot_short = selected.replace("FY26 ", "") if selected.startswith("FY26 ") else selected
    fcst_label = f"FY26 Fcst ({snapshot_short})"

    mtd_data = get_mtd_comparison(db, selected)
    ytd_data = get_ytd_comparison(db, selected)
    fy_data = get_fy_comparison(db, selected)
    yoy_data = get_yoy_comparison(db, selected)

    def fmt_var(v):
        if v < -0.05:
            return f'<span style="color:#c53030;">({abs(v):.1f})</span>'
        elif v > 0.05:
            return f'<span style="color:#38a169;">+{v:.1f}</span>'
        return "-"

    def render_variance_table(title, table_key, data, col_a, col_b, label_a, label_b):
        st.subheader(title)
        if not data:
            st.info("No data.")
            return
        saved_drivers = db.get_drivers(selected, table_key)
        for r in data:
            r["_var"] = r[col_a] - r[col_b]
        sorted_data = sorted(data, key=lambda x: abs(x["_var"]), reverse=True)
        key_items = [r for r in sorted_data if round(abs(r["_var"]) / 1e6, 1) >= 0.2]
        other_items = [r for r in sorted_data if round(abs(r["_var"]) / 1e6, 1) < 0.2]
        sub_a = sum(r[col_a] for r in key_items)
        sub_b = sum(r[col_b] for r in key_items)
        other_a = sum(r[col_a] for r in other_items)
        other_b = sum(r[col_b] for r in other_items)
        total_a = sum(r[col_a] for r in data)
        total_b = sum(r[col_b] for r in data)

        html = f"""<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Calibri,sans-serif;">
        <thead><tr style="background-color:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Project</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">{label_a}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">{label_b}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">Variance</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Variance Driver</th>
        </tr></thead><tbody>"""
        for i, item in enumerate(key_items):
            bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
            name = item["project_name"]
            v = item["_var"] / 1e6
            html += f"""<tr style="background-color:{bg};">
                <td style="padding:6px 12px; border:1px solid #cbd5e0; font-weight:bold;">{name}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{item[col_a]/1e6:.1f}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{item[col_b]/1e6:.1f}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(v)}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; font-size:12px;">{saved_drivers.get(name, "")}</td>
            </tr>"""
        sv = (sub_a - sub_b) / 1e6
        html += f"""<tr style="background-color:#edf2f7; font-weight:bold;">
            <td style="padding:6px 12px; border:1px solid #cbd5e0;">Subtotal (Key Items)</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{sub_a/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{sub_b/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(sv)}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td></tr>"""
        ov = (other_a - other_b) / 1e6
        html += f"""<tr><td style="padding:6px 12px; border:1px solid #cbd5e0;">Other (net)</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{other_a/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{other_b/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(ov)}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; font-size:12px;">기타 프로젝트 순합</td></tr>"""
        tv = (total_a - total_b) / 1e6
        html += f"""<tr style="background-color:{HEADER_COLOR}; color:white; font-weight:bold;">
            <td style="padding:6px 12px; border:1px solid #cbd5e0;">Grand Total</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{total_a/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{total_b/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(tv)}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td></tr>"""
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")

        # Export + Copy buttons
        exp_rows = []
        for item in key_items:
            name = item["project_name"]
            exp_rows.append({"Project": name, f"{label_a} (USD)": round(item[col_a],2),
                f"{label_b} (USD)": round(item[col_b],2), "Variance (USD)": round(item["_var"],2),
                "Variance Driver": saved_drivers.get(name,"")})
        exp_rows.append({"Project":"Subtotal",f"{label_a} (USD)":round(sub_a,2),f"{label_b} (USD)":round(sub_b,2),"Variance (USD)":round(sub_a-sub_b,2)})
        exp_rows.append({"Project":"Other",f"{label_a} (USD)":round(other_a,2),f"{label_b} (USD)":round(other_b,2),"Variance (USD)":round(other_a-other_b,2)})
        exp_rows.append({"Project":"Grand Total",f"{label_a} (USD)":round(total_a,2),f"{label_b} (USD)":round(total_b,2),"Variance (USD)":round(total_a-total_b,2)})
        export_button(pd.DataFrame(exp_rows), f"variance_{table_key}.xlsx", key=f"export_{table_key}")
        copy_html_button(html, key=f"copy_{table_key}", title=title)

        # Editable drivers
        with st.expander(f"Edit Variance Drivers — {title}"):
            updated = {}
            for item in key_items:
                name = item["project_name"]
                v = item["_var"] / 1e6
                updated[name] = st.text_area(
                    f"{name} (var {fmt_var(v)}M)", value=saved_drivers.get(name,""),
                    height=68, key=f"driver_{table_key}_{name}")
            if st.button("Save Drivers", key=f"save_{table_key}"):
                db.save_drivers(selected, table_key, updated)
                st.success("Saved!")
                st.rerun()

    # 2+10 Credit Fund merge
    fy_data_display = fy_data
    if selected == "FY26 2+10":
        CREDIT_EXCLUDE = {"West Icheon", "Icheon Lasalle"}
        credit_merge = [r for r in fy_data if r.get("platform") == "Credit Fund"
                        and r["project_name"] not in CREDIT_EXCLUDE]
        if credit_merge:
            merged = {"project_name": "Credit Fund pipelines", "platform": "Credit Fund",
                      "fy_fcst": sum(r["fy_fcst"] for r in credit_merge),
                      "fy_bud": sum(r["fy_bud"] for r in credit_merge)}
            merge_names = {r["project_name"] for r in credit_merge}
            fy_data_display = [r for r in fy_data if r["project_name"] not in merge_names]
            insert_idx = next((i for i, r in enumerate(fy_data_display)
                if r.get("platform") == "Credit Fund" and r["project_name"] not in CREDIT_EXCLUDE),
                len(fy_data_display))
            fy_data_display.insert(insert_idx, merged)

    # Tabs
    tab_fy, tab_mtd, tab_ytd, tab_yoy = st.tabs([
        "FY26 vs Bud", f"MTD {month_name}", f"YTD {month_name}", "FY26 vs FY25"])

    with tab_fy:
        render_variance_table(f"{fcst_label} vs FY26 Bud", "fy_bud",
            fy_data_display, "fy_fcst", "fy_bud", fcst_label, "FY26 Bud")
    with tab_mtd:
        render_variance_table(f"MTD {month_name} Act vs Bud", "mtd",
            mtd_data, "mtd_act", "mtd_bud", "MTD Act", "MTD Bud")
    with tab_ytd:
        render_variance_table(f"YTD {month_name} Act vs Bud", "ytd",
            ytd_data, "ytd_act", "ytd_bud", "YTD Act", "YTD Bud")
    with tab_yoy:
        render_variance_table(f"{fcst_label} vs FY25 Act", "fy_yoy",
            yoy_data, "fy26", "fy25", fcst_label, "FY25 Act")


main()

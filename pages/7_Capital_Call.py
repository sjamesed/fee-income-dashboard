"""Page 7: Capital Call — fund/project-level capital call history (line by line)."""
import streamlit as st
import json
import pandas as pd
import io
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
HEADER_COLOR = "#4a5568"
FUND_FILTER = ["Dev JV1 (Star)", "Dev JV2 (Nova)", "Sunwood Byul", "Dangmok"]


def export_button(df, filename="export.xlsx", key=None):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(label="Export to Excel", data=buf.getvalue(),
                        file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=key)


def fmt_krw(v):
    if v is None or v == 0:
        return "-"
    val = v / 1e9
    if abs(val) < 0.05:
        return "-"
    if val < 0:
        return f'<span style="color:#c53030;">({abs(val):.1f})</span>'
    return f"{val:.1f}"


def fmt_usd(v):
    if v is None or v == 0:
        return "-"
    val = v / 1e6
    if abs(val) < 0.05:
        return "-"
    if val < 0:
        return f'<span style="color:#c53030;">({abs(val):.1f})</span>'
    return f"{val:.1f}"


def fmt_krw_line(v):
    if v is None or v == 0:
        return "-"
    return f"{v:,.0f}"


def fmt_usd_line(v):
    if v is None or v == 0:
        return "-"
    return f"{v:,.0f}"


def main():
    st.title("Capital Call")

    json_path = DATA_DIR / "capital_call.json"
    if not json_path.exists():
        st.warning("No capital call data found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    funds = [f for f in data.get("funds", []) if f["fund"] in FUND_FILTER]
    if not funds:
        st.info("No capital call data available.")
        return

    fund_order = {name: i for i, name in enumerate(FUND_FILTER)}
    funds.sort(key=lambda f: fund_order.get(f["fund"], 99))

    TH = "padding:5px 6px; border:1px solid #cbd5e0;"
    TD = "padding:4px 6px; border:1px solid #cbd5e0;"

    # ===== FUND SUMMARY =====
    st.header("Fund Summary")
    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left;">Fund</th>
        <th style="{TH}">Projects</th>
        <th style="{TH}">Total Calls</th>
        <th style="{TH}">Total KRW (B)</th>
        <th style="{TH}">Total USD (M)</th>
        <th style="{TH}">Latest Call</th>
    </tr>
    </thead><tbody>"""

    grand_krw = 0
    grand_usd = 0
    for i, fund in enumerate(funds):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        t_krw = sum(p["total_krw"] or 0 for p in fund["projects"])
        t_usd = sum(p["total_usd"] or 0 for p in fund["projects"])
        n_calls = sum(len(p["calls"]) for p in fund["projects"])
        grand_krw += t_krw
        grand_usd += t_usd
        latest = max((c["date"] for p in fund["projects"] for c in p["calls"] if c.get("date")), default="")
        html += f'<tr style="background:{bg};">'
        html += f'<td style="{TD} font-weight:bold;">{fund["fund"]}</td>'
        html += f'<td style="{TD} text-align:center;">{len(fund["projects"])}</td>'
        html += f'<td style="{TD} text-align:center;">{n_calls}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_krw(t_krw)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_usd(t_usd)}</td>'
        html += f'<td style="{TD} text-align:center;">{latest}</td>'
        html += "</tr>"

    html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
    html += f'<td style="{TD}">Grand Total</td>'
    html += f'<td style="{TD} text-align:center;">{sum(len(f["projects"]) for f in funds)}</td>'
    html += f'<td style="{TD} text-align:center;">{sum(sum(len(p["calls"]) for p in f["projects"]) for f in funds)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_krw(grand_krw)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_usd(grand_usd)}</td>'
    html += f'<td style="{TD}"></td>'
    html += "</tr></tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("KRW in billions, USD in millions")

    # ===== VIEW MODE =====
    st.markdown("---")
    view_mode = st.radio("View", ["By Fund", "By Project"], horizontal=True, key="cc_view_mode")

    if view_mode == "By Project":
        # Flatten all calls with fund+project info
        all_entries = []
        all_project_names = set()
        for fund in funds:
            for p in fund["projects"]:
                all_project_names.add(p["project"])
                for c in p["calls"]:
                    all_entries.append({
                        "fund": fund["fund"],
                        "project": p["project"],
                        "call_label": c.get("call_label", ""),
                        "date": c.get("date", ""),
                        "fx_rate": c.get("fx_rate"),
                        "details": c.get("details", ""),
                        "krw": c.get("krw"),
                        "usd": c.get("usd"),
                    })

        sorted_projects = sorted(all_project_names)
        selected_projects = st.multiselect(
            "Search Project",
            sorted_projects,
            placeholder="Type to search (e.g. Sanha, Gimhae, Opo...)",
            key="cc_proj_select")

        matched_projects = selected_projects

        if not matched_projects:
            st.info("Select a project to see all capital calls across funds.")

        if matched_projects:
            for proj_name in matched_projects:
                proj_calls = [e for e in all_entries if e["project"] == proj_name]
                proj_calls.sort(key=lambda c: (c.get("date", ""), c.get("fund", "")))

                # Group by fund for display
                fund_set = sorted(set(c["fund"] for c in proj_calls))
                fund_label = " / ".join(fund_set)
                total_krw = sum(c["krw"] or 0 for c in proj_calls)
                total_usd = sum(c["usd"] or 0 for c in proj_calls)

                st.subheader(f"{proj_name}")
                st.caption(f"Funds: {fund_label} | {len(proj_calls)} calls | KRW {fmt_krw(total_krw)}B | USD {fmt_usd(total_usd)}M")

                html = f"""<table style="border-collapse:collapse; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
                <thead>
                <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
                    <th style="{TH} text-align:left; min-width:100px;">Fund</th>
                    <th style="{TH} text-align:left; min-width:100px;">Capital Call #</th>
                    <th style="{TH} min-width:90px;">Value Date</th>
                    <th style="{TH} min-width:60px;">FX Rate</th>
                    <th style="{TH} text-align:left; min-width:180px;">Details</th>
                    <th style="{TH} text-align:right; min-width:110px;">KRW</th>
                    <th style="{TH} text-align:right; min-width:90px;">USD</th>
                </tr>
                </thead><tbody>"""

                for idx, c in enumerate(proj_calls):
                    bg = "#f7fafc" if idx % 2 == 0 else "#ffffff"
                    fx = c.get("fx_rate")
                    fx_str = f"{fx:,.1f}" if fx else "-"
                    html += f'<tr style="background:{bg};">'
                    html += f'<td style="{TD}">{c["fund"]}</td>'
                    html += f'<td style="{TD}">{c["call_label"]}</td>'
                    html += f'<td style="{TD} text-align:center;">{c["date"]}</td>'
                    html += f'<td style="{TD} text-align:right;">{fx_str}</td>'
                    html += f'<td style="{TD}">{c["details"]}</td>'
                    html += f'<td style="{TD} text-align:right;">{fmt_krw_line(c.get("krw"))}</td>'
                    html += f'<td style="{TD} text-align:right;">{fmt_usd_line(c.get("usd"))}</td>'
                    html += "</tr>"

                html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
                html += f'<td style="{TD}" colspan="5">Total ({len(proj_calls)} calls)</td>'
                html += f'<td style="{TD} text-align:right;">{fmt_krw_line(total_krw)}</td>'
                html += f'<td style="{TD} text-align:right;">{fmt_usd_line(total_usd)}</td>'
                html += "</tr></tbody></table>"
                st.markdown(html, unsafe_allow_html=True)

        return  # Skip fund tabs view

    # ===== FUND TABS (By Fund view) =====
    fund_names = [f["fund"] for f in funds]
    tabs = st.tabs(fund_names)

    for tab, fund in zip(tabs, funds):
        with tab:
            # Flatten all calls across projects, attach project name
            all_calls = []
            for p in fund["projects"]:
                for c in p["calls"]:
                    all_calls.append({
                        "project": p["project"],
                        "call_label": c.get("call_label", ""),
                        "date": c.get("date", ""),
                        "fx_rate": c.get("fx_rate"),
                        "details": c.get("details", ""),
                        "krw": c.get("krw"),
                        "usd": c.get("usd"),
                    })

            if not all_calls:
                st.info("No capital call data.")
                continue

            # Project filter
            all_projects = sorted(set(c["project"] for c in all_calls))
            filter_col1, filter_col2 = st.columns([3, 3])
            with filter_col1:
                use_all = st.checkbox("All Projects", value=True, key=f"all_proj_{fund['fund']}")
            with filter_col2:
                if not use_all:
                    selected_projects = st.multiselect(
                        "Search / Select Projects", all_projects,
                        key=f"proj_filter_{fund['fund']}",
                        placeholder="Type to search...")
                else:
                    selected_projects = all_projects

            filtered = [c for c in all_calls if c["project"] in selected_projects]

            # Sort by value date, then project
            filtered.sort(key=lambda c: (c.get("date", ""), c.get("project", "")))

            # Render table
            html = f"""<table style="border-collapse:collapse; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
            <thead>
            <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
                <th style="{TH} text-align:left; min-width:100px;">Capital Call #</th>
                <th style="{TH} min-width:90px;">Value Date</th>
                <th style="{TH} text-align:left; min-width:100px;">Project</th>
                <th style="{TH} min-width:60px;">FX Rate</th>
                <th style="{TH} text-align:left; min-width:180px;">Details</th>
                <th style="{TH} text-align:right; min-width:110px;">KRW</th>
                <th style="{TH} text-align:right; min-width:90px;">USD</th>
            </tr>
            </thead><tbody>"""

            total_krw = 0
            total_usd = 0
            for idx, c in enumerate(filtered):
                bg = "#f7fafc" if idx % 2 == 0 else "#ffffff"
                fx = c.get("fx_rate")
                fx_str = f"{fx:,.1f}" if fx else "-"
                krw = c.get("krw")
                usd = c.get("usd")
                if krw:
                    total_krw += krw
                if usd:
                    total_usd += usd
                html += f'<tr style="background:{bg};">'
                html += f'<td style="{TD}">{c["call_label"]}</td>'
                html += f'<td style="{TD} text-align:center;">{c["date"]}</td>'
                html += f'<td style="{TD} font-weight:bold;">{c["project"]}</td>'
                html += f'<td style="{TD} text-align:right;">{fx_str}</td>'
                html += f'<td style="{TD}">{c["details"]}</td>'
                html += f'<td style="{TD} text-align:right;">{fmt_krw_line(krw)}</td>'
                html += f'<td style="{TD} text-align:right;">{fmt_usd_line(usd)}</td>'
                html += "</tr>"

            # Total row
            html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
            html += f'<td style="{TD}" colspan="5">Total ({len(filtered)} calls)</td>'
            html += f'<td style="{TD} text-align:right;">{fmt_krw_line(total_krw)}</td>'
            html += f'<td style="{TD} text-align:right;">{fmt_usd_line(total_usd)}</td>'
            html += "</tr></tbody></table>"

            st.markdown(html, unsafe_allow_html=True)

            # Export
            if filtered:
                exp_rows = [{
                    "Capital Call #": c["call_label"],
                    "Value Date": c["date"],
                    "Project": c["project"],
                    "FX Rate": c.get("fx_rate"),
                    "Details": c["details"],
                    "KRW": c.get("krw"),
                    "USD": c.get("usd"),
                } for c in filtered]
                safe = fund["fund"].replace(" ", "_").replace("/", "_")
                export_button(pd.DataFrame(exp_rows),
                              f"capital_call_{safe}.xlsx",
                              key=f"exp_cc_{safe}")


main()

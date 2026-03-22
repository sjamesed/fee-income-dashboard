"""Page 2b: Cash Flow Breakdown — project-level detail from 3b. CFS-breakdown."""
import streamlit as st
import json
import pandas as pd
import io
from pathlib import Path
from src.db import FeeIncomeDB


def export_button(df, filename="export.xlsx", key=None):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(label="Export to Excel", data=buf.getvalue(),
                        file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=key)

HEADER_COLOR = "#4a5568"
DATA_DIR = Path(__file__).parent.parent / "data"

# CFS Breakdown sections: (tab_label, [(section_label, total_row)])
CFS_SECTIONS = {
    "Investing Activities": [
        ("Proceeds from disposal of inv. property", 10),
        ("Proceeds from disposal of FVTPL/JV/Assoc", 35),
        ("Proceeds from disposal of other investments", 41),
        ("Payments for BS acquisition", 47),
        ("Payments for CAPEX (BS construction)", 53),
        ("Payments for capital injection in FVTPL/JV/Assoc", 85),
        ("Payments for other investments", 92),
        ("Dividend payment (to outside ESR Group)", 98),
        ("Other investing activities", 104),
    ],
    "Financing Activities": [
        ("Loan received", 113),
        ("Loan amortization and repayment", 120),
        ("Other financing received", 127),
        ("Capital call from ESR HQ", 153),
        ("Cash recycling to ESR HQ", 183),
        ("Inter-co other inflow/(outflow)", 190),
    ],
}


def fmt_v(v):
    """Format value: source in thousands → display in millions."""
    if v is None or v == 0:
        return "-"
    val = v / 1000
    if abs(val) < 0.05:
        return "-"
    if val < 0:
        return f'<span style="color:#c53030;">({abs(val):.1f})</span>'
    return f"{val:.1f}"


def load_cfs_breakdown(bd_list, total_row):
    """Extract project rows for a CFS section ending at total_row."""
    total_entry = None
    total_idx = None
    for idx, entry in enumerate(bd_list):
        if entry["row"] == total_row:
            total_entry = entry
            total_idx = idx
            break

    if total_entry is None:
        return [], {"fy26": 0, "fy25": 0}

    rows = []
    for i in range(total_idx - 1, -1, -1):
        e = bd_list[i]
        g = e.get("g", "")
        if g == "Total" and e["row"] != total_row:
            break
        if g and g != "Total":
            project = e.get("h", "")
            if project.startswith("[") and project.endswith("]"):
                continue
            vals = e.get("v", {})
            # Monthly FY26: V(22)-AG(33)
            monthly = [vals.get(str(c), 0) for c in range(22, 34)]
            rows.append({
                "platform": g,
                "project": project,
                "monthly": monthly,
                "fy26": sum(monthly),  # sum of monthly instead of col 40
                "fy25": vals.get("36", 0),  # AJ=2025 Fcst
            })

    rows.reverse()

    tv = total_entry.get("v", {})
    total_monthly = [tv.get(str(c), 0) for c in range(22, 34)]
    total = {
        "monthly": total_monthly,
        "fy26": sum(total_monthly),  # sum of monthly instead of col 40
        "fy25": tv.get("36", 0),
    }
    return rows, total


def render_cfs_breakdown_table(rows, total, section_label, snapshot_short):
    TH = "padding:5px 6px; border:1px solid #cbd5e0;"
    TD = "padding:4px 6px; border:1px solid #cbd5e0;"
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left; min-width:120px;">Platform</th>
        <th style="{TH} text-align:left; min-width:160px;">Project</th>"""
    for m in months:
        html += f'<th style="{TH}">{m}-26</th>'
    html += f'<th style="{TH} background:#2d3748;">FY26 ({snapshot_short})</th>'
    html += "</tr></thead><tbody>"

    row_idx = 0
    for r in rows:
        # Skip rows where fy26 is 0
        if (r.get("fy26") or 0) == 0:
            continue
        bg = "#f7fafc" if row_idx % 2 == 0 else "#ffffff"
        row_idx += 1
        html += f'<tr style="background:{bg};">'
        html += f'<td style="{TD}">{r["platform"]}</td>'
        html += f'<td style="{TD}">{r["project"]}</td>'
        for v in r["monthly"]:
            html += f'<td style="{TD} text-align:right;">{fmt_v(v)}</td>'
        html += f'<td style="{TD} text-align:right; font-weight:bold;">{fmt_v(r["fy26"])}</td>'
        html += "</tr>"

    html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
    html += f'<td style="{TD}" colspan="2">{section_label} Total</td>'
    for v in total["monthly"]:
        html += f'<td style="{TD} text-align:right;">{fmt_v(v)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(total["fy26"])}</td>'
    html += "</tr></tbody></table>"

    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")
    # Export (source in thousands → ×1000 for USD)
    _months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    exp_rows = []
    for r in rows:
        if (r.get("fy26") or 0) == 0:
            continue
        row_data = {"Platform": r["platform"], "Project": r["project"]}
        for mi, m in enumerate(_months):
            row_data[f"{m} (USD)"] = round((r["monthly"][mi] or 0) * 1000, 2)
        row_data["FY26 Total (USD)"] = round((r["fy26"] or 0) * 1000, 2)
        exp_rows.append(row_data)
    if exp_rows:
        _safe_key = section_label.replace(" ","_").replace("/","_")
        export_button(pd.DataFrame(exp_rows), f"cfs_{_safe_key}.xlsx",
                       key=f"exp_cfs_{_safe_key}_{snapshot_short}")


def render_cfs_summary(cfs, snapshot_short, n):
    """Render full CFS table (monthly FY26 + FY27 months)."""
    CFS_ROWS = [
        (7,"Opening Cash Balance",True),(None,None,False),
        (9,"Cash Flow from Operating Activities",True),
        (10,"  Rental, solar and construction NOI",False),(11,"  Fee Revenue",False),
        (12,"  Dividend",False),(13,"  SG&A and non-recurring expenses",False),
        (14,"  Tax and others",False),(None,None,False),
        (16,"Cash Flow from Investing Activities",True),
        (17,"  Proceeds from disposal of inv. property",False),
        (18,"  Proceeds from disposal of FVTPL/JV/Assoc",False),
        (19,"  Proceeds from disposal of other investments",False),
        (20,"  Payments for BS acquisition",False),
        (21,"  Payments for CAPEX (BS construction)",False),
        (22,"  Payments for capital injection in FVTPL/JV/Assoc",False),
        (23,"  Payments for other investments",False),
        (24,"  Dividend payment (to outside ESR Group)",False),
        (25,"  Other investing activities",False),(None,None,False),
        (27,"Cash Flow from Financing Activities",True),
        (28,"  Loan received",False),(29,"  Loan amortization and repayment",False),
        (30,"  Bank interest payment",False),(31,"  Other financing received",False),
        (32,"  Capital call from ESR HQ",False),(33,"  Cash recycling to ESR HQ",False),
        (34,"  Inter-co other inflow/(outflow)",False),(None,None,False),
        (36,"Total Cash Flows",True),(38,"FX Impact on Cash",False),
        (40,"Closing Cash Balance",True),(None,None,False),
        (42,"Restricted Cash Balance",False),(43,"Warehousing Risk",False),
        (45,"Closing Liquidity",True),(None,None,False),
        (47,"Operating CF (excl. Income Tax & Promote)",False),
        (48,"Operating EBITDA (excl. divestment & promote)",False),
        (49,"EBITDA Cash Conversion Rate",False),(None,None,False),
        (51,"Net Cash Flow to/from ESR HQ",False),
    ]
    FY26_MONTHS = [(str(c),m) for c,m in zip(range(17,29),
        ["Jan-26","Feb-26","Mar-26","Apr-26","May-26","Jun-26",
         "Jul-26","Aug-26","Sep-26","Oct-26","Nov-26","Dec-26"])]
    FY27_NAMES = ["Jan-27","Feb-27","Mar-27","Apr-27","May-27","Jun-27",
                  "Jul-27","Aug-27","Sep-27","Oct-27","Nov-27","Dec-27"]
    fy27_months = [(str(30+i), FY27_NAMES[i]) for i in range(n)]
    COL_DEFS = FY26_MONTHS + [("29", f"FY26 ({snapshot_short})")] + fy27_months

    TH = "padding:5px 6px; border:1px solid #cbd5e0;"
    TD = "padding:4px 6px; border:1px solid #cbd5e0;"

    def fc(v):
        if v is None or v == 0: return "-"
        if not isinstance(v,(int,float)): return str(v)
        if abs(v) < 0.05: return "-"
        if v < 0: return f'<span style="color:#c53030;">({abs(v):.1f})</span>'
        return f"{v:.1f}"

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left; min-width:250px;">(in US$'mil)</th>"""
    for _,lbl in COL_DEFS:
        html += f'<th style="{TH}">{lbl}</th>'
    html += "</tr></thead><tbody>"
    for row_def in CFS_ROWS:
        excel_row,label,bold = row_def
        if excel_row is None:
            html += f'<tr><td style="{TD}" colspan="{len(COL_DEFS)+1}">&nbsp;</td></tr>'
            continue
        # Skip non-bold rows where all COL_DEFS values are None/0
        if not bold:
            rd_check = cfs.get(str(excel_row), {})
            all_zero = True
            for col_key, _ in COL_DEFS:
                v = rd_check.get(col_key)
                if v is not None and isinstance(v, (int, float)) and abs(v) >= 0.05:
                    all_zero = False
                    break
            if all_zero:
                continue
        fw = "font-weight:bold;" if bold else ""
        bg_style = "background:#edf2f7;" if bold else ""
        rd = cfs.get(str(excel_row), {})
        html += f'<tr style="{bg_style}"><td style="{TD} {fw}">{label}</td>'
        for col_key,_ in COL_DEFS:
            v = rd.get(col_key)
            html += f'<td style="{TD} text-align:right; {fw}">{fc(v)}</td>'
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")
    # Export (source in millions → ×1_000_000 for USD)
    exp_rows = []
    for row_def in CFS_ROWS:
        excel_row, label, bold = row_def
        if excel_row is None:
            continue
        rd = cfs.get(str(excel_row), {})
        row_data = {"Label": label.strip()}
        for col_key, col_lbl in COL_DEFS:
            v = rd.get(col_key)
            row_data[f"{col_lbl} (USD)"] = round((v or 0) * 1_000_000, 2) if isinstance(v, (int, float)) else None
        exp_rows.append(row_data)
    if exp_rows:
        export_button(pd.DataFrame(exp_rows), "cfs_summary.xlsx", key="exp_cfs_summary")


def render_comment_section(db, key):
    """Render a comment text area saved per key."""
    saved = db.get_todo(key)
    comment = st.text_area("Comment", value=saved, height=100,
                            key=f"comment_{key}", placeholder="코멘트를 입력하세요...")
    if st.button("Save", key=f"save_{key}"):
        db.save_todo(key, comment)
        st.success("Saved!")


def main():
    st.title("Cash Flow")

    mm_json_files = sorted(DATA_DIR.glob("mm_report_*.json"), reverse=True)
    if not mm_json_files:
        st.warning("No MM Report data found. Upload via Data Management.")
        return

    db = FeeIncomeDB()
    db.init_db()

    snap_names = [f.stem.replace("mm_report_", "") for f in mm_json_files]
    selected = st.selectbox("Snapshot", snap_names)
    json_path = DATA_DIR / f"mm_report_{selected}.json"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfs_bd = data.get("cfs_breakdown", [])
    rc_analysis = data.get("rc_analysis", {})

    # Get N from snapshot name (e.g. "2+10" -> 2)
    try:
        n = int(selected.split("+")[0])
    except (ValueError, IndexError):
        n = 2

    cfs = data.get("output_cfs", {})

    tab_labels = ["Summary"] + list(CFS_SECTIONS.keys()) + ["Restricted Cash"]
    tabs = st.tabs(tab_labels)

    for tab, label in zip(tabs, tab_labels):
        with tab:
            if label == "Summary":
                if cfs:
                    render_cfs_summary(cfs, selected, n)
                else:
                    st.info("No CFS summary data available.")
                continue

            if label == "Restricted Cash":
                render_restricted_cash(rc_analysis, selected, n, db)
                continue

            if not cfs_bd:
                st.warning("No CFS breakdown data. Re-upload the MM Report file.")
                continue

            subsections = CFS_SECTIONS[label]
            for sub_label, total_row in subsections:
                rows, total = load_cfs_breakdown(cfs_bd, total_row)
                if rows or total["fy26"] != 0:
                    st.subheader(sub_label)
                    if rows:
                        render_cfs_breakdown_table(rows, total, sub_label, selected)
                    else:
                        st.write(f"FY26: {fmt_v(total['fy26'])}M", unsafe_allow_html=True)
                    # Comment per subsection
                    section_key = sub_label.replace(" ", "_").replace("/", "_").lower()[:30]
                    render_comment_section(db, f"cfs_{section_key}_{selected}")


def render_restricted_cash(rc_analysis, snapshot_short, n, db):
    """Render restricted cash analysis from 3a. CFS (rows 61-66), matching Output CFS Row 42."""
    if not rc_analysis:
        st.info("No restricted cash data available.")
        return

    TH = "padding:6px 8px; border:1px solid #cbd5e0;"
    TD = "padding:5px 8px; border:1px solid #cbd5e0;"

    def fmt_k(v):
        if v is None or v == 0:
            return "-"
        if not isinstance(v, (int, float)):
            return str(v)
        val = v / 1000
        if abs(val) < 0.05:
            return "-"
        if val < 0:
            return f'<span style="color:#c53030;">({abs(val):.1f})</span>'
        return f"{val:.1f}"

    # Rows from 3a. CFS restricted cash analysis
    RC_ROWS = [
        (61, "Project Need - No Restriction for Repatriation", False),
        (62, "Project Need - With Restriction", False),
        (63, "Interest Reserve/Payment", False),
        (64, "Daily Operation Need (3 months reserve)", False),
        (65, "Other Restrictions", False),
        (66, "Free Cash", False),
    ]

    # Monthly FY26: V(22)=Jan-26 to AG(33)=Dec-26
    # We show up to the actual month (N months)
    MONTH_NAMES = ["Jan-26","Feb-26","Mar-26","Apr-26","May-26","Jun-26",
                   "Jul-26","Aug-26","Sep-26","Oct-26","Nov-26","Dec-26"]
    month_cols = [(str(22 + i), MONTH_NAMES[i]) for i in range(n)]

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left; min-width:300px;">(in US$'mil)</th>"""
    for _, m in month_cols:
        html += f'<th style="{TH}">{m}</th>'
    html += "</tr></thead><tbody>"

    # Data rows
    totals = {col_key: 0 for col_key, _ in month_cols}
    for r, label, _ in RC_ROWS:
        rd = rc_analysis.get(str(r), {})
        is_free = r == 66
        bg = "background:#f7fafc;" if is_free else ""
        html += f'<tr style="{bg}">'
        html += f'<td style="{TD}">{label}</td>'
        for col_key, _ in month_cols:
            v = rd.get(col_key, 0)
            if isinstance(v, (int, float)):
                totals[col_key] += v
            html += f'<td style="{TD} text-align:right;">{fmt_k(v)}</td>'
        html += "</tr>"

    # Total row
    html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
    html += f'<td style="{TD}">Total (= Closing Cash Balance)</td>'
    for col_key, _ in month_cols:
        html += f'<td style="{TD} text-align:right;">{fmt_k(totals[col_key])}</td>'
    html += "</tr>"

    # Restricted = Total - Free Cash (rows 61+62+63+64+65)
    rd66 = rc_analysis.get("66", {})
    html += f'<tr style="background:#edf2f7; font-weight:bold;">'
    html += f'<td style="{TD}">Restricted Cash Balance (excl. Free Cash)</td>'
    for col_key, _ in month_cols:
        total_v = totals.get(col_key, 0)
        free_v = rd66.get(col_key, 0)
        if not isinstance(free_v, (int, float)):
            free_v = 0
        restricted = total_v - free_v
        html += f'<td style="{TD} text-align:right;">{fmt_k(restricted)}</td>'
    html += "</tr>"

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions  |  Restricted = Total - Free Cash (matches Output CFS Row 42)")
    # Export (source in thousands → ×1000 for USD)
    exp_rows = []
    for excel_row, label, _ in RC_ROWS:
        rd = rc_analysis.get(str(excel_row), {})
        row_data = {"Category": label}
        for col_key, col_lbl in month_cols:
            v = rd.get(col_key, 0)
            row_data[f"{col_lbl} (USD)"] = round((v or 0) * 1000, 2) if isinstance(v, (int, float)) else None
        exp_rows.append(row_data)
    # Total row
    row_data = {"Category": "Total (Closing Cash Balance)"}
    for col_key, col_lbl in month_cols:
        row_data[f"{col_lbl} (USD)"] = round((totals.get(col_key, 0) or 0) * 1000, 2)
    exp_rows.append(row_data)
    # Restricted row
    row_data = {"Category": "Restricted Cash Balance"}
    for col_key, col_lbl in month_cols:
        total_v = totals.get(col_key, 0)
        free_v = rd66.get(col_key, 0) if isinstance(rd66.get(col_key, 0), (int, float)) else 0
        row_data[f"{col_lbl} (USD)"] = round((total_v - free_v) * 1000, 2)
    exp_rows.append(row_data)
    export_button(pd.DataFrame(exp_rows), "restricted_cash.xlsx", key="exp_rc_analysis")

    # Per-item comments
    saved = db.get_drivers("rc_comments", snapshot_short)
    rc_labels = [label for _, label, _ in RC_ROWS]
    has_comments = any(saved.get(l) for l in rc_labels)

    # Display saved comments
    if has_comments:
        st.markdown("")
        TD2 = "padding:5px 8px; border:1px solid #cbd5e0;"
        ch = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif; margin-top:4px;">
        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="{TD2} text-align:left; width:30%;">Category</th>
            <th style="{TD2} text-align:left;">Comment</th>
        </tr></thead><tbody>"""
        for l in rc_labels:
            c = saved.get(l, "")
            if c:
                ch += f'<tr><td style="{TD2} font-weight:bold;">{l}</td><td style="{TD2}">{c}</td></tr>'
        ch += "</tbody></table>"
        st.markdown(ch, unsafe_allow_html=True)

    # Edit comments
    with st.expander("Edit Comments"):
        updated = {}
        for _, label, _ in RC_ROWS:
            updated[label] = st.text_area(
                label, value=saved.get(label, ""), height=68,
                key=f"rc_comment_{label}",
            )
        if st.button("Save Comments", key="save_rc_comments"):
            db.save_drivers("rc_comments", snapshot_short, updated)
            st.success("Saved!")
            st.rerun()


main()

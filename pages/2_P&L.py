"""Page 2: P&L — summary table + detailed breakdown by category."""
import streamlit as st
import json
import pandas as pd
import io
from pathlib import Path
from src.db import FeeIncomeDB
from src.queries import get_snapshot_n_value


def export_button(df, filename="export.xlsx", key=None):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(label="Export to Excel", data=buf.getvalue(),
                        file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=key)

HEADER_COLOR = "#4a5568"
DATA_DIR = Path(__file__).parent.parent / "data"


BREAKDOWN_SECTIONS = {
    "Fee Income": [
        ("Asset Management Fee", 133),
        ("Investment Management Fee", 151),
        ("Property Management Fee", 169),
        ("Development Management Fee", 220),
        ("Leasing Management Fee", 275),
        ("Acquisition / Disposal Fee", 334),
        ("Promote", 343),
        ("Others", 396),
        ("Fee Income Total", 398),
    ],
    "Share of Profit (JV/Assoc & FVTPL)": [
        ("Share of Profits from JV/Assoc (W/O FV)", 415),
        ("Share of Profits from FVTPL Fin. Assets (W/O FV)", 433),
    ],
    "Share of FV Gain (FVTPL)": [
        ("Share of FV Gains from JV/Assoc", 449),
        ("Share of FV Gains from FVTPL Fin. Assets", 467),
        ("FV Gains on Investment Properties", 476),
    ],
    "Dividend Income": [("Dividend Income", 490)],
    "Divestment Gain": [("Divestment Gain", 499)],
    "Non-Recurring": [("Non-Recurring Items", 513)],
    "Others": [("Others", 522)],
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


def fmt_v_raw(v):
    """Format value already in millions."""
    if v is None or v == 0:
        return "-"
    if abs(v) < 0.05:
        return "-"
    if v < 0:
        return f'<span style="color:#c53030;">({abs(v):.1f})</span>'
    return f"{v:.1f}"


def load_breakdown_from_json(bd_list, total_row):
    """Extract project rows for a section ending at total_row from pre-loaded JSON list."""
    # Find the total row entry
    total_entry = None
    total_idx = None
    for idx, entry in enumerate(bd_list):
        if entry["row"] == total_row:
            total_entry = entry
            total_idx = idx
            break

    if total_entry is None:
        return [], {"monthly": [0]*12, "fy26": 0, "fy25": 0, "fy24": 0}

    # Walk backwards from total to find data rows
    rows = []
    for i in range(total_idx - 1, -1, -1):
        e = bd_list[i]
        h = e.get("h", "")
        if h == "Total" and e["row"] != total_row:
            break  # hit previous section total
        if h and h != "Total":
            project = e.get("i", "")
            if project.startswith("[") and project.endswith("]"):
                continue
            vals = e.get("v", {})
            fcst_monthly = [vals.get(str(c), 0) for c in range(23, 35)]
            bud_monthly = [vals.get(f"b{c}", 0) for c in range(23, 35)]
            fy25_monthly = [vals.get(f"a{c}", 0) for c in range(11, 23)]
            rows.append({
                "platform": h,
                "project": project,
                "fy26": vals.get("41", 0),
                "fy25_bud": vals.get("58", 0),
                "fy25": vals.get("37", 0),
                "fy24": vals.get("75", 0),
                "fcst_monthly": fcst_monthly,
                "bud_monthly": bud_monthly,
                "fy25_monthly": fy25_monthly,
            })

    rows.reverse()

    # Total
    tv = total_entry.get("v", {})
    total = {
        "fy26": tv.get("41", 0),
        "fy25_bud": tv.get("58", 0),
        "fy25": tv.get("37", 0),
        "fy24": tv.get("75", 0),
        "fcst_monthly": [tv.get(str(c), 0) for c in range(23, 35)],
        "bud_monthly": [tv.get(f"b{c}", 0) for c in range(23, 35)],
        "fy25_monthly": [tv.get(f"a{c}", 0) for c in range(11, 23)],
    }
    return rows, total


def fmt_pct_delta(a, b):
    """Format percentage delta: (a-b)/|b|. Suppress if both values too small to display."""
    if b is None or b == 0 or a is None:
        return "-"
    # If both a and b are too small to show as numbers (< 0.05 in millions), suppress %
    a_mil = abs(a) / 1000 if isinstance(a, (int, float)) else 0
    b_mil = abs(b) / 1000 if isinstance(b, (int, float)) else 0
    if a_mil < 0.05 and b_mil < 0.05:
        return "-"
    pct = (a - b) / abs(b) * 100
    if abs(pct) < 0.05:
        return "-"
    color = "#38a169" if pct > 0 else "#c53030"
    return f'<span style="color:{color};">{pct:+.1f}%</span>'


def fmt_var(a, b):
    """Format variance a - b (both in thousands, display in millions)."""
    if a is None:
        a = 0
    if b is None:
        b = 0
    return fmt_v(a - b)



MONTH_NAMES = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
               7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}


def _get_mtd_ytd(r, n):
    """Calculate MTD and YTD values for a breakdown row. n = snapshot month (1-based)."""
    fm = r.get("fcst_monthly", [0]*12)
    bm = r.get("bud_monthly", [0]*12)
    am = r.get("fy25_monthly", [0]*12)
    idx = n - 1  # 0-based month index
    mtd_act = fm[idx] if idx < len(fm) else 0
    mtd_bud = bm[idx] if idx < len(bm) else 0
    mtd_ly = am[idx] if idx < len(am) else 0
    ytd_act = sum(fm[:n])
    ytd_bud = sum(bm[:n])
    ytd_ly = sum(am[:n])
    return mtd_act, mtd_bud, mtd_ly, ytd_act, ytd_bud, ytd_ly


def render_breakdown_table(rows, total, section_label, snapshot_short, total_row=0, n=2):
    """Render breakdown table in same style as P&L Summary (4-group header)."""
    TH = "padding:5px 6px; border:1px solid #cbd5e0;"
    TD = "padding:4px 6px; border:1px solid #cbd5e0;"
    mn = MONTH_NAMES.get(n, str(n))

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left; min-width:120px;" rowspan="2">Platform</th>
        <th style="{TH} text-align:left; min-width:140px;" rowspan="2">Project</th>
        <th style="{TH}" colspan="4">MTD {mn}</th>
        <th style="{TH}" colspan="4">YTD {mn}</th>
        <th style="{TH}" colspan="4">FY26 Fcst ({snapshot_short}) vs Budget</th>
        <th style="{TH}" colspan="4">FY26 Fcst ({snapshot_short}) vs FY25</th>
    </tr>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center; font-size:11px;">"""
    for sl in ["Actual","Budget","Var","%Δ","Actual","Budget","Var","%Δ","Fcst","Budget","Var","%Δ","Fcst","LY","Var","%Δ"]:
        html += f'<th style="{TH}">{sl}</th>'
    html += "</tr></thead><tbody>"

    row_idx = 0
    for r in rows:
        fy26 = r.get("fy26", 0) or 0
        bud = r.get("fy25_bud", 0) or 0
        fy25 = r.get("fy25", 0) or 0
        mtd_a, mtd_b, mtd_ly, ytd_a, ytd_b, ytd_ly = _get_mtd_ytd(r, n)
        if fy26 == 0 and bud == 0 and fy25 == 0 and mtd_a == 0 and ytd_a == 0:
            continue
        bg = "#f7fafc" if row_idx % 2 == 0 else "#ffffff"
        row_idx += 1
        html += f'<tr style="background:{bg};">'
        html += f'<td style="{TD}">{r["platform"]}</td>'
        html += f'<td style="{TD}">{r["project"]}</td>'
        # MTD
        html += f'<td style="{TD} text-align:right;">{fmt_v(mtd_a)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_v(mtd_b)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_var(mtd_a, mtd_b)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(mtd_a, mtd_b)}</td>'
        # YTD
        html += f'<td style="{TD} text-align:right;">{fmt_v(ytd_a)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_v(ytd_b)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_var(ytd_a, ytd_b)}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(ytd_a, ytd_b)}</td>'
        # FY26 Fcst vs Budget
        html += f'<td style="{TD} text-align:right; font-weight:bold;">{fmt_v(r.get("fy26"))}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_v(r.get("fy25_bud"))}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_var(r.get("fy26"), r.get("fy25_bud"))}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(r.get("fy26"), r.get("fy25_bud"))}</td>'
        # FY26 Fcst vs FY25
        html += f'<td style="{TD} text-align:right; font-weight:bold;">{fmt_v(r.get("fy26"))}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_v(r.get("fy25"))}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_var(r.get("fy26"), r.get("fy25"))}</td>'
        html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(r.get("fy26"), r.get("fy25"))}</td>'
        html += "</tr>"

    # Total row
    t_mtd_a, t_mtd_b, t_mtd_ly, t_ytd_a, t_ytd_b, t_ytd_ly = _get_mtd_ytd(total, n)
    html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
    html += f'<td style="{TD}" colspan="2">{section_label} Total</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(t_mtd_a)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(t_mtd_b)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_var(t_mtd_a, t_mtd_b)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(t_mtd_a, t_mtd_b)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(t_ytd_a)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(t_ytd_b)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_var(t_ytd_a, t_ytd_b)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(t_ytd_a, t_ytd_b)}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(total.get("fy26"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(total.get("fy25_bud"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_var(total.get("fy26"), total.get("fy25_bud"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(total.get("fy26"), total.get("fy25_bud"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(total.get("fy26"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_v(total.get("fy25"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_var(total.get("fy26"), total.get("fy25"))}</td>'
    html += f'<td style="{TD} text-align:right;">{fmt_pct_delta(total.get("fy26"), total.get("fy25"))}</td>'
    html += "</tr></tbody></table>"

    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")

    # Export
    exp_rows = []
    for r in rows:
        fy26 = r.get("fy26", 0) or 0
        bud = r.get("fy25_bud", 0) or 0
        fy25 = r.get("fy25", 0) or 0
        mtd_a, mtd_b, mtd_ly, ytd_a, ytd_b, ytd_ly = _get_mtd_ytd(r, n)
        if fy26 == 0 and bud == 0 and fy25 == 0 and mtd_a == 0 and ytd_a == 0:
            continue
        exp_rows.append({
            "Platform": r["platform"], "Project": r["project"],
            f"MTD {mn} Actual (USD)": round((mtd_a or 0) * 1000, 2),
            f"MTD {mn} Budget (USD)": round((mtd_b or 0) * 1000, 2),
            f"YTD {mn} Actual (USD)": round((ytd_a or 0) * 1000, 2),
            f"YTD {mn} Budget (USD)": round((ytd_b or 0) * 1000, 2),
            "FY26 Fcst (USD)": round((r.get("fy26") or 0) * 1000, 2),
            "FY26 Budget (USD)": round((r.get("fy25_bud") or 0) * 1000, 2),
            "FY25 Actual (USD)": round((r.get("fy25") or 0) * 1000, 2),
        })
    if exp_rows:
        _safe = section_label.replace(" ","_").replace("/","_")
        export_button(pd.DataFrame(exp_rows), f"pl_breakdown_{_safe}.xlsx",
                       key=f"exp_bd_{_safe}_{total_row}_{snapshot_short}")


def render_sga_tab(sga_data):
    """Render SG&A from pre-extracted JSON data."""
    SGA_ROWS = [
        (5, "Labour Costs", False),
        (6, "Bonuses", False),
        (7, "Travel & Entertainment", False),
        (8, "Office & Occupancy Costs", False),
        (9, "Professional Fees", False),
        (10, "IT Costs", False),
        (11, "Others", False),
        (12, "Total SG&A", True),
        (None, None, False),
        (14, "Headcount", False),
        (15, "Total Labour Cost", False),
        (16, "Fee Income (excl. Promote)", False),
        (None, None, False),
        (18, "Labour Efficiency Ratio", False),
        (19, "Total Labour Cost per HC (US$'000)", False),
        (20, "T&E per HC (US$'000)", False),
    ]

    COL_DEFS = [
        ("10", "FY26 Fcst", False),
        ("11", "FY26 Bud", False),
        ("8", "FY25 Act", False),
        ("19", "FY26F vs FY26B", False),
        ("20", "%Δ", True),
    ]

    TH = "padding:5px 6px; border:1px solid #cbd5e0;"
    TD = "padding:4px 6px; border:1px solid #cbd5e0;"

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left; min-width:200px;">(in US$'mil)</th>"""
    for _, lbl, _ in COL_DEFS:
        html += f'<th style="{TH}">{lbl}</th>'
    html += "</tr></thead><tbody>"

    for row_def in SGA_ROWS:
        excel_row, label, bold = row_def
        if excel_row is None:
            html += f'<tr><td style="{TD}" colspan="{len(COL_DEFS)+1}">&nbsp;</td></tr>'
            continue

        # Skip non-bold rows where all COL_DEFS values are None/0
        if not bold:
            rd_check = sga_data.get(str(excel_row), {})
            all_zero = True
            for col_key, _, _ in COL_DEFS:
                v = rd_check.get(col_key)
                if v is not None and isinstance(v, (int, float)) and abs(v) >= 0.005:
                    all_zero = False
                    break
            if all_zero:
                continue

        fw = "font-weight:bold;" if bold else ""
        bg_style = "background:#edf2f7;" if bold else ""
        rd = sga_data.get(str(excel_row), {})

        html += f'<tr style="{bg_style}">'
        html += f'<td style="{TD} {fw}">{label}</td>'

        for col_key, col_label, is_pct in COL_DEFS:
            v = rd.get(col_key)
            if is_pct:
                if v is None:
                    cell_html = "-"
                elif isinstance(v, (int, float)):
                    pct = v * 100
                    color = "#38a169" if pct > 0 else "#c53030"
                    cell_html = f'<span style="color:{color};">{pct:+.1f}%</span>'
                else:
                    cell_html = str(v)
            else:
                cell_html = fmt_v_raw(v) if isinstance(v, (int, float)) else ("-" if v is None else str(v))
            html += f'<td style="{TD} text-align:right; {fw}">{cell_html}</td>'
        html += "</tr>"

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")
    # Export (source in millions → ×1_000_000 for USD; pct rows kept as %)
    exp_rows = []
    for excel_row, label, bold in SGA_ROWS:
        if excel_row is None:
            continue
        rd = sga_data.get(str(excel_row), {})
        row_data = {"Label": label}
        for col_key, col_label, is_pct in COL_DEFS:
            v = rd.get(col_key)
            if is_pct:
                row_data[col_label] = round(v * 100, 2) if isinstance(v, (int, float)) else None
            else:
                row_data[f"{col_label} (USD)"] = round((v or 0) * 1_000_000, 2) if isinstance(v, (int, float)) else None
        exp_rows.append(row_data)
    if exp_rows:
        export_button(pd.DataFrame(exp_rows), "sga_analysis.xlsx", key="exp_sga")


def _load_pl_data(raw):
    """Load Output PL data from pre-extracted JSON."""
    pl = raw.get("output_pl", {})
    COL_MAP = {"2":1,"4":3,"5":4,"6":5,"7":6,"8":7,"9":8,"10":9,"11":10,
               "26":25,"27":26,"28":27,"29":28,"30":29,"31":30,"32":31,"33":32}
    data = {}
    for row_str, rd in pl.items():
        row_key = int(row_str) if row_str != "header" else row_str
        converted = {}
        for col_str, v in rd.items():
            ci_0 = COL_MAP.get(col_str)
            if ci_0 is not None:
                converted[ci_0] = v
        if row_key == 5:
            data["header"] = converted
        else:
            data[row_key] = converted
    return data


def render_pl_summary(pl_data, snapshot_short, highlighted_labels=None):
    """Render full P&L summary table. highlighted_labels: set of lowercased label prefixes to highlight."""
    highlighted_labels = highlighted_labels or set()
    PL_ROWS = [
        (7,"Asset / Investment Mgmt Fee",1,False,False),(8,"Property Mgmt Fee",1,False,False),
        (9,"Leasing Fee",1,False,False),(10,"Development Mgmt Fee",1,False,False),
        (11,"Acq / Div Fee",1,False,False),(12,"Other",1,False,False),
        (13,"Fee Income excl. Promote",0,True,False),(14,"Promote Fee",1,False,False),
        (15,"Fee Income",0,True,False),
        (17,"Rental Revenue",1,False,False),(18,"Rental Cost",1,False,False),(19,"Rental NOI",0,False,False),
        (20,"Solar Revenue",1,False,False),(21,"Solar Cost",1,False,False),(22,"Solar NOI",0,False,False),
        (23,"Dividend Income",0,False,False),
        (24,"Share of Profit/Loss from Fund/JV (excl. FV Gain/Loss)",0,False,False),
        (25,"Investment Income",0,True,False),
        (27,"Construction Revenue",1,False,False),(28,"Construction Cost",1,False,False),
        (29,"Construction NOI",0,False,False),(30,"SG&A Expenses",0,False,False),
        (31,"Operating EBITDA (excl. Divestment Gain/Loss)",0,True,False),
        (33,"Divestment Gain/Loss",0,False,False),(34,"Operating EBITDA",0,True,False),
        (36,"Fee-Based Operating EBITDA (FBOE = Fee Income - SG&A)",0,False,False),
        (37,"Fee-Based Operating EBITDA Margin (%)",0,False,True),
        (39,"Fee-Based Operating EBITDA excl. Promote",0,False,False),
        (40,"Fee-Based Operating EBITDA Margin excl. Promote (%)",0,False,True),
        (42,"Depreciation & Amortisation",0,False,False),
        (43,"Finance Costs (net of Interest Income)",0,False,False),
        (44,"Operating Profit (Pre-Tax)",0,True,False),
        (46,"Income Tax",0,False,False),(47,"Operating Profit (Post-Tax)",0,True,False),
        (50,"FV Gain/Loss - Fund/JV",0,False,False),(52,"Foreign Exchange Gain/Loss",0,False,False),
        (53,"Non-Recurring",0,False,False),(54,"Others",0,False,False),
        (56,"Profit After Tax",0,True,False),(58,"Minority Interest",0,False,False),
        (60,"PATMI",0,True,False),
    ]
    COL_GROUPS = [(3,4,5,6),(7,8,9,10),(25,26,27,28),(29,30,31,32)]
    hdr = pl_data.get("header", {})
    hdr_labels = []
    for grp in COL_GROUPS:
        for ci in grp:
            v = hdr.get(ci, "") or ""
            hdr_labels.append(str(v).replace("\n", "<br>"))

    def fv(v, is_pct=False):
        if v is None: return "-"
        if is_pct: return f"{v*100:.1f}%" if isinstance(v,(int,float)) else str(v)
        if isinstance(v,(int,float)):
            if abs(v) < 0.005: return "-"
            if v < 0: return f'<span style="color:#c53030;">({abs(v):.1f})</span>'
            return f"{v:.1f}"
        return str(v)
    def fpd(v):
        if v is None: return "-"
        if isinstance(v,(int,float)):
            if v == 0: return "-"
            pct = v*100; color = "#38a169" if pct > 0 else "#c53030"
            return f'<span style="color:{color};">{pct:+.1f}%</span>'
        return str(v)

    TH = "padding:5px 6px; border:1px solid #cbd5e0;"
    month_label = hdr_labels[0].split("<br>")[0].replace("MTD ","") if hdr_labels else ""
    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
        <th style="{TH} text-align:left; min-width:200px;" rowspan="2">(in US$'mil)</th>
        <th style="{TH}" colspan="4">MTD {month_label}</th>
        <th style="{TH}" colspan="4">YTD {month_label}</th>
        <th style="{TH}" colspan="4">FY26 Fcst ({snapshot_short}) vs Budget</th>
        <th style="{TH}" colspan="4">FY26 Fcst ({snapshot_short}) vs FY25</th>
    </tr>
    <tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center; font-size:11px;">"""
    for sl in ["Actual","Budget","Var","%Δ","Actual","Budget","Var","%Δ","Fcst","Budget","Var","%Δ","Fcst","LY","Var","%Δ"]:
        html += f'<th style="{TH}">{sl}</th>'
    html += "</tr></thead><tbody>"
    TD = "padding:4px 6px; border:1px solid #cbd5e0;"
    for row_def in PL_ROWS:
        excel_row,label,indent,bold,is_pct = row_def
        # Skip non-bold rows where all numeric values are zero/None
        if not bold and excel_row is not None:
            rd = pl_data.get(excel_row, {})
            all_zero = True
            for grp in COL_GROUPS:
                for ci in grp:
                    v = rd.get(ci)
                    if v is not None and isinstance(v, (int, float)) and abs(v) >= 0.005:
                        all_zero = False
                        break
                if not all_zero:
                    break
            if all_zero:
                continue
        fw = "font-weight:bold;" if bold else ""
        bg_style = f"background:#edf2f7;" if bold else ""
        # Check if this row has comments
        lbl_low = label.lower()
        _stop = {"and", "of", "from", "the", "a", "in", "on", "to", "vs", "for"}
        is_highlighted = any(h in lbl_low or all(w in lbl_low for w in h.split() if w not in _stop) for h in highlighted_labels)
        highlight_marker = ' <span style="color:#d69e2e; font-size:10px;" title="Has comments">&#9679;</span>' if is_highlighted else ""
        pad = f"padding-left:{12+indent*16}px;" if indent else ""
        hl_border = "border-left:3px solid #d69e2e;" if is_highlighted else ""
        html += f'<tr style="{bg_style}"><td style="{TD} {fw} {pad} {hl_border}">{label}{highlight_marker}</td>'
        for grp in COL_GROUPS:
            for i,ci in enumerate(grp):
                v = pl_data.get(excel_row,{}).get(ci)
                if i==3: cell_html = fpd(v) if not is_pct else fv(v,True)
                elif is_pct: cell_html = fv(v,True)
                else: cell_html = fv(v)
                html += f'<td style="{TD} text-align:right; {fw}">{cell_html}</td>'
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")
    # Export (source in millions → ×1_000_000 for USD; Var% kept as %)
    grp_names = ["MTD","YTD","FY26 vs Bud","FY26 vs FY25"]
    sub_names_map = {
        "MTD": ["Actual (USD)","Budget (USD)","Var (USD)","% Var"],
        "YTD": ["Actual (USD)","Budget (USD)","Var (USD)","% Var"],
        "FY26 vs Bud": ["Fcst (USD)","Budget (USD)","Var (USD)","% Var"],
        "FY26 vs FY25": ["Fcst (USD)","LY (USD)","Var (USD)","% Var"],
    }
    exp_cols = [f"{gn} {sn}" for gn in grp_names for sn in sub_names_map[gn]]
    exp_rows = []
    for row_def in PL_ROWS:
        excel_row, label, indent, bold, is_pct_row = row_def
        rd = pl_data.get(excel_row, {})
        row_data = {"Label": label.strip()}
        gi = 0
        for grp in COL_GROUPS:
            for i, ci in enumerate(grp):
                v = rd.get(ci)
                col_name = f"{grp_names[gi]} {sub_names_map[grp_names[gi]][i]}"
                if i == 3:
                    # % variance column — always percentage
                    row_data[col_name] = round(v * 100, 2) if isinstance(v, (int, float)) else None
                elif is_pct_row:
                    # % row (e.g. margin) — store as percentage
                    row_data[col_name] = round(v * 100, 2) if isinstance(v, (int, float)) else None
                else:
                    row_data[col_name] = round((v or 0) * 1_000_000, 2) if isinstance(v, (int, float)) else None
            gi += 1
        exp_rows.append(row_data)
    if exp_rows:
        export_button(pd.DataFrame(exp_rows, columns=["Label"] + exp_cols), "pl_summary.xlsx", key="exp_pl_summary")


def print_button():
    import streamlit.components.v1 as components
    # Inject print CSS into parent frame for landscape + fit-to-page
    components.html("""
    <script>
    (function() {
        var style = window.top.document.getElementById('pl-print-css');
        if (!style) {
            style = window.top.document.createElement('style');
            style.id = 'pl-print-css';
            style.textContent = `
                @media print {
                    @page { size: landscape; margin: 8mm; }
                    [data-testid="stSidebar"] { display: none !important; }
                    [data-testid="stHeader"] { display: none !important; }
                    header { display: none !important; }
                    .stDeployButton { display: none !important; }
                    section[data-testid="stSidebar"] { display: none !important; }
                    .main .block-container { max-width: 100% !important; padding: 0 !important; }
                    table { font-size: 9px !important; }
                    th, td { padding: 2px 4px !important; }
                    iframe { display: none !important; }
                }
            `;
            window.top.document.head.appendChild(style);
        }
    })();
    </script>
    <button onclick="window.top.print()" style="background:#4a5568; color:white; border:none;
        padding:6px 16px; border-radius:4px; cursor:pointer; font-size:13px; font-family:Calibri,sans-serif;">
        🖨️ Print
    </button>
    """, height=40)


def main():
    st.title("P&L")
    print_button()

    mm_json_files = sorted(DATA_DIR.glob("mm_report_*.json"), reverse=True)
    if not mm_json_files:
        st.warning("No MM Report data found. Upload via Data Management.")
        return

    snap_names = [f.stem.replace("mm_report_", "") for f in mm_json_files]
    selected = st.selectbox("Snapshot", snap_names)
    json_path = DATA_DIR / f"mm_report_{selected}.json"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pl_data = _load_pl_data(data)
    bd_list = data.get("pl_breakdown", [])
    sga_data = data.get("output_sga", {})
    n = get_snapshot_n_value(selected)

    tab_labels = ["Summary"] + list(BREAKDOWN_SECTIONS.keys())
    tab_labels.insert(2, "SG&A")  # After Fee Income
    tabs = st.tabs(tab_labels)

    for tab, label in zip(tabs, tab_labels):
        with tab:
            if label == "Summary":
                import pandas as pd
                db = FeeIncomeDB()
                db.init_db()
                # Collect highlighted labels from all comment sections
                import re
                _hl_labels = set()
                for _ck in ["pl_mtd_bud", "pl_ytd_bud", "pl_fy_bud", "pl_fy_fy25"]:
                    _saved = db.get_drivers(f"{_ck}_{selected}", "pl_comment")
                    for key in _saved:
                        # Extract item name before the parenthesized variance, e.g. "Fee income (-0.2m)" → "fee income"
                        item = re.sub(r"\s*\([^)]*\)\s*$", "", key).strip().lower()
                        if item:
                            _hl_labels.add(item)
                if pl_data:
                    render_pl_summary(pl_data, selected, highlighted_labels=_hl_labels)
                else:
                    st.info("No P&L summary data available.")
                comment_sections = [
                    ("MTD Key Variances vs Budget", "pl_mtd_bud"),
                    ("YTD Key Variances vs Budget", "pl_ytd_bud"),
                    ("Full Year Key Variances vs Budget", "pl_fy_bud"),
                    ("Full Year Key Variances vs FY25", "pl_fy_fy25"),
                ]
                st.markdown("---")
                st.subheader("P&L Comments")
                for cl, ck in comment_sections:
                    table_key = f"{ck}_{selected}"
                    saved = db.get_drivers(table_key, "pl_comment")
                    # Build display table
                    TD = "padding:4px 6px; border:1px solid #cbd5e0;"
                    if saved:
                        ch = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif; margin-top:4px;">
                        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
                            <th style="{TD} text-align:left; width:100%;" colspan="2">{cl}</th>
                        </tr></thead><tbody>"""
                        for item, comment in sorted(saved.items()):
                            if comment.strip():
                                ch += f'<tr><td style="{TD} font-weight:bold; width:25%;">{item}</td><td style="{TD}">{comment}</td></tr>'
                        ch += "</tbody></table>"
                        st.markdown(ch, unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{cl}** — No comments yet.")

                    with st.expander(f"Edit — {cl}"):
                        edit_data = []
                        if saved:
                            for item, comment in sorted(saved.items()):
                                edit_data.append({"Line Item": item, "Comment": comment})
                        if not edit_data:
                            edit_data = [{"Line Item": "", "Comment": ""}]
                        edited_df = st.data_editor(
                            pd.DataFrame(edit_data), num_rows="dynamic",
                            column_config={
                                "Line Item": st.column_config.TextColumn("Line Item", width="medium"),
                                "Comment": st.column_config.TextColumn("Comment", width="large"),
                            }, use_container_width=True, hide_index=True, key=f"edit_{ck}",
                        )
                        if st.button("Save", key=f"save_{ck}"):
                            drivers = {}
                            for _, row in edited_df.iterrows():
                                item = str(row.get("Line Item", "")).strip()
                                comment = str(row.get("Comment", "")).strip()
                                if item:
                                    drivers[item] = comment
                            db.save_drivers(table_key, "pl_comment", drivers)
                            st.success(f"{cl} saved!")
                            st.rerun()
                continue

            if label == "SG&A":
                if sga_data:
                    render_sga_tab(sga_data)
                else:
                    st.info("No SG&A data available.")
                continue

            if label == "Fee Income":
                st.info("Refer to Fee Breakdown tab")
                continue

            if not bd_list:
                st.info("No breakdown data available. Re-upload the MM Report file to extract breakdown data.")
                continue

            subsections = BREAKDOWN_SECTIONS[label]
            for sub_label, total_row in subsections:
                st.subheader(sub_label)
                rows, total = load_breakdown_from_json(bd_list, total_row)
                if rows:
                    render_breakdown_table(rows, total, sub_label, selected, total_row=total_row, n=n)
                else:
                    st.write(f"FY26 Fcst ({selected}): {fmt_v(total['fy26'])}M | FY25: {fmt_v(total['fy25'])}M", unsafe_allow_html=True)


main()

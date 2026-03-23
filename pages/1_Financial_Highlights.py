"""Page 1: Dashboard — key metrics, P&L/CFS highlights, watch list, and reporting tables."""
import streamlit as st
import pandas as pd
import io
import json
from pathlib import Path
from src.db import FeeIncomeDB
from src.queries import get_mtd_comparison, get_ytd_comparison, get_snapshot_n_value

DATA_DIR = Path(__file__).parent.parent / "data"
MONTH_NAMES = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
               7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
HEADER_COLOR = "#4a5568"


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def format_millions(value: float) -> str:
    return f"{value / 1_000_000:.1f}"

def format_millions_colored(value: float) -> str:
    """Format with $ sign; negative shown as -$X.X (no color)."""
    v = value / 1_000_000
    if v < -0.05:
        return f"-${abs(v):.1f}"
    return f"${v:.1f}"

def fmt_pl(v):
    """Format P&L value (already in millions)."""
    if v is None or not isinstance(v, (int, float)) or abs(v) < 0.005:
        return "-"
    if v < 0:
        return f'<span style="color:#c53030;">({abs(v):.1f})</span>'
    return f"{v:.1f}"

def fmt_pct(v):
    if v is None or not isinstance(v, (int, float)) or v == 0:
        return "-"
    pct = v * 100
    color = "#38a169" if pct > 0 else "#c53030"
    return f'<span style="color:{color};">{pct:+.1f}%</span>'

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


def render_kpi_card(label, value_str, sub_label="", color="#4a5568"):
    """Render a single KPI card."""
    return f"""<div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid {color}; text-align:center;">
        <div style="font-size:11px; color:#718096; text-transform:uppercase;">{label}</div>
        <div style="font-size:20px; font-weight:bold; color:#2d3748;">{value_str}</div>
        <div style="font-size:11px; color:#718096;">{sub_label}</div>
    </div>"""


def main():
    st.title("Financial Highlights")
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

    # --- Todo Memo ---
    with st.expander(f"Todo / Memo — {selected}", expanded=False):
        saved_todo = db.get_todo(selected)
        todo_text = st.text_area("", value=saved_todo, height=150, key="todo_memo",
                                  placeholder="Type your notes here... (saved per snapshot)")
        if st.button("Save Memo", key="save_todo"):
            db.save_todo(selected, todo_text)
            st.success("Saved!")

    # --- Fee Income data ---
    fy_totals = db.query("""
        SELECT
            SUM(CASE WHEN period = 'FY26' AND period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy_fcst,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'budget' THEN amount_usd ELSE 0 END) as fy_bud,
            SUM(CASE WHEN period = 'FY25' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy25_act
        FROM fee_income WHERE snapshot = ? AND period IN ('FY25', 'FY26')
    """, (selected,))
    mtd_data = get_mtd_comparison(db, selected)
    ytd_data = get_ytd_comparison(db, selected)
    mtd_act = sum(r["mtd_act"] for r in mtd_data) if mtd_data else 0
    mtd_bud = sum(r["mtd_bud"] for r in mtd_data) if mtd_data else 0
    ytd_act = sum(r["ytd_act"] for r in ytd_data) if ytd_data else 0
    ytd_bud = sum(r["ytd_bud"] for r in ytd_data) if ytd_data else 0
    fy_fcst = fy_totals[0]["fy_fcst"] or 0 if fy_totals else 0
    fy_bud = fy_totals[0]["fy_bud"] or 0 if fy_totals else 0
    fy25_act = fy_totals[0]["fy25_act"] or 0 if fy_totals else 0

    # --- Load MM Report data for P&L/CFS highlights ---
    mm_json = DATA_DIR / f"mm_report_{snapshot_short}.json"
    pl_data = {}
    cfs_data = {}
    if mm_json.exists():
        with open(mm_json, "r", encoding="utf-8") as f:
            mm = json.load(f)
        pl_raw = mm.get("output_pl", {})
        # Convert to int keys
        for row_str, rd in pl_raw.items():
            try:
                pl_data[int(row_str)] = rd
            except ValueError:
                pass
        cfs_data = mm.get("output_cfs", {})

    def get_pl(row, col):
        """Get P&L value: row=excel row, col=1-based column as string."""
        return pl_data.get(row, {}).get(str(col))

    def get_cfs(row, col):
        return cfs_data.get(str(row), {}).get(str(col))

    # ===== HELPER: metric_row (3-card: Fcst / Budget or Comp / Variance) =====
    def metric_row(actual, actual_label, budget, budget_label):
        var = actual - budget
        var_pct = (var / abs(budget) * 100) if budget != 0 else 0
        var_color = "#38a169" if var >= 0 else "#c53030"
        sign = "+" if var >= 0 else ""
        st.markdown(f"""
        <div style="display:flex; gap:12px; margin-bottom:8px;">
            <div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid #4a5568;">
                <div style="font-size:12px; color:#718096; text-transform:uppercase;">{actual_label}</div>
                <div style="font-size:22px; font-weight:bold; color:#2d3748;">{format_millions_colored(actual)}M</div>
            </div>
            <div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid #4a5568;">
                <div style="font-size:12px; color:#718096; text-transform:uppercase;">{budget_label}</div>
                <div style="font-size:22px; font-weight:bold; color:#2d3748;">{format_millions_colored(budget)}M</div>
            </div>
            <div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid {var_color};">
                <div style="font-size:12px; color:#718096; text-transform:uppercase;">Variance</div>
                <div style="font-size:22px; font-weight:bold; color:{var_color};">{sign}{format_millions(var)}M ({sign}{var_pct:.1f}%)</div>
            </div>
        </div>""", unsafe_allow_html=True)

    def pl_metric_row(label, pl_row):
        """Render 2x2 metric grid for a P&L line item using Output PL cols."""
        rd = pl_data.get(pl_row, {})
        # FY26 Fcst vs Bud: cols 26=Fcst, 27=Bud
        fy26_fcst = rd.get("26", 0) or 0
        fy26_bud = rd.get("27", 0) or 0
        # FY26 Fcst vs FY25: cols 30=Fcst, 31=FY25
        fy25_act = rd.get("31", 0) or 0
        # MTD: cols 4=Act, 5=Bud
        mtd_a = rd.get("4", 0) or 0
        mtd_b = rd.get("5", 0) or 0
        # YTD: cols 8=Act, 9=Bud
        ytd_a = rd.get("8", 0) or 0
        ytd_b = rd.get("9", 0) or 0
        # Convert to same scale (already in millions)
        st.subheader(label)
        r1l, r1r = st.columns(2)
        with r1l:
            metric_row(fy26_fcst * 1e6, fcst_label, fy26_bud * 1e6, "FY26 Budget")
        with r1r:
            metric_row(mtd_a * 1e6, f"MTD {month_name} Actual", mtd_b * 1e6, f"MTD {month_name} Budget")
        r2l, r2r = st.columns(2)
        with r2l:
            metric_row(ytd_a * 1e6, f"YTD Jan-{month_name} Actual", ytd_b * 1e6, f"YTD Jan-{month_name} Budget")
        with r2r:
            metric_row(fy26_fcst * 1e6, fcst_label, fy25_act * 1e6, "FY25 Actual")

    # ===== 1. WATCH LIST (first) =====
    st.header(f"Watch List {fcst_label}")

    watch_items = db.get_watch_list()
    pnl_items = [w for w in watch_items if w.get("category") == "P&L"]
    cf_items = [w for w in watch_items if w.get("category") == "CF"]

    watch_items = db.get_watch_list()
    pnl_items = [w for w in watch_items if w.get("category") == "P&L"]
    cf_items = [w for w in watch_items if w.get("category") == "CF"]

    def render_watch_html_v2(title, items):
        if not items:
            return
        wh = f"""<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Calibri,sans-serif; margin-bottom:16px;">
        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">{title}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Fund/Project</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">Impact($mil)</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Lost/Delay</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Comment</th>
        </tr></thead><tbody>"""
        for i, w in enumerate(items):
            bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
            impact = w.get("impact_mil")
            impact_str = f"{impact:.1f}" if impact is not None else ""
            wh += f"""<tr style="background:{bg};">
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("pnl_item", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("fund_project", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{impact_str}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("lost_delay", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("comment", "")}</td>
            </tr>"""
        for _ in range(max(0, 4 - len(items))):
            wh += f"""<tr><td style="padding:6px 12px; border:1px solid #cbd5e0;">&nbsp;</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td><td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td><td style="padding:6px 12px; border:1px solid #cbd5e0;"></td></tr>"""
        total_impact = sum(w.get("impact_mil", 0) or 0 for w in items)
        total_str = f"{total_impact:.1f}" if total_impact else ""
        wh += f"""<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <td style="padding:6px 12px; border:1px solid #cbd5e0;" colspan="2">Grand Total</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{total_str}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td><td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
        </tr>"""
        wh += "</tbody></table>"
        st.markdown(wh, unsafe_allow_html=True)

    pnl_display = [{"pnl_item": w.get("pnl_item",""), "fund_project": w["fund_project"],
                     "impact_mil": w.get("impact_mil"), "lost_delay": w.get("lost_delay",""),
                     "comment": w.get("comment","")} for w in pnl_items]
    cf_display = [{"pnl_item": w.get("pnl_item",""), "fund_project": w["fund_project"],
                    "impact_mil": w.get("impact_mil"), "lost_delay": w.get("lost_delay",""),
                    "comment": w.get("comment","")} for w in cf_items]

    render_watch_html_v2("P&L", pnl_display)
    render_watch_html_v2("CF", cf_display)

    all_watch = pnl_items + cf_items
    if all_watch:
        watch_exp = []
        for w in all_watch:
            impact_usd = (w.get("impact_mil") or 0) * 1_000_000 if w.get("impact_mil") is not None else None
            watch_exp.append({
                "Category": w.get("category", ""),
                "P&L Item": w.get("pnl_item", ""),
                "Fund/Project": w.get("fund_project", ""),
                "Impact (USD)": impact_usd,
                "Lost/Delay": w.get("lost_delay", ""),
                "Comment": w.get("comment", ""),
            })
        export_button(pd.DataFrame(watch_exp), "watch_list.xlsx", key="export_watch_list")

    if not pnl_items and not cf_items:
        st.info("No watch list items. Use the editor below to add items.")

    watch_note_key = f"{selected}__watch_note"
    saved_watch_note = db.get_todo(watch_note_key)

    # Display Watch List Note as table (if content exists)
    if saved_watch_note and saved_watch_note.strip():
        note_lines = [l.strip() for l in saved_watch_note.strip().split("\n") if l.strip()]
        if note_lines:
            nh = f"""<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Calibri,sans-serif; margin-top:8px;">
            <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
                <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Watch List Note</th>
            </tr></thead><tbody>"""
            for i, line in enumerate(note_lines):
                bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
                nh += f'<tr style="background:{bg};"><td style="padding:6px 12px; border:1px solid #cbd5e0;">{line}</td></tr>'
            nh += "</tbody></table>"
            st.markdown(nh, unsafe_allow_html=True)

    with st.expander("Edit Watch List Note"):
        watch_note = st.text_area("", value=saved_watch_note, height=100,
                                   key="watch_note", placeholder="한 줄에 하나씩 입력하세요 (각 줄이 테이블 행이 됩니다)")
        if st.button("Save Note", key="save_watch_note"):
            db.save_todo(watch_note_key, watch_note)
            st.success("Saved!")
            st.rerun()

    with st.expander("Edit Watch List"):
        if watch_items:
            edit_data = [{"category": w["category"], "pnl_item": w.get("pnl_item",""),
                          "fund_project": w["fund_project"], "impact_mil": w.get("impact_mil"),
                          "lost_delay": w.get("lost_delay",""), "comment": w.get("comment","")} for w in watch_items]
        else:
            edit_data = [{"category":"P&L","pnl_item":"","fund_project":"","impact_mil":None,"lost_delay":"","comment":""}]
        edited_df = st.data_editor(
            pd.DataFrame(edit_data), num_rows="dynamic",
            column_config={
                "category": st.column_config.SelectboxColumn("P&L/CF", options=["P&L","CF"], required=True),
                "pnl_item": st.column_config.TextColumn("P&L Line Item"),
                "fund_project": st.column_config.TextColumn("Fund/Project", required=True),
                "impact_mil": st.column_config.NumberColumn("Impact($mil)"),
                "lost_delay": st.column_config.SelectboxColumn("Lost/Delay", options=["Lost","Delay","Lost/Delay",""]),
                "comment": st.column_config.TextColumn("Comment"),
            }, use_container_width=True, hide_index=True, key="watch_list_editor",
        )
        if st.button("Save Watch List"):
            rows_to_save = edited_df.dropna(subset=["fund_project"])
            rows_to_save = rows_to_save[rows_to_save["fund_project"].str.strip() != ""]
            db.update_watch_list(rows_to_save.to_dict("records"))
            st.success(f"Saved {len(rows_to_save)} watch list item(s).")
            st.rerun()

    # ===== 2. P&L HIGHLIGHTS =====
    if pl_data:
        st.markdown("---")
        st.header("P&L Highlights")

        pl_highlight_items = [
            ("Fee Income", 15),
            ("SG&A Expenses", 30),
            ("Dividend Income", 23),
            ("Share of Profit/Loss from Fund/JV", 24),
        ]
        first_item = True
        for hl_label, hl_row in pl_highlight_items:
            rd = pl_data.get(hl_row, {})
            fy26_fcst_v = rd.get("26", 0) or 0
            fy26_bud_v = rd.get("27", 0) or 0
            mtd_v = rd.get("4", 0) or 0
            ytd_v = rd.get("8", 0) or 0
            if all(abs(v) < 0.005 for v in [fy26_fcst_v, fy26_bud_v, mtd_v, ytd_v]):
                continue
            if not first_item:
                st.markdown("---")
            first_item = False
            pl_metric_row(hl_label, hl_row)

    # ===== 3. CAPITAL CALL & CASH RECYCLING =====
    cfs_bd = []
    mm_json2 = DATA_DIR / f"mm_report_{snapshot_short}.json"
    if mm_json2.exists():
        with open(mm_json2, "r", encoding="utf-8") as f:
            mm_full = json.load(f)
        cfs_bd = mm_full.get("cfs_breakdown", [])

    if cfs_bd:
        TH = "padding:5px 6px; border:1px solid #cbd5e0;"
        TD = "padding:4px 6px; border:1px solid #cbd5e0;"
        MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

        def fc_k(v, white=False):
            if v is None or v == 0: return "-"
            val = v / 1000
            if abs(val) < 0.05: return "-"
            if white:
                if val < 0: return f"({abs(val):.1f})"
                return f"{val:.1f}"
            if val < 0: return f'<span style="color:#c53030;">({abs(val):.1f})</span>'
            return f"{val:.1f}"

        def render_hq_detail(title, total_row, comment_key):
            st.markdown("---")
            st.subheader(title)
            total_entry = None
            total_idx = None
            for idx, entry in enumerate(cfs_bd):
                if entry["row"] == total_row:
                    total_entry = entry
                    total_idx = idx
                    break
            if total_entry is None:
                return

            projects = []
            for i in range(total_idx - 1, -1, -1):
                e = cfs_bd[i]
                g = e.get("g", "")
                if g == "Total" and e["row"] != total_row:
                    break
                if g and g != "Total":
                    h = e.get("h", "")
                    if h.startswith("[") and h.endswith("]"):
                        continue
                    vals = e.get("v", {})
                    monthly = [vals.get(str(c), 0) for c in range(22, 34)]
                    fy26 = sum(monthly)
                    if fy26 == 0:
                        continue
                    first_idx = 99
                    for mi, mv in enumerate(monthly):
                        if mv != 0:
                            first_idx = mi
                            break
                    projects.append({"platform": g, "project": h,
                                     "monthly": monthly, "fy26": fy26, "first_idx": first_idx})

            projects.sort(key=lambda x: x["first_idx"])

            # Load saved comments
            saved_comments = db.get_drivers("hq_cf", comment_key)

            html = f"""<table style="border-collapse:collapse; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
            <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold; text-align:center;">
                <th style="{TH} text-align:left;">Platform</th>
                <th style="{TH} text-align:left;">Project</th>"""
            for m in MONTHS:
                html += f'<th style="{TH}">{m}</th>'
            html += f'<th style="{TH} background:#2d3748;">FY26</th></tr></thead><tbody>'

            for i, p in enumerate(projects):
                bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
                html += f'<tr style="background:{bg};"><td style="{TD}">{p["platform"]}</td>'
                html += f'<td style="{TD}">{p["project"]}</td>'
                for v in p["monthly"]:
                    html += f'<td style="{TD} text-align:right;">{fc_k(v)}</td>'
                html += f'<td style="{TD} text-align:right; font-weight:bold;">{fc_k(p["fy26"])}</td></tr>'

            tv = total_entry.get("v", {})
            t_monthly = [tv.get(str(c), 0) for c in range(22, 34)]
            html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">'
            html += f'<td style="{TD}" colspan="2">Total</td>'
            for v in t_monthly:
                html += f'<td style="{TD} text-align:right;">{fc_k(v, white=True)}</td>'
            html += f'<td style="{TD} text-align:right;">{fc_k(sum(t_monthly), white=True)}</td></tr>'
            html += "</tbody></table>"
            st.markdown(html, unsafe_allow_html=True)
            st.caption("Unit: USD millions")

            # Export to Excel (raw USD — source in thousands, ×1000)
            if projects:
                exp_rows = []
                for p in projects:
                    row_data = {"Platform": p["platform"], "Project": p["project"]}
                    for mi, m in enumerate(MONTHS):
                        row_data[m] = round((p["monthly"][mi] or 0) * 1000, 2)
                    row_data["FY26 Total"] = round((p["fy26"] or 0) * 1000, 2)
                    exp_rows.append(row_data)
                export_button(pd.DataFrame(exp_rows), f"{title.replace(' ', '_')}.xlsx", key=f"export_hq_{comment_key}")

            # Display saved comments as separate table
            has_comments = any(saved_comments.get(f"{p['platform']}_{p['project']}") for p in projects)
            if has_comments:
                ch = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif; margin-top:8px;">
                <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
                    <th style="{TD} text-align:left; width:15%;">Platform</th>
                    <th style="{TD} text-align:left; width:20%;">Project</th>
                    <th style="{TD} text-align:left;">Comment</th>
                </tr></thead><tbody>"""
                for p in projects:
                    pk = f"{p['platform']}_{p['project']}"
                    ct = saved_comments.get(pk, "")
                    if ct:
                        ch += f'<tr><td style="{TD}">{p["platform"]}</td><td style="{TD} font-weight:bold;">{p["project"]}</td><td style="{TD}">{ct}</td></tr>'
                ch += "</tbody></table>"
                st.markdown(ch, unsafe_allow_html=True)

            # Edit comments
            with st.expander(f"Edit Comments — {title}"):
                updated = {}
                for p in projects:
                    proj_key = f"{p['platform']}_{p['project']}"
                    updated[proj_key] = st.text_area(
                        f"{p['platform']} — {p['project']}",
                        value=saved_comments.get(proj_key, ""),
                        height=68, key=f"hq_{comment_key}_{proj_key}")
                if st.button("Save Comments", key=f"save_hq_{comment_key}"):
                    db.save_drivers("hq_cf", comment_key, updated)
                    st.success("Saved!")
                    st.rerun()

        render_hq_detail("Cash Recycling to ESR HQ", 183, f"cash_recycling_{snapshot_short}")
        render_hq_detail("Capital Call from ESR HQ", 153, f"capital_call_{snapshot_short}")


main()

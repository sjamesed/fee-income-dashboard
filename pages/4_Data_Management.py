"""Page 4: Data Management — upload, view, and manage snapshot data."""
import streamlit as st
import pandas as pd
import tempfile
import os
from src.db import FeeIncomeDB
from src.parser import parse_excel_file

@st.cache_resource
def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def main():
    st.title("Data Management")
    db = get_db()

    st.header("Upload Excel File")
    uploaded_file = st.file_uploader("Drop your Revenue Excel file here", type=["xlsx"],
        help="Expected format: Revenue_26 Bud and 25 Fcst (N+M).xlsx")

    if uploaded_file is not None:
        if st.button("Parse and Load", type="primary"):
            with st.spinner("Parsing Excel file..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", prefix="revenue_") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                try:
                    rows, snapshot = parse_excel_file(tmp_path)
                    db.insert_snapshot(snapshot, rows)
                    st.cache_data.clear()
                    st.success(f"Loaded **{len(rows):,}** data points for snapshot **{snapshot}**")
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    os.unlink(tmp_path)

    st.header("Snapshots")
    snapshots = db.list_snapshots()
    if not snapshots:
        st.info("No snapshots loaded yet.")
    else:
        for snap in snapshots:
            count = db.query("SELECT COUNT(*) as cnt FROM fee_income WHERE snapshot = ?", (snap,))[0]["cnt"]
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.write(f"**{snap}**")
            col2.write(f"{count:,} rows")
            if col3.button("Delete", key=f"del_{snap}"):
                db.delete_snapshot(snap)
                st.cache_data.clear()
                st.rerun()

    st.header("Raw Data Viewer")
    if snapshots:
        selected_snap = st.selectbox("Snapshot", snapshots)
        limit = st.number_input("Row limit", min_value=10, max_value=10000, value=100)
        raw = db.query("SELECT * FROM fee_income WHERE snapshot = ? LIMIT ?", (selected_snap, limit))
        if raw:
            st.dataframe(pd.DataFrame(raw), use_container_width=True)

main()

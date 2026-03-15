"""Page 4: Data Management — upload, view, and manage snapshot data."""
import streamlit as st
import pandas as pd
import tempfile
import os
from src.db import FeeIncomeDB
from src.parser import parse_excel_file


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def main():
    st.title("Data Management")
    db = get_db()

    # --- Instructions ---
    with st.expander("How to Upload / Update Data", expanded=False):
        st.markdown("""
        **File naming rule:**
        ```
        Revenue_26 Bud and 25 Fcst (N+M).xlsx
        ```
        - `N` = number of actual months, `M` = forecast months (N+M = 12)
        - Example: `Revenue_26 Bud and 25 Fcst (3+9).xlsx` → Mar close

        **Snapshot name** is auto-extracted from the filename:
        - `(2+10)` + `Revenue_26` → **FY26 2+10**

        **Upload rules:**
        - The file must contain a sheet named **`Summary_new template (작성탭)`**
        - Row 20 = headers, Row 21+ = data

        **Re-uploading the same snapshot:**
        - If you upload a file with the same `(N+M)` pattern, the **data is replaced** but **memos, notes, and watch list are preserved**
        - No need to delete first — just re-upload

        **Deleting a snapshot:**
        - Removes all data **and** associated memos/notes for that snapshot
        - Watch list is shared across all snapshots and is not affected
        """)

    # --- Upload ---
    st.header("Upload Excel File")
    uploaded_file = st.file_uploader("Drop your Revenue Excel file here", type=["xlsx"],
        help="Expected: Revenue_26 Bud and 25 Fcst (N+M).xlsx")

    if uploaded_file is not None:
        st.caption(f"Selected file: **{uploaded_file.name}**")
        if st.button("Parse and Load", type="primary"):
            with st.spinner("Parsing Excel file..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", prefix="revenue_") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                try:
                    rows, snapshot = parse_excel_file(tmp_path)
                    db.insert_snapshot(snapshot, rows)
                    db.save_snapshot_meta(snapshot, uploaded_file.name)
                    st.cache_data.clear()
                    st.success(f"Loaded **{len(rows):,}** data points for snapshot **{snapshot}**")
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    os.unlink(tmp_path)

    # --- Snapshots ---
    st.header("Snapshots")
    snapshots = db.list_snapshots()
    if not snapshots:
        st.info("No snapshots loaded yet.")
    else:
        for snap in snapshots:
            count = db.query("SELECT COUNT(*) as cnt FROM fee_income WHERE snapshot = ?", (snap,))[0]["cnt"]
            meta = db.get_snapshot_meta(snap)
            filename = meta["filename"] if meta else "-"
            uploaded_at = meta["uploaded_at"] if meta else "-"

            col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
            col1.write(f"**{snap}**")
            col2.write(f"{count:,} rows | `{filename}` | {uploaded_at}")
            if col3.button("Rename", key=f"ren_{snap}"):
                st.session_state[f"renaming_{snap}"] = True
            if col4.button("Delete", key=f"del_{snap}"):
                db.delete_snapshot(snap)
                st.cache_data.clear()
                st.rerun()
            # Rename input row
            if st.session_state.get(f"renaming_{snap}"):
                rc1, rc2 = st.columns([3, 1])
                new_name = rc1.text_input("New name:", value=snap, key=f"rename_input_{snap}")
                if rc2.button("Save", key=f"rename_save_{snap}"):
                    if new_name and new_name != snap:
                        db.rename_snapshot(snap, new_name)
                        st.session_state[f"renaming_{snap}"] = False
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.session_state[f"renaming_{snap}"] = False
                        st.rerun()

    # --- Raw Data Viewer ---
    st.header("Raw Data Viewer")
    if snapshots:
        selected_snap = st.selectbox("Snapshot", snapshots)
        limit = st.number_input("Row limit", min_value=10, max_value=10000, value=100)
        raw = db.query("SELECT * FROM fee_income WHERE snapshot = ? LIMIT ?", (selected_snap, limit))
        if raw:
            st.dataframe(pd.DataFrame(raw), use_container_width=True)

main()

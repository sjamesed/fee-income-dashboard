"""Fee Income Dashboard — main entry point."""
import streamlit as st
from src.db import FeeIncomeDB

st.set_page_config(page_title="Fee Income Dashboard", page_icon="📊", layout="wide")

@st.cache_resource
def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def main():
    st.title("Fee Income Dashboard")
    st.markdown("Navigate using the sidebar pages.")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded yet. Go to **Data Management** to upload an Excel file.")
    else:
        latest = db.get_latest_snapshot()
        st.info(f"Latest snapshot: **{latest}** | Total snapshots: **{len(snapshots)}**")

if __name__ == "__main__":
    main()

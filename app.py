"""Fee Income Dashboard — main entry point."""
import streamlit as st
from src.db import FeeIncomeDB

st.set_page_config(page_title="Fee Income Dashboard", page_icon="📊", layout="wide")

# Global CSS to match table color tone
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #2d3748; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stSelectbox label { color: #e2e8f0 !important; }
    h1, h2, h3 { color: #2d3748 !important; }
    [data-testid="stMetricLabel"] { color: #718096 !important; }
    [data-testid="stMetricValue"] { color: #2d3748 !important; }
    .stButton > button {
        background-color: #4a5568;
        color: white;
        border: none;
    }
    .stButton > button:hover {
        background-color: #2d3748;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

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
        st.markdown(f"""
        <div style="background:#f7fafc; border-left:4px solid #4a5568; padding:12px 16px; border-radius:4px;">
            <span style="color:#4a5568; font-weight:bold;">Latest snapshot: {latest}</span>
            &nbsp;|&nbsp; Total snapshots: {len(snapshots)}
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

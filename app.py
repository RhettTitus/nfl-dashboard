import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")
st.title("🏈 NFL Quant EV Dashboard")

DATA_FOLDER = "./data"
os.makedirs(DATA_FOLDER, exist_ok=True)

files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".xlsx")], reverse=True)

if not files:
    st.info("👋 Welcome! Run your Colab script to push the first slate here.")
    st.stop()

# Dropdown to select any slate
selected_file = st.sidebar.selectbox("📅 Select Slate:", files)
file_path = os.path.join(DATA_FOLDER, selected_file)

# --------------------------------------------------------------------------
# GLOBAL FILTER CONTROLS (Position, Team, Search)
# --------------------------------------------------------------------------
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    pos_choice = st.selectbox("🏈 Filter Position:", ["All Positions", "QB", "RB", "WR", "TE"])

with col2:
    action_choice = st.selectbox("⭐ Filter Action:", ["All Actions", "MAX BET", "ANCHOR", "STRONG BET", "BOOSTER", "FLYER"])

with col3:
    search = st.text_input("🔍 Search Player or Team:", "")

# Helper function to format percentages
def format_percentage(val, is_ev=False):
    if pd.isna(val) or val == "-" or not isinstance(val, (int, float)):
        return val
    v = val if abs(val) <= 1.0 else val / 100.0
    return f"{v:+.1%}" if is_ev else f"{v:.1%}"

# Load the Excel file
excel_data = pd.ExcelFile(file_path)
tab_names = [s for s in excel_data.sheet_names if s != "How To Use"]
tabs = st.tabs(tab_names)

for i, sheet_name in enumerate(tab_names):
    with tabs[i]:
        df = pd.read_excel(excel_data, sheet_name=sheet_name)

        if df.empty:
            st.info("No data in this sheet.")
            continue

        # 1. Format Decimals to Percentages
        for col in df.columns:
            if "EV" in col or "Market EV" in col:
                df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=True))
            elif any(w in col for w in ["Prob", "Probability", "Win Prob"]):
                df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=False))

        # 2. Filter by Position (Handles both 'Pos' and 'Position' columns like QB1, RB1)
        pos_col = next((c for c in ["Pos", "Position"] if c in df.columns), None)
        if pos_col and pos_choice != "All Positions":
            df = df[df[pos_col].astype(str).str.contains(pos_choice, case=False, na=False)]

        # 3. Filter by Action
        if "Action" in df.columns and action_choice != "All Actions":
            df = df[df["Action"].astype(str).str.contains(action_choice, case=False, na=False)]

        # 4. Filter by Text Search
        if search:
            mask = df.astype(str).apply(lambda row: row.str.contains(search, case=False).any(), axis=1)
            df = df[mask]

        # 5. Highlight Action Colors
        def highlight_actions(row):
            val = str(row.get("Action", ""))
            if "MAX" in val: return ["background-color: #e8d7ff"] * len(row)     # Purple
            elif "ANCHOR" in val: return ["background-color: #fff2cc"] * len(row) # Gold
            elif "STRONG" in val: return ["background-color: #d4edda"] * len(row) # Green
            elif "SKIP" in val: return ["background-color: #f8d7da"] * len(row)   # Red
            return [""] * len(row)

        st.dataframe(df.style.apply(highlight_actions, axis=1), use_container_width=True, height=550)

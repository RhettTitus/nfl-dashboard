import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")
st.title("🏈 NFL Quant EV Dashboard")

# Folder inside the repository where Colab sends the files
DATA_FOLDER = "./data"
os.makedirs(DATA_FOLDER, exist_ok=True)

files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".xlsx")], reverse=True)

if not files:
    st.info("👋 Welcome! Run your Colab script to push the first slate here.")
    st.stop()

# Dropdown to select any slate
selected_file = st.sidebar.selectbox("📅 Select Slate:", files)
file_path = os.path.join(DATA_FOLDER, selected_file)

search = st.text_input("🔍 Search Player or Team", "")

# Load the Excel file that Colab sent
excel_data = pd.ExcelFile(file_path)
tab_names = [s for s in excel_data.sheet_names if s != "How To Use"]
tabs = st.tabs(tab_names)

for i, sheet_name in enumerate(tab_names):
    with tabs[i]:
        df = pd.read_excel(excel_data, sheet_name=sheet_name)
        if search:
            mask = df.astype(str).apply(lambda row: row.str.contains(search, case=False).any(), axis=1)
            df = df[mask]

        def highlight_actions(row):
            val = str(row.get("Action", ""))
            if "MAX" in val: return ["background-color: #e8d7ff"] * len(row)
            elif "ANCHOR" in val: return ["background-color: #fff2cc"] * len(row)
            elif "STRONG" in val: return ["background-color: #d4edda"] * len(row)
            return [""] * len(row)

        st.dataframe(df.style.apply(highlight_actions, axis=1), use_container_width=True, height=550)

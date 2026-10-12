import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")

DATA_FOLDER = "./data"
os.makedirs(DATA_FOLDER, exist_ok=True)

files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".xlsx")], reverse=True)

if not files:
    st.info("👋 Welcome! Run your Colab script to push the first slate here.")
    st.stop()

# --------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------------------
st.sidebar.title("🏈 NFL Quant Engine")
selected_file = st.sidebar.selectbox("📅 Select Slate:", files)
file_path = os.path.join(DATA_FOLDER, selected_file)

app_mode = st.sidebar.radio("📱 Screen:", ["📋 Master EV Tables", "📊 Player Prop Deep Dive"])

excel_data = pd.ExcelFile(file_path)

def format_percentage(val, is_ev=False):
    if pd.isna(val) or val == "-" or not isinstance(val, (int, float)):
        return val
    v = val if abs(val) <= 1.0 else val / 100.0
    return f"{v:+.1%}" if is_ev else f"{v:.1%}"

# ==============================================================================
# SCREEN 1: MASTER EV TABLES
# ==============================================================================
if app_mode == "📋 Master EV Tables":
    st.title("📋 Master EV Tables & Projections")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        pos_choice = st.selectbox("🏈 Position:", ["All Positions", "QB", "RB", "WR", "TE"])
    with col2:
        action_choice = st.selectbox("⭐ Action:", ["All Actions", "MAX BET", "ANCHOR", "STRONG BET", "BOOSTER", "FLYER"])
    with col3:
        search = st.text_input("🔍 Search Player or Team:", "")

    tab_names = [s for s in excel_data.sheet_names if s != "How To Use"]
    tabs = st.tabs(tab_names)

    for i, sheet_name in enumerate(tab_names):
        with tabs[i]:
            df = pd.read_excel(excel_data, sheet_name=sheet_name)
            if df.empty:
                st.info("No data in this sheet.")
                continue

            for col in df.columns:
                if "EV" in col or "Market EV" in col:
                    df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=True))
                elif any(w in col for w in ["Prob", "Probability", "Win Prob"]):
                    df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=False))

            pos_col = next((c for c in ["Pos", "Position"] if c in df.columns), None)
            if pos_col and pos_choice != "All Positions":
                df = df[df[pos_col].astype(str).str.contains(pos_choice, case=False, na=False)]

            if "Action" in df.columns and action_choice != "All Actions":
                df = df[df["Action"].astype(str).str.contains(action_choice, case=False, na=False)]

            if search:
                mask = df.astype(str).apply(lambda row: row.str.contains(search, case=False).any(), axis=1)
                df = df[mask]

            def highlight_actions(row):
                val = str(row.get("Action", ""))
                if "MAX" in val: return ["background-color: #e8d7ff"] * len(row)
                elif "ANCHOR" in val: return ["background-color: #fff2cc"] * len(row)
                elif "STRONG" in val: return ["background-color: #d4edda"] * len(row)
                elif "SKIP" in val: return ["background-color: #f8d7da"] * len(row)
                return [""] * len(row)

            st.dataframe(df.style.apply(highlight_actions, axis=1), use_container_width=True, height=550)

# ==============================================================================
# SCREEN 2: DYNAMIC PLAYER PROP DEEP DIVE & CHARTS
# ==============================================================================
elif app_mode == "📊 Player Prop Deep Dive":
    st.title("📊 Player Prop Analytics & Visuals")

    # Dynamically find ALL sheets that have a 'Player' column
    player_dfs = []
    for sheet in excel_data.sheet_names:
        if sheet == "How To Use":
            continue
        sub_df = pd.read_excel(excel_data, sheet_name=sheet)
        # Check if Player column exists
        p_col = next((c for c in sub_df.columns if c.strip().lower() == "player"), None)
        if p_col and not sub_df.empty:
            sub_df["Source Sheet"] = sheet
            sub_df["Player"] = sub_df[p_col]  # Standardize name
            player_dfs.append(sub_df)

    if not player_dfs:
        st.warning(f"Could not find any sheets containing player data in: {selected_file}")
        st.info(f"Available sheets found: {excel_data.sheet_names}")
        st.stop()

    # Collect all unique player names across every sheet
    all_players = set()
    for df in player_dfs:
        all_players.update(df["Player"].dropna().unique())
    player_list = sorted(list(all_players))

    selected_player = st.selectbox("👤 Select Player:", player_list)

    st.subheader(f"Data & Projections for: {selected_player}")

    found_any = False
    for df in player_dfs:
        p_matches = df[df["Player"] == selected_player]
        if p_matches.empty:
            continue

        sheet_src = p_matches["Source Sheet"].iloc[0]

        for _, row in p_matches.iterrows():
            found_any = True
            prop_name = row.get("Prop") or row.get("Milestone (Alt Line)")

            # CASE A: It is a Betting Line (has Line and Projection)
            if pd.notna(row.get("Line")) and pd.notna(row.get("Projection")):
                line_val = float(row["Line"])
                proj_val = float(row["Projection"])
                side = row.get("Side", "Over")
                book = row.get("Book", sheet_src)
                ev_val = row.get("EV", "-")
                win_prob = row.get("Model Win Prob", "-")

                with st.expander(f"📌 {prop_name} ({book}) — Line: {line_val} | Pick: {side}", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Vegas Line", f"{line_val}")
                    c2.metric("Model Projection", f"{proj_val}")
                    c3.metric("Model Win Prob", format_percentage(win_prob))
                    c4.metric("EV Edge", format_percentage(ev_val, is_ev=True))

                    # Built-in comparison bar chart
                    chart_df = pd.DataFrame({
                        "Comparison": ["Vegas Line", "Model Projection"],
                        "Value": [line_val, proj_val]
                    }).set_index("Comparison")
                    st.bar_chart(chart_df, color="#28a745")

            # CASE B: Raw Player Projections Sheet (Passing, Rushing, Receiving)
            else:
                pred_cols = [c for c in row.index if "Predicted" in str(c) and pd.notna(row[c]) and isinstance(row[c], (int, float))]
                if pred_cols:
                    with st.expander(f"📋 Model Projections ({sheet_src})", expanded=True):
                        chart_data = {c.replace("Predicted ", ""): [float(row[c])] for c in pred_cols}
                        chart_df = pd.DataFrame(chart_data).T
                        chart_df.columns = ["Projected Value"]
                        st.bar_chart(chart_df, color="#007bff")

    if not found_any:
        st.info("No data entries found for this player.")

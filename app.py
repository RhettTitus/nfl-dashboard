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

app_mode = st.sidebar.radio("📱 Screen:", ["📋 Master EV Tables", "📊 Team & Player Prop Visualizer"])

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
# SCREEN 2: TEAM & POSITION VISUALIZER (STACKED CHARTS)
# ==============================================================================
elif app_mode == "📊 Team & Player Prop Visualizer":
    st.title("📊 Team & Position Prop Analytics")

    # Gather all player records across every sheet
    all_player_rows = []
    for sheet in excel_data.sheet_names:
        if sheet == "How To Use":
            continue
        sub_df = pd.read_excel(excel_data, sheet_name=sheet)
        p_col = next((c for c in sub_df.columns if c.strip().lower() == "player"), None)
        if p_col and not sub_df.empty:
            sub_df["Source Sheet"] = sheet
            sub_df["Player"] = sub_df[p_col]
            all_player_rows.append(sub_df)

    if not all_player_rows:
        st.warning("No player data found in this workbook.")
        st.stop()

    combined_df = pd.concat(all_player_rows, ignore_index=True)

    # Clean Team & Position columns
    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)

    # 1. TEAM & POSITION FILTERS
    f_col1, f_col2, f_col3 = st.columns([1, 1, 1])

    with f_col1:
        if team_col:
            team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist())
            selected_team = st.selectbox("🏈 Select Team:", team_list)
        else:
            selected_team = "All Teams"

    with f_col2:
        selected_pos = st.selectbox("🎯 Select Position:", ["All Positions", "QB", "RB", "WR", "TE"])

    with f_col3:
        market_type = st.selectbox("📊 Prop Type:", ["All Props", "Yards Only", "Counts/Volume Only"])

    # Filter data by Team and Position
    filtered_df = combined_df.copy()
    if team_col and selected_team != "All Teams":
        filtered_df = filtered_df[filtered_df[team_col].astype(str) == selected_team]

    if pos_col and selected_pos != "All Positions":
        filtered_df = filtered_df[filtered_df[pos_col].astype(str).str.contains(selected_pos, case=False, na=False)]

    # Extract all betting lines
    prop_rows = []
    for _, r in filtered_df.iterrows():
        p_name = r.get("Prop") or r.get("Milestone (Alt Line)")
        line = r.get("Line")
        proj = r.get("Projection")

        if pd.notna(p_name) and pd.notna(line) and pd.notna(proj):
            try:
                line_f = float(line)
                proj_f = float(proj)
                player_name = str(r["Player"])
                team_name = str(r.get(team_col, ""))
                book = str(r.get("Book", r.get("Source Sheet", "")))
                side = str(r.get("Side", "Over"))
                ev = r.get("EV", "-")
                prob = r.get("Model Win Prob", "-")
                act = str(r.get("Action", "-"))

                prop_rows.append({
                    "Player": player_name,
                    "Team": team_name,
                    "Prop Label": f"{player_name} — {p_name} ({book})",
                    "Prop Name": str(p_name),
                    "Vegas Line": line_f,
                    "Model Projection": proj_f,
                    "Pick": side,
                    "Margin": round(proj_f - line_f, 1),
                    "EV": format_percentage(ev, is_ev=True),
                    "Win Prob": format_percentage(prob),
                    "Action": act
                })
            except:
                pass

    if not prop_rows:
        st.info("No betting props found matching this Team & Position filter.")
        st.stop()

    props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Prop Label"])

    # Filter Market Type
    if market_type == "Yards Only":
        props_df = props_df[props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]
    elif market_type == "Counts/Volume Only":
        props_df = props_df[~props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]

    if props_df.empty:
        st.info("No props matching the selected Prop Type.")
        st.stop()

    # --------------------------------------------------------------------------
    # 2. ALL-PLAYER MACRO COMPARISON CHART
    # --------------------------------------------------------------------------
    st.markdown(f"### 📈 All Players Comparison: {selected_team} ({selected_pos})")
    st.caption("Grey = Vegas Line | Green = Model Projection")

    macro_chart_df = props_df.set_index("Prop Label")[["Vegas Line", "Model Projection"]]
    st.bar_chart(macro_chart_df, stack=False, color=["#4A5568", "#28A745"], height=400)

    st.divider()

    # --------------------------------------------------------------------------
    # 3. STACKED INDIVIDUAL PLAYER BREAKDOWNS (DOWN THE PAGE)
    # --------------------------------------------------------------------------
    st.markdown("### 🏆 Stacked Player Breakdowns")

    unique_players = sorted(props_df["Player"].unique())

    for player in unique_players:
        player_props = props_df[props_df["Player"] == player]
        team_tag = player_props["Team"].iloc[0] if not player_props.empty else ""

        with st.container(border=True):
            st.markdown(f"## 👤 {player} ({team_tag})")

            # Scorecards in rows of 3
            cols_per_row = 3
            for i in range(0, len(player_props), cols_per_row):
                batch = player_props.iloc[i:i + cols_per_row]
                cols = st.columns(len(batch))
                for c_idx, (_, r) in enumerate(batch.iterrows()):
                    with cols[c_idx]:
                        with st.container(border=True):
                            st.markdown(f"**📌 {r['Prop Name']}**")
                            st.markdown(f"**Pick:** `{r['Pick']}` | **Action:** `{r['Action']}`")
                            
                            m1, m2 = st.columns(2)
                            m1.metric("Vegas Line", f"{r['Vegas Line']}")
                            m2.metric("Model Proj", f"{r['Model Projection']}", delta=f"{r['Margin']:+0.1f}")
                            
                            m3, m4 = st.columns(2)
                            m3.metric("Win Prob", r['Win Prob'])
                            m4.metric("EV Edge", r['EV'])

            # Side-by-side bar chart for this individual player
            st.markdown(f"**{player} — Vegas Line vs. Model Projection:**")
            p_chart = player_props.set_index("Prop Label")[["Vegas Line", "Model Projection"]]
            st.bar_chart(p_chart, stack=False, color=["#4A5568", "#28A745"], height=250)

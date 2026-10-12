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
# SCREEN 2: ALL PROPS IN CONSOLIDATED CHARTS
# ==============================================================================
elif app_mode == "📊 Player Prop Deep Dive":
    st.title("📊 Player Prop Analytics & Visuals")

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
    player_list = sorted(combined_df["Player"].dropna().unique())

    selected_player = st.selectbox("👤 Select Player:", player_list)
    p_data = combined_df[combined_df["Player"] == selected_player]

    st.subheader(f"All Props & Projections for: {selected_player}")

    # Extract all betting lines for this player
    prop_rows = []
    for _, r in p_data.iterrows():
        p_name = r.get("Prop") or r.get("Milestone (Alt Line)")
        line = r.get("Line")
        proj = r.get("Projection")

        if pd.notna(p_name) and pd.notna(line) and pd.notna(proj):
            try:
                line_f = float(line)
                proj_f = float(proj)
                book = str(r.get("Book", r.get("Source Sheet", "")))
                side = str(r.get("Side", "Over"))
                ev = r.get("EV", "-")
                prob = r.get("Model Win Prob", "-")
                act = str(r.get("Action", "-"))

                label = f"{p_name} ({book})"
                prop_rows.append({
                    "Prop Label": label,
                    "Prop Name": str(p_name),
                    "Vegas Line": line_f,
                    "Model Projection": proj_f,
                    "Pick": side,
                    "Edge / Margin": round(proj_f - line_f, 1),
                    "EV": format_percentage(ev, is_ev=True),
                    "Win Prob": format_percentage(prob),
                    "Action": act
                })
            except:
                pass

    if prop_rows:
        props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Prop Label"])

        # Split into Yardage vs Counts for clean chart scaling
        yards_mask = props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)
        yards_df = props_df[yards_mask]
        counts_df = props_df[~yards_mask]

        # 1. YARDAGE PROPS (PASS / RUSH / REC YDS)
        if not yards_df.empty:
            st.markdown("### 📈 Yardage Props (Line vs. Projection)")
            chart_y = yards_df.set_index("Prop Label")[["Vegas Line", "Model Projection"]]
            st.bar_chart(chart_y)

        # 2. COUNT / VOLUME PROPS (ATTEMPTS / RECEPTIONS / CARRIES)
        if not counts_df.empty:
            st.markdown("### 🎯 Volume & Counts Props (Line vs. Projection)")
            chart_c = counts_df.set_index("Prop Label")[["Vegas Line", "Model Projection"]]
            st.bar_chart(chart_c)

        # 3. SCORECARD SUMMARY TABLE
        st.markdown("### 📋 Prop Scorecard Table")
        table_cols = ["Prop Label", "Pick", "Vegas Line", "Model Projection", "Edge / Margin", "Win Prob", "EV", "Action"]
        st.dataframe(props_df[table_cols], use_container_width=True)

    else:
        # Fallback: Raw projections if no betting lines exist
        raw_preds = {}
        for _, r in p_data.iterrows():
            for c in r.index:
                if "Predicted" in str(c) and pd.notna(r[c]) and isinstance(r[c], (int, float)):
                    raw_preds[str(c).replace("Predicted ", "")] = float(r[c])

        if raw_preds:
            st.markdown("### 📋 Model Projections Overview")
            chart_df = pd.DataFrame(list(raw_preds.items()), columns=["Stat", "Projected Value"]).set_index("Stat")
            st.bar_chart(chart_df)
        else:
            st.info("No active lines or projections found for this player.")

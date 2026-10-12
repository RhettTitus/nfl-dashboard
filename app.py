import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go

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

# Screen Switcher
app_mode = st.sidebar.radio("📱 Screen:", ["📋 Master EV Tables", "📊 Player Prop Deep Dive"])

# Load all data
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
# SCREEN 2: PLAYER PROP DEEP DIVE & CHARTS
# ==============================================================================
elif app_mode == "📊 Player Prop Deep Dive":
    st.title("📊 Player Prop Analytics & Visuals")

    # Combine all prop sheets into one search pool
    all_props = []
    for sheet in ["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"]:
        if sheet in excel_data.sheet_names:
            sub_df = pd.read_excel(excel_data, sheet_name=sheet)
            if not sub_df.empty:
                sub_df["Source"] = sheet
                all_props.append(sub_df)

    if not all_props:
        st.warning("No prop bet data found in this workbook.")
        st.stop()

    combined_df = pd.concat(all_props, ignore_index=True)
    player_list = sorted(combined_df["Player"].dropna().unique())

    selected_player = st.selectbox("👤 Select Player:", player_list)
    player_data = combined_df[combined_df["Player"] == selected_player]

    if player_data.empty:
        st.info("No props available for this player.")
        st.stop()

    st.subheader(f"Props Breakdown for {selected_player}")

    # Display KPI metrics for each prop available for this player
    for idx, row in player_data.iterrows():
        prop_name = row.get("Prop") or row.get("Milestone (Alt Line)") or "Prop"
        line_val = row.get("Line", "-")
        proj_val = row.get("Projection", "-")
        ev_val = row.get("EV", "-")
        win_prob = row.get("Model Win Prob", "-")
        side = row.get("Side", "Over")
        book = row.get("Book", "")

        with st.expander(f"📌 {prop_name} ({book}) — Line: {line_val} | Pick: {side}", expanded=True):
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Vegas Line", f"{line_val}")
            kpi2.metric("Model Projection", f"{proj_val}")
            kpi3.metric("Model Win Prob", format_percentage(win_prob))
            kpi4.metric("EV Edge", format_percentage(ev_val, is_ev=True))

            # Visual Comparison Bar Chart
            if isinstance(line_val, (int, float)) and isinstance(proj_val, (int, float)):
                diff = round(proj_val - line_val, 1)
                bar_color = "#28a745" if diff >= 0 else "#dc3545"

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Vegas Line",
                    x=["Vegas Line"],
                    y=[line_val],
                    marker_color="#6c757d",
                    text=[f"{line_val}"],
                    textposition="auto"
                ))
                fig.add_trace(go.Bar(
                    name="Model Projection",
                    x=["Model Projection"],
                    y=[proj_val],
                    marker_color=bar_color,
                    text=[f"{proj_val} (Margin: {diff:+0.1f})"],
                    textposition="auto"
                ))

                fig.update_layout(
                    title=f"{selected_player} — {prop_name}: Projection vs. Line Margin",
                    yaxis_title="Stat Value",
                    barmode="group",
                    height=350,
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)

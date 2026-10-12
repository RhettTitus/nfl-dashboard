import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import altair as alt

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")

DATA_FOLDER = "./data"
os.makedirs(DATA_FOLDER, exist_ok=True)

# --------------------------------------------------------------------------
# 1. SMART DATE-BASED FILE DETECTOR
# --------------------------------------------------------------------------
def parse_slate_date(filename):
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{2,4})\.xlsx$", filename)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        full_year = 2000 + year if year < 100 else year
        try:
            return datetime(full_year, month, day)
        except:
            return None
    return None

all_raw_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".xlsx")]
dated_files = []

for f in all_raw_files:
    d = parse_slate_date(f)
    if d:
        dated_files.append({"filename": f, "date": d, "label": d.strftime("%m/%d/%y")})

if not dated_files:
    st.info("👋 No dated spreadsheets (e.g. 10-9-26.xlsx) found in `./data`. Push a slate from Colab to begin!")
    st.stop()

# Sort chronologically (newest first)
dated_files.sort(key=lambda x: x["date"], reverse=True)
latest_file = dated_files[0]["filename"]

# --------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------------------
st.sidebar.title("🏈 NFL Quant Engine")
file_names = [x["filename"] for x in dated_files]
selected_file = st.sidebar.selectbox("📅 Select Slate (Defaults to Latest):", file_names, index=0)
file_path = os.path.join(DATA_FOLDER, selected_file)

app_mode = st.sidebar.radio("📱 Screen:", ["📋 Master EV Tables", "📊 Pro Betting Visualizer (Hit Rates & Edge)"])

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
# SCREEN 2: PRO BETTING VISUALIZER (HIT RATES & MARGIN EDGES)
# ==============================================================================
elif app_mode == "📊 Pro Betting Visualizer (Hit Rates & Edge)":
    st.title("📊 Pro Betting Visualizer")

    # Extract all betting records across sheets
    all_player_rows = []
    for sheet in excel_data.sheet_names:
        if sheet == "How To Use":
            continue
        sub_df = pd.read_excel(excel_data, sheet_name=sheet)
        p_col = next((c for c in sub_df.columns if c.strip().lower() == "player"), None)
        if p_col and not sub_df.empty:
            sub_df["Source Sheet"] = sheet
            sub_df["Player"] = sub_df[p_col]
            if "Book" not in sub_df.columns:
                sub_df["Book"] = "DraftKings" if "DK" in sheet else ("FanDuel" if "FD" in sheet else sheet)
            else:
                sub_df["Book"] = sub_df["Book"].fillna(sheet)
            all_player_rows.append(sub_df)

    if not all_player_rows:
        st.warning("No player data found in this workbook.")
        st.stop()

    combined_df = pd.concat(all_player_rows, ignore_index=True)

    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)

    # Filter Controls
    f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1, 1])
    with f_col1:
        team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist()) if team_col else ["All Teams"]
        selected_team = st.selectbox("🏈 Team:", team_list)
    with f_col2:
        selected_pos = st.selectbox("🎯 Position:", ["All Positions", "QB", "RB", "WR", "TE"])
    with f_col3:
        all_books = ["All Sportsbooks"] + sorted(combined_df["Book"].dropna().astype(str).unique().tolist())
        selected_book = st.selectbox("🎰 Sportsbook:", all_books)
    with f_col4:
        market_type = st.selectbox("📊 Prop Type:", ["All Props", "Yards Only", "Counts/Volume Only"])

    filtered_df = combined_df.copy()
    if team_col and selected_team != "All Teams":
        filtered_df = filtered_df[filtered_df[team_col].astype(str) == selected_team]
    if pos_col and selected_pos != "All Positions":
        filtered_df = filtered_df[filtered_df[pos_col].astype(str).str.contains(selected_pos, case=False, na=False)]
    if selected_book != "All Sportsbooks":
        filtered_df = filtered_df[filtered_df["Book"].astype(str) == selected_book]

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
                book = str(r.get("Book", ""))
                side = str(r.get("Side", "Over"))
                ev = r.get("EV", "-")
                prob = r.get("Model Win Prob", "-")
                act = str(r.get("Action", "-"))
                last_5 = str(r.get("Last 5", "-"))

                prop_rows.append({
                    "Player": player_name,
                    "Team": team_name,
                    "Book": book,
                    "Prop Label": f"{p_name} [{book}]",
                    "Prop Name": str(p_name),
                    "Vegas Line": line_f,
                    "Model Projection": proj_f,
                    "Last 5": last_5,
                    "Pick": side,
                    "Margin": round(proj_f - line_f, 1),
                    "EV": format_percentage(ev, is_ev=True),
                    "Win Prob": format_percentage(prob),
                    "Action": act
                })
            except:
                pass

    if not prop_rows:
        st.info("No betting props found matching these filters.")
        st.stop()

    props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Player", "Prop Label", "Vegas Line"])

    if market_type == "Yards Only":
        props_df = props_df[props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]
    elif market_type == "Counts/Volume Only":
        props_df = props_df[~props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]

    if props_df.empty:
        st.info("No props matching the selected Prop Type.")
        st.stop()

    # --------------------------------------------------------------------------
    # STACKED BREAKDOWNS PER PLAYER
    # --------------------------------------------------------------------------
    unique_players = sorted(props_df["Player"].unique())

    for player in unique_players:
        player_props = props_df[props_df["Player"] == player]
        team_tag = player_props["Team"].iloc[0] if not player_props.empty else ""

        with st.container(border=True):
            st.markdown(f"## 👤 {player} ({team_tag})")

            # Scorecards
            cols_per_row = 3
            for i in range(0, len(player_props), cols_per_row):
                batch = player_props.iloc[i:i + cols_per_row]
                cols = st.columns(len(batch))
                for c_idx, (_, r) in enumerate(batch.iterrows()):
                    with cols[c_idx]:
                        with st.container(border=True):
                            st.markdown(f"#### 📌 {r['Prop Name']} `[{r['Book']}]`")
                            st.markdown(f"**Pick:** `{r['Pick']}` | **Action:** `{r['Action']}`")
                            m1, m2 = st.columns(2)
                            m1.metric("Vegas Line", f"{r['Vegas Line']}")
                            m2.metric("Model Proj", f"{r['Model Projection']}", delta=f"{r['Margin']:+0.1f}")
                            m3, m4 = st.columns(2)
                            m3.metric("Win Prob", r['Win Prob'])
                            m4.metric("EV Edge", r['EV'])

            # ------------------------------------------------------------------
            # VISUAL 1: HORIZONTAL EDGE / MARGIN BAR CHART
            # ------------------------------------------------------------------
            st.markdown("#### ⚡ Model Edge / Margin vs. Vegas Line")
            st.caption("Green bars extend right (Model Over) | Red bars extend left (Model Under)")

            edge_df = player_props.copy()
            edge_df["Edge Color"] = edge_df["Margin"].apply(lambda m: "Over Edge" if m >= 0 else "Under Edge")

            bars_edge = alt.Chart(edge_df).mark_bar(size=20, cornerRadiusTopLeft=3, cornerRadiusBottomLeft=3).encode(
                y=alt.Y("Prop Label:N", title=None, sort="-x"),
                x=alt.X("Margin:Q", title="Model Advantage (Margin vs. Line)"),
                color=alt.Color(
                    "Edge Color:N",
                    scale=alt.Scale(domain=["Over Edge", "Under Edge"], range=["#10B981", "#EF4444"]),
                    legend=alt.Legend(title=None, orient="top")
                )
            )

            text_edge = alt.Chart(edge_df).mark_text(
                align=alt.expr("datum.Margin >= 0 ? 'left' : 'right'"),
                dx=alt.expr("datum.Margin >= 0 ? 5 : -5"),
                fontSize=11,
                fontWeight="bold"
            ).encode(
                y=alt.Y("Prop Label:N", sort="-x"),
                x=alt.X("Margin:Q"),
                text=alt.Text("Margin:Q", format="+.1f")
            )

            zero_line = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#4A5568", strokeDash=[2, 2]).encode(x="x:Q")
            chart_edge_final = (bars_edge + text_edge + zero_line).properties(height=max(120, len(edge_df) * 35))
            st.altair_chart(chart_edge_final, use_container_width=True)

            # ------------------------------------------------------------------
            # VISUAL 2: ROLLING HIT RATE TREND CHART (LAST 5 GAMES)
            # ------------------------------------------------------------------
            st.markdown("#### 📈 Rolling Hit Rate & Game Trend (Last 5 Games)")

            for _, r_prop in player_props.iterrows():
                target_prop_name = r_prop["Prop Name"]
                cur_line = r_prop["Vegas Line"]
                book_tag = r_prop["Book"]
                last_5_raw = str(r_prop.get("Last 5", "")).strip()

                if last_5_raw and last_5_raw != "-" and last_5_raw != "nan":
                    try:
                        stats_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
                    except Exception:
                        stats_list = []

                    if stats_list:
                        trend_points = []
                        total_games = len(stats_list)
                        for idx, val in enumerate(stats_list):
                            # Chronological game labels: G-5 (oldest) up to G-1 (most recent)
                            g_label = f"G-{total_games - idx}" if (total_games - idx) > 1 else "Last Game"
                            trend_points.append({
                                "Game": g_label,
                                "Value": val,
                                "Line": cur_line
                            })

                        t_df = pd.DataFrame(trend_points)
                        t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= cur_line else "Under Miss")
                        hits = sum(t_df["Value"] >= cur_line)
                        total = len(t_df)
                        hit_pct = round((hits / total) * 100)

                        st.markdown(f"**📌 {target_prop_name} `[{book_tag}]` — Line: `{cur_line}` | Hit Rate: `{hits}/{total} ({hit_pct}%)`**")

                        hit_bars = alt.Chart(t_df).mark_bar(size=26, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                            x=alt.X("Game:N", title="Recent Game Log", sort=None),
                            y=alt.Y("Value:Q", title="Stat Value"),
                            color=alt.Color(
                                "Result:N",
                                scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#10B981", "#EF4444"]),
                                legend=alt.Legend(title=None, orient="top")
                            )
                        )

                        ref_line = alt.Chart(pd.DataFrame({"y": [cur_line]})).mark_rule(
                            color="#2563EB", strokeWidth=2, strokeDash=[4, 4]
                        ).encode(y="y:Q")

                        bar_text = alt.Chart(t_df).mark_text(dy=-8, fontSize=11, fontWeight="bold").encode(
                            x=alt.X("Game:N", sort=None),
                            y=alt.Y("Value:Q"),
                            text=alt.Text("Value:Q", format=".1f")
                        )

                        trend_chart = (hit_bars + bar_text + ref_line).properties(height=230)
                        st.altair_chart(trend_chart, use_container_width=True)
                    else:
                        st.caption(f"ℹ️ {target_prop_name} `[{book_tag}]`: No recent game stats recorded.")
                else:
                    st.caption(f"ℹ️ {target_prop_name} `[{book_tag}]`: No recent game stats recorded.")

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

dated_files.sort(key=lambda x: x["date"], reverse=True)
latest_file = dated_files[0]["filename"]

# --------------------------------------------------------------------------
# 2. VERIFIED NFL HEADSHOT DATABASE
# --------------------------------------------------------------------------
def clean_player_name(name):
    n = re.sub(r"\b(jr.?|sr.?|iii|ii|iv)\b", "", str(name), flags=re.IGNORECASE)
    return re.sub(r"[^\w\s]", "", n).lower().strip()

@st.cache_data(ttl=86400)
def load_verified_headshots():
    headshot_map = {}
    for yr in [2024, 2023]:
        try:
            url = f"https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{yr}.csv"
            df = pd.read_csv(url, usecols=["full_name", "headshot_url"]).dropna()
            for _, row in df.iterrows():
                c_name = clean_player_name(row["full_name"])
                if c_name and c_name not in headshot_map:
                    headshot_map[c_name] = str(row["headshot_url"])
        except Exception:
            pass
    return headshot_map

headshot_db = load_verified_headshots()

def get_headshot_url(player_name):
    c_name = clean_player_name(player_name)
    if c_name in headshot_db:
        return headshot_db[c_name]
    for db_name, url in headshot_db.items():
        if c_name in db_name or db_name in c_name:
            return url
    parts = c_name.split()
    if len(parts) >= 2:
        last = parts[-1]
        first_init = parts[0][0]
        for db_name, url in headshot_db.items():
            if db_name.endswith(last) and db_name.startswith(first_init):
                return url
    return None

# Brand Colored Sportsbook Helper
def get_book_styled(book_name):
    b = str(book_name).strip()
    if "draftkings" in b.lower() or "dk" in b.lower():
        return '<span style="color:#52B034; font-weight:bold;">DraftKings</span>'
    elif "fanduel" in b.lower() or "fd" in b.lower():
        return '<span style="color:#1493FF; font-weight:bold;">FanDuel</span>'
    return f"<span>{b}</span>"

# Percentage & Decimal Formatters
def format_percentage(val, is_ev=False):
    if pd.isna(val) or val == "-" or not isinstance(val, (int, float)):
        return val
    v = val if abs(val) <= 1.0 else val / 100.0
    return f"{v:+.1%}" if is_ev else f"{v:.1%}"

def format_clean_decimal(val):
    if pd.isna(val) or val == "-" or not isinstance(val, (int, float)):
        return val
    f_val = float(val)
    return f"{int(f_val)}" if f_val.is_integer() else f"{f_val:.1f}"

# Best Line Badge Generator
def get_best_line_badge_html(line_adv_note):
    if line_adv_note:
        return f'<span style="background-color:#FEF3C7; color:#92400E; padding:3px 8px; border-radius:12px; font-weight:bold; font-size:11px; border:1px solid #F59E0B; margin-left:6px;">{line_adv_note}</span>'
    return ""

# --------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------------------
st.sidebar.title("🏈 NFL Quant Engine")
file_names = [x["filename"] for x in dated_files]
selected_file = st.sidebar.selectbox("📅 Select Slate (Defaults to Latest):", file_names, index=0)
file_path = os.path.join(DATA_FOLDER, selected_file)

app_mode = st.sidebar.radio(
    "📱 Screen:", 
    [
        "📊 Pro Visualizer: Over / Under",
        "⚡ Pro Visualizer: Alt Lines",
        "💎 Best of the Best (Top Edges)",
        "📋 Master EV Tables"
    ]
)

excel_data = pd.ExcelFile(file_path)

# ==============================================================================
# DATA LOADER & BEST LINE ADVANTAGE CALCULATOR
# ==============================================================================
def load_visualizer_data(target_sheets):
    all_rows = []
    for sheet in target_sheets:
        if sheet not in excel_data.sheet_names:
            continue
        sub_df = pd.read_excel(excel_data, sheet_name=sheet)
        p_col = next((c for c in sub_df.columns if c.strip().lower() == "player"), None)
        if p_col and not sub_df.empty:
            sub_df["Player"] = sub_df[p_col]
            if "DK" in sheet: sub_df["Book"] = "DraftKings"
            elif "FD" in sheet: sub_df["Book"] = "FanDuel"
            else:
                b_val = str(sub_df.get("Book", pd.Series(["DraftKings"])).iloc[0])
                sub_df["Book"] = "FanDuel" if "fanduel" in b_val.lower() else "DraftKings"
            all_rows.append(sub_df)

    if not all_rows:
        return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True)

def tag_best_line_advantages(df):
    if df.empty:
        return df
    
    df["Is_Best_Line"] = False
    df["Line_Adv_Note"] = ""

    # Parse numeric EV
    def parse_ev_float(v):
        try: return float(v)
        except: return -1.0
    
    df["_ev_num"] = df["EV"].apply(parse_ev_float)

    # Compare books per Player and Prop
    for (p_name, prop_n), grp in df.groupby(["Player", "Prop Name"]):
        if len(grp) > 1:
            side = grp["Pick"].iloc[0]
            if side == "Over":
                min_line = grp["Vegas Line"].min()
                candidates = grp[grp["Vegas Line"] == min_line]
                best_idx = candidates["_ev_num"].idxmax()
                diff = grp["Vegas Line"].max() - min_line
                df.loc[best_idx, "Is_Best_Line"] = True
                df.loc[best_idx, "Line_Adv_Note"] = f"⭐ BEST LINE (+{diff:.1f} adv)" if diff > 0 else "⭐ BEST ODDS"
            else:
                max_line = grp["Vegas Line"].max()
                candidates = grp[grp["Vegas Line"] == max_line]
                best_idx = candidates["_ev_num"].idxmax()
                diff = max_line - grp["Vegas Line"].min()
                df.loc[best_idx, "Is_Best_Line"] = True
                df.loc[best_idx, "Line_Adv_Note"] = f"⭐ BEST LINE (+{diff:.1f} adv)" if diff > 0 else "⭐ BEST ODDS"
        elif len(grp) == 1:
            idx = grp.index[0]
            if grp.loc[idx, "_ev_num"] >= 0.05:
                df.loc[idx, "Is_Best_Line"] = True
                df.loc[idx, "Line_Adv_Note"] = "⭐ TOP VALUE"

    return df

# Common Render Function for Visualizers
def render_prop_visualizer(combined_df, is_alt_mode=False):
    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)

    f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1, 1])
    with f_col1:
        team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist()) if team_col else ["All Teams"]
        selected_team = st.selectbox("🏈 Team:", team_list)
    with f_col2:
        selected_pos = st.selectbox("🎯 Position:", ["All Positions", "QB", "RB", "WR", "TE"])
    with f_col3:
        selected_book = st.selectbox("🎰 Sportsbook:", ["All Sportsbooks", "DraftKings", "FanDuel"])
    with f_col4:
        prop_choices = ["All Props", "Yards Only", "Counts/Volume Only"]
        selected_prop_filter = st.selectbox("📊 Prop Filter:", prop_choices)

    filtered_df = combined_df.copy()
    if team_col and selected_team != "All Teams":
        filtered_df = filtered_df[filtered_df[team_col].astype(str) == selected_team]
    if pos_col and selected_pos != "All Positions":
        filtered_df = filtered_df[filtered_df[pos_col].astype(str).str.contains(selected_pos, case=False, na=False)]
    if selected_book != "All Sportsbooks":
        filtered_df = filtered_df[filtered_df["Book"].astype(str) == selected_book]

    prop_rows = []
    for _, r in filtered_df.iterrows():
        p_name = r.get("Milestone (Alt Line)") if is_alt_mode else r.get("Prop")
        line = r.get("Line") or (float(re.search(r"\d+(\.\d+)?", str(p_name)).group()) if re.search(r"\d+(\.\d+)?", str(p_name)) else None)
        proj = r.get("Projection")

        if pd.notna(p_name) and pd.notna(line) and pd.notna(proj):
            try:
                line_f = float(line)
                proj_f = float(proj)
                player_name = str(r["Player"])
                team_name = str(r.get(team_col, ""))
                pos_val = str(r.get(pos_col, ""))
                book = str(r.get("Book", "DraftKings"))
                side = str(r.get("Side", "Over"))
                ev = r.get("EV", "-")
                prob = r.get("Model Win Prob", "-")
                act = str(r.get("Action", "-"))
                last_5 = str(r.get("Last 5", "-"))

                prop_rows.append({
                    "Player": player_name,
                    "Team": team_name,
                    "Position": pos_val,
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
        st.info("No props matching these filter criteria.")
        return

    raw_props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Player", "Prop Label", "Vegas Line"])

    # Calculate Line Advantage
    props_df = tag_best_line_advantages(raw_props_df)

    if selected_prop_filter == "Yards Only":
        props_df = props_df[props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]
    elif selected_prop_filter == "Counts/Volume Only":
        props_df = props_df[~props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]

    if props_df.empty:
        st.info("No props available under this filter.")
        return

    unique_players = sorted(props_df["Player"].unique())

    for player in unique_players:
        p_props = props_df[props_df["Player"] == player]
        team_tag = p_props["Team"].iloc[0] if not p_props.empty else ""
        depth_tag = p_props["Position"].iloc[0] if not p_props.empty and p_props["Position"].iloc[0] else ""
        player_depth_label = f"({depth_tag})" if depth_tag else ""

        with st.container(border=True):
            # Header with Headshot & Depth Role
            headshot_url = get_headshot_url(player)
            h_col1, h_col2 = st.columns([1, 7])
            with h_col1:
                if headshot_url: st.image(headshot_url, width=95)
                else: st.markdown("## 👤")
            with h_col2:
                st.markdown(f"## {player} — {team_tag} **{player_depth_label}**")
                st.caption(f"Props Available: {len(p_props)}")

            # Scorecards with ⭐ Best Line Advantage Badging
            cols_per_row = 3
            for i in range(0, len(p_props), cols_per_row):
                batch = p_props.iloc[i:i + cols_per_row]
                cols = st.columns(len(batch))
                for c_idx, (_, r) in enumerate(batch.iterrows()):
                    with cols[c_idx]:
                        with st.container(border=True):
                            b_html = get_book_styled(r['Book'])
                            star_badge = get_best_line_badge_html(r['Line_Adv_Note'])
                            st.markdown(f"#### 📌 {r['Prop Name']} [{b_html}] {star_badge}", unsafe_allow_html=True)
                            st.markdown(f"**Pick:** `{r['Pick']}` | **Action:** `{r['Action']}`")
                            m1, m2 = st.columns(2)
                            m1.metric("Vegas Line", format_clean_decimal(r['Vegas Line']))
                            m2.metric("Model Proj", format_clean_decimal(r['Model Projection']), delta=f"{r['Margin']:+0.1f}")
                            m3, m4 = st.columns(2)
                            m3.metric("Win Prob", r['Win Prob'])
                            m4.metric("EV Edge", r['EV'])

            # Visual 1: Horizontal Edge Chart (With Star on Best Book)
            st.markdown("#### ⚡ Model Edge / Margin vs. Vegas Line")
            
            edge_df = p_props.groupby("Prop Label", as_index=False).first().copy()
            edge_df["Chart_Label"] = edge_df.apply(lambda row: f"⭐ {row['Prop Label']}" if row['Is_Best_Line'] else row['Prop Label'], axis=1)
            edge_df["Edge Color"] = edge_df["Margin"].apply(lambda m: "Over Edge" if m >= 0 else "Under Edge")

            max_m = max(abs(edge_df["Margin"].max()), abs(edge_df["Margin"].min()), 1.0)
            x_domain = [-max_m * 1.45, max_m * 1.45]

            bars_edge = alt.Chart(edge_df).mark_bar(
                size=16, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, cornerRadiusTopLeft=4, cornerRadiusBottomLeft=4
            ).encode(
                y=alt.Y("Chart_Label:N", title=None, sort="-x", scale=alt.Scale(paddingInner=0.55, paddingOuter=0.35), axis=alt.Axis(offset=15, labelPadding=12, labelLimit=240)),
                x=alt.X("Margin:Q", title="Model Advantage (Margin vs. Line)", scale=alt.Scale(domain=x_domain)),
                color=alt.Color("Edge Color:N", scale=alt.Scale(domain=["Over Edge", "Under Edge"], range=["#10B981", "#EF4444"]), legend=alt.Legend(title=None, orient="top"))
            )

            text_edge = alt.Chart(edge_df).mark_text(
                align=alt.expr("datum.Margin >= 0 ? 'left' : 'right'"),
                dx=alt.expr("datum.Margin >= 0 ? 8 : -8"),
                fontSize=11, fontWeight="bold"
            ).encode(y=alt.Y("Chart_Label:N", sort="-x"), x=alt.X("Margin:Q"), text=alt.Text("Margin:Q", format="+.1f"))

            zero_line = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#4A5568", strokeDash=[3, 3]).encode(x="x:Q")
            st.altair_chart((bars_edge + text_edge + zero_line).properties(height=alt.Step(42)), use_container_width=True)

            # Visual 2: Hit Rate Chart
            st.markdown("#### 📈 Rolling Hit Rate & Game Trend (Last 5 Games)")
            has_l5 = False
            for _, r_prop in p_props.iterrows():
                last_5_raw = str(r_prop.get("Last 5", "")).strip()
                cur_line = r_prop["Vegas Line"]
                book_tag = r_prop["Book"]
                p_label = r_prop["Prop Name"]
                adv_tag = f" — {r_prop['Line_Adv_Note']}" if r_prop['Line_Adv_Note'] else ""

                if last_5_raw and last_5_raw not in ["-", "nan", ""]:
                    try: stats_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
                    except: stats_list = []

                    if stats_list:
                        has_l5 = True
                        trend_points = []
                        total_g = len(stats_list)
                        for idx, val in enumerate(stats_list):
                            trend_points.append({"Game": f"G-{total_g - idx}" if (total_g - idx) > 1 else "Last Game", "Value": val, "Line": cur_line})

                        t_df = pd.DataFrame(trend_points)
                        t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= cur_line else "Under Miss")
                        hits = sum(t_df["Value"] >= cur_line)
                        hit_pct = round((hits / len(t_df)) * 100)

                        b_html = get_book_styled(book_tag)
                        st.markdown(f"**📌 {p_label} [{b_html}]{adv_tag} — Line: `{format_clean_decimal(cur_line)}` | Hit Rate: `{hits}/{len(t_df)} ({hit_pct}%)`**", unsafe_allow_html=True)

                        y_max = max(max(t_df["Value"]), cur_line) * 1.30

                        hit_bars = alt.Chart(t_df).mark_bar(size=26, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                            x=alt.X("Game:N", title="Recent Games", sort=None),
                            y=alt.Y("Value:Q", title="Stat Value", scale=alt.Scale(domain=[0, y_max])),
                            color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#10B981", "#EF4444"]), legend=alt.Legend(title=None, orient="top"))
                        )

                        ref_line = alt.Chart(pd.DataFrame({"y": [cur_line]})).mark_rule(color="#2563EB", strokeWidth=2, strokeDash=[4, 4]).encode(y="y:Q")
                        bar_text = alt.Chart(t_df).mark_text(dy=-10, fontSize=11, fontWeight="bold").encode(x=alt.X("Game:N", sort=None), y=alt.Y("Value:Q"), text=alt.Text("Value:Q", format=".1f"))

                        st.altair_chart((hit_bars + bar_text + ref_line).properties(height=230), use_container_width=True)

            if not has_l5:
                st.caption("ℹ️ *Last 5 stats will appear once updated Script 3 is pushed.*")

# ==============================================================================
# SCREEN 1: PRO VISUALIZER (OVER / UNDER)
# ==============================================================================
if app_mode == "📊 Pro Visualizer: Over / Under":
    st.title("📊 Pro Visualizer: Over / Under")
    ou_df = load_visualizer_data(["Top DK OU", "Top FD OU"])
    if ou_df.empty:
        st.warning("No Over/Under props found in this workbook.")
    else:
        render_prop_visualizer(ou_df, is_alt_mode=False)

# ==============================================================================
# SCREEN 2: PRO VISUALIZER (ALT LINES)
# ==============================================================================
elif app_mode == "⚡ Pro Visualizer: Alt Lines":
    st.title("⚡ Pro Visualizer: Alt Lines (Milestones & Parlays)")
    alt_df = load_visualizer_data(["Top DK Alt Lines", "Top FD Alt Lines"])
    if alt_df.empty:
        st.warning("No Alt Line props found in this workbook.")
    else:
        render_prop_visualizer(alt_df, is_alt_mode=True)

# ==============================================================================
# SCREEN 3: BEST OF THE BEST (TOP EDGES ON THE SLATE)
# ==============================================================================
elif app_mode == "💎 Best of the Best (Top Edges)":
    st.title("💎 Best of the Best (Top Conviction Plays)")
    all_curated = load_visualizer_data(["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"])
    
    if all_curated.empty:
        st.warning("No plays available.")
    else:
        def parse_ev_num(v):
            try: return float(v)
            except: return -1.0
            
        all_curated["_ev_val"] = all_curated["EV"].apply(parse_ev_num)
        best_plays = all_curated[
            all_curated["Action"].astype(str).str.contains("MAX|DUAL|ANCHOR|STRONG", case=False, na=False) |
            (all_curated["_ev_val"] >= 0.06)
        ].sort_values(by="_ev_val", ascending=False).drop_duplicates(subset=["Player", "Line", "Book"]).head(12)

        st.caption("Showing the top conviction bets on the slate clearing dual model edge and market devig.")

        for rank, (_, row) in enumerate(best_plays.iterrows(), 1):
            p_name = row["Player"]
            prop_n = row.get("Prop") or row.get("Milestone (Alt Line)")
            book_s = get_book_styled(row["Book"])
            headshot_url = get_headshot_url(p_name)

            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 2])
                with c1:
                    if headshot_url: st.image(headshot_url, width=70)
                    else: st.markdown("### 🏈")
                with c2:
                    st.markdown(f"### #{rank} {p_name}")
                    st.markdown(f"**📌 {prop_n}** [{book_s}]", unsafe_allow_html=True)
                with c3:
                    st.metric("Line / Pick", f"{row.get('Side', 'Over')} {format_clean_decimal(row.get('Line'))}")
                with c4:
                    st.metric("Model Proj", format_clean_decimal(row.get('Projection')))
                with c5:
                    st.metric("EV Edge", format_percentage(row.get('EV'), is_ev=True))
                st.caption(f"⭐ **Recommendation:** `{row.get('Action')}` | Win Prob: {format_percentage(row.get('Model Win Prob'))}")

# ==============================================================================
# SCREEN 4: MASTER EV TABLES (WITH FULL TOP-LINE FILTERING)
# ==============================================================================
elif app_mode == "📋 Master EV Tables":
    st.title("📋 Master EV Tables & Projections")

    tab_names = [s for s in excel_data.sheet_names if s != "How To Use"]
    tabs = st.tabs(tab_names)

    for i, sheet_name in enumerate(tab_names):
        with tabs[i]:
            df = pd.read_excel(excel_data, sheet_name=sheet_name)
            if df.empty:
                st.info("No data in this sheet.")
                continue

            # TOP-LINE FILTERS
            tf1, tf2, tf3, tf4, tf5 = st.columns([1, 1, 1, 1, 2])
            with tf1:
                t_list = ["All Teams"] + sorted(df["Team"].dropna().astype(str).unique().tolist()) if "Team" in df.columns else ["All Teams"]
                f_team = st.selectbox(f"Team ({sheet_name}):", t_list, key=f"t_{sheet_name}")
            with tf2:
                pos_col = next((c for c in ["Pos", "Position"] if c in df.columns), None)
                p_list = ["All Positions", "QB", "RB", "WR", "TE"] if pos_col else ["All Positions"]
                f_pos = st.selectbox(f"Pos ({sheet_name}):", p_list, key=f"p_{sheet_name}")
            with tf3:
                side_list = ["All Sides", "Over", "Under"] if "Side" in df.columns else ["All Sides"]
                f_side = st.selectbox(f"Side ({sheet_name}):", side_list, key=f"s_{sheet_name}")
            with tf4:
                act_col = "Action" if "Action" in df.columns else None
                act_list = ["All Actions", "MAX BET", "ANCHOR", "STRONG BET"] if act_col else ["All Actions"]
                f_act = st.selectbox(f"Action ({sheet_name}):", act_list, key=f"a_{sheet_name}")
            with tf5:
                f_search = st.text_input(f"🔍 Search ({sheet_name}):", "", key=f"sr_{sheet_name}")

            # Apply filters
            if f_team != "All Teams" and "Team" in df.columns:
                df = df[df["Team"].astype(str) == f_team]
            if f_pos != "All Positions" and pos_col:
                df = df[df[pos_col].astype(str).str.contains(f_pos, case=False, na=False)]
            if f_side != "All Sides" and "Side" in df.columns:
                df = df[df["Side"].astype(str) == f_side]
            if f_act != "All Actions" and act_col:
                df = df[df["Action"].astype(str).str.contains(f_act, case=False, na=False)]
            if f_search:
                mask = df.astype(str).apply(lambda row: row.str.contains(f_search, case=False).any(), axis=1)
                df = df[mask]

            for col in df.columns:
                if "EV" in col or "Market EV" in col:
                    df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=True))
                elif any(w in col for w in ["Prob", "Probability", "Win Prob"]):
                    df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=False))
                elif any(w in col for w in ["Line", "Projection", "Calibrated Proj"]):
                    df[col] = df[col].apply(format_clean_decimal)

            df = df.drop(columns=[c for c in ["GameSortKey", "SortScore", "CleanName"] if c in df.columns])

            def highlight_actions(row):
                val = str(row.get("Action", ""))
                if "MAX" in val: return ["background-color: #e8d7ff"] * len(row)
                elif "ANCHOR" in val: return ["background-color: #fff2cc"] * len(row)
                elif "STRONG" in val: return ["background-color: #d4edda"] * len(row)
                elif "SKIP" in val: return ["background-color: #f8d7da"] * len(row)
                return [""] * len(row)

            st.dataframe(df.style.apply(highlight_actions, axis=1), use_container_width=True, height=380)

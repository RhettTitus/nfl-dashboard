import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import altair as alt

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")

# --------------------------------------------------------------------------
# GLOBAL CSS GUARD (PREVENTS METRICS FROM COLLAPSING TO ...)
# --------------------------------------------------------------------------
st.markdown("""
<style>
[data-testid="stMetricValue"] {
    font-size: 1.30rem !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.85rem !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
}
</style>
""", unsafe_allow_html=True)

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
    if pd.isna(val) or val == "-" or str(val).strip().lower() in ["nan", "none", "", "unposted"]:
        return "-"
    try:
        f_val = float(str(val).replace("%", "").strip())
        v = f_val if abs(f_val) <= 1.0 else f_val / 100.0
        return f"{v:+.1%}" if is_ev else f"{v:.1%}"
    except:
        return str(val)

def format_clean_decimal(val):
    if pd.isna(val) or val == "-" or str(val).strip().lower() in ["nan", "none", "", "unposted"]:
        return ""
    try:
        f_val = float(val)
        return f"{int(f_val)}" if f_val.is_integer() else f"{f_val:.1f}"
    except:
        return str(val)

def format_american_odds(val):
    if pd.isna(val) or val == "-" or str(val).strip().lower() in ["nan", "none", "", "unposted"]:
        return "-"
    try:
        f_val = int(float(val))
        return f"+{f_val}" if f_val > 0 else f"{f_val}"
    except:
        return str(val)

def get_best_line_badge_html(line_adv_note):
    if line_adv_note:
        return f'<span style="background-color:#FEF3C7; color:#92400E; padding:3px 8px; border-radius:12px; font-weight:bold; font-size:11px; border:1px solid #F59E0B; margin-left:6px;">{line_adv_note}</span>'
    return ""

def extract_sanitized_prop_and_line(r):
    p_val = r.get("Prop")
    if pd.isna(p_val) or str(p_val).strip().lower() in ["nan", "none", "", "unposted"]:
        p_val = r.get("Milestone (Alt Line)")
    if pd.isna(p_val) or str(p_val).strip().lower() in ["nan", "none", "", "unposted"]:
        return None, None
    p_name = str(p_val).strip()

    line_val = r.get("Line")
    if pd.isna(line_val) or str(line_val).strip().lower() in ["nan", "none", "", "unposted"]:
        m_num = re.search(r"(\d+(\.\d+)?)", p_name)
        if m_num: line_val = float(m_num.group(1))
        else: return None, None
    else:
        try: line_val = float(line_val)
        except: return None, None

    return p_name, line_val

# --------------------------------------------------------------------------
# AUTO-DERIVE BOOK WIN PROBABILITY (HANDLES AMERICAN & DECIMAL ODDS, NEVER "UNPOSTED")
# --------------------------------------------------------------------------
def get_or_calculate_book_prob(book_prob_raw, odds_raw):
    # 1. Direct percentage check
    if pd.notna(book_prob_raw) and str(book_prob_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            v = float(str(book_prob_raw).replace("%", "").strip())
            return v if abs(v) <= 1.0 else v / 100.0
        except:
            pass

    # 2. Derive from odds (handles American and Decimal odds)
    if pd.notna(odds_raw) and str(odds_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            o_clean = str(odds_raw).replace("+", "").strip()
            o_num = float(o_clean)
            if o_num >= 100:
                return 100.0 / (o_num + 100.0)
            elif o_num <= -100:
                return abs(o_num) / (abs(o_num) + 100.0)
            elif 1.01 <= o_num < 50.0:  # Decimal odds fallback
                return 1.0 / o_num
        except:
            pass
    return None

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

    def parse_ev_float(v):
        try: return float(str(v).replace("%", "").strip())
        except: return -1.0
    
    df["_ev_num"] = df["EV"].apply(parse_ev_float)

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

def render_gambly_copy_box(df, box_title="📋 Gambly / Tracker Copy Slip"):
    with st.expander(box_title, expanded=False):
        c_book = st.selectbox(
            "Select Sportsbook for Copy Slip:",
            ["DraftKings", "FanDuel", "All Books (Combined)"],
            key=f"cb_{box_title}"
        )
        
        slip_df = df.copy()
        if c_book != "All Books (Combined)":
            slip_df = slip_df[slip_df["Book"] == c_book]
            
        slip_lines = []
        for _, r in slip_df.iterrows():
            p = str(r["Player"]).strip()
            side = str(r["Pick"]).strip()
            line = format_clean_decimal(r["Vegas Line"])
            prop = str(r["Prop Name"]).strip()
            
            if p and line and prop and "nan" not in f"{line} {prop}".lower():
                slip_lines.append(f"{p} {side} {line} {prop}")
                
        if slip_lines:
            st.caption(f"Showing **{len(slip_lines)}** {c_book} bets (Click icon in top-right to copy):")
            st.code("\n".join(slip_lines), language="text")
        else:
            st.info(f"No bets available for {c_book} under current filters.")

# Common Render Function for Visualizers (Grouped Hit Rates in Strict Chronological Order)
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
        p_name, line_f = extract_sanitized_prop_and_line(r)
        if not p_name or line_f is None:
            continue

        proj = r.get("Projection")
        if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]:
            continue

        try:
            proj_f = float(proj)
            player_name = str(r["Player"]).strip()
            team_name = str(r.get(team_col, "")).strip()
            pos_val = str(r.get(pos_col, "")).strip()
            book = str(r.get("Book", "DraftKings")).strip()
            
            side = str(r.get("Side", "Over")).strip()
            if not side or side.lower() in ["nan", "none"]: side = "Over"
            
            odds_val = r.get("Odds", "-")
            book_prob_raw = r.get("Book Win Prob", "-")
            model_prob = r.get("Model Win Prob", "-")
            ev = r.get("EV", "-")
            act = str(r.get("Action", "-"))
            last_5 = str(r.get("Last 5", "-"))

            # Calculate Book Implied Prob from Odds (Outputs clean '-' if none, never 'Unposted')
            calc_bp = get_or_calculate_book_prob(book_prob_raw, odds_val)
            book_prob_str = format_percentage(calc_bp) if calc_bp is not None else "-"

            prob_delta_str = None
            if calc_bp is not None and str(model_prob).strip() not in ["-", "nan", ""]:
                try:
                    mp_f = float(str(model_prob).replace("%","").strip())
                    mp_norm = mp_f if abs(mp_f) <= 1.0 else mp_f / 100.0
                    prob_delta_str = f"{(mp_norm - calc_bp):+.1%}"
                except:
                    pass

            prop_rows.append({
                "Player": player_name,
                "Team": team_name,
                "Position": pos_val,
                "Book": book,
                "Prop Label": f"{p_name} [{book}]",
                "Prop Name": str(p_name),
                "Vegas Line": line_f,
                "Odds": format_american_odds(odds_val),
                "Book Win Prob": book_prob_str,
                "Model Projection": proj_f,
                "Last 5": last_5,
                "Pick": side,
                "Margin": round(proj_f - line_f, 1),
                "EV": format_percentage(ev, is_ev=True),
                "Win Prob": format_percentage(model_prob),
                "Prob Delta": prob_delta_str,
                "Action": act
            })
        except:
            pass

    if not prop_rows:
        st.info("No props matching these filter criteria.")
        return

    raw_props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Player", "Prop Label", "Vegas Line"])
    props_df = tag_best_line_advantages(raw_props_df)

    if selected_prop_filter == "Yards Only":
        props_df = props_df[props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]
    elif selected_prop_filter == "Counts/Volume Only":
        props_df = props_df[~props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]

    if props_df.empty:
        st.info("No props available under this filter.")
        return

    render_gambly_copy_box(props_df, box_title="📋 Gambly Copy Slip (Clean Format by Sportsbook)")

    unique_players = sorted(props_df["Player"].unique())

    for player in unique_players:
        p_props = props_df[props_df["Player"] == player]
        team_tag = p_props["Team"].iloc[0] if not p_props.empty else ""
        depth_tag = p_props["Position"].iloc[0] if not p_props.empty and p_props["Position"].iloc[0] else ""
        player_depth_label = f"({depth_tag})" if depth_tag else ""

        with st.container(border=True):
            headshot_url = get_headshot_url(player)
            h_col1, h_col2 = st.columns([1, 7])
            with h_col1:
                if headshot_url: st.image(headshot_url, width=95)
                else: st.markdown("## 👤")
            with h_col2:
                st.markdown(f"## {player} — {team_tag} **{player_depth_label}**")
                st.caption(f"Props Available: {len(p_props)}")

            # Scorecards (2 Spacious Cards per Row)
            cols_per_row = 2
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
                            
                            # Row 1
                            m1, m2, m3 = st.columns(3)
                            odds_display = f" ({r['Odds']})" if r['Odds'] != "-" else ""
                            m1.metric("Line & Odds", f"{format_clean_decimal(r['Vegas Line'])}{odds_display}")
                            m2.metric("Model Proj", format_clean_decimal(r['Model Projection']), delta=f"{r['Margin']:+0.1f}")
                            m3.metric("EV Edge", r['EV'])
                            
                            # Row 2 (With Book Win Prob Clean '-')
                            m4, m5 = st.columns(2)
                            m4.metric("Book Win Prob", r['Book Win Prob'])
                            m5.metric("Model Win Prob", r['Win Prob'], delta=r['Prob Delta'])

            # Visual 1: Horizontal Edge Chart
            st.markdown("#### ⚡ Model Edge / Margin vs. Vegas Line")
            
            edge_df = p_props.groupby("Prop Label", as_index=False).first().copy()
            edge_df["Chart_Label"] = edge_df.apply(lambda row: f"⭐ {row['Prop Label']}" if row['Is_Best_Line'] else row['Prop Label'], axis=1)
            edge_df["Edge Color"] = edge_df["Margin"].apply(lambda m: "Over Edge" if m >= 0 else "Under Edge")

            max_m = max(abs(edge_df["Margin"].max()), abs(edge_df["Margin"].min()), 1.0)
            x_domain = [-max_m * 1.45, max_m * 1.45]

            bars_edge = alt.Chart(edge_df).mark_bar(
                size=16, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, cornerRadiusTopLeft=4, cornerRadiusBottomLeft=4
            ).encode(
                y=alt.Y(
                    "Chart_Label:N", 
                    title=None, 
                    sort="-x", 
                    scale=alt.Scale(paddingInner=0.55, paddingOuter=0.35), 
                    axis=alt.Axis(offset=15, labelPadding=12, labelLimit=0)
                ),
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

            # Visual 2: Grouped Hit Rates (Grouped by Prop Name in Strict Chronological Order)
            st.markdown("#### 📈 Rolling Hit Rate & Game Trend (Last 5 Games — Chronological)")

            # Group all lines belonging to the same base prop (e.g., all "Pass Yds" lines together)
            grouped_props = p_props.groupby("Prop Name")
            has_l5 = False

            for base_prop_name, grp in grouped_props:
                # Find valid Last 5 stats for this prop
                last_5_raw = ""
                for _, r_cand in grp.iterrows():
                    l5_c = str(r_cand.get("Last 5", "")).strip()
                    if l5_c and l5_c not in ["-", "nan", ""]:
                        last_5_raw = l5_c
                        break

                if last_5_raw:
                    try:
                        stats_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
                    except:
                        stats_list = []

                    if stats_list:
                        has_l5 = True
                        total_g = len(stats_list)

                        # Strict Chronological Labels (Left = Oldest, Right = Latest)
                        chronological_labels = []
                        trend_points = []
                        for idx, val in enumerate(stats_list):
                            label = f"G{idx + 1}" if (idx + 1) < total_g else f"G{idx + 1} (Latest)"
                            chronological_labels.append(label)
                            trend_points.append({"Game": label, "Value": val})

                        t_df = pd.DataFrame(trend_points)

                        # Header listing all books and lines available for this prop
                        book_badges_summary = []
                        for _, b_row in grp.iterrows():
                            b_html = get_book_styled(b_row["Book"])
                            cur_line = b_row["Vegas Line"]
                            hits = sum(t_df["Value"] >= cur_line)
                            hit_pct = round((hits / total_g) * 100)
                            star_b = f" {b_row['Line_Adv_Note']}" if b_row["Line_Adv_Note"] else ""
                            book_badges_summary.append(f"[{b_html}]{star_b} Line `{format_clean_decimal(cur_line)}` ({hits}/{total_g} — {hit_pct}%)")

                        st.markdown(f"**📌 {base_prop_name}:** " + " | ".join(book_badges_summary), unsafe_allow_html=True)

                        # Base primary line for coloring
                        primary_line = grp["Vegas Line"].iloc[0]
                        t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= primary_line else "Under Miss")

                        y_max = max(max(t_df["Value"]), grp["Vegas Line"].max()) * 1.30

                        # Bars explicitly sorted in chronological order (G1 to G5)
                        hit_bars = alt.Chart(t_df).mark_bar(size=26, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                            x=alt.X("Game:N", title="Chronological Game Log (Oldest ➔ Latest)", sort=chronological_labels, axis=alt.Axis(labelLimit=0)),
                            y=alt.Y("Value:Q", title="Stat Value", scale=alt.Scale(domain=[0, y_max])),
                            color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#10B981", "#EF4444"]), legend=alt.Legend(title=None, orient="top"))
                        )

                        bar_text = alt.Chart(t_df).mark_text(dy=-10, fontSize=11, fontWeight="bold").encode(
                            x=alt.X("Game:N", sort=chronological_labels), y=alt.Y("Value:Q"), text=alt.Text("Value:Q", format=".1f")
                        )

                        # Reference lines for each sportsbook line
                        ref_lines = []
                        for _, b_row in grp.iterrows():
                            c_line = b_row["Vegas Line"]
                            l_color = "#52B034" if "draftkings" in str(b_row["Book"]).lower() else "#1493FF"
                            ref_line = alt.Chart(pd.DataFrame({"y": [c_line]})).mark_rule(
                                color=l_color, strokeWidth=2, strokeDash=[4, 4]
                            ).encode(y="y:Q")
                            ref_lines.append(ref_line)

                        combined_chart = hit_bars + bar_text
                        for r_line in ref_lines:
                            combined_chart += r_line

                        st.altair_chart(combined_chart.properties(height=230), use_container_width=True)

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
# SCREEN 3: BEST OF THE BEST
# ==============================================================================
elif app_mode == "💎 Best of the Best (Top Edges)":
    st.title("💎 Best of the Best (Top Conviction Plays)")
    all_curated = load_visualizer_data(["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"])
    
    if all_curated.empty:
        st.warning("No plays available.")
    else:
        sanitized_plays = []
        for _, r_cand in all_curated.iterrows():
            p_n, line_f = extract_sanitized_prop_and_line(r_cand)
            if not p_n or line_f is None:
                continue
            
            proj = r_cand.get("Projection")
            if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]:
                continue
                
            try:
                ev_str = str(r_cand.get("EV", "-")).replace("%", "").strip()
                ev_f = float(ev_str)
                r_cand_copy = r_cand.copy()
                r_cand_copy["Clean_Prop"] = p_n
                r_cand_copy["Clean_Line"] = line_f
                r_cand_copy["_ev_val"] = ev_f
                sanitized_plays.append(r_cand_copy)
            except:
                pass

        if not sanitized_plays:
            st.warning("No valid plays found.")
            st.stop()

        clean_curated_df = pd.DataFrame(sanitized_plays)
        best_plays = clean_curated_df[
            clean_curated_df["Action"].astype(str).str.contains("MAX|DUAL|ANCHOR|STRONG", case=False, na=False) |
            (clean_curated_df["_ev_val"] >= 0.06)
        ].sort_values(by="_ev_val", ascending=False).drop_duplicates(subset=["Player", "Clean_Prop", "Clean_Line", "Book"]).head(15)

        st.caption("Showing the top conviction bets on the slate clearing dual model edge and market devig.")

        # Gambly Copy Box for Best of the Best
        with st.expander("📋 Gambly Copy Slip (Clean Format by Sportsbook)", expanded=True):
            best_c_book = st.selectbox(
                "Select Sportsbook for Copy Slip:",
                ["DraftKings", "FanDuel", "All Books (Combined)"],
                key="best_copy_book_select"
            )
            
            b_slip_df = best_plays.copy()
            if best_c_book != "All Books (Combined)":
                b_slip_df = b_slip_df[b_slip_df["Book"] == best_c_book]
                
            b_slip_lines = []
            for _, r_best in b_slip_df.iterrows():
                p = str(r_best["Player"]).strip()
                side = "Over" if pd.isna(r_best.get("Side")) or str(r_best.get("Side")).strip().lower() in ["nan", "none", ""] else str(r_best.get("Side")).strip()
                line = format_clean_decimal(r_best["Clean_Line"])
                prop = str(r_best["Clean_Prop"]).strip()
                if p and line and prop and "nan" not in f"{line} {prop}".lower():
                    b_slip_lines.append(f"{p} {side} {line} {prop}")
                    
            if b_slip_lines:
                st.caption(f"Showing **{len(b_slip_lines)}** {best_c_book} bets (Click icon in top-right to copy):")
                st.code("\n".join(b_slip_lines), language="text")
            else:
                st.info(f"No bets found for {best_c_book}.")

        for rank, (_, row) in enumerate(best_plays.iterrows(), 1):
            p_name = row["Player"]
            prop_n = row["Clean_Prop"]
            line_display = format_clean_decimal(row["Clean_Line"])
            book_s = get_book_styled(row["Book"])
            headshot_url = get_headshot_url(p_name)

            side_raw = str(row.get("Side", "")).strip()
            side_clean = "Over" if not side_raw or side_raw.lower() in ["nan", "none"] else side_raw

            odds_clean = format_american_odds(row.get("Odds", "-"))
            odds_str = f" ({odds_clean})" if odds_clean != "-" else ""

            # Ensure Book Win Prob is populated (derives from odds if missing, never displays "Unposted")
            calc_bp_best = get_or_calculate_book_prob(row.get("Book Win Prob"), row.get("Odds"))
            book_prob = format_percentage(calc_bp_best) if calc_bp_best is not None else "-"
            
            model_prob = format_percentage(row.get("Model Win Prob"))
            ev_clean = format_percentage(row.get("EV"), is_ev=True)

            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 2])
                with c1:
                    if headshot_url: st.image(headshot_url, width=70)
                    else: st.markdown("### 🏈")
                with c2:
                    st.markdown(f"### #{rank} {p_name}")
                    st.markdown(f"**📌 {prop_n}** [{book_s}]", unsafe_allow_html=True)
                with c3:
                    st.metric("Line & Odds", f"{side_clean} {line_display}{odds_str}")
                    st.caption(f"Book Win Prob: **{book_prob}**")
                with c4:
                    st.metric("Model Proj", format_clean_decimal(row.get('Projection')))
                    st.caption(f"Model Win Prob: **{model_prob}**")
                with c5:
                    st.metric("EV Edge", ev_clean)
                    st.caption(f"Action: `{row.get('Action', 'STRONG BET')}`")

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
                elif col == "Odds":
                    df[col] = df[col].apply(format_american_odds)

            df = df.drop(columns=[c for c in ["GameSortKey", "SortScore", "CleanName"] if c in df.columns])

            def highlight_actions(row):
                val = str(row.get("Action", ""))
                if "MAX" in val: return ["background-color: #e8d7ff"] * len(row)
                elif "ANCHOR" in val: return ["background-color: #fff2cc"] * len(row)
                elif "STRONG" in val: return ["background-color: #d4edda"] * len(row)
                elif "SKIP" in val: return ["background-color: #f8d7da"] * len(row)
                return [""] * len(row)

            st.dataframe(df.style.apply(highlight_actions, axis=1), use_container_width=True, height=380)

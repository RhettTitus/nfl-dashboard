import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
import altair as alt

# Forces Streamlit to auto-fit to whatever screen the user is holding
st.set_page_config(page_title="Props.Cash NFL Analytics", layout="wide", page_icon="🏈", initial_sidebar_state="expanded")

# --------------------------------------------------------------------------
# RESPONSIVE, MOBILE-FIRST CSS (AUTO-ADAPTS TO ALL SCREENS)
# --------------------------------------------------------------------------
st.markdown("""
<style>
/* Native Clean System Font for all devices */
html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    background-color: #07090E !important;
    color: #F8FAFC !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Fluid Container Padding */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    padding-left: 4% !important;
    padding-right: 4% !important;
    max-width: 1400px !important; /* Prevents ultra-wide stretching, but fills normal monitors */
    margin: auto !important;
}

h1, h2, h3, h4, h5, h6, p, div {
    color: #F8FAFC !important;
}

/* Responsive Selectbox Filters */
div[data-baseweb="select"] > div {
    background-color: #121824 !important;
    border: 1px solid #23304A !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
}
div[data-baseweb="select"] * {
    color: #FFFFFF !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
}
div[data-baseweb="popover"] {
    background-color: #121824 !important;
}

/* PROPS.CASH PILL TABS (WRAP ON SMALL SCREENS) */
div[data-baseweb="tab-list"] {
    gap: 8px !important;
    background-color: transparent !important;
    border-bottom: none !important;
    padding-bottom: 6px !important;
    flex-wrap: wrap !important; /* Allows tabs to drop to a second line on small phones */
}
button[data-baseweb="tab"], 
button[data-baseweb="tab"] * {
    background-color: #151D2A !important;
    color: #FFFFFF !important;
    opacity: 1 !important;
    font-weight: 800 !important;
    font-size: 0.96rem !important;
    letter-spacing: 0.3px !important;
}
button[data-baseweb="tab"] {
    border: 1.5px solid #2B3A52 !important;
    border-radius: 22px !important;
    padding: 8px 18px !important;
    margin-right: 6px !important;
    margin-bottom: 6px !important;
}
button[data-baseweb="tab"][aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"] * {
    background-color: #1F2E45 !important;
    color: #00E676 !important;
    border-color: #00E676 !important;
    box-shadow: 0 0 12px rgba(0, 230, 118, 0.3) !important;
}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
    display: none !important;
}

/* Checkbox Touch Target */
div[data-testid="stCheckbox"] {
    background: transparent !important;
    border: none !important;
    padding: 2px 0px !important;
    margin-top: 2px !important;
}
div[data-testid="stCheckbox"] label span:first-child {
    width: 22px !important;
    height: 22px !important;
    margin-right: 8px !important;
}
div[data-testid="stCheckbox"] label p {
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    color: #94A3B8 !important;
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
        dated_files.append({"filename": f, "date": d, "label": d.strftime("%-m/%-d")})

if not dated_files:
    st.info("👋 No dated spreadsheets found in `./data`. Push a slate from Colab to begin!")
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
    if c_name in headshot_db: return headshot_db[c_name]
    for db_name, url in headshot_db.items():
        if c_name in db_name or db_name in c_name: return url
    parts = c_name.split()
    if len(parts) >= 2:
        last = parts[-1]
        first_init = parts[0][0]
        for db_name, url in headshot_db.items():
            if db_name.endswith(last) and db_name.startswith(first_init): return url
    return "https://a.espncdn.com/combiner/i?img=/i/headshots/nfl/players/full/default.png&w=150&h=150"

def get_book_styled(book_name):
    b = str(book_name).strip()
    if "draftkings" in b.lower() or "dk" in b.lower():
        return '<span style="color:#00E676; font-weight:900;">DK</span>'
    elif "fanduel" in b.lower() or "fd" in b.lower():
        return '<span style="color:#0091FF; font-weight:900;">FD</span>'
    return f"<span>{b}</span>"

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
        return f'<span style="background-color:#FEF3C7; color:#92400E; padding:3px 9px; border-radius:10px; font-weight:900; font-size:10px; margin-left:6px; white-space:nowrap; display:inline-block;">{line_adv_note}</span>'
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

def format_gambly_bet_string(player, side, line, prop_name):
    p = str(player).strip()
    prop = str(prop_name).strip()
    side = str(side).strip() if str(side).strip() else "Over"
    line = str(line).strip()

    m = re.search(r"(\d+)\+\s*([A-Za-z\s\+]+)", prop)
    if m:
        milestone_num = m.group(1)
        stat_type = re.sub(r"\(.*?\)", "", m.group(2)).strip()
        return f"{p} {milestone_num}+ {stat_type}"

    clean_prop = re.sub(r"\(.*?\)", "", prop).strip()
    return f"{p} {side} {line} {clean_prop}"

def get_or_calculate_book_prob(book_prob_raw, odds_raw):
    if pd.notna(book_prob_raw) and str(book_prob_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            v = float(str(book_prob_raw).replace("%", "").strip())
            return v if abs(v) <= 1.0 else v / 100.0
        except: pass

    if pd.notna(odds_raw) and str(odds_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            o_clean = str(odds_raw).replace("+", "").strip()
            o_num = float(o_clean)
            if o_num >= 100: return 100.0 / (o_num + 100.0)
            elif o_num <= -100: return abs(o_num) / (abs(o_num) + 100.0)
            elif 1.01 <= o_num < 50.0: return 1.0 / o_num
        except: pass
    return None

# --------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------------------
st.sidebar.title("🏈 Props.Cash Engine")
file_names = [x["filename"] for x in dated_files]
selected_file = st.sidebar.selectbox("📅 Select Slate:", file_names, index=0)
file_path = os.path.join(DATA_FOLDER, selected_file)

app_mode = st.sidebar.radio(
    "📱 View Mode:", 
    [
        "📊 Props.Cash: Over / Under",
        "⚡ Props.Cash: Alt Lines",
        "💎 Best of the Best (Top Edges)",
        "📋 Master EV Tables"
    ]
)

excel_data = pd.ExcelFile(file_path)

def load_visualizer_data(target_sheets):
    all_rows = []
    for sheet in target_sheets:
        if sheet not in excel_data.sheet_names: continue
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

    if not all_rows: return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True)

def tag_best_line_advantages(df):
    if df.empty: return df
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
            
            bet_str = format_gambly_bet_string(p, side, line, prop)
            if bet_str and "nan" not in bet_str.lower():
                slip_lines.append(bet_str)
                
        slip_lines = list(dict.fromkeys(slip_lines))
        
        if slip_lines:
            st.caption(f"Showing **{len(slip_lines)}** {c_book} bets (Click icon in top-right to copy):")
            st.code("\n".join(slip_lines), language="text")
        else:
            st.info(f"No bets available for {c_book} under current filters.")

# --------------------------------------------------------------------------
# FAILSAFE ALTAIR CHART (FLAT UN-OUTLINED BARS WITH HALO-PROTECTED TEXT)
# --------------------------------------------------------------------------
def render_exact_props_cash_chart(base_prop_name, grp):
    last_5_raw = ""
    for _, r_cand in grp.iterrows():
        l5_c = str(r_cand.get("Last 5", "")).strip()
        if l5_c and l5_c not in ["-", "nan", ""]:
            last_5_raw = l5_c
            break

    if last_5_raw:
        try: stats_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
        except: stats_list = []

        if stats_list:
            total_g = len(stats_list)
            date_labels = []
            if len(dated_files) >= total_g:
                recent_chron_dates = [x["label"] for x in reversed(dated_files[:total_g])]
                date_labels = recent_chron_dates
            else:
                base_d = datetime.now()
                date_labels = [(base_d - timedelta(days=(total_g - i)*7)).strftime("%-m/%-d") for i in range(total_g)]

            trend_points = []
            for idx, val in enumerate(stats_list):
                d_str = date_labels[idx] if idx < len(date_labels) else f"G{idx+1}"
                trend_points.append({"Date": d_str, "Value": val})

            t_df = pd.DataFrame(trend_points)
            primary_line = grp["Vegas Line"].iloc[0]
            
            t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= primary_line else "Under Miss")
            t_df["Baseline"] = 0
            t_df["VegasLine"] = primary_line

            max_val = max(t_df["Value"])
            max_line = grp["Vegas Line"].max()
            if max_line <= 3.0: y_max = max(max_val * 1.5, max_line * 2.0, 3.5)
            else: y_max = max(max_val * 1.35, max_line * 1.45)

            base_chart = alt.Chart(t_df).encode(
                x=alt.X("Date:N", title=None, sort=date_labels, axis=alt.Axis(labelAngle=-90, labelColor="#94A3B8", labelFontSize=12, labelFontWeight="bold")),
                y=alt.Y("Value:Q", title=None, scale=alt.Scale(domain=[0, y_max]), axis=alt.Axis(labels=True, labelColor="#94A3B8", gridColor="#192333"))
            )

            # FLAT, SHARP BARS (NO ROUNDING, NO STROKE)
            hit_bars = base_chart.mark_bar(size=28, cornerRadius=0, strokeWidth=0).encode(
                color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#00E676", "#FF3B30"]), legend=None)
            )

            # DARK HALO PROTECTED TEXT
            bar_text_bg = base_chart.mark_text(
                dy=-6, baseline="bottom", fontSize=12, fontWeight="900", color="#07090E", stroke="#07090E", strokeWidth=5
            ).encode(y=alt.value(145), text=alt.Text("Value:Q", format=".1f"))

            bar_text_fg = base_chart.mark_text(
                dy=-6, baseline="bottom", fontSize=12, fontWeight="900", color="#FFFFFF"
            ).encode(y=alt.value(145), text=alt.Text("Value:Q", format=".1f"))

            # BLACK DOTTED VEGAS LINE (color="#000000", strokeDash=[2,3])
            ref_line = alt.Chart(t_df).mark_rule(
                color="#000000", strokeWidth=2.5, strokeDash=[2, 3]
            ).encode(y=alt.Y("VegasLine:Q"))

            final_chart = alt.layer(hit_bars, ref_line, bar_text_bg, bar_text_fg).properties(
                height=175
            ).configure(
                background="transparent"
            ).configure_view(
                strokeWidth=0
            )

            st.altair_chart(final_chart, use_container_width=True)

# FULL PROPS.CASH DASHBOARD
def render_props_cash_view(combined_df, is_alt_mode=False):
    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)

    f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1, 1])
    with f_col1:
        team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist()) if team_col else ["All Teams"]
        selected_team = st.selectbox("Team:", team_list)
    with f_col2:
        selected_pos = st.selectbox("Position:", ["All Positions", "QB", "RB", "WR", "TE"])
    with f_col3:
        selected_book = st.selectbox("Sportsbook:", ["All Sportsbooks", "DraftKings", "FanDuel"])
    with f_col4:
        selected_prop_filter = st.selectbox("Prop Filter:", ["All Props", "Yards Only", "Counts/Volume Only"])

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
        if not p_name or line_f is None: continue
        proj = r.get("Projection")
        if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]: continue

        try:
            proj_f = float(proj)
            team_val = str(r.get(team_col, "")).strip()
            pos_val = str(r.get(pos_col, "")).strip()
            book_val = str(r.get("Book", "DraftKings")).strip()
            grade_val = str(r.get("Grade", "A")).strip()
            opp_val = str(r.get("opponent", r.get("Game", "vs WAS • 1:00PM"))).strip()
            
            side_val = str(r.get("Side", "Over")).strip()
            if not side_val or side_val.lower() in ["nan", "none"]: side_val = "Over"
            
            odds_val = r.get("Odds", "-")
            book_prob_raw = r.get("Book Win Prob", "-")
            model_prob = r.get("Model Win Prob", "-")
            ev_val = r.get("EV", "-")
            act_val = str(r.get("Action", "-"))
            last_5_val = str(r.get("Last 5", "-"))

            calc_bp = get_or_calculate_book_prob(book_prob_raw, odds_val)
            book_prob_str = format_percentage(calc_bp) if calc_bp is not None else "-"

            prob_delta_str = None
            if calc_bp is not None and str(model_prob).strip() not in ["-", "nan", ""]:
                try:
                    mp_f = float(str(model_prob).replace("%","").strip())
                    mp_norm = mp_f if abs(mp_f) <= 1.0 else mp_f / 100.0
                    prob_delta_str = f"{(mp_norm - calc_bp):+.1%}"
                except: pass

            prop_rows.append({
                "Player": str(r["Player"]), "Team": team_val, "Position": pos_val, "Book": book_val,
                "Prop Name": str(p_name), "Vegas Line": line_f, "Odds": format_american_odds(odds_val),
                "Book Win Prob": book_prob_str, "Model Projection": proj_f, "Grade": grade_val,
                "Opponent": opp_val, "Last 5": last_5_val, "Pick": side_val, "Margin": round(proj_f - line_f, 1),
                "EV": format_percentage(ev_val, is_ev=True), "Win Prob": format_percentage(model_prob),
                "Prob Delta": prob_delta_str, "Action": act_val
            })
        except: pass

    if not prop_rows:
        st.info("No active lines found matching filters.")
        return

    props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Book", "Prop Name", "Vegas Line"])

    if selected_prop_filter == "Yards Only":
        props_df = props_df[props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]
    elif selected_prop_filter == "Counts/Volume Only":
        props_df = props_df[~props_df["Prop Name"].str.contains("Yds|Yards", case=False, na=False)]

    if props_df.empty: return

    render_gambly_copy_box(props_df, box_title="📋 Gambly Copy Slip (Tap to View)")

    unique_players = sorted(props_df["Player"].unique())
    for player in unique_players:
        p_props = props_df[props_df["Player"] == player]
        team_tag = p_props["Team"].iloc[0] if not p_props.empty else ""
        depth_tag = p_props["Position"].iloc[0] if not p_props.empty and p_props["Position"].iloc[0] else ""
        headshot_url = get_headshot_url(player)

        grouped_props = p_props.groupby("Prop Name")
        prop_names_list = list(grouped_props.groups.keys())

        # HERO PLAYER CARD
        st.markdown(f"""
        <div style="background:#0D111A; border:1px solid #1E283D; border-radius:14px; padding:14px 18px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:1.55rem; font-weight:900; color:#FFFFFF;">{player}</div>
                    <div style="font-size:0.95rem; color:#8F9CAE; font-weight:700;">{team_tag} • ({depth_tag})</div>
                </div>
                <div>
                    <img src="{headshot_url}" style="width:75px; height:75px; border-radius:50%; object-fit:cover; border:2px solid #00E676; background:#1C2436;">
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if len(prop_names_list) > 1:
            tabs_obj = st.tabs([pn for pn in prop_names_list])
            for t_idx, prop_name in enumerate(prop_names_list):
                with tabs_obj[t_idx]:
                    render_props_cash_tab_content(player, prop_name, grouped_props.get_group(prop_name))
        else:
            render_props_cash_tab_content(player, prop_names_list[0], grouped_props.get_group(prop_names_list[0]))

def render_props_cash_tab_content(player, prop_name, p_group):
    # Total Container Around Each Prop Block
    with st.container(border=True):
        dk_row = p_group[p_group["Book"] == "DraftKings"]
        fd_row = p_group[p_group["Book"] == "FanDuel"]

        primary_row = dk_row.iloc[0] if not dk_row.empty else fd_row.iloc[0]
        line_display = format_clean_decimal(primary_row["Vegas Line"])
        proj_display = format_clean_decimal(primary_row["Model Projection"])
        grade_char = primary_row.get("Grade", "A")

        last_5_raw = str(primary_row.get("Last 5", "")).strip()
        l5_avg_disp = "-"
        hit_rate_disp = "-"
        hit_color = "#00E676"

        if last_5_raw and last_5_raw not in ["-", "nan", ""]:
            try:
                s_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
                if s_list:
                    l5_avg_disp = f"{sum(s_list)/len(s_list):.1f}"
                    hits = sum(x >= float(primary_row["Vegas Line"]) for x in s_list)
                    pct = round((hits / len(s_list)) * 100)
                    hit_rate_disp = f"▲ {pct}%"
                    hit_color = "#00E676" if pct >= 50 else "#FF3B30"
            except: pass

        ev_val = primary_row['EV']
        win_prob = primary_row['Win Prob']

        # UNIFIED COCKPIT CARD (6-PACK + CONTEXT PILLS ALL IN THE TOP SLOT)
        st.markdown(f"""
        <div style="background:#0C111C; border:1px solid #1D263B; border-radius:12px; padding:16px 18px; margin-bottom:12px; box-shadow:0 4px 10px rgba(0,0,0,0.3);">
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); gap:10px; align-items:center; margin-bottom:14px;">
                <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">L5 AVG</div><div style="font-size:18px; font-weight:900; color:#FFFFFF;">▲ {l5_avg_disp}</div></div>
                <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">LINE</div><div style="font-size:18px; font-weight:900; color:#FFFFFF;">{line_display} &gt;</div></div>
                <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">PROP</div><div style="font-size:15px; font-weight:900; color:#FFFFFF;">{prop_name}</div></div>
                <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">HIT RATE</div><div style="font-size:18px; font-weight:900; color:{hit_color};">{hit_rate_disp}</div></div>
                <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">PROJECTION</div><div style="font-size:18px; font-weight:900; color:#00E676;">{proj_display}</div></div>
                <div style="text-align:center;">
                    <div style="width:40px; height:40px; border-radius:50%; border:3px solid #00E676; display:flex; align-items:center; justify-content:center; margin:0 auto; font-weight:900; color:#00E676; font-size:17px; background:#161E2E;">{grade_char}</div>
                </div>
            </div>
            <div style="height:1px; background:#1D263B; margin-bottom:12px;"></div>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:14px; font-size:12px; font-weight:800;">L5: <b style="color:{hit_color};">{hit_rate_disp}</b></span>
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:14px; font-size:12px; font-weight:800;">H2H: <b style="color:#00E676;">60%</b></span>
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:14px; font-size:12px; font-weight:800;">Model Win: <b style="color:#00E676;">{win_prob}</b></span>
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:14px; font-size:12px; font-weight:800;">Edge: <b style="color:#00E676;">{ev_val}</b></span>
                <span style="background:#131B2B; color:#00E676; border:1px solid #00E67680; padding:4px 12px; border-radius:14px; font-size:12px; font-weight:900;">DvP: 28th</span>
                <span style="background:#131B2B; color:#00E676; border:1px solid #00E67680; padding:4px 12px; border-radius:14px; font-size:12px; font-weight:900;">Def Rank: 30th</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # EXACT CHART WITH BLACK DOTTED LINE AND PROTECTED NUMBERS
        render_exact_props_cash_chart(prop_name, p_group)

        # DRAFTKINGS & FANDUEL ODDS ROW WITH ADD TO SLIP
        col_dk, col_fd = st.columns(2)
        with col_dk:
            if not dk_row.empty:
                r_b = dk_row.iloc[0]
                chk_k = f"m_chk_{r_b['Player']}_{r_b['Book']}_{r_b['Prop Name']}_{format_clean_decimal(r_b['Vegas Line'])}"
                st.markdown(f"""
                <div style="background:#101624; border:1px solid #243048; border-radius:8px; padding:7px 10px;">
                    <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:800;">
                        <span style="color:#00E676;">DraftKings</span>
                        <span style="color:#00E676;">{r_b['EV']} EV</span>
                    </div>
                    <div style="font-size:14px; font-weight:900; color:#FFFFFF; margin-top:2px;">
                        {r_b['Pick']} {format_clean_decimal(r_b['Vegas Line'])} <span style="font-size:11px; color:#94A3B8;">({r_b['Odds']})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.checkbox("➕ Slip", key=chk_k)
            else:
                st.markdown('<div style="background:#101624; border:1px dashed #243048; border-radius:8px; padding:12px; text-align:center; color:#64748B; font-size:11px; font-weight:700;"><span style="color:#00E676;">DK</span>: Unposted</div>', unsafe_allow_html=True)

        with col_fd:
            if not fd_row.empty:
                r_b = fd_row.iloc[0]
                chk_k = f"m_chk_{r_b['Player']}_{r_b['Book']}_{r_b['Prop Name']}_{format_clean_decimal(r_b['Vegas Line'])}"
                st.markdown(f"""
                <div style="background:#101624; border:1px solid #243048; border-radius:8px; padding:7px 10px;">
                    <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:800;">
                        <span style="color:#0091FF;">FanDuel</span>
                        <span style="color:#00E676;">{r_b['EV']} EV</span>
                    </div>
                    <div style="font-size:14px; font-weight:900; color:#FFFFFF; margin-top:2px;">
                        {r_b['Pick']} {format_clean_decimal(r_b['Vegas Line'])} <span style="font-size:11px; color:#94A3B8;">({r_b['Odds']})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.checkbox("➕ Slip", key=chk_k)
            else:
                st.markdown('<div style="background:#101624; border:1px dashed #243048; border-radius:8px; padding:12px; text-align:center; color:#64748B; font-size:11px; font-weight:700;"><span style="color:#0091FF;">FD</span>: Unposted</div>', unsafe_allow_html=True)

# ==============================================================================
# SCREENS
# ==============================================================================
if app_mode == "📊 Props.Cash: Over / Under":
    ou_df = load_visualizer_data(["Top DK OU", "Top FD OU"])
    if ou_df.empty: st.warning("No Over/Under props found.")
    else: render_props_cash_view(ou_df, is_alt_mode=False)

elif app_mode == "⚡ Props.Cash: Alt Lines":
    alt_df = load_visualizer_data(["Top DK Alt Lines", "Top FD Alt Lines"])
    if alt_df.empty: st.warning("No Alt Line props found.")
    else: render_props_cash_view(alt_df, is_alt_mode=True)

elif app_mode == "💎 Best of the Best (Top Edges)":
    st.markdown("<h2 style='color:#FFFFFF; font-weight:900; margin-bottom:8px;'>💎 Top Conviction Plays</h2>", unsafe_allow_html=True)
    all_curated = load_visualizer_data(["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"])
    if not all_curated.empty:
        for rank, (_, row) in enumerate(all_curated.head(10).iterrows(), 1):
            st.markdown(f"**#{rank} {row['Player']}** — {row.get('Prop', 'Prop')} ({row.get('Book','')}) | EV: **{row['EV']}**")

elif app_mode == "📋 Master EV Tables":
    st.markdown("<h2 style='color:#FFFFFF; font-weight:900; margin-bottom:12px;'>📋 Master EV Tables</h2>", unsafe_allow_html=True)
    for sheet in [s for s in excel_data.sheet_names if s != "How To Use"]:
        df = pd.read_excel(excel_data, sheet_name=sheet)
        if not df.empty:
            st.markdown(f"### {sheet}")
            st.dataframe(df, use_container_width=True, height=250)import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
import altair as alt

st.set_page_config(page_title="Props.Cash NFL Analytics", layout="wide", page_icon="🏈")

# --------------------------------------------------------------------------
# TOGGLEABLE VIEWPORT (MOBILE PHONE VS. DESKTOP WIDE MODE)
# --------------------------------------------------------------------------
is_desktop = st.sidebar.toggle("🖥️ Desktop Wide Mode", value=False)
max_w_css = "100%" if is_desktop else "600px"

# No f-string used here to prevent Syntax Errors with CSS brackets
css_template = """
<style>
/* Pure Dark Background */
.stApp {
    background-color: #07090E !important;
    color: #F8FAFC !important;
}

/* Dynamic Container Padding */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
    max-width: MAX_WIDTH_TOKEN !important;
    margin: auto !important;
}

/* Force All Headings to Pure White */
h1, h2, h3, h4, h5, h6, p, div {
    color: #F8FAFC !important;
}

/* High-Contrast Filters */
div[data-baseweb="select"] > div {
    background-color: #121824 !important;
    border: 1px solid #23304A !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
}
div[data-baseweb="select"] * {
    color: #FFFFFF !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
}

/* PROPS.CASH PILL TABS */
div[data-baseweb="tab-list"] {
    gap: 6px !important;
    border-bottom: none !important;
    padding-bottom: 2px !important;
}
button[data-baseweb="tab"], 
button[data-baseweb="tab"] * {
    background-color: #131A29 !important;
    color: #FFFFFF !important;
    font-size: 0.88rem !important;
    font-weight: 800 !important;
}
button[data-baseweb="tab"] {
    border: 1px solid #23304A !important;
    border-radius: 18px !important;
    padding: 5px 14px !important;
    margin-right: 4px !important;
}
button[data-baseweb="tab"][aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"] * {
    background-color: #1F2B42 !important;
    color: #00DF81 !important;
    border-color: #00DF81 !important;
}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
    display: none !important;
}

/* Compact Mobile Checkboxes */
div[data-testid="stCheckbox"] {
    background: transparent !important;
    border: none !important;
    padding: 2px 0px !important;
    margin-top: 2px !important;
}
div[data-testid="stCheckbox"] label span:first-child {
    width: 20px !important;
    height: 20px !important;
}
div[data-testid="stCheckbox"] label p {
    font-size: 0.85rem !important;
    font-weight: 800 !important;
    color: #94A3B8 !important;
}
</style>
"""
st.markdown(css_template.replace("MAX_WIDTH_TOKEN", max_w_css), unsafe_allow_html=True)

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
        dated_files.append({"filename": f, "date": d, "label": d.strftime("%-m/%-d")})

if not dated_files:
    st.info("👋 No dated spreadsheets found in `./data`. Push a slate from Colab to begin!")
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
    if c_name in headshot_db: return headshot_db[c_name]
    for db_name, url in headshot_db.items():
        if c_name in db_name or db_name in c_name: return url
    parts = c_name.split()
    if len(parts) >= 2:
        last = parts[-1]
        first_init = parts[0][0]
        for db_name, url in headshot_db.items():
            if db_name.endswith(last) and db_name.startswith(first_init): return url
    return "https://a.espncdn.com/combiner/i?img=/i/headshots/nfl/players/full/default.png&w=150&h=150"

def get_book_styled(book_name):
    b = str(book_name).strip()
    if "draftkings" in b.lower() or "dk" in b.lower():
        return '<span style="color:#00E676; font-weight:900;">DK</span>'
    elif "fanduel" in b.lower() or "fd" in b.lower():
        return '<span style="color:#0091FF; font-weight:900;">FD</span>'
    return f"<span>{b}</span>"

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

def format_gambly_bet_string(player, side, line, prop_name):
    p = str(player).strip()
    prop = str(prop_name).strip()
    side = str(side).strip() if str(side).strip() else "Over"
    line = str(line).strip()

    m = re.search(r"(\d+)\+\s*([A-Za-z\s\+]+)", prop)
    if m:
        milestone_num = m.group(1)
        stat_type = re.sub(r"\(.*?\)", "", m.group(2)).strip()
        return f"{p} {milestone_num}+ {stat_type}"

    clean_prop = re.sub(r"\(.*?\)", "", prop).strip()
    return f"{p} {side} {line} {clean_prop}"

def get_or_calculate_book_prob(book_prob_raw, odds_raw):
    if pd.notna(book_prob_raw) and str(book_prob_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            v = float(str(book_prob_raw).replace("%", "").strip())
            return v if abs(v) <= 1.0 else v / 100.0
        except: pass

    if pd.notna(odds_raw) and str(odds_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            o_clean = str(odds_raw).replace("+", "").strip()
            o_num = float(o_clean)
            if o_num >= 100: return 100.0 / (o_num + 100.0)
            elif o_num <= -100: return abs(o_num) / (abs(o_num) + 100.0)
            elif 1.01 <= o_num < 50.0: return 1.0 / o_num
        except: pass
    return None

# --------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------------------
st.sidebar.title("🏈 Props.Cash Engine")
file_names = [x["filename"] for x in dated_files]
selected_file = st.sidebar.selectbox("📅 Select Slate:", file_names, index=0)
file_path = os.path.join(DATA_FOLDER, selected_file)

app_mode = st.sidebar.radio(
    "📱 View Mode:", 
    [
        "📊 Props.Cash: Over / Under",
        "⚡ Props.Cash: Alt Lines",
        "💎 Best of the Best (Top Edges)",
        "📋 Master EV Tables"
    ]
)

excel_data = pd.ExcelFile(file_path)

def load_visualizer_data(target_sheets):
    all_rows = []
    for sheet in target_sheets:
        if sheet not in excel_data.sheet_names: continue
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

    if not all_rows: return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True)

# --------------------------------------------------------------------------
# PROPS.CASH EXACT CHART (NUMBERS AT BASE OF BARS, NEVER CUT BY LINE)
# --------------------------------------------------------------------------
def render_exact_props_cash_chart(base_prop_name, grp):
    last_5_raw = ""
    for _, r_cand in grp.iterrows():
        l5_c = str(r_cand.get("Last 5", "")).strip()
        if l5_c and l5_c not in ["-", "nan", ""]:
            last_5_raw = l5_c
            break

    if last_5_raw:
        try: stats_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
        except: stats_list = []

        if stats_list:
            total_g = len(stats_list)
            
            date_labels = []
            if len(dated_files) >= total_g:
                recent_chron_dates = [x["label"] for x in reversed(dated_files[:total_g])]
                date_labels = recent_chron_dates
            else:
                base_d = datetime.now()
                date_labels = [(base_d - timedelta(days=(total_g - i)*7)).strftime("%-m/%-d") for i in range(total_g)]

            trend_points = []
            for idx, val in enumerate(stats_list):
                d_str = date_labels[idx] if idx < len(date_labels) else f"G{idx+1}"
                trend_points.append({"Date": d_str, "Value": val})

            t_df = pd.DataFrame(trend_points)
            primary_line = grp["Vegas Line"].iloc[0]
            t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= primary_line else "Under Miss")

            max_val = max(t_df["Value"])
            max_line = grp["Vegas Line"].max()
            if max_line <= 3.0: y_max = max(max_val * 1.5, max_line * 2.0, 3.5)
            else: y_max = max(max_val * 1.35, max_line * 1.45)

            # SCHEMA-COMPLIANT LAYERED CHART
            base_chart = alt.Chart(t_df).encode(
                x=alt.X("Date:N", title=None, sort=date_labels, axis=alt.Axis(labelAngle=-90, labelColor="#94A3B8", labelFontSize=10)),
                y=alt.Y("Value:Q", title=None, scale=alt.Scale(domain=[0, y_max]), axis=alt.Axis(labels=True, labelColor="#94A3B8", gridColor="#192333"))
            )

            hit_bars = base_chart.mark_bar(size=28, cornerRadius=0, strokeWidth=0).encode(
                color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#00E676", "#FF3B30"]), legend=None)
            )

            bar_text = base_chart.mark_text(
                dy=-6,
                baseline="bottom",
                fontSize=11.5,
                fontWeight="900",
                color="#0A0E17",
                stroke="#FFFFFF",
                strokeWidth=0.5
            ).encode(
                y=alt.value(165),
                text=alt.Text("Value:Q", format=".1f")
            )

            ref_line = alt.Chart(pd.DataFrame({"y": [primary_line]})).mark_rule(
                color="#FFFFFF", strokeWidth=1.5, strokeDash=[4, 4]
            ).encode(y="y:Q")

            line_label = alt.Chart(pd.DataFrame({"y": [primary_line]})).mark_text(
                align="left", dx=2, dy=-8, fontSize=10, fontWeight="bold", color="#FFFFFF"
            ).encode(y="y:Q", text=alt.value(f"{primary_line:.1f}"))

            final_chart = alt.layer(hit_bars, ref_line, line_label, bar_text, data=t_df).properties(
                height=190
            ).configure(
                background="transparent"
            ).configure_view(
                strokeWidth=0
            )

            st.altair_chart(final_chart, use_container_width=True)

# --------------------------------------------------------------------------
# EXACT PROPS.CASH 1-SCREEN MOBILE DASHBOARD
# --------------------------------------------------------------------------
def render_props_cash_view(combined_df, is_alt_mode=False):
    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)

    # Clean Top Selectors
    top_col1, top_col2 = st.columns([1, 1])
    with top_col1:
        team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist()) if team_col else ["All Teams"]
        selected_team = st.selectbox("Team:", team_list, label_visibility="collapsed")
    with top_col2:
        player_pool = combined_df.copy()
        if team_col and selected_team != "All Teams":
            player_pool = player_pool[player_pool[team_col].astype(str) == selected_team]
        avail_players = sorted(player_pool["Player"].dropna().unique().tolist())
        selected_player = st.selectbox("Player:", avail_players, label_visibility="collapsed")

    if not selected_player:
        st.info("No player selected.")
        return

    p_records = combined_df[combined_df["Player"] == selected_player].copy()
    if p_records.empty:
        st.warning("No props found.")
        return

    # Extract all props
    prop_rows = []
    for _, r in p_records.iterrows():
        p_name, line_f = extract_sanitized_prop_and_line(r)
        if not p_name or line_f is None: continue
        proj = r.get("Projection")
        if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]: continue

        try:
            line_f = float(line_f)
            proj_f = float(proj)
            team_val = str(r.get(team_col, "")).strip()
            pos_val = str(r.get(pos_col, "")).strip()
            book_val = str(r.get("Book", "DraftKings")).strip()
            grade_val = str(r.get("Grade", "A")).strip()
            opp_val = str(r.get("opponent", r.get("Game", "vs WAS • 1:00PM"))).strip()
            
            side_val = str(r.get("Side", "Over")).strip()
            if not side_val or side_val.lower() in ["nan", "none"]: side_val = "Over"
            
            odds_val = r.get("Odds", "-")
            book_prob_raw = r.get("Book Win Prob", "-")
            model_prob = r.get("Model Win Prob", "-")
            ev_val = r.get("EV", "-")
            act_val = str(r.get("Action", "-"))
            last_5_val = str(r.get("Last 5", "-"))

            calc_bp = get_or_calculate_book_prob(book_prob_raw, odds_val)
            book_prob_str = format_percentage(calc_bp) if calc_bp is not None else "-"

            prob_delta_str = None
            if calc_bp is not None and str(model_prob).strip() not in ["-", "nan", ""]:
                try:
                    mp_f = float(str(model_prob).replace("%","").strip())
                    mp_norm = mp_f if abs(mp_f) <= 1.0 else mp_f / 100.0
                    prob_delta_str = f"{(mp_norm - calc_bp):+.1%}"
                except: pass

            prop_rows.append({
                "Player": selected_player,
                "Team": team_val,
                "Position": pos_val,
                "Book": book_val,
                "Prop Name": str(p_name),
                "Vegas Line": line_f,
                "Odds": format_american_odds(odds_val),
                "Book Win Prob": book_prob_str,
                "Model Projection": proj_f,
                "Grade": grade_val,
                "Opponent": opp_val,
                "Last 5": last_5_val,
                "Pick": side_val,
                "Margin": round(proj_f - line_f, 1),
                "EV": format_percentage(ev_val, is_ev=True),
                "Win Prob": format_percentage(model_prob),
                "Prob Delta": prob_delta_str,
                "Action": act_val
            })
        except: pass

    if not prop_rows:
        st.info("No active lines found for this player.")
        return

    p_props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Book", "Prop Name", "Vegas Line"])

    # Collect Checked Bets
    selected_dk = []
    selected_fd = []
    for _, r_check in p_props_df.iterrows():
        chk_id = f"m_chk_{r_check['Player']}_{r_check['Book']}_{r_check['Prop Name']}_{format_clean_decimal(r_check['Vegas Line'])}"
        if st.session_state.get(chk_id, False):
            bet_line = format_gambly_bet_string(r_check['Player'], r_check['Pick'], r_check['Vegas Line'], r_check['Prop Name'])
            if r_check['Book'] == 'DraftKings': selected_dk.append(bet_line)
            elif r_check['Book'] == 'FanDuel': selected_fd.append(bet_line)

    selected_dk = list(dict.fromkeys(selected_dk))
    selected_fd = list(dict.fromkeys(selected_fd))

    # Gambly Copy Slips
    with st.expander("📋 Copyable Gambly Slips (Tap to View)", expanded=(len(selected_dk) > 0 or len(selected_fd) > 0)):
        c_dk_c, c_fd_c = st.columns(2)
        with c_dk_c:
            st.markdown("<span style='color:#00DF81; font-weight:800;'>🟢 DraftKings</span>", unsafe_allow_html=True)
            if selected_dk: st.code("\n".join(selected_dk), language="text")
            else: st.caption("Empty. Check boxes below.")
        with c_fd_c:
            st.markdown("<span style='color:#0091FF; font-weight:800;'>🔵 FanDuel</span>", unsafe_allow_html=True)
            if selected_fd: st.code("\n".join(selected_fd), language="text")
            else: st.caption("Empty. Check boxes below.")

    # --------------------------------------------------------------------------
    # PROPS.CASH SINGLE PHONE SCREEN COCKPIT
    # --------------------------------------------------------------------------
    team_tag = p_props_df["Team"].iloc[0]
    pos_tag = p_props_df["Position"].iloc[0]
    headshot_url = get_headshot_url(selected_player)

    grouped_props = p_props_df.groupby("Prop Name")
    prop_names_list = list(grouped_props.groups.keys())

    # HERO PLAYER CARD
    card_html = f"""
    <div style="background:#0D111A; border:1px solid #1E283D; border-radius:14px; padding:12px 14px; margin-bottom:6px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div>
                <div style="font-size:1.35rem; font-weight:900; color:#FFFFFF; line-height:1.2;">{selected_player}</div>
                <div style="font-size:0.80rem; color:#8F9CAE; font-weight:700;">{team_tag} • {pos_tag}</div>
                <div style="display:flex; gap:6px; margin-top:4px;">
                    <span style="font-size:10px; background:#182236; color:#00DF81; padding:2px 7px; border-radius:4px; font-weight:800;">vs WAS • 1:00PM</span>
                </div>
            </div>
            <div>
                <img src="{headshot_url}" style="width:65px; height:65px; border-radius:50%; object-fit:cover; border:2px solid #00DF81; background:#1C2436;">
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    # 1. TOP HORIZONTAL PILL TABS
    if len(prop_names_list) > 1:
        tabs_obj = st.tabs([pn for pn in prop_names_list])
    else:
        tabs_obj = [st.container()]

    for t_idx, prop_name in enumerate(prop_names_list):
        with tabs_obj[t_idx]:
            p_group = grouped_props.get_group(prop_name)
            dk_row = p_group[p_group["Book"] == "DraftKings"]
            fd_row = p_group[p_group["Book"] == "FanDuel"]
            primary_r = dk_row.iloc[0] if not dk_row.empty else fd_row.iloc[0]

            line_disp = format_clean_decimal(primary_r["Vegas Line"])
            proj_disp = format_clean_decimal(primary_r["Model Projection"])
            grade_char = primary_r.get("Grade", "A")
            
            last_5_raw = str(primary_r.get("Last 5", "")).strip()
            l5_avg_disp = "-"
            hit_rate_disp = "-"
            hit_color = "#00DF81"
            if last_5_raw and last_5_raw not in ["-", "nan", ""]:
                try:
                    s_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
                    if s_list:
                        l5_avg_disp = f"{sum(s_list)/len(s_list):.1f}"
                        hits = sum(x >= float(primary_r["Vegas Line"]) for x in s_list)
                        pct = round((hits / len(s_list)) * 100)
                        hit_rate_disp = f"▲ {pct}%"
                        hit_color = "#00DF81" if pct >= 50 else "#FF3B30"
                except: pass

            ev_val = primary_r['EV']
            win_prob = primary_r['Win Prob']

            # 2. PROPS.CASH 6-PACK MATRIX + GRADE RING
            matrix_html = f"""
            <div style="background:#0C111C; border:1px solid #1D263B; border-radius:12px; padding:12px 16px; margin-bottom:10px;">
                <div style="display:grid; grid-template-columns: 1fr 1fr 1.2fr 1fr 1fr 65px; gap:8px; align-items:center;">
                    <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">L5 AVG</div><div style="font-size:16px; font-weight:900; color:#FFFFFF;">▲ {l5_avg_disp}</div></div>
                    <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">LINE</div><div style="font-size:16px; font-weight:900; color:#FFFFFF;">{line_disp} &gt;</div></div>
                    <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">PROP</div><div style="font-size:14px; font-weight:900; color:#FFFFFF;">{prop_name}</div></div>
                    <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">HIT RATE</div><div style="font-size:16px; font-weight:900; color:{hit_color};">{hit_rate_disp}</div></div>
                    <div><div style="font-size:10px; color:#8F9CAE; font-weight:800; letter-spacing:0.5px;">PROJECTION</div><div style="font-size:16px; font-weight:900; color:#00DF81;">{proj_disp}</div></div>
                    <div style="text-align:center;">
                        <div style="width:38px; height:38px; border-radius:50%; border:3px solid #00DF81; display:flex; align-items:center; justify-content:center; margin:0 auto; font-weight:900; color:#00DF81; font-size:16px; background:#161E2E; box-shadow:0 0 12px rgba(0,230,118,0.35);">{grade_char}</div>
                        <div style="font-size:9px; color:#8F9CAE; font-weight:800; margin-top:2px;">Matchup</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(matrix_html, unsafe_allow_html=True)

            # 3. EXACT CHART
            render_exact_props_cash_chart(prop_name, p_group)

            # 4. CONTEXT PILLS
            pills_html = f"""
            <div style="display:flex; gap:6px; margin-top:2px; margin-bottom:12px; flex-wrap:wrap;">
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:16px; font-size:11.5px; font-weight:800;">L5: <b style="color:{hit_color};">{hit_rate_disp}</b></span>
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:16px; font-size:11.5px; font-weight:800;">H2H: <b style="color:#00E676;">60%</b></span>
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:16px; font-size:11.5px; font-weight:800;">Model Win: <b style="color:#00E676;">{win_prob}</b></span>
                <span style="background:#131B2B; color:#FFFFFF; border:1px solid #23304A; padding:4px 12px; border-radius:16px; font-size:11.5px; font-weight:800;">Edge: <b style="color:#00E676;">{ev_val}</b></span>
                <span style="background:#131B2B; color:#00E676; border:1.5px solid #00E676; padding:4px 12px; border-radius:16px; font-size:11.5px; font-weight:900;">DvP: 28th</span>
                <span style="background:#131B2B; color:#00E676; border:1.5px solid #00E676; padding:4px 12px; border-radius:16px; font-size:11.5px; font-weight:900;">Def Rank: 30th</span>
            </div>
            """
            st.markdown(pills_html, unsafe_allow_html=True)

            # 5. DRAFTKINGS & FANDUEL FOOTER
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if not dk_row.empty:
                    r_b = dk_row.iloc[0]
                    chk_k = f"m_chk_{r_b['Player']}_{r_b['Book']}_{r_b['Prop Name']}_{format_clean_decimal(r_b['Vegas Line'])}"
                    st.markdown(f"""
                    <div style="background:#101624; border:1px solid #243048; border-radius:8px; padding:7px 10px;">
                        <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:800;">
                            <span style="color:#00E676;">DraftKings</span>
                            <span style="color:#00E676;">{r_b['EV']} EV</span>
                        </div>
                        <div style="font-size:14px; font-weight:900; color:#FFFFFF; margin-top:2px;">
                            {r_b['Pick']} {format_clean_decimal(r_b['Vegas Line'])} <span style="font-size:11px; color:#94A3B8;">({r_b['Odds']})</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.checkbox("➕ Slip", key=chk_k)
                else:
                    st.markdown('<div style="background:#101624; border:1px dashed #243048; border-radius:8px; padding:12px; text-align:center; color:#64748B; font-size:11px; font-weight:700;"><span style="color:#00E676;">DK</span>: Unposted</div>', unsafe_allow_html=True)

            with col_b2:
                if not fd_row.empty:
                    r_b = fd_row.iloc[0]
                    chk_k = f"m_chk_{r_b['Player']}_{r_b['Book']}_{r_b['Prop Name']}_{format_clean_decimal(r_b['Vegas Line'])}"
                    st.markdown(f"""
                    <div style="background:#101624; border:1px solid #243048; border-radius:8px; padding:7px 10px;">
                        <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:800;">
                            <span style="color:#0091FF;">FanDuel</span>
                            <span style="color:#00E676;">{r_b['EV']} EV</span>
                        </div>
                        <div style="font-size:14px; font-weight:900; color:#FFFFFF; margin-top:2px;">
                            {r_b['Pick']} {format_clean_decimal(r_b['Vegas Line'])} <span style="font-size:11px; color:#94A3B8;">({r_b['Odds']})</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.checkbox("➕ Slip", key=chk_k)
                else:
                    st.markdown('<div style="background:#101624; border:1px dashed #243048; border-radius:8px; padding:12px; text-align:center; color:#64748B; font-size:11px; font-weight:700;"><span style="color:#0091FF;">FD</span>: Unposted</div>', unsafe_allow_html=True)

# ==============================================================================
# SCREENS
# ==============================================================================
if app_mode == "📊 Props.Cash: Over / Under":
    ou_df = load_visualizer_data(["Top DK OU", "Top FD OU"])
    if ou_df.empty: st.warning("No Over/Under props found.")
    else: render_props_cash_view(ou_df, is_alt_mode=False)

elif app_mode == "⚡ Props.Cash: Alt Lines":
    alt_df = load_visualizer_data(["Top DK Alt Lines", "Top FD Alt Lines"])
    if alt_df.empty: st.warning("No Alt Line props found.")
    else: render_props_cash_view(alt_df, is_alt_mode=True)

elif app_mode == "💎 Best of the Best (Top Edges)":
    st.markdown("<h2 style='color:#FFFFFF; font-weight:900; margin-bottom:8px;'>💎 Top Conviction Plays</h2>", unsafe_allow_html=True)
    all_curated = load_visualizer_data(["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"])
    
    if all_curated.empty:
        st.warning("No plays available.")
    else:
        sanitized_plays = []
        for _, r_cand in all_curated.iterrows():
            p_n, line_f = extract_sanitized_prop_and_line(r_cand)
            if not p_n or line_f is None: continue
            proj = r_cand.get("Projection")
            if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]: continue
                
            try:
                ev_str = str(r_cand.get("EV", "-")).replace("%", "").strip()
                ev_f = float(ev_str)
                m_prob_raw = r_cand.get("Model Win Prob")
                m_prob_f = float(str(m_prob_raw).replace("%", "").strip()) if pd.notna(m_prob_raw) else 0.50
                m_prob_norm = m_prob_f if abs(m_prob_f) <= 1.0 else m_prob_f / 100.0
                b_prob_calc = get_or_calculate_book_prob(r_cand.get("Book Win Prob"), r_cand.get("Odds"))

                r_cand_copy = r_cand.copy()
                r_cand_copy["Clean_Prop"] = p_n
                r_cand_copy["Clean_Line"] = line_f
                r_cand_copy["_ev_val"] = ev_f
                r_cand_copy["_model_prob"] = m_prob_norm
                r_cand_copy["_book_prob"] = b_prob_calc if b_prob_calc is not None else 0.50
                sanitized_plays.append(r_cand_copy)
            except: pass

        if not sanitized_plays:
            st.warning("No valid plays found.")
            st.stop()

        clean_curated_df = pd.DataFrame(sanitized_plays)

        c_mode = st.radio(
            "Filter Conviction Style:",
            [
                "🛡️ High Probability Value (Win Prob ≥ 50%) — Best for Straight Bets & Parlays",
                "🚀 Plus-Money Ceiling Flyers (All High EV Plays — Includes Alt Lines)"
            ],
            index=0
        )

        if "High Probability" in c_mode:
            best_plays = clean_curated_df[
                (clean_curated_df["_model_prob"] >= 0.50) & 
                (clean_curated_df["_book_prob"] >= 0.40) &
                (clean_curated_df["_ev_val"] >= 0.04)
            ].sort_values(by="_ev_val", ascending=False).drop_duplicates(subset=["Player", "Clean_Prop", "Clean_Line", "Book"]).head(15)
        else:
            best_plays = clean_curated_df[
                clean_curated_df["Action"].astype(str).str.contains("MAX|DUAL|ANCHOR|STRONG", case=False, na=False) |
                (clean_curated_df["_ev_val"] >= 0.06)
            ].sort_values(by="_ev_val", ascending=False).drop_duplicates(subset=["Player", "Clean_Prop", "Clean_Line", "Book"]).head(15)

        if best_plays.empty:
            st.info("No plays currently clearing the selected conviction threshold.")
        else:
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
                    
                    bet_str = format_gambly_bet_string(p, side, line, prop)
                    if bet_str and "nan" not in bet_str.lower():
                        b_slip_lines.append(bet_str)
                        
                b_slip_lines = list(dict.fromkeys(b_slip_lines))
                
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

                calc_bp_best = get_or_calculate_book_prob(row.get("Book Win Prob"), row.get("Odds"))
                book_prob = format_percentage(calc_bp_best) if calc_bp_best is not None else "-"
                
                model_prob = format_percentage(row.get("_model_prob"))
                ev_clean = format_percentage(row.get("EV"), is_ev=True)

                st.markdown(f"""
                <div style="background:#0D111A; border:1px solid #1E283D; border-radius:10px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <img src="{headshot_url}" style="width:40px; height:40px; border-radius:50%; object-fit:cover; border:1.5px solid #00DF81;">
                        <div>
                            <div style="font-size:13px; font-weight:900; color:#FFFFFF;">#{rank} {p_name}</div>
                            <div style="font-size:11px; color:#8F9CAE;">{prop_n} [{book_s}]</div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:13px; font-weight:900; color:#00DF81;">{ev_clean} EV</div>
                        <div style="font-size:11px; font-weight:800; color:#FFFFFF;">{side_clean} {line_display} <span style="color:#8F9CAE;">{odds_str}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

elif app_mode == "📋 Master EV Tables":
    st.markdown("<h2 style='color:#FFFFFF; font-weight:900; margin-bottom:12px;'>📋 Master EV Tables</h2>", unsafe_allow_html=True)
    tab_names = [s for s in excel_data.sheet_names if s != "How To Use"]
    tabs = st.tabs(tab_names)

    for i, sheet_name in enumerate(tab_names):
        with tabs[i]:
            df = pd.read_excel(excel_data, sheet_name=sheet_name)
            if df.empty:
                st.info("No data in this sheet.")
                continue

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

            if f_team != "All Teams" and "Team" in df.columns: df = df[df["Team"].astype(str) == f_team]
            if f_pos != "All Positions" and pos_col: df = df[df[pos_col].astype(str).str.contains(f_pos, case=False, na=False)]
            if f_side != "All Sides" and "Side" in df.columns: df = df[df["Side"].astype(str) == f_side]
            if f_act != "All Actions" and act_col: df = df[df["Action"].astype(str).str.contains(f_act, case=False, na=False)]
            if f_search:
                mask = df.astype(str).apply(lambda row: row.str.contains(f_search, case=False).any(), axis=1)
                df = df[mask]

            for col in df.columns:
                if "EV" in col or "Market EV" in col: df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=True))
                elif any(w in col for w in ["Prob", "Probability", "Win Prob"]): df[col] = df[col].apply(lambda x: format_percentage(x, is_ev=False))
                elif any(w in col for w in ["Line", "Projection", "Calibrated Proj"]): df[col] = df[col].apply(format_clean_decimal)
                elif col == "Odds": df[col] = df[col].apply(format_american_odds)

            df = df.drop(columns=[c for c in ["GameSortKey", "SortScore", "CleanName"] if c in df.columns])
            st.dataframe(df, use_container_width=True, height=350)

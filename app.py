import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
import altair as alt

st.set_page_config(page_title="Props.Cash NFL Analytics", layout="wide", page_icon="🏈", initial_sidebar_state="expanded")

# --------------------------------------------------------------------------
# RESPONSIVE, UNRESTRICTED MOBILE-FIRST CSS THEME
# --------------------------------------------------------------------------
st.markdown("""
<style>
/* Pure Dark Background */
.stApp {
    background-color: #07090E !important;
    color: #F8FAFC !important;
}

/* Fluid Container Padding (No Clipping) */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2% !important;
    padding-right: 2% !important;
    max-width: 1300px !important;
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
div[data-baseweb="popover"] {
    background-color: #121824 !important;
}

/* PROPS.CASH PILL TABS */
div[data-testid="stTabs"] {
    background-color: transparent !important;
}
div[data-baseweb="tab-list"] {
    gap: 6px !important;
    border-bottom: none !important;
    padding-bottom: 6px !important;
    flex-wrap: wrap !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    background-color: #151D2A !important;
    border: 1.5px solid #2B3A52 !important;
    border-radius: 22px !important;
    padding: 8px 18px !important;
    margin-right: 6px !important;
    margin-bottom: 6px !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"] p {
    color: #FFFFFF !important;
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    opacity: 1 !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #1F2E45 !important;
    border: 2px solid #00E676 !important;
    box-shadow: 0 0 12px rgba(0, 230, 118, 0.3) !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] p {
    color: #00E676 !important;
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
    width: 20px !important;
    height: 20px !important;
}
div[data-testid="stCheckbox"] label p {
    font-size: 0.85rem !important;
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
# SAFE SCHEMA-COMPLIANT ALTAIR CHART
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

            primary_line = float(grp["Vegas Line"].iloc[0])
            
            trend_points = []
            for idx, val in enumerate(stats_list):
                d_str = date_labels[idx] if idx < len(date_labels) else f"G{idx+1}"
                trend_points.append({
                    "Date": d_str, 
                    "Value": val, 
                    "Result": "Over Hit" if val >= primary_line else "Under Miss",
                    "Baseline": 0.0,
                    "VegasLine": primary_line
                })

            t_df = pd.DataFrame(trend_points)

            max_val = max(t_df["Value"])
            if primary_line <= 3.0: y_max = max(max_val * 1.5, primary_line * 2.0, 3.5)
            else: y_max = max(max_val * 1.35, primary_line * 1.45)

            hit_bars = alt.Chart(t_df).mark_bar(size=28, cornerRadius=0, strokeWidth=0).encode(
                x=alt.X("Date:N", title=None, sort=date_labels, axis=alt.Axis(labelAngle=-90, labelColor="#94A3B8", labelFontSize=10)),
                y=alt.Y("Value:Q", title=None, scale=alt.Scale(domain=[0, y_max]), axis=alt.Axis(labels=True, labelColor="#94A3B8", gridColor="#192333")),
                color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#00E676", "#FF3B30"]), legend=None)
            )

            text_bg = alt.Chart(t_df).mark_text(
                dy=-8, baseline="bottom", fontSize=11.5, fontWeight="900", color="#07090E", stroke="#07090E", strokeWidth=5
            ).encode(
                x=alt.X("Date:N", sort=date_labels),
                y=alt.Y("Baseline:Q"),
                text=alt.Text("Value:Q", format=".1f")
            )

            text_fg = alt.Chart(t_df).mark_text(
                dy=-8, baseline="bottom", fontSize=11.5, fontWeight="900", color="#FFFFFF"
            ).encode(
                x=alt.X("Date:N", sort=date_labels),
                y=alt.Y("Baseline:Q"),
                text=alt.Text("Value:Q", format=".1f")
            )

            ref_line = alt.Chart(t_df).mark_rule(
                color="#FFFFFF", strokeWidth=1.5, strokeDash=[4, 4]
            ).encode(y=alt.Y("VegasLine:Q"))

            final_chart = alt.layer(hit_bars, ref_line, text_bg, text_fg).properties(
                height=190
            ).configure(
                background="transparent"
            ).configure_view(
                strokeWidth=0
            )

            st.altair_chart(final_chart, use_container_width=True)

# --------------------------------------------------------------------------
# FULL PROPS.CASH DASHBOARD RENDERER (WITH ALL PLAYERS LISTED IN DROPDOWN)
# --------------------------------------------------------------------------
def render_props_cash_view(combined_df, is_alt_mode=False):
    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)

    f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
    with f_col1:
        team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist()) if team_col else ["All Teams"]
        selected_team = st.selectbox("Team:", team_list)
    with f_col2:
        pos_list = ["All Positions", "QB", "RB", "WR", "TE"] if pos_col else ["All Positions"]
        selected_pos = st.selectbox("Position:", pos_list)
    with f_col3:
        player_pool = combined_df.copy()
        if team_col and selected_team != "All Teams":
            player_pool = player_pool[player_pool[team_col].astype(str) == selected_team]
        if pos_col and selected_pos != "All Positions":
            player_pool = player_pool[player_pool[pos_col].astype(str).str.contains(selected_pos, case=False, na=False)]
        
        avail_players = sorted(player_pool["Player"].dropna().unique().tolist())
        selected_player = st.selectbox("Select Player:", avail_players if avail_players else ["No Players Found"])

    if not selected_player or selected_player == "No Players Found": return
    p_records = combined_df[combined_df["Player"] == selected_player].copy()
    if p_records.empty: return

    prop_rows = []
    for _, r in p_records.iterrows():
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
                "Player": selected_player, "Team": team_val, "Position": pos_val, "Book": book_val,
                "Prop Name": str(p_name), "Vegas Line": line_f, "Odds": format_american_odds(odds_val),
                "Book Win Prob": book_prob_str, "Model Projection": proj_f, "Grade": grade_val,
                "Opponent": opp_val, "Last 5": last_5_val, "Pick": side_val, "Margin": round(proj_f - line_f, 1),
                "EV": format_percentage(ev_val, is_ev=True), "Win Prob": format_percentage(model_prob),
                "Prob Delta": prob_delta_str, "Action": act_val
            })
        except: pass

    if not prop_rows: return
    props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Book", "Prop Name", "Vegas Line"])

    # TAP-TO-ADD GAMBLY SLIPS
    selected_dk_bets = []
    selected_fd_bets = []

    for _, r_check in props_df.iterrows():
        chk_id = f"chk_{r_check['Player']}_{r_check['Book']}_{r_check['Prop Name']}_{format_clean_decimal(r_check['Vegas Line'])}"
        if st.session_state.get(chk_id, False):
            bet_line = format_gambly_bet_string(r_check['Player'], r_check['Pick'], r_check['Vegas Line'], r_check['Prop Name'])
            if r_check['Book'] == 'DraftKings': selected_dk_bets.append(bet_line)
            elif r_check['Book'] == 'FanDuel': selected_fd_bets.append(bet_line)

    selected_dk_bets = list(dict.fromkeys(selected_dk_bets))
    selected_fd_bets = list(dict.fromkeys(selected_fd_bets))

    with st.expander("📋 Interactive Gambly Slips (Tap '➕ Add to Slip' Below)", expanded=(len(selected_dk_bets) > 0 or len(selected_fd_bets) > 0)):
        col_clear, _ = st.columns([1, 4])
        with col_clear:
            if st.button("🗑️ Clear Selected Slips", key=f"clr_slips_{is_alt_mode}"):
                for k in list(st.session_state.keys()):
                    if k.startswith("chk_"): st.session_state[k] = False
                st.rerun()

        col_dk_slip, col_fd_slip = st.columns(2)
        with col_dk_slip:
            st.markdown("<span style='color:#00E676; font-weight:800;'>🟢 DraftKings Slip</span>", unsafe_allow_html=True)
            if selected_dk_bets: st.code("\n".join(selected_dk_bets), language="text")
            else: st.caption("No DraftKings bets selected yet.")
        with col_fd_slip:
            st.markdown("<span style='color:#0091FF; font-weight:800;'>🔵 FanDuel Slip</span>", unsafe_allow_html=True)
            if selected_fd_bets: st.code("\n".join(selected_fd_bets), language="text")
            else: st.caption("No FanDuel bets selected yet.")

    team_tag = props_df["Team"].iloc[0]
    depth_tag = props_df["Position"].iloc[0]
    player_depth_label = f"({depth_tag})" if depth_tag else ""
    headshot_url = get_headshot_url(selected_player)

    grouped_props = props_df.groupby("Prop Name")
    prop_names_list = list(grouped_props.groups.keys())

    # HERO PLAYER CARD
    st.markdown(f"""
    <div style="background:#0D111A; border:1px solid #1E283D; border-radius:14px; padding:16px 20px; margin-bottom:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-size:1.60rem; font-weight:900; color:#FFFFFF;">{selected_player}</div>
                <div style="font-size:0.95rem; color:#8F9CAE; font-weight:700;">{team_tag} • {player_depth_label}</div>
            </div>
            <div>
                <img src="{headshot_url}" style="width:75px; height:75px; border-radius:50%; object-fit:cover; border:2.5px solid #00E676; background:#1C2436;">
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if len(prop_names_list) > 1:
        tabs_obj = st.tabs([pn for pn in prop_names_list])
        for t_idx, prop_name in enumerate(prop_names_list):
            with tabs_obj[t_idx]:
                render_props_cash_tab_content(selected_player, prop_name, grouped_props.get_group(prop_name))
    else:
        render_props_cash_tab_content(selected_player, prop_names_list[0], grouped_props.get_group(prop_names_list[0]))

def render_props_cash_tab_content(player, prop_name, p_group):
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

        # UNIFIED COCKPIT CARD
        st.markdown(f"""
        <div style="background:#0C111C; border:1.5px solid #1D263B; border-radius:12px; padding:16px 18px; margin-bottom:12px; box-shadow:0 4px 10px rgba(0,0,0,0.3);">
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

        render_exact_props_cash_chart(prop_name, p_group)

        col_dk, col_fd = st.columns(2)
        with col_dk:
            if not dk_row.empty:
                r_b = dk_row.iloc[0]
                chk_k = f"m_chk_{r_b['Player']}_DK_{r_b['Prop Name']}_{format_clean_decimal(r_b['Vegas Line'])}"
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
                chk_k = f"m_chk_{r_b['Player']}_FD_{r_b['Prop Name']}_{format_clean_decimal(r_b['Vegas Line'])}"
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
    if ou_df.empty: st.warning("No Over/Under props found in this workbook.")
    else: render_props_cash_view(ou_df, is_alt_mode=False)

elif app_mode == "⚡ Props.Cash: Alt Lines":
    alt_df = load_visualizer_data(["Top DK Alt Lines", "Top FD Alt Lines"])
    if alt_df.empty: st.warning("No Alt Line props found in this workbook.")
    else: render_props_cash_view(alt_df, is_alt_mode=True)

elif app_mode == "💎 Best of the Best (Top Edges)":
    st.markdown("<h2 style='color:#FFFFFF; font-weight:900; margin-bottom:8px;'>💎 Top Conviction Plays</h2>", unsafe_allow_html=True)
    all_curated = load_visualizer_data(["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"])
    
    if all_curated.empty:
        st.warning("No plays available.")
    else:
        san

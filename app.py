import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
import altair as alt

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")

# --------------------------------------------------------------------------
# PROPS.CASH HIGH-CONTRAST CSS THEME
# --------------------------------------------------------------------------
st.markdown("""
<style>
/* Clean Mobile System Font */
html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    background-color: #07090E !important;
    color: #F8FAFC !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Crisp Headings */
h1, h2, h3, h4, h5, h6 {
    color: #F8FAFC !important;
    font-weight: 800 !important;
    letter-spacing: 0.3px !important;
}

/* TARGET SPECIFIC STREAMLIT TABS (KILLS RED LINE, FORCES BRIGHT WHITE TABS) */
[data-testid="stTabs"] {
    background-color: transparent !important;
}
[data-testid="stTabs"] div[data-baseweb="tab-list"] {
    gap: 8px !important;
    border-bottom: none !important;
    background-color: transparent !important;
    padding-bottom: 6px !important;
}
[data-testid="stTabs"] div[data-baseweb="tab-highlight"],
[data-testid="stTabs"] div[data-baseweb="tab-border"] {
    display: none !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background-color: #151D2A !important;
    border: 1.5px solid #2B3A52 !important;
    border-radius: 22px !important;
    padding: 8px 18px !important;
    margin-right: 6px !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] * {
    color: #FFFFFF !important;
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    opacity: 1 !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #1F2E45 !important;
    border: 2px solid #00E676 !important;
    box-shadow: 0 0 12px rgba(0, 230, 118, 0.3) !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] * {
    color: #00E676 !important;
}

/* Selectbox Styling */
div[data-baseweb="select"] > div {
    background-color: #121824 !important;
    border: 1.5px solid #23304A !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
}
div[data-baseweb="select"] * {
    color: #FFFFFF !important;
    font-weight: 700 !important;
}
div[data-baseweb="popover"] {
    background-color: #121824 !important;
}

/* Checkbox Styling for Inside Book Cards */
div[data-testid="stCheckbox"] {
    background: #111827 !important;
    border: 1.5px solid #243048 !important;
    border-top: none !important;
    border-bottom-left-radius: 12px !important;
    border-bottom-right-radius: 12px !important;
    padding: 8px 16px !important;
    margin-top: -8px !important;
    margin-bottom: 10px !important;
}
div[data-testid="stCheckbox"] label span:first-child {
    width: 18px !important;
    height: 18px !important;
    margin-right: 8px !important;
}
div[data-testid="stCheckbox"] label p {
    font-size: 0.88rem !important;
    font-weight: 800 !important;
    color: #00E676 !important;
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
    return "https://a.espncdn.com/combiner/i?img=/i/headshots/nfl/players/full/default.png&w=150&h=150"

def get_book_styled(book_name):
    b = str(book_name).strip()
    if "draftkings" in b.lower() or "dk" in b.lower():
        return '<span style="color:#00E676; font-weight:800; letter-spacing:0.3px;">DraftKings</span>'
    elif "fanduel" in b.lower() or "fd" in b.lower():
        return '<span style="color:#0091FF; font-weight:800; letter-spacing:0.3px;">FanDuel</span>'
    return f"<span style='font-weight:700; color:#FFFFFF;'>{b}</span>"

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
        return f'<span style="background-color:#FEF3C7; color:#92400E; padding:3px 8px; border-radius:8px; font-weight:800; font-size:11px; letter-spacing:0.3px; margin-left:6px;">{line_adv_note}</span>'
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
        except:
            pass

    if pd.notna(odds_raw) and str(odds_raw).strip().lower() not in ["-", "nan", "none", "", "unposted"]:
        try:
            o_clean = str(odds_raw).replace("+", "").strip()
            o_num = float(o_clean)
            if o_num >= 100: return 100.0 / (o_num + 100.0)
            elif o_num <= -100: return abs(o_num) / (abs(o_num) + 100.0)
            elif 1.01 <= o_num < 50.0: return 1.0 / o_num
        except:
            pass
    return None

# --------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------------------
st.sidebar.title("🏈 NFL Quant Engine")
file_names = [x["filename"] for x in dated_files]
selected_file = st.sidebar.selectbox("📅 Select Slate:", file_names, index=0)
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

def render_compact_book_box(r, chk_key):
    book_html = get_book_styled(r["Book"])
    star_badge = get_best_line_badge_html(r["Line_Adv_Note"])
    action_text = r["Action"]
    
    margin_val = r["Margin"]
    is_pos = margin_val >= 0
    margin_arrow = "▲" if is_pos else "▼"
    margin_bg = "#00E67614" if is_pos else "#FF3B3014"
    margin_border = "#00E67699" if is_pos else "#FF3B3099"
    margin_color = "#00E676" if is_pos else "#FF3B30"

    odds_str = f"({r['Odds']})" if r['Odds'] != "-" else ""
    prob_delta_str = f"({r['Prob Delta']})" if r['Prob Delta'] else ""

    card_html = (
        f'<div style="background:#111827; border:1.5px solid #243048; border-top-left-radius:12px; border-top-right-radius:12px; padding:14px 16px; border-bottom:none;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
        f'<div style="display:flex; align-items:center;">{book_html} {star_badge}</div>'
        f'<span style="font-size:11px; font-weight:700; color:#FFFFFF; background:#1E293B; padding:3px 9px; border-radius:4px; letter-spacing:0.3px;">{action_text}</span>'
        f'</div>'
        f'<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">'
        f'<span style="font-size:1.20rem; font-weight:800; color:#FFFFFF; letter-spacing:0.4px;">{r["Pick"]} {format_clean_decimal(r["Vegas Line"])} <span style="font-size:0.9rem; font-weight:600; color:#94A3B8;">{odds_str}</span></span>'
        f'<span style="font-size:1.20rem; font-weight:800; color:#00E676; letter-spacing:0.3px;">{r["EV"]} EV</span>'
        f'</div>'
        f'<div style="display:flex; justify-content:space-between; font-size:0.85rem; font-weight:600; color:#94A3B8; letter-spacing:0.2px; margin-bottom:10px;">'
        f'<span>Model: <b style="color:#FFFFFF; font-weight:700;">{r["Win Prob"]}</b></span>'
        f'<span>Book: <b style="color:#FFFFFF; font-weight:700;">{r["Book Win Prob"]}</b> <span style="color:#00E676; font-weight:800;">{prob_delta_str}</span></span>'
        f'</div>'
        f'<div style="display:flex; align-items:center; justify-content:space-between; background:{margin_bg}; border:1.5px solid {margin_border}; border-radius:6px; padding:5px 10px;">'
        f'<span style="font-size:11.5px; font-weight:700; color:{margin_color}; letter-spacing:0.3px;">Margin vs Line:</span>'
        f'<span style="font-size:12px; font-weight:800; color:{margin_color}; letter-spacing:0.4px;">{margin_arrow} {margin_val:+0.1f} (Proj: {format_clean_decimal(r["Model Projection"])})</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    st.checkbox("➕ Add to Slip", key=chk_key)

def render_prop_hit_rate_chart_compact(base_prop_name, grp):
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

            max_val = max(t_df["Value"]) if not t_df.empty else 5.0
            max_line = grp["Vegas Line"].max()
            y_max = max(max_val * 1.3, max_line * 1.4, 3.0)

            hit_bars = alt.Chart(t_df).mark_bar(size=18, cornerRadius=3, strokeWidth=0).encode(
                x=alt.X("Date:N", title=None, sort=date_labels, axis=alt.Axis(labelAngle=0, labelFontWeight="bold", labelColor="#94A3B8", labelFontSize=9.5)),
                y=alt.Y("Value:Q", title=None, scale=alt.Scale(domain=[0, y_max]), axis=alt.Axis(labels=False, ticks=False, grid=False)),
                color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#00E676", "#FF3B30"]), legend=None)
            )

            # Numbers safely above baseline
            text_fg = alt.Chart(t_df).mark_text(dy=-12, fontSize=10.5, fontWeight="bold", color="#FFFFFF").encode(
                x=alt.X("Date:N", sort=date_labels), y=alt.Y("Value:Q"), text=alt.Text("Value:Q", format=".1f")
            )

            # Prominent baseline rule
            ref_line = alt.Chart(pd.DataFrame({"y": [primary_line]})).mark_rule(color="#00E676", strokeWidth=2.0, strokeDash=[4, 4]).encode(y="y:Q")

            compact_chart = (hit_bars + ref_line + text_fg).properties(
                height=130, width=310
            ).configure(background="transparent").configure_view(strokeWidth=0)

            return compact_chart
    return None

# FULL PROPS.CASH DASHBOARD
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
        prop_choices = ["All

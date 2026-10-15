import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
import altair as alt
from openpyxl import load_workbook
import pytz

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")

# --------------------------------------------------------------------------
# PROPS.CASH THEME & HEAD-TO-HEAD CSS
# --------------------------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    background-color: #07090E !important;
    color: #F8FAFC !important;
}

/* STYLES THE GAMBLY EXPANDER TO LOOK SLEEK AND INTENTIONAL */
div[data-testid="stExpander"] {
    background-color: #0C111C !important;
    border: 1.5px solid #1E283D !important;
    border-radius: 14px !important;
    margin-bottom: 16px !important;
}
div[data-testid="stExpander"] summary {
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    padding: 10px 16px !important;
}

/* STREAMLIT TABS (WORKS CLEANLY ACROSS ALL SCREENS) */
[data-testid="stTabs"] {
    background-color: transparent !important;
}
[data-testid="stTabs"] div[data-baseweb="tab-list"] {
    gap: 8px !important;
    border-bottom: 2px solid #1E283D !important;
    background-color: transparent !important;
    padding-bottom: 4px !important;
    margin-bottom: 12px !important;
}
[data-testid="stTabs"] div[data-baseweb="tab-highlight"],
[data-testid="stTabs"] div[data-baseweb="tab-border"] {
    display: none !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background-color: #121824 !important;
    border: 1.5px solid #23304A !important;
    border-radius: 12px !important;
    padding: 6px 16px !important;
    margin-right: 4px !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] * {
    color: #FFFFFF !important;
    font-size: 0.90rem !important;
    font-weight: 800 !important;
    opacity: 1 !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #1E293B !important;
    border: 2px solid #00E676 !important;
    box-shadow: 0 0 10px rgba(0, 230, 118, 0.3) !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] * {
    color: #00E676 !important;
}

/* Crisp Headings */
h1, h2, h3, h4, h5, h6 {
    color: #F8FAFC !important;
    font-weight: 800 !important;
    letter-spacing: 0.3px !important;
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

/* Flush Checkbox inside Book Card */
div[data-testid="stCheckbox"] {
    background: #111827 !important;
    border: 1.5px solid #243048 !important;
    border-top: none !important;
    border-bottom-left-radius: 12px !important;
    border-bottom-right-radius: 12px !important;
    padding: 8px 16px !important;
    margin-top: -6px !important;
    margin-bottom: 16px !important;
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

# Anchor for Back to Top
st.markdown("<div id='top_of_page'></div>", unsafe_allow_html=True)

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
        return '<span style="color:#00E676; font-weight:900; letter-spacing:0.3px;">🟢 DraftKings</span>'
    elif "fanduel" in b.lower() or "fd" in b.lower():
        return '<span style="color:#0091FF; font-weight:900; letter-spacing:0.3px;">🔵 FanDuel</span>'
    return f"<span style='font-weight:800; color:#FFFFFF;'>{b}</span>"

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
        clean_str = str(val).replace("+", "").strip()
        f_val = int(float(clean_str))
        return f"+{f_val}" if f_val > 0 else f"{f_val}"
    except:
        return str(val)

def get_best_line_badge_html(line_adv_note):
    if line_adv_note:
        return f'<span style="background-color:#FEF3C7; color:#92400E; padding:3px 8px; border-radius:8px; font-weight:800; font-size:11px; letter-spacing:0.3px; margin-left:6px;">{line_adv_note}</span>'
    return ""

def format_short_gametime(raw_time_str):
    if not raw_time_str or pd.isna(raw_time_str) or str(raw_time_str).strip() in ["-", "nan", ""]:
        return ""
    try:
        dt = pd.to_datetime(raw_time_str)
        day_str = dt.strftime("%a %-m-%-d")
        hour_str = dt.strftime("%-I:%M%p").replace(":00", "").replace("AM", "am").replace("PM", "pm")
        return f"{day_str} @ {hour_str}"
    except:
        return str(raw_time_str).replace(" EST", "")

def extract_sanitized_prop_and_line(r):
    p_val = r.get("Prop")
    is_alt = False
    if pd.isna(p_val) or str(p_val).strip().lower() in ["nan", "none", "", "unposted"]:
        p_val = r.get("Milestone (Alt Line)")
        is_alt = True

    if pd.isna(p_val) or str(p_val).strip().lower() in ["nan", "none", "", "unposted"]:
        return None, None, None

    raw_str = str(p_val).strip()
    line_val = r.get("Line")

    if is_alt:
        m_over = re.search(r"Over\s*(\d+(\.\d+)?)", raw_str, re.IGNORECASE)
        m_plus = re.search(r"(\d+(\.\d+)?)\+", raw_str)

        if pd.notna(line_val) and str(line_val).strip().lower() not in ["nan", "none", "", "unposted"]:
            try: line_f = float(line_val)
            except: line_f = None
        elif m_over:
            line_f = float(m_over.group(1))
        elif m_plus:
            line_f = float(m_plus.group(1))
        else:
            return None, None, None

        pure_prop = re.sub(r"^\d+\+\s*", "", raw_str)
        pure_prop = re.sub(r"\(.*?\)", "", pure_prop).strip()
        display_label = f"{int(line_f) if line_f.is_integer() else line_f}+ {pure_prop}"
        return pure_prop, line_f, display_label

    else:
        if pd.isna(line_val) or str(line_val).strip().lower() in ["nan", "none", "", "unposted"]:
            return None, None, None
        try:
            line_f = float(line_val)
        except:
            return None, None, None

        clean_p = re.sub(r"\(.*?\)", "", raw_str).strip()
        display_label = f"{clean_p}"
        return clean_p, line_f, display_label

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

# TRUE WORKBOOK IMPORT / CREATION TIMESTAMP
@st.cache_data(ttl=60)
def get_file_imported_time(f_path):
    if not os.path.exists(f_path):
        return "Recently"
    try:
        wb_meta = load_workbook(f_path, read_only=True)
        created_dt = wb_meta.properties.created or wb_meta.properties.modified
        if created_dt:
            est_dt = created_dt - timedelta(hours=4)
            return est_dt.strftime("%b %-d, %-I:%M %p EST")
    except:
        pass
    mtime = os.path.getmtime(f_path)
    return datetime.fromtimestamp(mtime).strftime("%b %-d, %-I:%M %p EST")

file_imported_str = get_file_imported_time(file_path)

screens_dict = {
    "📊 Pro Visualizer: Over / Under": "Over / Under",
    "⚡ Pro Visualizer: Alt Lines": "Alt Lines",
    "💎 Best of the Best (Top Edges)": "Top Edges",
    "📋 Master EV Tables": "EV Tables"
}

# PERSISTENT NAVIGATION STATE
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = list(screens_dict.keys())[0]

app_mode = st.sidebar.radio("📱 Screen:", list(screens_dict.keys()), index=list(screens_dict.keys()).index(st.session_state["app_mode"]))
st.session_state["app_mode"] = app_mode

def render_screen_header(title_text):
    other_screens = [k for k in screens_dict.keys() if k != app_mode]
    
    # RENDER STYLIZED HTML FORM BUTTONS SPANNING THE WIDTH OF THE PAGE
    nav_html = '<div style="display:flex; justify-content:space-between; align-items:center; width:100%; gap:12px; margin-bottom:18px;">'
    for s_key in other_screens:
        screen_label = screens_dict[s_key]
        nav_html += f'''
            <form action="" method="get" style="flex:1; margin:0;">
                <input type="hidden" name="screen" value="{s_key}">
                <button type="submit" style="
                    width: 100%;
                    background-color: #151D2A;
                    border: 1.5px solid #2B3A52;
                    color: #FFFFFF;
                    padding: 10px 16px;
                    border-radius: 12px;
                    font-weight: 800;
                    font-size: 0.9rem;
                    cursor: pointer;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                    letter-spacing: 0.3px;
                ">📌 Go to {screen_label}</button>
            </form>
        '''
    nav_html += '</div>'
    st.markdown(nav_html, unsafe_allow_html=True)

    # Handle query param navigation
    query_screen = st.query_params.get("screen")
    if query_screen and query_screen in screens_dict and query_screen != app_mode:
        st.session_state["app_mode"] = query_screen
        st.query_params.clear()
        st.rerun()

    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown(f"<h1 style='color:#FFFFFF; font-weight:900; margin-bottom:12px;'>{title_text}</h1>", unsafe_allow_html=True)
    with h_col2:
        st.markdown(
            f"<div style='text-align:right; margin-top:8px;'>"
            f"<div style='background:#121824; border:1px solid #23304A; border-radius:10px; padding:6px 12px; display:inline-block; text-align:right;'>"
            f"<div style='color:#94A3B8; font-size:10.5px; font-weight:800; letter-spacing:0.5px; text-transform:uppercase;'>Last Updated</div>"
            f"<div style='color:#FFFFFF; font-size:12.5px; font-weight:800; margin-top:1px;'>{file_imported_str}</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
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

# PROPS.CASH ADAPTIVE CHART
def render_props_cash_chart(row, last_5_raw):
    primary_line = float(row["Vegas Line"])
    stats_list = []
    if last_5_raw and last_5_raw not in ["-", "nan", ""]:
        try:
            stats_list = [float(x.strip()) for x in str(last_5_raw).split(",") if x.strip()]
        except: pass

    if not stats_list:
        return None

    total_g = len(stats_list)
    date_labels = []
    if len(dated_files) >= total_g:
        date_labels = [x["label"] for x in reversed(dated_files[:total_g])]
    else:
        base_d = datetime.now()
        date_labels = [(base_d - timedelta(days=(total_g - i)*7)).strftime("%-m/%-d") for i in range(total_g)]

    trend_points = []
    for idx, val in enumerate(stats_list):
        d_str = date_labels[idx] if idx < len(date_labels) else f"G{idx+1}"
        trend_points.append({"Date": d_str, "Value": val})

    t_df = pd.DataFrame(trend_points)
    t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= primary_line else "Under Miss")

    max_val = max(t_df["Value"]) if not t_df.empty else 5.0
    y_max = max(max_val * 1.45, primary_line * 1.55, 3.5)

    hit_bars = alt.Chart(t_df).mark_bar(size=20, cornerRadius=3, strokeWidth=0).encode(
        x=alt.X("Date:N", title=None, sort=date_labels, axis=alt.Axis(labelAngle=0, labelFontWeight="bold", labelColor="#94A3B8", labelFontSize=10)),
        y=alt.Y("Value:Q", title=None, scale=alt.Scale(domain=[0, y_max]), axis=alt.Axis(labels=False, ticks=False, grid=False)),
        color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#00E676", "#FF3B30"]), legend=None)
    )

    text_bg = alt.Chart(t_df).mark_text(
        dy=-10, fontSize=11, fontWeight="bold", color="#0C111C", stroke="#0C111C", strokeWidth=5, strokeJoin="round"
    ).encode(x=alt.X("Date:N", sort=date_labels), y=alt.Y("Value:Q"), text=alt.Text("Value:Q", format=".1f"))

    text_fg = alt.Chart(t_df).mark_text(dy=-10, fontSize=11, fontWeight="bold", color="#FFFFFF").encode(
        x=alt.X("Date:N", sort=date_labels), y=alt.Y("Value:Q"), text=alt.Text("Value:Q", format=".1f")
    )

    ref_line = alt.Chart(pd.DataFrame({"y": [primary_line]})).mark_rule(
        color="#FFFFFF", strokeWidth=1.8, strokeDash=[4, 4]
    ).encode(y="y:Q")

    base_axis = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#FFFFFF", strokeWidth=2.5).encode(y="y:Q")

    return (base_axis + hit_bars + ref_line + text_bg + text_fg).properties(
        height=140, width=320
    ).configure(background="transparent").configure_view(strokeWidth=0)

# SINGLE PROPS.CASH BOOK CARD
def render_props_cash_book_card(r, player, player_depth_label, headshot_url, chk_key, is_alt_mode=False):
    book_html = get_book_styled(r["Book"])
    star_badge = get_best_line_badge_html(r.get("Line_Adv_Note", ""))
    grade_char = r.get("Grade", "A")
    grade_color = "#00E676" if grade_char in ['A', 'B'] else ("#F59E0B" if grade_char == 'C' else "#FF3B30")

    game_str = r.get("Game", "")
    short_time = format_short_gametime(r.get("Game Time", ""))
    time_and_matchup = f"{short_time} • {game_str}" if short_time else game_str
    game_script = r.get("Game Script", "Standard")
    
    role_alert = str(r.get("Role Alert", "")).strip()
    role_badge = f'<div style="font-size:0.80rem; color:#F59E0B; font-weight:800; letter-spacing:0.3px; margin-bottom:2px;">⚡ {role_alert}</div>' if role_alert and role_alert.lower() not in ["nan", "none", "", "null"] else ""
    game_badge = f'<div style="font-size:0.82rem; color:#94A3B8; font-weight:700; margin-bottom:2px;">{time_and_matchup} • {game_script}</div>' if time_and_matchup else ""

    last_5_raw = str(r.get("Last 5", "")).strip()
    hit_rate_display = "-"
    hit_rate_color = "#00E676"
    if last_5_raw and last_5_raw not in ["-", "nan", ""]:
        try:
            s_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
            if s_list:
                hits = sum(x >= float(r["Vegas Line"]) for x in s_list)
                pct = round((hits / len(s_list)) * 100)
                hit_rate_display = f"▲ {pct}%"
                hit_rate_color = "#00E676" if pct >= 50 else "#FF3B30"
        except: pass

    margin_val = r["Margin"]
    is_pos = margin_val >= 0
    margin_arrow = "▲" if is_pos else "▼"
    margin_color = "#00E676" if is_pos else "#FF3B30"

    raw_bp = r.get("_raw_book_prob")
    try:
        val_clean = float(str(raw_bp).replace("%", "").strip())
        norm_bp = val_clean if val_clean <= 1.0 else val_clean / 100.0
    except:
        norm_bp = 0.50

    b_prob_color = "#00E676" if norm_bp >= 0.50 else "#FF3B30"

    raw_mp = r.get("Win Prob")
    try:
        val_clean_m = float(str(raw_mp).replace("%", "").strip())
        norm_mp = val_clean_m if val_clean_m <= 1.0 else val_clean_m / 100.0
    except:
        norm_mp = 0.50
    m_prob_color = "#00E676" if norm_mp >= 0.50 else "#FF3B30"

    hist_sig = str(r.get("History Signal", "-")).strip()
    hist_badge = ""
    if "IMPROVED" in hist_sig:
        hist_badge = '<span style="background:#00E67620; color:#00E676; border:1px solid #00E676; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:800; margin-left:6px;">📈 PRICE IMPROVED</span>'
    elif "WORSENED" in hist_sig:
        hist_badge = '<span style="background:#F59E0B20; color:#F59E0B; border:1px solid #F59E0B; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:800; margin-left:6px;">📉 PRICE WORSENED</span>'

    live_sig = str(r.get("Live Signal", "-")).strip()
    live_badge = ""
    if "DUAL CONFIRMED" in live_sig:
        live_badge = '<span style="background:#8B5CF620; color:#A78BFA; border:1px solid #8B5CF6; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:800; margin-left:6px;">⚡ DUAL CONFIRMED</span>'

    odds_raw_val = r.get("Odds", "-")
    if odds_raw_val in ["-", "", "nan", "None"]:
        odds_str = "<span style='font-size:0.85rem; color:#94A3B8; font-weight:600;'>(Unposted Line)</span>"
    else:
        odds_str = f"<span style='font-size:0.92rem; font-weight:600; color:#94A3B8;'>({odds_raw_val})</span>"

    line_display_clean = r.get("Clean_Display_Line", "")

    card_top_html = (
        f'<div style="background:#0C111C; border:1.5px solid #1E283D; border-top-left-radius:14px; border-top-right-radius:14px; padding:16px 18px; border-bottom:none;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
        f'<div style="display:flex; align-items:center;">{book_html} {star_badge} {hist_badge} {live_badge}</div>'
        f'<span style="font-size:11px; font-weight:700; color:#FFFFFF; background:#1E293B; padding:3px 9px; border-radius:4px; letter-spacing:0.3px;">{r["Action"]}</span>'
        f'</div>'
        
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">'
        f'<div>'
        f'{game_badge}'
        f'{role_badge}'
        f'<div style="font-size:1.35rem; font-weight:900; color:#FFFFFF; letter-spacing:0.3px;">{player}</div>'
        f'<div style="font-size:0.92rem; color:#00E676; font-weight:800; letter-spacing:0.3px; margin-top:2px;">{player_depth_label}</div>'
        f'</div>'
        f'<div style="position:relative;">'
        f'<img src="{headshot_url}" style="width:68px; height:68px; border-radius:50%; object-fit:cover; border:2.5px solid #00E676; background:#1C2436; box-shadow:0 0 10px rgba(0,230,118,0.25);">'
        f'<div style="position:absolute; bottom:-4px; right:-4px; width:25px; height:25px; border-radius:50%; background:#161E2E; border:2px solid {grade_color}; display:flex; align-items:center; justify-content:center; font-size:11.5px; font-weight:900; color:{grade_color}; box-shadow:0 0 6px rgba(0,0,0,0.6);">{grade_char}</div>'
        f'</div>'
        f'</div>'

        f'<div style="background:#111827; border:1px solid #1E283D; border-radius:10px; padding:10px 14px; margin-bottom:14px;">'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; margin-bottom:8px; border-bottom:1px solid #1E283D; padding-bottom:8px;">'
        f'<div><div style="font-size:10px; color:#94A3B8; font-weight:800; letter-spacing:0.4px;">LINE</div><div style="font-size:16px; font-weight:900; color:#FFFFFF;">{line_display_clean}</div></div>'
        f'<div><div style="font-size:10px; color:#94A3B8; font-weight:800; letter-spacing:0.4px;">PROJECTION</div><div style="font-size:16px; font-weight:900; color:#00E676;">{format_clean_decimal(r["Model Projection"])}</div></div>'
        f'<div><div style="font-size:10px; color:#94A3B8; font-weight:800; letter-spacing:0.4px;">MARGIN</div><div style="font-size:16px; font-weight:900; color:{margin_color};">{margin_arrow} {margin_val:+0.1f}</div></div>'
        f'</div>'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px;">'
        f'<div><div style="font-size:10px; color:#94A3B8; font-weight:800; letter-spacing:0.4px;">HIT RATE</div><div style="font-size:15px; font-weight:900; color:{hit_rate_color};">{hit_rate_display}</div></div>'
        f'<div><div style="font-size:10px; color:#94A3B8; font-weight:800; letter-spacing:0.4px;">MODEL WIN</div><div style="font-size:15px; font-weight:900; color:{m_prob_color};">{r["Win Prob"]}</div></div>'
        f'<div><div style="font-size:10px; color:#94A3B8; font-weight:800; letter-spacing:0.4px;">BOOK WIN</div><div style="font-size:15px; font-weight:900; color:{b_prob_color};">{r["Book Win Prob"]}</div></div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(card_top_html, unsafe_allow_html=True)

    chart_obj = render_props_cash_chart(r, last_5_raw)
    if chart_obj:
        st.altair_chart(chart_obj, use_container_width=True)

    card_bot_html = (
        f'<div style="background:#0C111C; border:1.5px solid #1E283D; border-top:none; padding:10px 18px 14px 18px; border-bottom-left-radius:14px; border-bottom-right-radius:14px;">'
        f'<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px;">'
        f'<span style="font-size:1.15rem; font-weight:900; color:#FFFFFF; letter-spacing:0.3px;">{line_display_clean} {odds_str}</span>'
        f'<span style="font-size:1.20rem; font-weight:900; color:#00E676; letter-spacing:0.3px;">{r["EV"]} EV</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(card_bot_html, unsafe_allow_html=True)
    st.checkbox(f"➕ Add to {r['Book']} Slip", key=chk_key)

# MASTER VISUALIZER WITH MATCHUP & DETAILED CATEGORY FILTERS
def render_prop_visualizer(combined_df, is_alt_mode=False):
    team_col = next((c for c in ["Team", "team"] if c in combined_df.columns), None)
    pos_col = next((c for c in ["Pos", "Position"] if c in combined_df.columns), None)
    game_col = next((c for c in ["Game", "game"] if c in combined_df.columns), None)

    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([1.2, 1, 1, 1, 1.2])
    with f_col1:
        matchup_list = ["All Matchups"] + sorted(combined_df[game_col].dropna().astype(str).unique().tolist()) if game_col else ["All Matchups"]
        selected_matchup = st.selectbox("⚔️ Matchup:", matchup_list, key=f"m_{is_alt_mode}")
    with f_col2:
        team_list = ["All Teams"] + sorted(combined_df[team_col].dropna().astype(str).unique().tolist()) if team_col else ["All Teams"]
        selected_team = st.selectbox("🏈 Team:", team_list, key=f"t_{is_alt_mode}")
    with f_col3:
        selected_pos = st.selectbox("🎯 Position:", ["All Positions", "QB", "RB", "WR", "TE"], key=f"p_{is_alt_mode}")
    with f_col4:
        selected_book = st.selectbox("🎰 Sportsbook:", ["All Sportsbooks", "DraftKings", "FanDuel"], key=f"b_{is_alt_mode}")
    with f_col5:
        prop_categories = [
            "All Props",
            "Passing Yards",
            "Pass Attempts",
            "Rushing Yards",
            "Rush Attempts",
            "Receiving Yards",
            "Receptions"
        ]
        selected_prop_filter = st.selectbox("📊 Prop Category:", prop_categories, key=f"cat_{is_alt_mode}")

    filtered_df = combined_df.copy()
    if game_col and selected_matchup != "All Matchups":
        filtered_df = filtered_df[filtered_df[game_col].astype(str) == selected_matchup]
    if team_col and selected_team != "All Teams":
        filtered_df = filtered_df[filtered_df[team_col].astype(str) == selected_team]
    if pos_col and selected_pos != "All Positions":
        filtered_df = filtered_df[filtered_df[pos_col].astype(str).str.contains(selected_pos, case=False, na=False)]
    if selected_book != "All Sportsbooks":
        filtered_df = filtered_df[filtered_df["Book"].astype(str) == selected_book]

    prop_rows = []
    for _, r in filtered_df.iterrows():
        if is_alt_mode:
            odds_check = str(r.get("Odds", "-")).strip()
            if odds_check in ["-", "", "nan", "None"]:
                continue

        p_name, line_f, clean_display_line = extract_sanitized_prop_and_line(r)
        if not p_name or line_f is None: continue

        proj = r.get("Calibrated Proj")
        if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]:
            proj = r.get("Projection")
        if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]: continue

        try:
            proj_f = float(proj)
            player_name = str(r["Player"]).strip()
            team_name = str(r.get(team_col, "")).strip()
            pos_val = str(r.get(pos_col, "")).strip()
            book = str(r.get("Book", "DraftKings")).strip()
            grade_val = str(r.get("Grade", "A")).strip()
            game_str = str(r.get("Game", "")).strip()
            game_time_str = str(r.get("Game Time", "")).strip()
            
            raw_role = str(r.get("Role Alert", "")).strip()
            role_alert = "" if raw_role.lower() in ["nan", "none", "", "null"] else raw_role
            
            side = str(r.get("Side", "Over")).strip()
            if not side or side.lower() in ["nan", "none"]: side = "Over"
            
            odds_val = r.get("Odds", "-")
            book_prob_raw = r.get("Book Win Prob", "-")
            model_prob = r.get("Model Win Prob", "-")
            ev = r.get("EV", "-")
            act = str(r.get("Action", "-"))
            last_5 = str(r.get("Last 5", "-"))
            script_env = str(r.get("Game Script", "Standard"))
            hist_sig = str(r.get("History Signal", "-"))
            live_sig = str(r.get("Live Signal", "-"))

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

            margin_calc = round(proj_f - line_f, 1) if side == "Over" else round(line_f - proj_f, 1)

            prop_rows.append({
                "Player": player_name,
                "Team": team_name,
                "Position": pos_val,
                "Book": book,
                "Prop Label": f"{p_name} [{book}]",
                "Prop Name": str(p_name),
                "Clean_Display_Line": clean_display_line,
                "Vegas Line": line_f,
                "Odds": format_american_odds(odds_val),
                "Book Win Prob": book_prob_str,
                "_raw_book_prob": calc_bp if calc_bp is not None else 0.5,
                "Model Projection": proj_f,
                "Grade": grade_val,
                "Game": game_str,
                "Game Time": game_time_str,
                "Role Alert": role_alert,
                "Last 5": last_5,
                "Pick": side,
                "Margin": margin_calc,
                "EV": format_percentage(ev, is_ev=True),
                "Win Prob": format_percentage(model_prob),
                "Prob Delta": prob_delta_str,
                "Action": act,
                "Game Script": script_env,
                "History Signal": hist_sig,
                "Live Signal": live_sig
            })
        except:
            pass

    if not prop_rows:
        st.info("No props matching these filter criteria.")
        return

    raw_props_df = pd.DataFrame(prop_rows).drop_duplicates(subset=["Player", "Prop Label", "Vegas Line"])
    props_df = tag_best_line_advantages(raw_props_df)

    if selected_prop_filter == "Passing Yards":
        props_df = props_df[props_df["Prop Name"].str.contains("Pass Yds|Passing Yards", case=False, na=False)]
    elif selected_prop_filter == "Pass Attempts":
        props_df = props_df[props_df["Prop Name"].str.contains("Pass Att|Passing Attempts", case=False, na=False)]
    elif selected_prop_filter == "Rushing Yards":
        props_df = props_df[props_df["Prop Name"].str.contains("Rush Yds|Rushing Yards", case=False, na=False) & ~props_df["Prop Name"].str.contains("Rush\+Rec", case=False, na=False)]
    elif selected_prop_filter == "Rush Attempts":
        props_df = props_df[props_df["Prop Name"].str.contains("Rush Att|Carries|Rushing Attempts", case=False, na=False)]
    elif selected_prop_filter == "Receiving Yards":
        props_df = props_df[props_df["Prop Name"].str.contains("Rec Yds|Receiving Yards", case=False, na=False) & ~props_df["Prop Name"].str.contains("Rush\+Rec", case=False, na=False)]
    elif selected_prop_filter == "Receptions":
        props_df = props_df[props_df["Prop Name"].str.contains("Recs|Receptions", case=False, na=False)]

    if props_df.empty:
        st.info("No props available under this filter.")
        return

    selected_dk_bets = []
    selected_fd_bets = []

    for _, r_check in props_df.iterrows():
        chk_id = f"chk_{r_check['Player']}_{r_check['Book']}_{r_check['Prop Name']}_{format_clean_decimal(r_check['Vegas Line'])}_{is_alt_mode}"
        if st.session_state.get(chk_id, False):
            bet_line = format_gambly_bet_string(r_check['Player'], r_check['Pick'], r_check['Vegas Line'], r_check['Clean_Display_Line'])
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
            if selected_dk_bets:
                st.code("\n".join(selected_dk_bets), language="text")
            else:
                st.caption("No DraftKings bets selected yet.")

        with col_fd_slip:
            st.markdown("<span style='color:#0091FF; font-weight:800;'>🔵 FanDuel Slip</span>", unsafe_allow_html=True)
            if selected_fd_bets:
                st.code("\n".join(selected_fd_bets), language="text")
            else:
                st.caption("No FanDuel bets selected yet.")

    unique_players = sorted(props_df["Player"].unique())

    # PROPS STACKED VERTICALLY ONE UNDER THE OTHER FOR EACH PLAYER
    for player in unique_players:
        p_props = props_df[props_df["Player"] == player]
        team_tag = p_props["Team"].iloc[0] if not p_props.empty else ""
        depth_tag = p_props["Position"].iloc[0] if not p_props.empty and p_props["Position"].iloc[0] else ""
        player_depth_label = f"{depth_tag} • {team_tag}" if depth_tag else f"{team_tag}"
        headshot_url = get_headshot_url(player)

        grouped_props = p_props.groupby("Prop Name")
        prop_names_list = list(grouped_props.groups.keys())

        for prop_name in prop_names_list:
            p_group = grouped_props.get_group(prop_name)
            dk_row = p_group[p_group["Book"] == "DraftKings"]
            fd_row = p_group[p_group["Book"] == "FanDuel"]

            col_dk, col_fd = st.columns(2)
            with col_dk:
                if not dk_row.empty:
                    r_dk = dk_row.iloc[0]
                    chk_key_dk = f"chk_{r_dk['Player']}_{r_dk['Book']}_{r_dk['Prop Name']}_{format_clean_decimal(r_dk['Vegas Line'])}_{is_alt_mode}"
                    render_props_cash_book_card(r_dk, player, player_depth_label, headshot_url, chk_key_dk, is_alt_mode=is_alt_mode)
                else:
                    st.markdown(f'<div style="background:#0C111C; border:1.5px dashed #1E283D; border-radius:14px; padding:32px; text-align:center; color:#94A3B8; margin-bottom:16px;"><span style="color:#00E676; font-weight:800;">🟢 DraftKings</span>: No line posted for {prop_name} ({player})</div>', unsafe_allow_html=True)
            with col_fd:
                if not fd_row.empty:
                    r_fd = fd_row.iloc[0]
                    chk_key_fd = f"chk_{r_fd['Player']}_{r_fd['Book']}_{r_fd['Prop Name']}_{format_clean_decimal(r_fd['Vegas Line'])}_{is_alt_mode}"
                    render_props_cash_book_card(r_fd, player, player_depth_label, headshot_url, chk_key_fd, is_alt_mode=is_alt_mode)
                else:
                    st.markdown(f'<div style="background:#0C111C; border:1.5px dashed #1E283D; border-radius:14px; padding:32px; text-align:center; color:#94A3B8; margin-bottom:16px;"><span style="color:#0091FF; font-weight:800;">🔵 FanDuel</span>: No line posted for {prop_name} ({player})</div>', unsafe_allow_html=True)

    # BACK TO TOP BUTTON
    st.markdown("""
        <div style="text-align:center; margin: 36px 0 20px 0;">
            <a href="#top_of_page" style="background:#151D2A; border:1.5px solid #2B3A52; color:#FFFFFF; padding:10px 24px; border-radius:24px; text-decoration:none; font-weight:800; font-size:0.9rem; box-shadow:0 4px 12px rgba(0,0,0,0.4);">
                ⬆️ Back to Top
            </a>
        </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# SCREEN 1: PRO VISUALIZER (OVER / UNDER)
# ==============================================================================
if app_mode == "📊 Pro Visualizer: Over / Under":
    render_screen_header("📊 Pro Visualizer: Over / Under")
    ou_df = load_visualizer_data(["Top DK OU", "Top FD OU"])
    if ou_df.empty:
        st.warning("No Over/Under props found in this workbook.")
    else:
        render_prop_visualizer(ou_df, is_alt_mode=False)

# ==============================================================================
# SCREEN 2: PRO VISUALIZER (ALT LINES)
# ==============================================================================
elif app_mode == "⚡ Pro Visualizer: Alt Lines":
    render_screen_header("⚡ Pro Visualizer: Alt Lines")
    alt_df = load_visualizer_data(["Top DK Alt Lines", "Top FD Alt Lines"])
    if alt_df.empty:
        st.warning("No Alt Line props found in this workbook.")
    else:
        render_prop_visualizer(alt_df, is_alt_mode=True)

# ==============================================================================
# SCREEN 3: BEST OF THE BEST (SKIP UNPOSTED ALT PROPS & PROBABILITY COLOR CODED)
# ==============================================================================
elif app_mode == "💎 Best of the Best (Top Edges)":
    render_screen_header("💎 Best of the Best (Top Conviction Plays)")
    all_curated = load_visualizer_data(["Top DK OU", "Top FD OU", "Top DK Alt Lines", "Top FD Alt Lines"])
    
    if all_curated.empty:
        st.warning("No plays available.")
    else:
        sanitized_plays = []
        for _, r_cand in all_curated.iterrows():
            odds_str_check = str(r_cand.get("Odds", "-")).strip()
            if odds_str_check in ["-", "", "nan", "None"]:
                continue

            p_n, line_f, clean_display_line = extract_sanitized_prop_and_line(r_cand)
            if not p_n or line_f is None: continue
            
            proj = r_cand.get("Calibrated Proj")
            if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]:
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
                r_cand_copy["Clean_Display_Line"] = clean_display_line
                r_cand_copy["Clean_Line"] = line_f
                r_cand_copy["_ev_val"] = ev_f
                r_cand_copy["_model_prob"] = m_prob_norm
                r_cand_copy["_book_prob"] = b_prob_calc if b_prob_calc is not None else 0.50
                sanitized_plays.append(r_cand_copy)
            except:
                pass

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
                display_label = row.get("Clean_Display_Line", f"{line_display} {prop_n}")
                book_s = get_book_styled(row["Book"])
                headshot_url = get_headshot_url(p_name)

                side_raw = str(row.get("Side", "")).strip()
                side_clean = "Over" if not side_raw or side_raw.lower() in ["nan", "none"] else side_raw

                odds_clean = format_american_odds(row.get("Odds", "-"))
                odds_str = f" ({odds_clean})" if odds_clean != "-" else ""

                calc_bp_best = get_or_calculate_book_prob(row.get("Book Win Prob"), row.get("Odds"))
                book_prob = format_percentage(calc_bp_best) if calc_bp_best is not None else "-"
                
                b_color = "#00E676" if (calc_bp_best is not None and calc_bp_best >= 0.50) else "#FF3B30"
                m_color_prob = "#00E676" if row.get("_model_prob", 0.5) >= 0.50 else "#FF3B30"

                model_prob = format_percentage(row.get("_model_prob"))
                ev_clean = format_percentage(row.get("EV"), is_ev=True)

                proj_val = float(row.get('Calibrated Proj', row.get('Projection', 0)))
                line_f_val = float(row.get('Clean_Line', 0))
                margin_val = round(proj_val - line_f_val, 1) if side_clean == "Over" else round(line_f_val - proj_val, 1)
                is_pos = margin_val >= 0
                m_color = "#00E676" if is_pos else "#FF3B30"
                m_bg = "#00E67610" if is_pos else "#FF3B3010"
                m_border = "#00E67680" if is_pos else "#FF3B3080"

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1, 4, 3, 3])
                    with c1:
                        if headshot_url: st.image(headshot_url, width=65)
                        else: st.markdown("### 🏈")
                    with c2:
                        st.markdown(f"<div style='font-size:1.15rem; font-weight:800; color:#FFFFFF;'>#{rank} {p_name}</div>", unsafe_allow_html=True)
                        st.markdown(f"📌 {prop_n} [{book_s}]", unsafe_allow_html=True)
                        st.caption(f"Action: `{row.get('Action', 'STRONG BET')}`")
                    with c3:
                        st.markdown(f"<div style='font-size:1.10rem; font-weight:800; color:#FFFFFF;'>{display_label} <span style='color:#94A3B8; font-weight:600;'>{odds_str}</span></div>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:12.5px; font-weight:800; color:{m_color}; background:{m_bg}; padding:3px 8px; border-radius:5px; border:1px solid {m_border};'>Margin: {margin_val:+0.1f}</span>", unsafe_allow_html=True)
                    with c4:
                        st.markdown(f"<div style='font-size:1.25rem; font-weight:800; color:#00E676;'>{ev_clean} EV</div>", unsafe_allow_html=True)
                        st.caption(f"Win Prob: <b style='color:{m_color_prob};'>{model_prob}</b> (Book: <b style='color:{b_color};'>{book_prob}</b>)", unsafe_allow_html=True)

# ==============================================================================
# SCREEN 4: MASTER EV TABLES
# ==============================================================================
elif app_mode == "📋 Master EV Tables":
    render_screen_header("📋 Master EV Tables & Projections")

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

            st.dataframe(df, use_container_width=True, height=380)

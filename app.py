import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import altair as alt

st.set_page_config(page_title="NFL Quant Dashboard", layout="wide", page_icon="🏈")

# --------------------------------------------------------------------------
# PROPS.CASH / MODERN SPORTSBOOK CSS THEME
# --------------------------------------------------------------------------
st.markdown("""
<style>
/* High-Contrast Crisp Player Containers */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 2px solid #94A3B8 !important;
    border-radius: 12px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.06) !important;
    margin-bottom: 16px !important;
    padding: 12px 14px !important;
}

/* Props.cash Style Tab Navigation */
button[data-baseweb="tab"] {
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    padding: 6px 14px !important;
    color: #475569 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #0F172A !important;
    border-bottom: 3px solid #0F172A !important;
}

/* Big Mobile Touch Checkboxes */
div[data-testid="stCheckbox"] {
    background: #F8FAFC !important;
    border: 1.5px solid #94A3B8 !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
    margin-top: 4px !important;
}
div[data-testid="stCheckbox"] label span:first-child {
    width: 22px !important;
    height: 22px !important;
    margin-right: 8px !important;
}
div[data-testid="stCheckbox"] label p {
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
}

/* Metric Font & Contrast */
[data-testid="stMetricValue"] {
    font-size: 1.25rem !important;
    font-weight: 900 !important;
    color: #0F172A !important;
    white-space: normal !important;
    overflow: visible !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.80rem !important;
    font-weight: 700 !important;
    color: #334155 !important;
    white-space: normal !important;
    overflow: visible !important;
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

def get_book_styled(book_name):
    b = str(book_name).strip()
    if "draftkings" in b.lower() or "dk" in b.lower():
        return '<span style="color:#16A34A; font-weight:900; letter-spacing:0.3px;">DraftKings</span>'
    elif "fanduel" in b.lower() or "fd" in b.lower():
        return '<span style="color:#0284C7; font-weight:900; letter-spacing:0.3px;">FanDuel</span>'
    return f"<span style='font-weight:800; color:#0F172A;'>{b}</span>"

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
        return f'<span style="background-color:#FEF3C7; color:#92400E; padding:3px 9px; border-radius:12px; font-weight:800; font-size:11px; border:1.5px solid #D97706; white-space:nowrap; display:inline-block; flex-shrink:0;">{line_adv_note}</span>'
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
            if o_num >= 100:
                return 100.0 / (o_num + 100.0)
            elif o_num <= -100:
                return abs(o_num) / (abs(o_num) + 100.0)
            elif 1.01 <= o_num < 50.0:
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
            
            bet_str = format_gambly_bet_string(p, side, line, prop)
            if bet_str and "nan" not in bet_str.lower():
                slip_lines.append(bet_str)
                
        slip_lines = list(dict.fromkeys(slip_lines))
        
        if slip_lines:
            st.caption(f"Showing **{len(slip_lines)}** {c_book} bets (Click icon in top-right to copy):")
            st.code("\n".join(slip_lines), language="text")
        else:
            st.info(f"No bets available for {c_book} under current filters.")

def render_compact_book_box(r, chk_key):
    book_html = get_book_styled(r["Book"])
    star_badge = get_best_line_badge_html(r["Line_Adv_Note"])
    action_text = r["Action"]
    
    is_max = "MAX" in action_text
    is_strong = "STRONG" in action_text
    action_color = "#581C87" if is_max else ("#14532D" if is_strong else "#0F172A")
    action_bg = "#E9D5FF" if is_max else ("#BBF7D0" if is_strong else "#E2E8F0")
    
    margin_val = r["Margin"]
    is_pos = margin_val >= 0
    margin_arrow = "▲" if is_pos else "▼"
    margin_bg = "#DCFCE7" if is_pos else "#FEE2E2"
    margin_border = "#16A34A" if is_pos else "#DC2626"
    margin_color = "#14532D" if is_pos else "#991B1B"

    odds_str = f"({r['Odds']})" if r['Odds'] != "-" else ""
    prob_delta_str = f"({r['Prob Delta']})" if r['Prob Delta'] else ""

    card_html = f"""
    <div style="background:#FFFFFF; border:2px solid #CBD5E1; border-radius:10px; padding:10px 12px; margin-bottom:4px; box-shadow:0 2px 4px rgba(0,0,0,0.04);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <div style="display:flex; align-items:center;">
                {book_html} {star_badge}
            </div>
            <span style="font-size:10px; font-weight:800; color:{action_color}; background:{action_bg}; padding:2px 7px; border-radius:4px; border:1px solid #94A3B8;">
                {action_text}
            </span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px;">
            <span style="font-size:1.15rem; font-weight:900; color:#0F172A;">
                {r['Pick']} {format_clean_decimal(r['Vegas Line'])} <span style="font-size:0.85rem; font-weight:700; color:#475569;">{odds_str}</span>
            </span>
            <span style="font-size:1.15rem; font-weight:900; color:#15803D;">
                {r['EV']} EV
            </span>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.80rem; font-weight:600; color:#334155; margin-bottom:6px;">
            <span>Model: <b style="color:#0F172A; font-weight:800;">{r['Win Prob']}</b></span>
            <span>Book: <b style="color:#0F172A; font-weight:800;">{r['Book Win Prob']}</b> <span style="color:#15803D; font-weight:800;">{prob_delta_str}</span></span>
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; background:{margin_bg}; border:1.5px solid {margin_border}; border-radius:6px; padding:3px 8px;">
            <span style="font-size:11px; font-weight:800; color:{margin_color};">Margin vs Line:</span>
            <span style="font-size:12px; font-weight:900; color:{margin_color};">
                {margin_arrow} {margin_val:+0.1f} (Proj: {format_clean_decimal(r['Model Projection'])})
            </span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    st.checkbox("➕ Add to Slip", key=chk_key)

def render_prop_hit_rate_chart(base_prop_name, grp):
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
            total_g = len(stats_list)
            chronological_labels = []
            trend_points = []
            for idx, val in enumerate(stats_list):
                label = f"G{idx + 1}" if (idx + 1) < total_g else f"G{idx + 1} (Latest)"
                chronological_labels.append(label)
                trend_points.append({"Game": label, "Value": val})

            t_df = pd.DataFrame(trend_points)

            book_badges_summary = []
            for _, b_row in grp.iterrows():
                b_html = get_book_styled(b_row["Book"])
                cur_line = b_row["Vegas Line"]
                hits = sum(t_df["Value"] >= cur_line)
                hit_pct = round((hits / total_g) * 100)
                star_b = f" {b_row['Line_Adv_Note']}" if b_row["Line_Adv_Note"] else ""
                
                if hit_pct >= 75:
                    pct_html = f'<span style="background-color:#DCFCE7; color:#14532D; padding:2px 7px; border-radius:4px; font-weight:900; border:1px solid #16A34A;">{hit_pct}%</span>'
                elif hit_pct <= 35:
                    pct_html = f'<span style="background-color:#FEE2E2; color:#991B1B; padding:2px 7px; border-radius:4px; font-weight:900; border:1px solid #DC2626;">{hit_pct}%</span>'
                else:
                    pct_html = f'<span style="font-weight:800; color:#0F172A;">{hit_pct}%</span>'

                book_badges_summary.append(
                    f"[{b_html}]{star_b} {base_prop_name} <b>{format_clean_decimal(cur_line)}</b> ({hits}/{total_g} — {pct_html})"
                )

            summary_html = " | ".join(book_badges_summary)
            st.markdown(f"<div style='font-size:0.88rem; color:#0F172A; font-weight:700; margin-top:6px; margin-bottom:6px;'>📈 <b>Historical Trend:</b> {summary_html}</div>", unsafe_allow_html=True)

            primary_line = grp["Vegas Line"].iloc[0]
            t_df["Result"] = t_df["Value"].apply(lambda v: "Over Hit" if v >= primary_line else "Under Miss")

            max_val = max(t_df["Value"])
            max_line = grp["Vegas Line"].max()
            if max_line <= 3.0:
                y_max = max(max_val * 1.6, max_line * 2.2, 3.5)
            else:
                y_max = max(max_val * 1.35, max_line * 1.45)

            hit_bars = alt.Chart(t_df).mark_bar(size=26, cornerRadius=0, strokeWidth=0).encode(
                x=alt.X("Game:N", title=None, sort=chronological_labels, axis=alt.Axis(labelLimit=0, labelFontWeight="bold", labelColor="#0F172A")),
                y=alt.Y("Value:Q", title="Stat Value", scale=alt.Scale(domain=[0, y_max]), axis=alt.Axis(titleColor="#334155", labelColor="#334155", titleFontWeight="bold")),
                color=alt.Color("Result:N", scale=alt.Scale(domain=["Over Hit", "Under Miss"], range=["#15803D", "#DC2626"]), legend=alt.Legend(title=None, orient="top"))
            )

            bar_text = alt.Chart(t_df).mark_text(dy=-12, fontSize=11.5, fontWeight="bold", color="#0F172A").encode(
                x=alt.X("Game:N", sort=chronological_labels), y=alt.Y("Value:Q"), text=alt.Text("Value:Q", format=".1f")
            )

            ref_lines = []
            for _, b_row in grp.iterrows():
                c_line = b_row["Vegas Line"]
                ref_line = alt.Chart(pd.DataFrame({"y": [c_line]})).mark_rule(
                    color="#000000", strokeWidth=2.2, strokeDash=[3, 3]
                ).encode(y="y:Q")
                ref_lines.append(ref_line)

            combined_chart = hit_bars + bar_text
            for r_line in ref_lines:
                combined_chart += r_line

            st.altair_chart(combined_chart.properties(height=260), use_container_width=True)

# PROPS.CASH TABBED PROPS ARCHITECTURE
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

    # INTERACTIVE TAP-TO-ADD GAMBLY SLIPS
    selected_dk_bets = []
    selected_fd_bets = []

    for _, r_check in props_df.iterrows():
        chk_id = f"chk_{r_check['Player']}_{r_check['Book']}_{r_check['Prop Name']}_{format_clean_decimal(r_check['Vegas Line'])}"
        if st.session_state.get(chk_id, False):
            bet_line = format_gambly_bet_string(r_check['Player'], r_check['Pick'], r_check['Vegas Line'], r_check['Prop Name'])
            if r_check['Book'] == 'DraftKings':
                selected_dk_bets.append(bet_line)
            elif r_check['Book'] == 'FanDuel':
                selected_fd_bets.append(bet_line)

    selected_dk_bets = list(dict.fromkeys(selected_dk_bets))
    selected_fd_bets = list(dict.fromkeys(selected_fd_bets))

    with st.expander("📋 Interactive Gambly Slips (Tap '➕ Add to Slip' on Props Below)", expanded=(len(selected_dk_bets) > 0 or len(selected_fd_bets) > 0)):
        col_clear, _ = st.columns([1, 4])
        with col_clear:
            if st.button("🗑️ Clear Selected Slips", key=f"clr_slips_{is_alt_mode}"):
                for k in list(st.session_state.keys()):
                    if k.startswith("chk_"):
                        st.session_state[k] = False
                st.rerun()

        col_dk_slip, col_fd_slip = st.columns(2)
        with col_dk_slip:
            st.markdown("### 🟢 DraftKings Slip")
            if selected_dk_bets:
                st.caption(f"**{len(selected_dk_bets)}** bets selected (Click copy icon):")
                st.code("\n".join(selected_dk_bets), language="text")
            else:
                st.caption("No DraftKings bets selected yet. Check boxes below to add.")

        with col_fd_slip:
            st.markdown("### 🔵 FanDuel Slip")
            if selected_fd_bets:
                st.caption(f"**{len(selected_fd_bets)}** bets selected (Click copy icon):")
                st.code("\n".join(selected_fd_bets), language="text")
            else:
                st.caption("No FanDuel bets selected yet. Check boxes below to add.")

    unique_players = sorted(props_df["Player"].unique())

    for player in unique_players:
        p_props = props_df[props_df["Player"] == player]
        team_tag = p_props["Team"].iloc[0] if not p_props.empty else ""
        depth_tag = p_props["Position"].iloc[0] if not p_props.empty and p_props["Position"].iloc[0] else ""
        player_depth_label = f"({depth_tag})" if depth_tag else ""

        # HIGH CONTRAST PROPS.CASH PLAYER CARD
        with st.container(border=True):
            headshot_url = get_headshot_url(player)
            h_col1, h_col2 = st.columns([1, 8])
            with h_col1:
                if headshot_url: st.image(headshot_url, width=65)
                else: st.markdown("### 🏈")
            with h_col2:
                # Compact Player Name (Not massive)
                st.markdown(f"<div style='font-size:1.20rem; font-weight:900; color:#0F172A; margin-bottom:2px;'>{player} — <span style='color:#334155; font-weight:700;'>{team_tag} {player_depth_label}</span></div>", unsafe_allow_html=True)
                st.markdown(f"""
                <span style="background-color:#F1F5F9; border:1px solid #CBD5E1; color:#0F172A; font-weight:700; font-size:11.5px; padding:2px 10px; border-radius:12px; display:inline-block;">
                    🏈 Available Props: <b>{len(p_props)}</b>
                </span>
                """, unsafe_allow_html=True)

            grouped_props = p_props.groupby("Prop Name")
            prop_names_list = list(grouped_props.groups.keys())

            # PROPS.CASH MULTI-TAB PROP NAVIGATION
            if len(prop_names_list) > 1:
                prop_tabs = st.tabs([f"📌 {pn}" for pn in prop_names_list])
                for t_idx, prop_name in enumerate(prop_names_list):
                    with prop_tabs[t_idx]:
                        p_group = grouped_props.get_group(prop_name)
                        dk_row = p_group[p_group["Book"] == "DraftKings"]
                        fd_row = p_group[p_group["Book"] == "FanDuel"]
                        proj_val = format_clean_decimal(p_group["Model Projection"].iloc[0])

                        # Context repeated cleanly inside tab (Never get lost while scrolling)
                        st.markdown(f"<div style='font-size:1.0rem; font-weight:800; color:#1E293B; margin-top:4px; margin-bottom:8px;'>👤 {player} — <b>{prop_name}</b> <span style='font-size:0.85rem; font-weight:700; color:#64748B;'>(Model: {proj_val})</span></div>", unsafe_allow_html=True)

                        col_dk, col_fd = st.columns(2)
                        with col_dk:
                            if not dk_row.empty:
                                r_dk = dk_row.iloc[0]
                                chk_key_dk = f"chk_{r_dk['Player']}_{r_dk['Book']}_{r_dk['Prop Name']}_{format_clean_decimal(r_dk['Vegas Line'])}"
                                render_compact_book_box(r_dk, chk_key_dk)
                            else:
                                st.markdown("""
                                <div style="background:#F8FAFC; border:1.5px dashed #CBD5E1; border-radius:10px; padding:14px; text-align:center; color:#64748B; font-size:12.5px; font-weight:700; margin-bottom:4px;">
                                    <span style="color:#16A34A; font-weight:900;">DraftKings</span>: No Line Posted
                                </div>
                                """, unsafe_allow_html=True)

                        with col_fd:
                            if not fd_row.empty:
                                r_fd = fd_row.iloc[0]
                                chk_key_fd = f"chk_{r_fd['Player']}_{r_fd['Book']}_{r_fd['Prop Name']}_{format_clean_decimal(r_fd['Vegas Line'])}"
                                render_compact_book_box(r_fd, chk_key_fd)
                            else:
                                st.markdown("""
                                <div style="background:#F8FAFC; border:1.5px dashed #CBD5E1; border-radius:10px; padding:14px; text-align:center; color:#64748B; font-size:12.5px; font-weight:700; margin-bottom:4px;">
                                    <span style="color:#0284C7; font-weight:900;">FanDuel</span>: No Line Posted
                                </div>
                                """, unsafe_allow_html=True)

                        render_prop_hit_rate_chart(prop_name, p_group)
            else:
                # Single Prop: Render directly
                prop_name = prop_names_list[0]
                p_group = grouped_props.get_group(prop_name)
                dk_row = p_group[p_group["Book"] == "DraftKings"]
                fd_row = p_group[p_group["Book"] == "FanDuel"]
                proj_val = format_clean_decimal(p_group["Model Projection"].iloc[0])

                st.markdown(f"<div style='font-size:1.0rem; font-weight:800; color:#1E293B; margin-top:4px; margin-bottom:8px;'>👤 {player} — <b>{prop_name}</b> <span style='font-size:0.85rem; font-weight:700; color:#64748B;'>(Model: {proj_val})</span></div>", unsafe_allow_html=True)

                col_dk, col_fd = st.columns(2)
                with col_dk:
                    if not dk_row.empty:
                        r_dk = dk_row.iloc[0]
                        chk_key_dk = f"chk_{r_dk['Player']}_{r_dk['Book']}_{r_dk['Prop Name']}_{format_clean_decimal(r_dk['Vegas Line'])}"
                        render_compact_book_box(r_dk, chk_key_dk)
                    else:
                        st.markdown("""
                        <div style="background:#F8FAFC; border:1.5px dashed #CBD5E1; border-radius:10px; padding:14px; text-align:center; color:#64748B; font-size:12.5px; font-weight:700; margin-bottom:4px;">
                            <span style="color:#16A34A; font-weight:900;">DraftKings</span>: No Line Posted
                        </div>
                        """, unsafe_allow_html=True)

                with col_fd:
                    if not fd_row.empty:
                        r_fd = fd_row.iloc[0]
                        chk_key_fd = f"chk_{r_fd['Player']}_{r_fd['Book']}_{r_fd['Prop Name']}_{format_clean_decimal(r_fd['Vegas Line'])}"
                        render_compact_book_box(r_fd, chk_key_fd)
                    else:
                        st.markdown("""
                        <div style="background:#F8FAFC; border:1.5px dashed #CBD5E1; border-radius:10px; padding:14px; text-align:center; color:#64748B; font-size:12.5px; font-weight:700; margin-bottom:4px;">
                            <span style="color:#0284C7; font-weight:900;">FanDuel</span>: No Line Posted
                        </div>
                        """, unsafe_allow_html=True)

                render_prop_hit_rate_chart(prop_name, p_group)

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
            st.caption(f"Showing **{len(best_plays)}** top conviction plays clearing dual model edge and market devig.")

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

                proj_val = float(row.get('Projection', 0))
                line_f_val = float(row.get('Clean_Line', 0))
                margin_val = round(proj_val - line_f_val, 1)
                is_pos = margin_val >= 0
                m_color = "#14532D" if is_pos else "#991B1B"
                m_bg = "#DCFCE7" if is_pos else "#FEE2E2"
                m_border = "#16A34A" if is_pos else "#DC2626"

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1, 4, 3, 3])
                    with c1:
                        if headshot_url: st.image(headshot_url, width=65)
                        else: st.markdown("### 🏈")
                    with c2:
                        st.markdown(f"**#{rank} {p_name}**")
                        st.markdown(f"📌 {prop_n} [{book_s}]", unsafe_allow_html=True)
                        st.caption(f"Action: `{row.get('Action', 'STRONG BET')}`")
                    with c3:
                        st.markdown(f"**{side_clean} {line_display}** <span style='color:#475569; font-weight:700;'>{odds_str}</span>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:12.5px; font-weight:900; color:{m_color}; background:{m_bg}; padding:3px 8px; border-radius:5px; border:1px solid {m_border};'>Margin: {margin_val:+0.1f}</span>", unsafe_allow_html=True)
                    with c4:
                        st.markdown(f"<span style='font-size:1.25rem; font-weight:900; color:#15803D;'>{ev_clean} EV</span>", unsafe_allow_html=True)
                        st.caption(f"Win Prob: **{model_prob}** (Book: {book_prob})")

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

            def highlight_actions(row):
                val = str(row.get("Action", ""))
                if "MAX" in val: return ["background-color: #e8d7ff"] * len(row)
                elif "ANCHOR" in val: return ["background-color: #fff2cc"] * len(row)
                elif "STRONG" in val: return ["background-color: #d4edda"] * len(row)
                elif "SKIP" in val: return ["background-color: #f8d7da"] * len(row)
                return [""] * len(row)

            st.dataframe(df.style.apply(highlight_actions, axis=1), use_container_width=True, height=380)

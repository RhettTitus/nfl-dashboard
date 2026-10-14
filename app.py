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
        if not p_name or line_f is None: continue

        proj = r.get("Projection")
        if pd.isna(proj) or str(proj).strip().lower() in ["nan", "none", "", "unposted"]: continue

        try:
            proj_f = float(proj)
            player_name = str(r["Player"]).strip()
            team_name = str(r.get(team_col, "")).strip()
            pos_val = str(r.get(pos_col, "")).strip()
            book = str(r.get("Book", "DraftKings")).strip()
            grade_val = str(r.get("Grade", "A")).strip()
            opp_val = str(r.get("opponent", r.get("Game", ""))).strip()
            
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
                "Grade": grade_val,
                "Opponent": opp_val,
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

    for player in unique_players:
        p_props = props_df[props_df["Player"] == player]
        team_tag = p_props["Team"].iloc[0] if not p_props.empty else ""
        depth_tag = p_props["Position"].iloc[0] if not p_props.empty and p_props["Position"].iloc[0] else ""
        player_depth_label = f"({depth_tag})" if depth_tag else ""
        headshot_url = get_headshot_url(player)

        grouped_props = p_props.groupby("Prop Name")
        prop_names_list = list(grouped_props.groups.keys())

        # SOLID PURE-WHITE TABS FOR MULTI-PROP PLAYERS
        if len(prop_names_list) > 1:
            prop_tabs = st.tabs([f"{pn}" for pn in prop_names_list])
            for t_idx, prop_name in enumerate(prop_names_list):
                with prop_tabs[t_idx]:
                    render_props_cash_tab_content(player, team_tag, player_depth_label, headshot_url, len(p_props), prop_name, grouped_props.get_group(prop_name))
        else:
            render_props_cash_tab_content(player, team_tag, player_depth_label, headshot_url, len(p_props), prop_names_list[0], grouped_props.get_group(prop_names_list[0]))

# FULLY UNIFIED MASTER BLOCK (PLAYER HEADER + 6-PACK + STATS + CHART + SPORTSBOOKS)
def render_props_cash_tab_content(player, team_tag, player_depth_label, headshot_url, total_props_count, prop_name, p_group):
    dk_row = p_group[p_group["Book"] == "DraftKings"]
    fd_row = p_group[p_group["Book"] == "FanDuel"]

    primary_row = dk_row.iloc[0] if not dk_row.empty else fd_row.iloc[0]
    line_display = format_clean_decimal(primary_row["Vegas Line"])
    proj_display = format_clean_decimal(primary_row["Model Projection"])
    grade_char = primary_row.get("Grade", "A")

    last_5_raw = str(primary_row.get("Last 5", "")).strip()
    l5_avg_display = "-"
    hit_rate_display = "-"
    hit_rate_color = "#00E676"

    if last_5_raw and last_5_raw not in ["-", "nan", ""]:
        try:
            s_list = [float(x.strip()) for x in last_5_raw.split(",") if x.strip()]
            if s_list:
                l5_avg_display = f"{sum(s_list)/len(s_list):.1f}"
                hits = sum(x >= float(primary_row["Vegas Line"]) for x in s_list)
                pct = round((hits / len(s_list)) * 100)
                hit_rate_display = f"{pct}%"
                hit_rate_color = "#00E676" if pct >= 50 else "#FF3B30"
        except: pass

    ev_val = primary_row['EV']
    win_prob = primary_row['Win Prob']

    # MASTER CONTAINER HOLDING PLAYER INFO, METRICS, AND BADGES TOGETHER
    unified_card_html = (
        f'<div style="background:#0C111C; border:1.5px solid #1E283D; border-radius:18px; padding:22px; margin-top:10px; margin-bottom:18px; box-shadow:0 8px 20px rgba(0,0,0,0.5);">'
        
        # 1. PLAYER HERO HEADER SECTION
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">'
        f'<div>'
        f'<div style="font-size:1.60rem; font-weight:900; color:#FFFFFF; letter-spacing:0.3px;">{player}</div>'
        f'<div style="font-size:1.0rem; color:#94A3B8; font-weight:700; margin-top:2px;">{team_tag} • {player_depth_label}</div>'
        f'<div style="margin-top:8px;">'
        f'<span style="background-color:#172033; border:1px solid #2F3E5C; color:#00E676; font-weight:800; font-size:12px; padding:4px 14px; border-radius:14px; display:inline-block;">'
        f'🏈 Props: <b>{total_props_count}</b>'
        f'</span>'
        f'</div>'
        f'</div>'
        f'<div>'
        f'<img src="{headshot_url}" style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:3px solid #00E676; background:#1C2436; box-shadow:0 0 16px rgba(0,230,118,0.25);">'
        f'</div>'
        f'</div>'
        
        f'<div style="height:1px; background:#1E283D; margin-bottom:18px;"></div>'
        
        # 2. TOP 6-PACK METRICS ROW
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1.2fr 1fr 1fr 65px; gap:16px; align-items:center; margin-bottom:18px;">'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">L5 AVG</div><div style="font-size:19px; font-weight:900; color:#FFFFFF;">▲ {l5_avg_display}</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">LINE</div><div style="font-size:19px; font-weight:900; color:#FFFFFF;">{line_display} &gt;</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">PROP</div><div style="font-size:15px; font-weight:900; color:#FFFFFF;">{prop_name}</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">HIT RATE</div><div style="font-size:19px; font-weight:900; color:{hit_rate_color};">▲ {hit_rate_display}</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">PROJECTION</div><div style="font-size:19px; font-weight:900; color:#00E676;">{proj_display}</div></div>'
        f'<div style="text-align:center;"><div style="width:42px; height:42px; border-radius:50%; border:3px solid #00E676; display:flex; align-items:center; justify-content:center; margin:0 auto; font-weight:900; color:#00E676; font-size:18px; background:#161E2E; box-shadow:0 0 12px rgba(0,230,118,0.35);">{grade_char}</div><div style="font-size:10px; color:#94A3B8; font-weight:800; margin-top:4px;">Matchup</div></div>'
        f'</div>'
        
        f'<div style="height:1px; background:#1E283D; margin-bottom:18px;"></div>'
        
        # 3. BOTTOM ROW: SPACED OUT READABILITY BADGES/PILLS
        f'<div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center;">'
        f'<span style="background:#131B2B; color:#FFFFFF; border:1px solid #2B3A54; padding:7px 16px; border-radius:16px; font-size:13px; font-weight:800;">L5: <b style="color:{hit_rate_color};">{hit_rate_display}</b></span>'
        f'<span style="background:#131B2B; color:#FFFFFF; border:1px solid #2B3A54; padding:7px 16px; border-radius:16px; font-size:13px; font-weight:800;">H2H: <b style="color:#00E676;">60%</b></span>'
        f'<span style="background:#131B2B; color:#FFFFFF; border:1px solid #2B3A54; padding:7px 16px; border-radius:16px; font-size:13px; font-weight:800;">Model Win: <b style="color:#00E676;">{win_prob}</b></span>'
        f'<span style="background:#131B2B; color:#FFFFFF; border:1px solid #2B3A54; padding:7px 16px; border-radius:16px; font-size:13px; font-weight:800;">Edge: <b style="color:#00E676;">{ev_val}</b></span>'
        f'<span style="background:#131B2B; color:#00E676; border:1.5px solid #00E676; padding:7px 16px; border-radius:16px; font-size:13px; font-weight:900;">DvP: 28th</span>'
        f'<span style="background:#131B2B; color:#00E676; border:1.5px solid #00E676; padding:7px 16px; border-radius:16px; font-size:13px; font-weight:900;">Def Rank: 30th</span>'
        f'</div>'
        
        f'</div>'
    )
    st.markdown(unified_card_html, unsafe_allow_html=True)

    # 4. PROPS.CASH CHART
    render_prop_hit_rate_chart(prop_name, p_group)

    # 5. DRAFTKINGS VS FANDUEL COMPARISON CARDS
    col_dk, col_fd = st.columns(2)
    with col_dk:
        if not dk_row.empty:
            r_dk = dk_row.iloc[0]
            chk_key_dk = f"chk_{r_dk['Player']}_{r_dk['Book']}_{r_dk['Prop Name']}_{format_clean_decimal(r_dk['Vegas Line'])}"
            render_compact_book_box(r_dk, chk_key_dk)
        else:
            st.markdown('<div style="background:#111827; border:1.5px dashed #243048; border-radius:10px; padding:16px; text-align:center; color:#94A3B8; font-size:13px; font-weight:700;"><span style="color:#00E676; font-weight:800;">DraftKings</span>: No Line Posted</div>', unsafe_allow_html=True)

    with col_fd:
        if not fd_row.empty:
            r_fd = fd_row.iloc[0]
            chk_key_fd = f"chk_{r_fd['Player']}_{r_fd['Book']}_{r_fd['Prop Name']}_{format_clean_decimal(r_fd['Vegas Line'])}"
            render_compact_book_box(r_fd, chk_key_fd)
        else:
            st.markdown('<div style="background:#111827; border:1.5px dashed #243048; border-radius:10px; padding:16px; text-align:center; color:#94A3B8; font-size:13px; font-weight:700;"><span style="color:#0091FF; font-weight:800;">FanDuel</span>: No Line Posted</div>', unsafe_allow_html=True)

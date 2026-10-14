def render_props_cash_tab_content(player, prop_name, p_group):
    dk_row = p_group[p_group["Book"] == "DraftKings"]
    fd_row = p_group[p_group["Book"] == "FanDuel"]

    primary_row = dk_row.iloc[0] if not dk_row.empty else fd_row.iloc[0]
    line_display = format_clean_decimal(primary_row["Vegas Line"])
    proj_display = format_clean_decimal(primary_row["Model Projection"])
    grade_char = primary_row.get("Grade", "A")
    margin_num = primary_row["Margin"]

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

    # UNIFIED CONTAINER: 6-PACK COCKPIT + BADGES + CHART + BOOK ODDS ALL IN ONE BLOCK
    unified_card_html = (
        f'<div style="background:#0C111C; border:1.5px solid #1E283D; border-radius:14px; padding:22px; margin-top:6px; margin-bottom:18px; box-shadow:0 6px 16px rgba(0,0,0,0.4);">'
        
        # TOP 6-PACK METRICS ROW
        f'<div style="display:grid; grid-template-columns: 1fr 1fr 1.2fr 1fr 1fr 65px; gap:16px; align-items:center; margin-bottom:18px;">'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">L5 AVG</div><div style="font-size:19px; font-weight:900; color:#FFFFFF;">▲ {l5_avg_display}</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">LINE</div><div style="font-size:19px; font-weight:900; color:#FFFFFF;">{line_display} &gt;</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">PROP</div><div style="font-size:15px; font-weight:900; color:#FFFFFF;">{prop_name}</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">HIT RATE</div><div style="font-size:19px; font-weight:900; color:{hit_rate_color};">▲ {hit_rate_display}</div></div>'
        f'<div><div style="font-size:11.5px; color:#94A3B8; font-weight:800; letter-spacing:0.6px; margin-bottom:4px;">PROJECTION</div><div style="font-size:19px; font-weight:900; color:#00E676;">{proj_display}</div></div>'
        f'<div style="text-align:center;"><div style="width:42px; height:42px; border-radius:50%; border:3px solid #00E676; display:flex; align-items:center; justify-content:center; margin:0 auto; font-weight:900; color:#00E676; font-size:18px; background:#161E2E; box-shadow:0 0 12px rgba(0,230,118,0.35);">{grade_char}</div><div style="font-size:10px; color:#94A3B8; font-weight:800; margin-top:4px;">Matchup</div></div>'
        f'</div>'
        
        f'<div style="height:1px; background:#1E283D; margin-bottom:18px;"></div>'
        
        # BOTTOM ROW: SPACED OUT, CRISP READABILITY BADGES/PILLS
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

    # 2. PROPS.CASH CHART (VERTICAL DATES + HALO PROTECTED NUMBERS)
    render_prop_hit_rate_chart(prop_name, p_group)

    # 3. DRAFTKINGS VS FANDUEL COMPARISON (WITH ADD TO SLIP)
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

"""
SCBF Brace/Strut Checker
AISC 341-22 · AISC 360-22 · Special Concentrically Braced Frames
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import math
import streamlit as st
import pandas as pd

from engine import profiles as prof_db
from engine import materials as mat_db
from engine.brace import run_brace_checks
from engine.strut import run_strut_checks, expected_strengths_full

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SCBF Checker",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Main background */
.stApp { background: #f8f9fb; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #1F3864;
    color: white;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span { color: white !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stNumberInput label { color: #D6E4F0 !important; }
section[data-testid="stSidebar"] h3 {
    color: #D6E4F0 !important; font-size: 0.85rem;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-top: 1.2rem; margin-bottom: 0.3rem;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    padding-bottom: 0.3rem;
}

/* Check table rows */
.check-pass { background: #C6EFCE; color: #375623; font-weight: 600; border-radius: 4px; padding: 2px 8px; }
.check-fail { background: #FFC7CE; color: #9C0006; font-weight: 600; border-radius: 4px; padding: 2px 8px; }
.check-sub  { color: #595959; font-style: italic; }
.ratio-ok   { color: #375623; }
.ratio-fail { color: #9C0006; font-weight: 700; }

/* Section headers */
.sec-header {
    background: linear-gradient(90deg, #1F3864, #2E75B6);
    color: white; padding: 8px 16px; border-radius: 6px;
    font-weight: 700; margin: 1rem 0 0.5rem; font-size: 0.95rem;
}

/* Metric cards */
.metric-card {
    background: white; border: 1px solid #e0e0e0;
    border-radius: 8px; padding: 12px 16px;
    text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.metric-card .val { font-size: 1.6rem; font-weight: 700; color: #1F3864; }
.metric-card .lbl { font-size: 0.75rem; color: #595959; margin-top: 2px; }

/* Capacity summary box */
.cap-box {
    background: #D6E4F0; border-radius: 6px;
    padding: 10px 14px; margin: 6px 0; font-size: 0.85rem;
}
.cap-box b { color: #1F3864; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR — ALL INPUTS
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏗️ SCBF Checker")
    st.caption("AISC 341-22 · AISC 360-22")
    st.divider()

    # ── Project ────────────────────────────────────────────────────────────
    st.markdown("### ❶ Project")
    proj_name = st.text_input("Project Name", placeholder="e.g. Office Building A")
    member_id = st.text_input("Member / Brace ID", placeholder="e.g. B-101")

    # ── Frame geometry ─────────────────────────────────────────────────────
    st.markdown("### ❷ Frame Geometry")
    L_m = st.number_input("Beam Span L (m)", value=6.0, min_value=1.0, step=0.5,
                           help="Clear span between column faces")
    H_m = st.number_input("Story Height H (m)", value=3.0, min_value=1.0, step=0.5,
                           help="Floor-to-floor height")
    K   = st.number_input("Eff. Length Factor K", value=1.0, min_value=0.5, max_value=2.0,
                           step=0.1, help="1.0 for pin-pin (SCBF)")

    # Auto-calc angle and brace length
    theta_deg = math.degrees(math.atan(H_m / (L_m / 2)))
    Lbr_m     = math.sqrt((L_m/2)**2 + H_m**2)
    c1, c2 = st.columns(2)
    c1.metric("θ (auto)", f"{theta_deg:.1f}°")
    c2.metric("Lbr (auto)", f"{Lbr_m:.2f} m")

    # ── Brace type selection ──────────────────────────────────────────────
    st.markdown("### ❸ Brace Type")
    brace_type = st.selectbox(
        "Configuration",
        ["Chevron (V-Brace)", "X-Brace (Both Floors)", "Chevron + X-Brace"],
        index=2,
    )

    show_chevron = "Chevron" in brace_type
    show_xbrace  = "X-Brace" in brace_type or "Both" in brace_type

    # ── Chevron brace ─────────────────────────────────────────────────────
    if show_chevron:
        st.markdown("### ❹ Chevron Brace")
        chev_prof_name = st.selectbox("Profile", prof_db.PROFILE_NAMES,
                                       index=prof_db.PROFILE_NAMES.index("HE 240 B"),
                                       key="chev_prof")
        chev_grade = st.selectbox("Steel Grade", ["S-235","S-275","S-355"],
                                   key="chev_grade")
        chev_Pu = st.number_input("Pu (kN) — Compression demand", value=500.0,
                                   min_value=0.0, key="chev_pu")
        chev_Tu = st.number_input("Tu (kN) — Tension demand", value=500.0,
                                   min_value=0.0, key="chev_tu")

    # ── Bottom brace ─────────────────────────────────────────────────────
    st.markdown("### ❺ Bottom Brace")
    same_as_chev = st.checkbox("Same as Chevron brace", value=False) if show_chevron else False

    if same_as_chev and show_chevron:
        bot_prof_name = chev_prof_name
        bot_grade     = chev_grade
        bot_Pu        = chev_Pu
        bot_Tu        = chev_Tu
    else:
        bot_prof_name = st.selectbox("Profile", prof_db.PROFILE_NAMES,
                                      index=prof_db.PROFILE_NAMES.index("HE 220 B"),
                                      key="bot_prof")
        bot_grade = st.selectbox("Steel Grade", ["S-235","S-275","S-355"],
                                  key="bot_grade")
        bot_Pu = st.number_input("Pu (kN) — Compression demand", value=500.0,
                                  min_value=0.0, key="bot_pu")
        bot_Tu = st.number_input("Tu (kN) — Tension demand", value=500.0,
                                  min_value=0.0, key="bot_tu")

    # ── Beam / Strut ──────────────────────────────────────────────────────
    st.markdown("### ❻ Beam / Strut")
    beam_prof_name = st.selectbox("Profile", prof_db.PROFILE_NAMES,
                                   index=prof_db.PROFILE_NAMES.index("HE 340 B"),
                                   key="beam_prof")
    beam_grade = st.selectbox("Steel Grade", ["S-235","S-275","S-355"],
                               index=1, key="beam_grade")

    col_a, col_b = st.columns(2)
    wg_kNm = col_a.number_input("wg (kN/m)", value=2.0, min_value=0.0, step=0.5,
                                  help="Factored gravity load — self weight + slab")
    PQ_kN  = col_b.number_input("PQ (kN)", value=1.5, min_value=0.0, step=0.5,
                                  help="Concentrated live load at midspan")
    PS_kN  = col_a.number_input("PS (kN)", value=0.0, min_value=0.0, step=0.5,
                                  help="Snow load at midspan (roof only, else 0)")
    Lb_m   = col_b.number_input("Lb (m)", value=2.0, min_value=0.1, step=0.5,
                                  help="Unbraced length for LTB")
    SDS    = st.number_input("SDS", value=1.0, min_value=0.0, max_value=3.0, step=0.1,
                              help="Short-period spectral parameter")

    st.divider()
    run_btn = st.button("▶  Run Checks", type="primary", use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════════════════
st.markdown(f"# 🏗️ SCBF Member Check")
if proj_name or member_id:
    st.caption(f"{proj_name}  ·  {member_id}")
st.caption("AISC 341-22 · AISC 360-22 · Special Concentrically Braced Frames")
st.divider()


def status_badge(ok):
    if ok:
        return '<span class="check-pass">✓  OK</span>'
    return '<span class="check-fail">✗  FAIL</span>'


def ratio_colored(r):
    color = "#375623" if r <= 1.0 else "#9C0006"
    weight = "400" if r <= 1.0 else "700"
    return f'<span style="color:{color};font-weight:{weight}">{r:.3f}</span>'


def render_check_table(results, title):
    """Render a check table with colored status and ratios."""
    st.markdown(f'<div class="sec-header">{title}</div>', unsafe_allow_html=True)

    rows_html = ""
    for r in results:
        is_sub = r.label.startswith("  ↳")
        bg = "rgba(248,249,251,0.5)" if is_sub else "white"
        font_style = "italic; color:#595959" if is_sub else ""
        font_size  = "0.82rem" if is_sub else "0.9rem"
        ratio_str  = f"{r.ratio:.3f}" if r.capacity != 1.0 or r.case != "governing" else f"{r.demand:.3f}"
        # for H1-1, demand IS the ratio already
        if r.unit == "—" and r.capacity == 1.0:
            dem_str = f"{r.demand:.3f}"
            cap_str = "1.000"
        else:
            dem_str = f"{r.demand:.2f}"
            cap_str = f"{r.capacity:.2f}"

        status_html = status_badge(r.ok) if not is_sub else (
            '<span style="color:#375623;font-size:0.8rem">✓</span>' if r.ok
            else '<span style="color:#9C0006;font-size:0.8rem">✗</span>'
        )
        ratio_html  = ratio_colored(r.ratio)
        code_html   = f'<div style="font-size:0.72rem;color:#808080;margin-top:1px">{r.code}</div>' if r.code else ""

        rows_html += f"""
        <tr style="background:{bg}; border-bottom:1px solid #eee;">
          <td style="padding:6px 10px; font-size:{font_size}; font-style:{font_style}; width:50%">
            {r.label}{code_html}
          </td>
          <td style="padding:6px; text-align:center; font-size:0.85rem">{r.case}</td>
          <td style="padding:6px; text-align:center; font-size:0.85rem">{dem_str}</td>
          <td style="padding:6px; text-align:center; font-size:0.85rem">{cap_str}</td>
          <td style="padding:6px; text-align:center; font-size:0.85rem">{r.unit}</td>
          <td style="padding:6px; text-align:center; font-size:0.85rem">{ratio_html}</td>
          <td style="padding:6px; text-align:center">{status_html}</td>
        </tr>"""

    table_html = f"""
    <table style="width:100%;border-collapse:collapse;background:white;
                  border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
      <thead>
        <tr style="background:#2E75B6;color:white;font-size:0.8rem">
          <th style="padding:8px 10px;text-align:left">CHECK DESCRIPTION</th>
          <th style="padding:8px;text-align:center">CASE</th>
          <th style="padding:8px;text-align:center">DEMAND</th>
          <th style="padding:8px;text-align:center">CAPACITY</th>
          <th style="padding:8px;text-align:center">UNIT</th>
          <th style="padding:8px;text-align:center">RATIO</th>
          <th style="padding:8px;text-align:center">STATUS</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>"""

    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("")


# ── Run calculations ───────────────────────────────────────────────────────
if run_btn or True:   # show placeholder on load too

    # Fetch profile/material data
    chev_p  = prof_db.get(chev_prof_name if show_chevron else bot_prof_name)
    bot_p   = prof_db.get(bot_prof_name)
    beam_p  = prof_db.get(beam_prof_name)
    chev_m  = mat_db.get(chev_grade if show_chevron else bot_grade)
    bot_m   = mat_db.get(bot_grade)
    beam_m  = mat_db.get(beam_grade)

    if not (bot_p and beam_p):
        st.warning("Profil bulunamadı — lütfen profil seçimini kontrol edin.")
        st.stop()

    # ── BRACE CHECKS (bottom brace — governs) ────────────────────────────
    brace_results = run_brace_checks(
        h_mm=bot_p["h"], b_mm=bot_p["b"], tw_mm=bot_p["tw"],
        tf_mm=bot_p["tf"], r_mm=bot_p["r"], A_cm2=bot_p["A"],
        iy_cm=bot_p["iy"], iz_cm=bot_p["iz"],
        Ag_cm2=bot_p["A"], Wel_y_cm3=bot_p["Wel_y"], Fu_MPa=bot_m["Fu"],
        Fy=bot_m["Fy"], E=bot_m["E"], Ry=bot_m["Ry"],
        L_m=Lbr_m, K=K,
        Pu_kN=bot_Pu, Tu_kN=bot_Tu,
    )

    # ── STRUT CHECKS ─────────────────────────────────────────────────────
    cp = chev_p if show_chevron else bot_p
    cm = chev_m if show_chevron else bot_m

    strut_chev, strut_x, cap_info = run_strut_checks(
        beam_h=beam_p["h"], beam_b=beam_p["b"],
        beam_tw=beam_p["tw"], beam_tf=beam_p["tf"], beam_r=beam_p["r"],
        beam_A=beam_p["A"], beam_iy=beam_p["iy"], beam_iz=beam_p["iz"],
        beam_Wpl_y=beam_p["Wpl_y"], beam_Wel_y=beam_p["Wel_y"],
        beam_Iz=beam_p["Iz"], beam_It=beam_p["It"],
        beam_Fy=beam_m["Fy"], beam_E=beam_m["E"],
        L_m=L_m, theta_deg=theta_deg, Lb_m=Lb_m,
        wg_kNm=wg_kNm, PQ_kN=PQ_kN, PS_kN=PS_kN, SDS=SDS,
        chev_Ry=cm["Ry"], chev_Fy=cm["Fy"], chev_A=cp["A"],
        chev_iz=cp["iz"], chev_Lbr=Lbr_m, K=K,
        bot_Ry=bot_m["Ry"], bot_Fy=bot_m["Fy"], bot_A=bot_p["A"],
        bot_iz=bot_p["iz"], bot_Lbr=Lbr_m,
    )

    # ═══════════════════════════════════════════════════════════════════
    # SUMMARY CARDS
    # ═══════════════════════════════════════════════════════════════════
    all_results = brace_results + (strut_chev if show_chevron else []) + (strut_x if show_xbrace else [])
    gov_results = [r for r in all_results if not r.label.startswith("  ↳")]
    n_ok   = sum(1 for r in gov_results if r.ok)
    n_fail = sum(1 for r in gov_results if not r.ok)
    max_ratio = max((r.ratio for r in gov_results), default=0)

    cols = st.columns(4)
    with cols[0]:
        color = "#C6EFCE" if n_fail == 0 else "#FFC7CE"
        icon  = "✅" if n_fail == 0 else "❌"
        label = "ALL PASS" if n_fail == 0 else f"{n_fail} FAIL"
        st.markdown(f'<div class="metric-card" style="border-top:4px solid {"#375623" if n_fail==0 else "#9C0006"}"><div class="val">{icon} {label}</div><div class="lbl">Overall Result</div></div>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f'<div class="metric-card"><div class="val">{n_ok}</div><div class="lbl">Checks Passed</div></div>', unsafe_allow_html=True)
    with cols[2]:
        ratio_color = "#375623" if max_ratio <= 1.0 else "#9C0006"
        st.markdown(f'<div class="metric-card"><div class="val" style="color:{ratio_color}">{max_ratio:.3f}</div><div class="lbl">Max Ratio</div></div>', unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f'<div class="metric-card"><div class="val">{beam_prof_name}</div><div class="lbl">Strut Profile</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # TABS
    # ═══════════════════════════════════════════════════════════════════
    tab_labels = ["📋 Summary", "🔩 Brace"]
    if show_chevron: tab_labels.append("🔶 Chevron Strut")
    if show_xbrace:  tab_labels.append("✖ X-Brace Strut")
    tab_labels.append("ℹ️ Section Info")

    tabs = st.tabs(tab_labels)
    tab_idx = 0

    # ── SUMMARY TAB ───────────────────────────────────────────────────────
    with tabs[tab_idx]:
        tab_idx += 1

        # Capacity summary
        st.markdown('<div class="sec-header">⚙️ Beam/Strut Capacity</div>', unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(f'<div class="cap-box"><b>φcPn</b><br>{cap_info["phi_Pn"]:.1f} kN</div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="cap-box"><b>φbMn</b><br>{cap_info["phi_Mn"]:.1f} kN·m<br><small>{cap_info["ltb_zone"]}</small></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="cap-box"><b>φvVn</b><br>{cap_info["phi_Vn"]:.1f} kN</div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="cap-box"><b>Expected</b><br>T_ET={cap_info["T_ET_c"]:.0f} kN<br>C_EB={cap_info["C_EB_c"]:.0f} kN</div>', unsafe_allow_html=True)
        st.markdown("")

        # Summary check table (governing rows only)
        all_gov = [r for r in all_results if not r.label.startswith("  ↳")]
        render_check_table(all_gov, "✅ Check Summary — Governing Values")

    # ── BRACE TAB ─────────────────────────────────────────────────────────
    with tabs[tab_idx]:
        tab_idx += 1
        st.info(f"**Brace:** {bot_prof_name}  ·  {bot_grade}  ·  "
                f"Pu = {bot_Pu:.0f} kN  ·  Tu = {bot_Tu:.0f} kN  ·  "
                f"Lbr = {Lbr_m:.2f} m")
        render_check_table(brace_results, "🔩 Brace Member Checks  [AISC 341-22 §F2.5b | 360-22 §D/E]")

    # ── CHEVRON STRUT TAB ─────────────────────────────────────────────────
    if show_chevron:
        with tabs[tab_idx]:
            tab_idx += 1
            st.info(f"**Chevron Brace:** {chev_prof_name} {chev_grade}  ·  "
                    f"T_ET = {cap_info['T_ET_c']:.1f} kN  ·  "
                    f"C_EB = {cap_info['C_EB_c']:.1f} kN  ·  "
                    f"C_EPB = {cap_info['C_EPB_c']:.1f} kN")
            render_check_table(strut_chev,
                "🔶 Chevron Strut Checks  [AISC 341-22 §F2.3 | §F2.4b | 360-22 §E/F/G/H1]")

    # ── X-BRACE STRUT TAB ────────────────────────────────────────────────
    if show_xbrace:
        with tabs[tab_idx]:
            tab_idx += 1
            st.info(f"**Top:** {chev_prof_name if show_chevron else bot_prof_name}  ·  "
                    f"**Bottom:** {bot_prof_name}  ·  "
                    f"T_ET,top = {cap_info['T_ET_c']:.1f} kN  ·  "
                    f"T_ET,bot = {cap_info['T_ET_b']:.1f} kN")
            render_check_table(strut_x,
                "✖ X-Brace Strut Checks  [AISC 341-22 §F2.3 | 360-22 §E/F/G/H1]")

    # ── SECTION INFO TAB ─────────────────────────────────────────────────
    with tabs[tab_idx]:
        c1, c2, c3 = st.columns(3)
        for col, (name, grade, p) in zip([c1,c2,c3], [
            ("Chevron Brace" if show_chevron else "Brace", chev_grade if show_chevron else bot_grade, cp),
            ("Bottom Brace",  bot_grade,  bot_p),
            ("Beam / Strut",  beam_grade, beam_p),
        ]):
            mat = mat_db.get(grade)
            col.markdown(f"**{name}**")
            col.markdown(f"`{p['name']}`  ·  {grade}")
            data = {
                "Property": ["h (mm)","b (mm)","tw (mm)","tf (mm)",
                              "A (cm²)","iy (cm)","iz (cm)","Wpl,y (cm³)"],
                "Value": [p["h"],p["b"],p["tw"],p["tf"],
                          p["A"],p["iy"],p["iz"],p["Wpl_y"]],
            }
            col.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            col.markdown(f"Fy={mat['Fy']} MPa · E={mat['E']:,} MPa · Ry={mat['Ry']}")

    # ═══════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════
    st.divider()
    st.caption("AISC 341-22 §F2 · AISC 360-22 Ch.D/E/F/G/H · All calculations per LRFD")

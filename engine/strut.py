"""
Strut beam checks — AISC 341-22 §F2.3 (Ecl) + AISC 360-22 §E3/F2/G2.1/H1.1
Checks 5A-5D: Chevron (V-brace)
Checks 6A-6D: X-Brace (other floor)
"""
import math
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    label:    str
    code:     str
    case:     str
    demand:   float
    capacity: float
    unit:     str
    ratio:    float = field(init=False)
    ok:       bool  = field(init=False)
    note:     str   = ""

    def __post_init__(self):
        self.ratio = self.demand / self.capacity if self.capacity else 999.0
        self.ok    = self.ratio <= 1.0


# ── Expected brace strengths [§F2.3] ─────────────────────────────────────
def _expected_strengths(Ry, Fy, Ag_cm2, E, Lbr_m, K):
    """T_ET, C_EB, C_EPB in kN — AISC 341-22 §F2.3"""
    Ag_mm2 = Ag_cm2 * 100
    T_ET   = Ry * Fy * Ag_mm2 / 1000          # kN

    kl_r   = K * Lbr_m * 1000 / math.sqrt(Ag_mm2 / math.pi)  # rough — updated below
    # Use proper radius of gyration — passed separately or approximate
    # (caller passes iz_cm as min r.g.)
    return T_ET   # returns only T_ET here; full version below uses iz


def expected_strengths_full(Ry, Fy, Ag_cm2, E, Lbr_m, K, iz_cm):
    """Returns (T_ET, C_EB, C_EPB) in kN"""
    Ag_mm2 = Ag_cm2 * 100            # mm²
    T_ET   = Ry * Fy * Ag_mm2 / 1000 # kN

    kl_r = K * Lbr_m * 100 / iz_cm   # using min r.g.
    Fe   = (math.pi**2 * E) / kl_r**2
    lim  = 4.71 * math.sqrt(E / (Ry * Fy))
    if kl_r <= lim:
        Fne = (0.658 ** (Ry * Fy / Fe)) * Ry * Fy
    else:
        Fne = 0.877 * Fe
    C_EB  = min(T_ET, Fne * Ag_mm2 / 1000 / 0.877)
    C_EPB = 0.3 * C_EB
    return T_ET, C_EB, C_EPB


# ── Beam capacities [AISC 360-22 §E3 / §F2 / §G2.1] ─────────────────────
def beam_capacities(h, b, tw, tf, r, A_cm2, iy_cm, iz_cm,
                    Wpl_y, Wel_y, Iz_cm4, It_cm4,
                    Fy, E, L_span_m, Lb_m):
    """Returns (phi_Pn, phi_Mn, phi_Vn) in kN, kN·m, kN"""
    # Axial φcPn [§E3] — K=1, L=span
    kl_r = 1.0 * L_span_m * 100 / min(iy_cm, iz_cm)
    Fe   = (math.pi**2 * E) / kl_r**2
    lim  = 4.71 * math.sqrt(E / Fy)
    if kl_r <= lim:
        Fcr = (0.658 ** (Fy / Fe)) * Fy
    else:
        Fcr = 0.877 * Fe
    phi_Pn = 0.90 * Fcr * A_cm2 * 100 / 1000   # kN

    # Flexure φbMn [§F2] — Cb=1.0
    Mp = Fy * Wpl_y / 1000   # kN·m
    # Lp = 1.76·iy·√(E/Fy)
    Lp = 1.76 * iy_cm / 100 * math.sqrt(E / Fy)   # m
    ho = h - tf               # mm — dist between flange centroids
    # rts ≈ √(Iz·ho·5/Wel_y)  [Commentary]
    rts = math.sqrt(Iz_cm4 * 5 * ho / Wel_y) if Wel_y else 0  # mm
    # J·c/(Sx·ho)
    Jc_SxHo = It_cm4 * 10000 / (Wel_y * 1000 * ho) if (Wel_y and ho) else 0
    # Lr [Eq.F2-6]
    try:
        Lr = (1.95 * rts * (E / (0.7 * Fy)) *
              math.sqrt(Jc_SxHo + math.sqrt(Jc_SxHo**2 + 6.76 * (0.7*Fy/E)**2))
              ) / 1000   # m
    except Exception:
        Lr = 999.0

    if Lb_m <= Lp:
        Mn = Mp
        ltb_zone = "No LTB (Lb ≤ Lp) → φbMn = φbMp"
    elif Lb_m <= Lr:
        Mn = max(0.7 * Fy * Wel_y / 1000,
                 Mp - (Mp - 0.7*Fy*Wel_y/1000) * (Lb_m - Lp) / (Lr - Lp))
        ltb_zone = "Inelastic LTB (Lp < Lb ≤ Lr)"
    else:
        Fcr_ltb = (math.pi**2 * E / (Lb_m*1000/rts)**2 *
                   math.sqrt(1 + 0.078 * Jc_SxHo * (Lb_m*1000/rts)**2)
                   ) if rts else 0
        Mn = min(Fcr_ltb * Wel_y / 1000, Mp)
        ltb_zone = "Elastic LTB (Lb > Lr)"

    phi_Mn = 0.90 * Mn   # kN·m

    # Shear φvVn [§G2.1]
    hw_tw = (h - 2*tf) / tw if tw else 999
    if hw_tw <= 2.24 * math.sqrt(E / Fy):
        Cv1, phi_v = 1.0, 1.0
    else:
        Cv1, phi_v = min(1.0, 1.51*E / (hw_tw**2 * Fy)), 0.9
    Aw     = h * tw     # mm²
    phi_Vn = phi_v * 0.6 * Fy * Aw / 1000   # kN

    return phi_Pn, phi_Mn, phi_Vn, ltb_zone, Lp, Lr


# ── H1-1 interaction [AISC 360-22 §H1.1] ────────────────────────────────
def h11_ratio(Nu_kN, Mu_kNm, phi_Pn, phi_Mn):
    alpha = abs(Nu_kN) / phi_Pn if phi_Pn else 999.0
    beta  = abs(Mu_kNm) / phi_Mn if phi_Mn else 999.0
    if alpha >= 0.2:
        return alpha + 8/9 * beta, "H1-1a  (Nu/φcPn ≥ 0.2)"
    else:
        return alpha / 2 + beta,   "H1-1b  (Nu/φcPn < 0.2)"


# ── CHEVRON strut demands [§F2.3, §F2.4b] ────────────────────────────────
def chevron_demands(T_ET, C_EB, C_EPB, theta_deg, L_m,
                    wg_kNm, PQ_kN, PS_kN, SDS):
    """Returns (Mu1, Mu2, Vu1, Vu2, Nu1, Nu2) in kN·m / kN"""
    sin_t = math.sin(math.radians(theta_deg))
    cos_t = math.cos(math.radians(theta_deg))

    # Seismic unbalanced forces [§F2.3]
    Vub1  = (T_ET  - C_EB)  * sin_t   # kN
    Vub2  = (T_ET  - C_EPB) * sin_t
    ME1   = Vub1 * L_m / 4
    ME2   = Vub2 * L_m / 4
    Nu1   = (T_ET + C_EB)  * cos_t / 2
    Nu2   = (T_ET + C_EPB) * cos_t / 2

    # Gravity + live + snow moments
    wg_eff = wg_kNm   # includes self-weight — user-entered
    MG = wg_eff * L_m**2 / 8
    MQ = PQ_kN  * L_m / 4
    MS = PS_kN  * L_m / 4
    VG = wg_eff * L_m / 2
    VQ = PQ_kN / 2
    VS = PS_kN / 2

    # Load combinations (1.2 + 0.2·SDS)·G + E + Q + 0.2·S
    fac = 1.2 + 0.2 * SDS
    Mu1 = fac * MG + ME1 + MQ + 0.2 * MS
    Mu2 = fac * MG + ME2 + MQ + 0.2 * MS
    Vu1 = fac * VG + Vub1 + VQ + 0.2 * VS
    Vu2 = fac * VG + Vub2 + VQ + 0.2 * VS

    return Mu1, Mu2, Vu1, Vu2, Nu1, Nu2


# ── X-BRACE strut demands [§F2.3] ────────────────────────────────────────
def xbrace_demands(T_ET_top, C_EB_top, C_EPB_top,
                   T_ET_bot, C_EB_bot, C_EPB_bot,
                   theta_deg, L_m, wg_kNm, PQ_kN, SDS):
    sin_t = math.sin(math.radians(theta_deg))
    cos_t = math.cos(math.radians(theta_deg))

    Vub1 = ((T_ET_top + C_EB_bot) - (T_ET_bot + C_EB_top)) * sin_t
    Vub2 = ((T_ET_top + C_EPB_bot) - (T_ET_bot + C_EPB_top)) * sin_t
    ME1  = Vub1 * L_m / 4
    ME2  = Vub2 * L_m / 4
    Nu1  = ((T_ET_top + C_EB_bot) - (T_ET_bot + C_EB_top)) * cos_t / 2
    Nu2  = ((T_ET_top + C_EPB_bot) - (T_ET_bot + C_EPB_top)) * cos_t / 2

    MG = wg_kNm * L_m**2 / 8
    MQ = PQ_kN  * L_m / 4
    VG = wg_kNm * L_m / 2
    VQ = PQ_kN / 2

    fac = 1.2 + 0.2 * SDS
    Mu1 = fac * MG + ME1 + MQ
    Mu2 = fac * MG + ME2 + MQ
    Vu1 = fac * VG + Vub1 + VQ
    Vu2 = fac * VG + Vub2 + VQ

    return Mu1, Mu2, Vu1, Vu2, Nu1, Nu2


# ── Full strut check runner ───────────────────────────────────────────────
def run_strut_checks(
    # Beam section
    beam_h, beam_b, beam_tw, beam_tf, beam_r,
    beam_A, beam_iy, beam_iz, beam_Wpl_y, beam_Wel_y,
    beam_Iz, beam_It,
    beam_Fy, beam_E,
    # Frame geometry
    L_m, theta_deg, Lb_m, wg_kNm, PQ_kN, PS_kN, SDS,
    # Chevron (top) brace
    chev_Ry, chev_Fy, chev_A, chev_iz, chev_Lbr, K=1.0,
    # Bottom brace
    bot_Ry=1.5, bot_Fy=235, bot_A=91.04, bot_iz=5.59, bot_Lbr=None,
):
    results_chev = []
    results_x    = []

    # ── beam capacities ──────────────────────────────────────────────────
    phi_Pn, phi_Mn, phi_Vn, ltb_zone, Lp, Lr = beam_capacities(
        beam_h, beam_b, beam_tw, beam_tf, beam_r,
        beam_A, beam_iy, beam_iz,
        beam_Wpl_y, beam_Wel_y, beam_Iz, beam_It,
        beam_Fy, beam_E, L_m, Lb_m,
    )

    # ── Chevron brace expected strengths ─────────────────────────────────
    T_ET_c, C_EB_c, C_EPB_c = expected_strengths_full(
        chev_Ry, chev_Fy, chev_A, beam_E, chev_Lbr, K, chev_iz)

    # ── Bottom brace expected strengths ──────────────────────────────────
    if bot_Lbr is None:
        bot_Lbr = chev_Lbr
    T_ET_b, C_EB_b, C_EPB_b = expected_strengths_full(
        bot_Ry, bot_Fy, bot_A, beam_E, bot_Lbr, K, bot_iz)

    # ── Chevron demands ───────────────────────────────────────────────────
    Mu1_c, Mu2_c, Vu1_c, Vu2_c, Nu1_c, Nu2_c = chevron_demands(
        T_ET_c, C_EB_c, C_EPB_c, theta_deg, L_m,
        wg_kNm, PQ_kN, PS_kN, SDS)

    # ── X-brace demands ───────────────────────────────────────────────────
    Mu1_x, Mu2_x, Vu1_x, Vu2_x, Nu1_x, Nu2_x = xbrace_demands(
        T_ET_c, C_EB_c, C_EPB_c,
        T_ET_b, C_EB_b, C_EPB_b,
        theta_deg, L_m, wg_kNm, PQ_kN, SDS)

    # ── Build check results ───────────────────────────────────────────────
    def gov_check(label, code, d1, d2, cap, unit, gov_note=""):
        d_gov = max(abs(d1), abs(d2))
        r = CheckResult(label=label, code=code,
                        case="governing", demand=d_gov, capacity=cap, unit=unit)
        sub1 = CheckResult(label="  ↳ Case 1  (C = C_EB)",  code="",
                           case="1", demand=abs(d1), capacity=cap, unit=unit)
        sub2 = CheckResult(label="  ↳ Case 2  (C = C_EPB)", code="",
                           case="2", demand=abs(d2), capacity=cap, unit=unit)
        return r, sub1, sub2

    # 5A Axial
    for c in gov_check("5A — Axial   Nu / φcPn ≤ 1.0",
                        "AISC 341-22 §F2.3 Ecl | 360-22 §E3  φcPn = 0.90·Fcr·Ag",
                        Nu1_c, Nu2_c, phi_Pn, "kN"):
        results_chev.append(c)

    # 5B Flexure
    for c in gov_check("5B — Flexure   Mu / φbMn ≤ 1.0",
                        f"AISC 341-22 §F2.3 Ecl | 360-22 §F2  {ltb_zone}",
                        Mu1_c, Mu2_c, phi_Mn, "kN·m"):
        results_chev.append(c)

    # 5C Shear
    for c in gov_check("5C — Shear   Vu / φvVn ≤ 1.0",
                        "AISC 341-22 §F2.3 Ecl | 360-22 §G2.1  φvVn = 1.0·0.6·Fy·Aw·Cv1",
                        Vu1_c, Vu2_c, phi_Vn, "kN"):
        results_chev.append(c)

    # 5D H1-1
    h11_1, eq1 = h11_ratio(Nu1_c, Mu1_c, phi_Pn, phi_Mn)
    h11_2, eq2 = h11_ratio(Nu2_c, Mu2_c, phi_Pn, phi_Mn)
    h11_gov = max(h11_1, h11_2)
    results_chev.append(CheckResult(
        label="5D — H1-1 Combined   Nu/φcPn + 8/9·Mu/φbMn ≤ 1.0",
        code="AISC 360-22 §H1.1  H1-1a (≥0.2) or H1-1b (<0.2)",
        case="governing", demand=h11_gov, capacity=1.0, unit="—"))
    results_chev.append(CheckResult(
        label=f"  ↳ Case 1  ({eq1})", code="",
        case="1", demand=h11_1, capacity=1.0, unit="—"))
    results_chev.append(CheckResult(
        label=f"  ↳ Case 2  ({eq2})", code="",
        case="2", demand=h11_2, capacity=1.0, unit="—"))

    # ── X-brace checks 6A-6D ─────────────────────────────────────────────
    for c in gov_check("6A — Axial   Nu / φcPn ≤ 1.0",
                        "AISC 341-22 §F2.3 Ecl (X-brace) | 360-22 §E3",
                        Nu1_x, Nu2_x, phi_Pn, "kN"):
        results_x.append(c)
    for c in gov_check("6B — Flexure   Mu / φbMn ≤ 1.0",
                        "AISC 341-22 §F2.3 Ecl (X-brace) | 360-22 §F2",
                        Mu1_x, Mu2_x, phi_Mn, "kN·m"):
        results_x.append(c)
    for c in gov_check("6C — Shear   Vu / φvVn ≤ 1.0",
                        "AISC 341-22 §F2.3 Ecl (X-brace) | 360-22 §G2.1",
                        Vu1_x, Vu2_x, phi_Vn, "kN"):
        results_x.append(c)

    h11_x1, eqx1 = h11_ratio(Nu1_x, Mu1_x, phi_Pn, phi_Mn)
    h11_x2, eqx2 = h11_ratio(Nu2_x, Mu2_x, phi_Pn, phi_Mn)
    h11_xg = max(h11_x1, h11_x2)
    results_x.append(CheckResult(
        label="6D — H1-1 Combined   Nu/φcPn + 8/9·Mu/φbMn ≤ 1.0",
        code="AISC 360-22 §H1.1",
        case="governing", demand=h11_xg, capacity=1.0, unit="—"))
    results_x.append(CheckResult(label=f"  ↳ Case 1  ({eqx1})", code="",
        case="1", demand=h11_x1, capacity=1.0, unit="—"))
    results_x.append(CheckResult(label=f"  ↳ Case 2  ({eqx2})", code="",
        case="2", demand=h11_x2, capacity=1.0, unit="—"))

    return results_chev, results_x, {
        "phi_Pn": phi_Pn, "phi_Mn": phi_Mn, "phi_Vn": phi_Vn,
        "ltb_zone": ltb_zone, "Lp": Lp, "Lr": Lr,
        "T_ET_c": T_ET_c, "C_EB_c": C_EB_c, "C_EPB_c": C_EPB_c,
        "T_ET_b": T_ET_b, "C_EB_b": C_EB_b, "C_EPB_b": C_EPB_b,
    }

"""
Brace member checks — AISC 341-22 §F2.5b + AISC 360-22 Ch.D & E
Checks 1-4 apply to the BOTTOM brace (governs).
"""
import math
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    label: str
    code:  str
    demand:   float
    capacity: float
    unit:  str
    ratio: float = field(init=False)
    ok:    bool  = field(init=False)

    def __post_init__(self):
        self.ratio = self.demand / self.capacity if self.capacity else 999.0
        self.ok    = self.ratio <= 1.0


def run_brace_checks(
    h_mm: float, b_mm: float, tw_mm: float, tf_mm: float,
    r_mm: float, A_cm2: float, iy_cm: float, iz_cm: float,
    Ag_cm2: float, Wel_y_cm3: float, Fu_MPa: float,
    Fy: float, E: float, Ry: float,
    L_m: float, K: float,
    Pu_kN: float, Tu_kN: float,
    # Net section (conservative defaults)
    n_holes: int = 0, dh_mm: float = 22.0, U: float = 1.0,
) -> list[CheckResult]:
    """Return all brace check results."""
    results = []

    # ── CHECK 1 — Slenderness [AISC 341-22 §F2.5b(a)] ─────────────────
    Lc_m = K * L_m
    r_gov = min(iy_cm, iz_cm)           # cm
    kl_r  = Lc_m * 100 / r_gov          # dimensionless
    results.append(CheckResult(
        label="CHECK 1 — Slenderness  KL/r ≤ 200",
        code="AISC 341-22 §F2.5b(a)",
        demand=kl_r, capacity=200.0, unit="—",
    ))

    # ── CHECK 2a — Flange compactness [Table D1.1] ─────────────────────
    lam_flange = b_mm / (2 * tf_mm)
    lam_hd_f   = 0.30 * math.sqrt(E / (Ry * Fy))
    results.append(CheckResult(
        label="CHECK 2a — Flange  b/(2tf) ≤ λhd",
        code="AISC 341-22 Table D1.1  λhd = 0.30√(E/Ry·Fy)",
        demand=lam_flange, capacity=lam_hd_f, unit="—",
    ))

    # ── CHECK 2b — Web compactness [Table D1.1] ────────────────────────
    hw_mm    = h_mm - 2 * tf_mm - 2 * r_mm
    lam_web  = hw_mm / tw_mm
    lam_hd_w = 2.57 * math.sqrt(E / (Ry * Fy))
    results.append(CheckResult(
        label="CHECK 2b — Web  hw/tw ≤ λhd",
        code="AISC 341-22 Table D1.1  λhd = 2.57√(E/Ry·Fy)",
        demand=lam_web, capacity=lam_hd_w, unit="—",
    ))

    # ── CHECK 3 — Axial compression [AISC 360-22 §E3] ─────────────────
    Fe    = (math.pi**2 * E) / kl_r**2
    limit = 4.71 * math.sqrt(E / Fy)
    if kl_r <= limit:
        Fcr = (0.658 ** (Fy / Fe)) * Fy     # inelastic (E3-2)
    else:
        Fcr = 0.877 * Fe                      # elastic   (E3-3)
    Pn      = Fcr * A_cm2 * 100 / 1000       # kN  (cm²→mm², MPa→kN)
    phi_Pn  = 0.90 * Pn
    results.append(CheckResult(
        label="CHECK 3 — Compression  Pu / φcPn ≤ 1.0",
        code="AISC 360-22 §E3  φcPn = 0.90·Fcr·Ag  (Eq.E3-1/2/3/4)",
        demand=Pu_kN, capacity=phi_Pn, unit="kN",
    ))

    # ── CHECK 4 — Axial tension [AISC 360-22 §D2] ─────────────────────
    # Limit state 1 — yielding
    phi_Pny = 0.90 * Fy * A_cm2 * 100 / 1000

    # Limit state 2 — rupture
    if n_holes > 0:
        delta   = n_holes * dh_mm * tf_mm          # mm²  (flanges assumed)
        An_cm2  = A_cm2 - delta / 100              # cm²
    else:
        An_cm2  = A_cm2
    Ae_cm2  = U * An_cm2
    phi_Pnr = 0.75 * Fu_MPa * Ae_cm2 * 100 / 1000

    phi_Tn  = min(phi_Pny, phi_Pnr)
    results.append(CheckResult(
        label="CHECK 4 — Tension  Tu / φtPn ≤ 1.0",
        code="AISC 360-22 §D2  φt=0.90 yielding, 0.75 rupture  (Eq.D2-1/2)",
        demand=Tu_kN, capacity=phi_Tn, unit="kN",
    ))

    return results

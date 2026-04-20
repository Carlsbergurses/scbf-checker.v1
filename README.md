# SCBF Brace/Strut Checker

**AISC 341-22 · AISC 360-22 · Special Concentrically Braced Frames**

Structural engineering web app for SCBF brace and strut beam capacity checks.

## Features
- Brace: KL/r, HD compactness, axial, tension (Checks 1-4)
- Chevron strut: Axial, Flexure, Shear, H1-1 interaction (5A-5D)
- X-Brace strut: Same set (6A-6D)
- 184 HE/IPE profiles, S-235/275/355 materials
- Automatic θ and Lbr from L and H
- Color-coded pass/fail with ratio display

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud — FREE)

1. Push this folder to a GitHub repo (public or private)
2. Go to https://share.streamlit.io
3. "New app" → select repo → `app.py` → Deploy
4. Share the link with your team

## Code references
- AISC 341-22 §F2.3 — Ecl analysis
- AISC 341-22 §F2.4b — V/Inverted-V beam requirements
- AISC 341-22 §F2.5b — Brace slenderness + compactness
- AISC 341-22 Table D1.1 — Highly ductile limits
- AISC 360-22 §E3 — Compression
- AISC 360-22 §D2 — Tension
- AISC 360-22 §F2 — Flexure (LTB)
- AISC 360-22 §G2.1 — Shear
- AISC 360-22 §H1.1 — Combined forces (H1-1a / H1-1b)

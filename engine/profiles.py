"""Profile database — 184 HE/IPE sections"""
import json, os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "profiles_data.json")

def load_profiles() -> list[dict]:
    with open(_DATA_PATH) as f:
        raw = json.load(f)
    cleaned = []
    for p in raw:
        name = p.get(",") or p.get("name", "")
        if not name:
            continue
        cleaned.append({
            "name":   name,
            "G":      p.get("G (kg/m)", 0),
            "h":      p.get("h (mm)", 0),
            "b":      p.get("b (mm)", 0),
            "tw":     p.get("tw (mm)", 0),
            "tf":     p.get("tf (mm)", 0),
            "r":      p.get("r (mm)", 0),
            "A":      p.get("A (cm²)", 0),
            "iy":     p.get("iy (cm)", 0),
            "iz":     p.get("iz (cm)", 0),
            "Wel_y":  p.get("Wel.y (cm³)", 0),
            "Wpl_y":  p.get("Wpl.y (cm³)", 0),
            "Wel_z":  p.get("Wel.z (cm³)", 0),
            "Iz":     p.get("Iz (cm⁴)", 0),
            "It":     p.get("It (cm⁴)", 0),
        })
    return cleaned

ALL_PROFILES = load_profiles()
PROFILE_NAMES = [p["name"] for p in ALL_PROFILES]
PROFILE_MAP   = {p["name"]: p for p in ALL_PROFILES}

def get(name: str) -> dict | None:
    return PROFILE_MAP.get(name)

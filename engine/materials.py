"""Steel material properties — AISC 341-22 Table A3.2"""

MATERIALS = {
    "S-235": {"Fy": 235, "Fu": 360, "E": 200_000, "Ry": 1.5, "Rt": 1.2},
    "S-275": {"Fy": 275, "Fu": 430, "E": 200_000, "Ry": 1.3, "Rt": 1.1},
    "S-355": {"Fy": 355, "Fu": 490, "E": 200_000, "Ry": 1.1, "Rt": 1.1},
}

def get(grade: str) -> dict:
    return MATERIALS[grade]

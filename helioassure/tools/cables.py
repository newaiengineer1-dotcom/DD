"""Cable Routing Agent (deterministic, conceptual): MV station clustering + Manhattan MV routes + DC length estimate."""
from __future__ import annotations
import math


def route_cables(tables: list[dict], substation: dict, n_stations: int, mv_slack: float = 1.05, bess_units: list[dict] | None = None) -> dict:
    if not tables:
        return {"stations": [], "mv_routes": [], "mv_length_m": 0, "dc_length_m": 0}
    order = sorted(tables, key=lambda t: (round(t["x"] / 120), t["y"]))      # strip-wise ordering keeps clusters compact
    size = math.ceil(len(order) / n_stations)
    stations, routes, dc = [], [], 0.0
    for k in range(n_stations):
        grp = order[k * size:(k + 1) * size]
        if not grp:
            continue
        cx = sum(t["x"] for t in grp) / len(grp); cy = sum(t["y"] for t in grp) / len(grp)
        stations.append({"id": f"MVS{k+1:03d}", "x": round(cx, 2), "y": round(cy, 2), "tables": len(grp)})
        dc += sum((abs(t["x"] - cx) + abs(t["y"] - cy)) * (t["modules"] / 24) * 2 for t in grp)   # per string: +/- cables, 24 modules/string
        routes.append({"from": f"MVS{k+1:03d}", "to": "SUBSTATION", "path": [[cx, cy], [substation["x"], cy], [substation["x"], substation["y"]]],
                       "length_m": round((abs(substation["x"] - cx) + abs(substation["y"] - cy)) * mv_slack, 1)})
    if bess_units:
        bx = sum(u["x"] for u in bess_units) / len(bess_units); by = sum(u["y"] for u in bess_units) / len(bess_units)
        routes.append({"from": "BESS_COMPOUND", "to": "SUBSTATION", "path": [[bx, by], [substation["x"], by], [substation["x"], substation["y"]]],
                       "length_m": round((abs(substation["x"] - bx) + abs(substation["y"] - by)) * mv_slack, 1)})
    return {"stations": stations, "mv_routes": routes, "mv_length_m": round(sum(r["length_m"] for r in routes)), "dc_length_m": round(dc),
            "basis": "Manhattan routing, straight-line clustering, 5% slack; conceptual only - detailed routing requires survey, ground conditions and trench design."}

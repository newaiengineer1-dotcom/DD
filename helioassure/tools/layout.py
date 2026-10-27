"""PV Layout Agent + BESS Layout Agent (deterministic). Conceptual-design geometry in UTM metres; every parameter is explicit and logged."""
from __future__ import annotations
import math
from helioassure.tools import geometry as G


def pv_layout(boundary_utm, target_kwp: float, module_wp: float = 580, module_w: float = 1.134, module_l: float = 2.278, modules_per_table: int = 48,
              gcr: float = 0.33, setback_m: float = 10.0, exclusions=None, azimuth_deg: float = 0.0, row_gap_m: float = 0.6, max_tables: int = 12000) -> dict:
    """1P horizontal single-axis tracker tables on N-S axes. exclusions: [{'id','x','y','r'}] circular buffers (e.g. archaeology, flood pads)."""
    poly = [tuple(p) for p in boundary_utm]
    exclusions = exclusions or []
    table_len, table_w = modules_per_table * module_w, module_l
    pitch = table_w / gcr
    need_modules = math.ceil(target_kwp * 1000 / module_wp)
    xs = [p[0] for p in poly]; x = min(xs) + setback_m + table_w / 2
    tables, placed = [], 0
    while x < max(xs) - setback_m and placed < need_modules and len(tables) < max_tables:
        for y0, y1 in G.vertical_intervals(poly, x):
            y = y0 + setback_m
            while y + table_len <= y1 - setback_m + 1e-6 and placed < need_modules:
                cx, cy = x, y + table_len / 2
                corners = [(x - table_w / 2, y), (x + table_w / 2, y), (x - table_w / 2, y + table_len), (x + table_w / 2, y + table_len)]
                ok = all(G.inside_with_setback(px, py, poly, setback_m) for px, py in corners)
                ok = ok and not any(math.hypot(cx - e["x"], cy - e["y"]) < e["r"] + table_len / 2 for e in exclusions)
                if ok:
                    m = min(modules_per_table, need_modules - placed)
                    tables.append({"id": f"T{len(tables)+1:05d}", "x": round(cx, 2), "y": round(cy, 2), "modules": m})
                    placed += m
                y += table_len + row_gap_m
        x += pitch
    kwp = placed * module_wp / 1000
    return {"tables": tables, "table_len_m": round(table_len, 2), "table_w_m": table_w, "pitch_m": round(pitch, 2), "gcr": gcr, "modules_placed": placed,
            "modules_required": need_modules, "kwp_placed": round(kwp, 1), "kwp_target": target_kwp, "capacity_shortfall_kwp": round(max(0, target_kwp - kwp), 1),
            "area_used_ha": round(len(tables) * table_len * pitch / 1e4, 1), "setback_m": setback_m, "exclusions": exclusions,
            "parameters": {"module_wp": module_wp, "modules_per_table": modules_per_table, "row_gap_m": row_gap_m, "azimuth_deg": azimuth_deg}}


def bess_layout(boundary_utm, containers: int, container_mwh: float = 5.0, origin: tuple[float, float] | None = None, cont_l: float = 6.06, cont_w: float = 2.44,
                spacing_m: float = 3.0, aisle_m: float = 6.0, per_row: int = 9, min_spacing_m: float = 3.0) -> dict:
    poly = [tuple(p) for p in boundary_utm]
    ex = max(p[0] for p in poly); ey = G.centroid(poly)[1]
    ox, oy = origin or (ex - 160, ey - 40)
    rows = math.ceil(containers / per_row)
    units = []
    for i in range(containers):
        r, c = divmod(i, per_row)
        units.append({"id": f"BESS{i+1:03d}", "x": round(ox + c * (cont_l + spacing_m) + cont_l / 2, 2), "y": round(oy + r * (cont_w + aisle_m) + cont_w / 2, 2)})
    w = per_row * cont_l + (per_row - 1) * spacing_m; h = rows * cont_w + (rows - 1) * aisle_m
    comp = [(ox - 10, oy - 10), (ox + w + 10, oy - 10), (ox + w + 10, oy + h + 10), (ox - 10, oy + h + 10)]
    inside = all(G.point_in_polygon(px, py, poly) for px, py in comp)
    return {"units": units, "container_mwh": container_mwh, "total_mwh_dc": round(containers * container_mwh, 1), "compound_utm": [list(p) for p in comp],
            "compound_area_m2": round(G.polygon_area(comp)), "spacing_m": spacing_m, "min_spacing_required_m": min_spacing_m, "spacing_ok": spacing_m >= min_spacing_m,
            "compound_inside_boundary": inside, "note": "Separation distance must be confirmed by fire-spread analysis / large-scale fire test evidence (NFPA 855)."}


def place_substation(boundary_utm, bess_compound=None) -> dict:
    poly = [tuple(p) for p in boundary_utm]
    ex = max(p[0] for p in poly); ys = [p[1] for p in poly]
    y = (min(ys) + max(ys)) / 2 + 60
    x = ex - 40
    return {"x": round(x, 2), "y": round(y, 2), "inside_boundary": G.point_in_polygon(x, y, poly), "assumed": True}

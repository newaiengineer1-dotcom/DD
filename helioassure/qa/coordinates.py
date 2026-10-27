"""Coordinate Consistency Agent: geometry vs layout vs drawings."""
from __future__ import annotations
import math
from helioassure.qa import QAResult
from helioassure.tools import geometry as G


def check(state: dict) -> list[QAResult]:
    geo, pv, bess, sub = state.get("geometry"), state.get("pv_layout"), state.get("bess_layout"), state.get("substation")
    proj = state.get("project", {})
    if not geo:
        return [QAResult("COORD-00", "coordinate_consistency", "fail", "no site geometry available", "WS3")]
    poly = geo["boundary_utm"]
    out = []
    out.append(QAResult("COORD-01", "coordinate_consistency", "pass" if geo["epsg"] == G.epsg(proj.get("lat", 0), proj.get("lon", 0)) else "fail", f"EPSG {geo['epsg']} vs expected {G.epsg(proj.get('lat',0), proj.get('lon',0))}", "WS3"))
    out.append(QAResult("COORD-02", "coordinate_consistency", "pass" if geo["utm_roundtrip_error_m"] < 0.01 else "fail", f"UTM round-trip error {geo['utm_roundtrip_error_m']} m", "WS3"))
    if geo.get("boundary_assumed"):
        out.append(QAResult("COORD-03", "coordinate_consistency", "warn", "site boundary was NOT supplied: an assumed rectangle was generated - layout is indicative only; supply surveyed boundary", "WS3"))
    cx, cy = G.centroid(poly)
    clat, clon = G.from_utm(cx, cy, geo["utm_zone"], geo["hemisphere"] == "N")
    off_km = math.hypot((clat - proj.get("lat", clat)) * 111.32, (clon - proj.get("lon", clon)) * 111.32 * math.cos(math.radians(clat)))
    out.append(QAResult("COORD-04", "coordinate_consistency", "pass" if off_km < 5 else "fail", f"boundary centroid is {off_km:.2f} km from stated site coordinates", "WS3"))
    if pv:
        outside = [t["id"] for t in pv["tables"] if not G.point_in_polygon(t["x"], t["y"], poly)]
        out.append(QAResult("COORD-05", "coordinate_consistency", "pass" if not outside else "fail", f"{len(outside)} PV tables outside boundary", "WS3"))
        viol = [t["id"] for t in pv["tables"] for e in pv.get("exclusions", []) if math.hypot(t["x"] - e["x"], t["y"] - e["y"]) < e["r"]]
        out.append(QAResult("COORD-06", "coordinate_consistency", "pass" if not viol else "fail", f"{len(viol)} PV tables inside exclusion buffers", "WS3"))
    if bess:
        out.append(QAResult("COORD-07", "coordinate_consistency", "pass" if bess["compound_inside_boundary"] else "fail", "BESS compound inside boundary" if bess["compound_inside_boundary"] else "BESS compound outside boundary", "WS7"))
    if sub:
        out.append(QAResult("COORD-08", "coordinate_consistency", "pass" if sub["inside_boundary"] else "warn", "substation inside boundary" if sub["inside_boundary"] else "substation outside boundary", "WS4"))
    return out

"""Drawing/geospatial export (pure Python): GeoJSON (WGS84), ASCII DXF (R12, opens in AutoCAD/QGIS/LibreCAD), SVG."""
from __future__ import annotations
import json, math

from helioassure.tools import geometry as G


def _ll(e, n, geo):
    la, lo = G.from_utm(e, n, geo["utm_zone"], geo["hemisphere"] == "N")
    return [round(lo, 7), round(la, 7)]


def _rect(cx, cy, w, h):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def layout_geojson(geo, pv=None, bess=None, sub=None, cables=None) -> str:
    feats = [{"type": "Feature", "properties": {"layer": "BOUNDARY", "area_ha": geo["area_ha"], "assumed": geo["boundary_assumed"]}, "geometry": {"type": "Polygon", "coordinates": [[_ll(e, n, geo) for e, n in geo["boundary_utm"]] + [_ll(*geo["boundary_utm"][0], geo)]]}}]
    if pv:
        for t in pv["tables"]:
            ring = [_ll(x, y, geo) for x, y in _rect(t["x"], t["y"], pv["table_w_m"], pv["table_len_m"])]
            feats.append({"type": "Feature", "properties": {"layer": "PV_TABLE", "id": t["id"], "modules": t["modules"]}, "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]}})
        for e in pv.get("exclusions", []):
            feats.append({"type": "Feature", "properties": {"layer": "EXCLUSION", "id": e["id"], "radius_m": e["r"]}, "geometry": {"type": "Point", "coordinates": _ll(e["x"], e["y"], geo)}})
    if bess:
        for u in bess["units"]:
            feats.append({"type": "Feature", "properties": {"layer": "BESS_CONTAINER", "id": u["id"], "mwh": bess["container_mwh"]}, "geometry": {"type": "Point", "coordinates": _ll(u["x"], u["y"], geo)}})
        ring = [_ll(x, y, geo) for x, y in bess["compound_utm"]]
        feats.append({"type": "Feature", "properties": {"layer": "BESS_COMPOUND"}, "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]}})
    if sub:
        feats.append({"type": "Feature", "properties": {"layer": "SUBSTATION", "assumed": True}, "geometry": {"type": "Point", "coordinates": _ll(sub["x"], sub["y"], geo)}})
    if cables:
        for s in cables["stations"]:
            feats.append({"type": "Feature", "properties": {"layer": "MV_STATION", "id": s["id"]}, "geometry": {"type": "Point", "coordinates": _ll(s["x"], s["y"], geo)}})
        for r in cables["mv_routes"]:
            feats.append({"type": "Feature", "properties": {"layer": "MV_CABLE", "from": r["from"], "length_m": r["length_m"]}, "geometry": {"type": "LineString", "coordinates": [_ll(x, y, geo) for x, y in r["path"]]}})
    return json.dumps({"type": "FeatureCollection", "name": "HelioAssure conceptual layout (CONCEPTUAL - NOT FOR CONSTRUCTION)", "crs": {"type": "name", "properties": {"name": "EPSG:4326"}}, "features": feats})


class Dxf:
    """Minimal ASCII DXF R12 writer (LINE, POLYLINE-as-LINEs, CIRCLE, TEXT) in UTM metres of the project EPSG."""
    def __init__(self):
        self.e: list[str] = []

    def line(self, x1, y1, x2, y2, layer="0"):
        self.e += ["0", "LINE", "8", layer, "10", f"{x1:.3f}", "20", f"{y1:.3f}", "30", "0", "11", f"{x2:.3f}", "21", f"{y2:.3f}", "31", "0"]

    def poly(self, pts, layer="0", close=True):
        for i in range(len(pts) - (0 if close else 1)):
            self.line(*pts[i], *pts[(i + 1) % len(pts)], layer)

    def circle(self, x, y, r, layer="0"):
        self.e += ["0", "CIRCLE", "8", layer, "10", f"{x:.3f}", "20", f"{y:.3f}", "30", "0", "40", f"{r:.3f}"]

    def text(self, x, y, s, h=5, layer="TEXT"):
        self.e += ["0", "TEXT", "8", layer, "10", f"{x:.3f}", "20", f"{y:.3f}", "30", "0", "40", f"{h}", "1", s]

    def dumps(self) -> str:
        return "\n".join(["0", "SECTION", "2", "ENTITIES"] + self.e + ["0", "ENDSEC", "0", "EOF"]) + "\n"


def layout_dxf(geo, pv=None, bess=None, sub=None, title="") -> str:
    d = Dxf()
    d.poly(geo["boundary_utm"], "BOUNDARY")
    cx, cy = G.centroid(geo["boundary_utm"])
    d.text(cx, max(p[1] for p in geo["boundary_utm"]) + 30, f"{title} - EPSG:{geo['epsg']} - CONCEPTUAL, NOT FOR CONSTRUCTION", 12)
    if pv:
        for t in pv["tables"]:
            d.poly(_rect(t["x"], t["y"], pv["table_w_m"], pv["table_len_m"]), "PV_TABLE")
        for e in pv.get("exclusions", []):
            d.circle(e["x"], e["y"], e["r"], "EXCLUSION"); d.text(e["x"], e["y"], e["id"], 6, "TEXT")
    if bess:
        d.poly(bess["compound_utm"], "BESS_COMPOUND")
        for u in bess["units"]:
            d.poly(_rect(u["x"], u["y"], 6.06, 2.44), "BESS_CONTAINER")
    if sub:
        d.poly(_rect(sub["x"], sub["y"], 40, 30), "SUBSTATION"); d.text(sub["x"] - 15, sub["y"], "150/30 kV SUBSTATION (assumed)", 5)
    return d.dumps()


def layout_svg(geo, pv=None, bess=None, sub=None, cables=None, width=1100, title="") -> str:
    bnd = geo["boundary_utm"]; xs = [p[0] for p in bnd]; ys = [p[1] for p in bnd]
    x0, y0, W, H = min(xs) - 40, min(ys) - 40, max(xs) - min(xs) + 80, max(ys) - min(ys) + 80
    s = width / W; h = H * s
    X = lambda x: round((x - x0) * s, 1); Y = lambda y: round(h - (y - y0) * s, 1)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h+30:.0f}" viewBox="0 0 {width} {h+30:.0f}"><rect width="100%" height="100%" fill="white"/>',
           f'<polygon points="{" ".join(f"{X(a)},{Y(b)}" for a, b in bnd)}" fill="#f6f9ec" stroke="#375623" stroke-width="2"/>']
    if pv:
        for t in pv["tables"]:
            out.append(f'<rect x="{X(t["x"]-pv["table_w_m"]/2)}" y="{Y(t["y"]+pv["table_len_m"]/2)}" width="{max(0.8, pv["table_w_m"]*s):.1f}" height="{pv["table_len_m"]*s:.1f}" fill="#7fa7d6"/>')
        for e in pv.get("exclusions", []):
            out.append(f'<circle cx="{X(e["x"])}" cy="{Y(e["y"])}" r="{e["r"]*s:.1f}" fill="#f4b18344" stroke="#c55a11" stroke-dasharray="4"/><text x="{X(e["x"])}" y="{Y(e["y"])}" font-size="10" fill="#c55a11">{e["id"]}</text>')
    if cables:
        for r in cables["mv_routes"]:
            out.append(f'<polyline points="{" ".join(f"{X(a)},{Y(b)}" for a, b in r["path"])}" fill="none" stroke="#c00000" stroke-width="0.8"/>')
        for st in cables["stations"]:
            out.append(f'<rect x="{X(st["x"])-2}" y="{Y(st["y"])-2}" width="4" height="4" fill="#ffc000"/>')
    if bess:
        out.append(f'<polygon points="{" ".join(f"{X(a)},{Y(b)}" for a, b in bess["compound_utm"])}" fill="#c6e0b4" stroke="#375623"/>')
    if sub:
        out.append(f'<rect x="{X(sub["x"])-8}" y="{Y(sub["y"])-6}" width="16" height="12" fill="#ffe699" stroke="#7f6000"/><text x="{X(sub["x"])+10}" y="{Y(sub["y"])}" font-size="10">Substation (assumed)</text>')
    out.append(f'<text x="8" y="{h+20:.0f}" font-size="12" fill="#333">{title} | EPSG:{geo["epsg"]} | boundary {geo["area_ha"]} ha{" (ASSUMED)" if geo["boundary_assumed"] else ""} | CONCEPTUAL - NOT FOR CONSTRUCTION</text></svg>')
    return "".join(out)

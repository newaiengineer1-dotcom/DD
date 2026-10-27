"""Site Geometry Agent (deterministic): WGS84 <-> UTM (Kruger n-series, mm-level), polygon utilities. Pure Python."""
from __future__ import annotations
import math

A, F = 6378137.0, 1 / 298.257223563
N = F / (2 - F)
K0 = 0.9996
_AA = A / (1 + N) * (1 + N**2 / 4 + N**4 / 64)
_AL = (N / 2 - 2 * N**2 / 3 + 5 * N**3 / 16, 13 * N**2 / 48 - 3 * N**3 / 5, 61 * N**3 / 240)
_BE = (N / 2 - 2 * N**2 / 3 + 37 * N**3 / 96, N**2 / 48 + N**3 / 15, 17 * N**3 / 480)
_DE = (2 * N - 2 * N**2 / 3 - 2 * N**3, 7 * N**2 / 3 - 8 * N**3 / 5, 56 * N**3 / 15)


def utm_zone(lon: float) -> int:
    return int((lon + 180) // 6) + 1


def epsg(lat: float, lon: float) -> int:
    return (32600 if lat >= 0 else 32700) + utm_zone(lon)


def to_utm(lat: float, lon: float, zone: int | None = None) -> tuple[float, float, int]:
    zone = zone or utm_zone(lon)
    lam0 = math.radians((zone - 1) * 6 - 180 + 3)
    phi, lam = math.radians(lat), math.radians(lon) - lam0
    c = 2 * math.sqrt(N) / (1 + N)
    t = math.sinh(math.atanh(math.sin(phi)) - c * math.atanh(c * math.sin(phi)))
    xi_p, eta_p = math.atan2(t, math.cos(lam)), math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    xi = xi_p + sum(_AL[j] * math.sin(2 * (j + 1) * xi_p) * math.cosh(2 * (j + 1) * eta_p) for j in range(3))
    eta = eta_p + sum(_AL[j] * math.cos(2 * (j + 1) * xi_p) * math.sinh(2 * (j + 1) * eta_p) for j in range(3))
    return 500000 + K0 * _AA * eta, (0 if lat >= 0 else 10_000_000) + K0 * _AA * xi, zone


def from_utm(e: float, n: float, zone: int, north: bool = True) -> tuple[float, float]:
    xi, eta = (n - (0 if north else 10_000_000)) / (K0 * _AA), (e - 500000) / (K0 * _AA)
    xi_p = xi - sum(_BE[j] * math.sin(2 * (j + 1) * xi) * math.cosh(2 * (j + 1) * eta) for j in range(3))
    eta_p = eta - sum(_BE[j] * math.cos(2 * (j + 1) * xi) * math.sinh(2 * (j + 1) * eta) for j in range(3))
    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    phi = chi + sum(_DE[j] * math.sin(2 * (j + 1) * chi) for j in range(3))
    lam = math.radians((zone - 1) * 6 - 180 + 3) + math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return math.degrees(phi), math.degrees(lam)


def polygon_area(poly: list[tuple[float, float]]) -> float:
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def centroid(poly):
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def point_in_polygon(x: float, y: float, poly) -> bool:
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def dist_to_segment(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    t = 0.0 if dx == dy == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def dist_to_boundary(x, y, poly) -> float:
    return min(dist_to_segment(x, y, *poly[i], *poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def inside_with_setback(x, y, poly, setback: float) -> bool:
    return point_in_polygon(x, y, poly) and dist_to_boundary(x, y, poly) >= setback


def vertical_intervals(poly, x: float) -> list[tuple[float, float]]:
    """y-intervals of polygon along the vertical line at x (supports concave polygons)."""
    ys = []
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (x1 <= x < x2) or (x2 <= x < x1):
            ys.append(y1 + (x - x1) * (y2 - y1) / (x2 - x1))
    ys.sort()
    return [(ys[i], ys[i + 1]) for i in range(0, len(ys) - 1, 2)]


def default_boundary(lat: float, lon: float, area_ha: float, aspect: float = 1.4) -> list[tuple[float, float]]:
    """Rectangle (lon/lat vertices) of given area centred on lat/lon -- used only when no boundary is supplied (assumption is logged)."""
    e0, n0, z = to_utm(lat, lon)
    w = math.sqrt(area_ha * 1e4 * aspect); h = area_ha * 1e4 / w
    corners = [(e0 - w / 2, n0 - h / 2), (e0 + w / 2, n0 - h / 2), (e0 + w / 2, n0 + h / 2), (e0 - w / 2, n0 + h / 2)]
    return [tuple(reversed(from_utm(e, n, z, lat >= 0))) for e, n in corners]   # (lon, lat)


def site_geometry(lat: float, lon: float, boundary_lonlat=None, stated_area_ha: float | None = None) -> dict:
    assumed = boundary_lonlat is None
    if assumed:
        boundary_lonlat = default_boundary(lat, lon, stated_area_ha or 200.0)
    zone = utm_zone(lon)
    utm = [to_utm(la, lo, zone)[:2] for lo, la in boundary_lonlat]
    back = [from_utm(e, n, zone, lat >= 0) for e, n in utm]
    rt_err_m = max(math.hypot((b[0] - la) * 111_320, (b[1] - lo) * 111_320 * math.cos(math.radians(la))) for b, (lo, la) in zip(back, boundary_lonlat))
    e, n, _ = to_utm(lat, lon, zone)
    return {"epsg": epsg(lat, lon), "utm_zone": zone, "hemisphere": "N" if lat >= 0 else "S", "site_centre_utm": [round(e, 2), round(n, 2)],
            "boundary_lonlat": [list(p) for p in boundary_lonlat], "boundary_utm": [[round(a, 3), round(b, 3)] for a, b in utm],
            "area_ha": round(polygon_area(utm) / 1e4, 2), "boundary_assumed": assumed, "utm_roundtrip_error_m": round(rt_err_m, 4)}

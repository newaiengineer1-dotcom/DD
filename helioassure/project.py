"""ProjectInput: validated project basis (the only thing the human must supply to start)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict

FLAGS = ["remote_site", "heritage_sensitive", "protected_habitat", "receptors_nearby", "airport_or_road_nearby", "avian_zone",
         "community_required", "land_title_complex", "decommissioning_required", "local_content_required"]


class ProjectError(ValueError):
    pass


@dataclass
class ProjectInput:
    name: str = "Solara Alentejo Hybrid (PV + BESS)"
    code: str = "SAH-2026"
    lat: float = 37.62
    lon: float = -8.19
    site_area_ha: float | None = 262.0
    boundary_lonlat: list | None = None            # [(lon, lat), ...]; if None an assumed rectangle is generated and logged as an assumption
    pv_mwp: float = 150.0
    pv_mwac: float = 120.0
    module_wp: float = 580.0
    module_voc: float = 52.7
    module_isc: float = 14.02
    module_tc_voc: float = -0.25
    modules_per_string: int = 24
    modules_per_table: int = 48
    gcr: float = 0.33
    inverter_kva: float = 320.0
    t_min_c: float = -5.0
    bess_mw: float = 60.0
    bess_containers: int = 54
    container_mwh: float = 5.0
    bess_usable_mwh_poi: float = 240.0
    export_limit_mw: float = 130.0
    trafo_mva: float = 90.0
    n_trafo: int = 2
    mv_kv: float = 30.0
    n_mv_stations: int = 36
    exclusions: list = field(default_factory=list)  # [{'id','lat','lon','r'}] circular exclusion buffers (e.g. archaeology)
    flags: dict = field(default_factory=dict)
    p50_specific_yield: float | None = None
    sigma_components_pct: list = field(default_factory=lambda: [3.5, 2.2, 1.8, 2.0, 1.0])
    capex_m: float | None = None
    opex_m: float | None = None
    price_eur_mwh: float | None = None
    debt_m: float | None = None

    def validate(self) -> "ProjectInput":
        if not (-90 <= self.lat <= 90 and -180 <= self.lon <= 180):
            raise ProjectError("invalid coordinates")
        for k in ("pv_mwp", "pv_mwac", "module_wp", "gcr", "inverter_kva"):
            if getattr(self, k) <= 0:
                raise ProjectError(f"{k} must be > 0")
        if not 0.1 <= self.gcr <= 0.7:
            raise ProjectError("gcr outside 0.1-0.7")
        if self.pv_mwp / self.pv_mwac > 2.0:
            raise ProjectError("DC/AC ratio > 2.0 is not credible")
        if self.bess_containers * self.container_mwh < self.bess_usable_mwh_poi:
            raise ProjectError("installed BESS DC energy is below usable energy at POI")
        if self.boundary_lonlat is not None and len(self.boundary_lonlat) < 3:
            raise ProjectError("boundary needs >= 3 vertices")
        unknown = set(self.flags) - set(FLAGS)
        if unknown:
            raise ProjectError(f"unknown flags {unknown}")
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bess_mwh_dc"] = self.bess_containers * self.container_mwh
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectInput":
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in keys}).validate()

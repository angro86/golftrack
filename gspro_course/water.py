"""Assemble the course water: pond polygons + the creek buffered into a channel.

The creek ("Green Hills Creek") is mapped in OSM as waterway=stream lines; we
buffer them into a thin water-hazard channel. Ponds come from natural=water /
golf=water_hazard polygons.
"""
import json

from shapely.geometry import mapping, shape
from shapely.ops import transform as shp_transform, unary_union
from pyproj import Transformer

POND_CATS = {"water", "water_hazard", "lateral_water_hazard"}
CREEK_HALFWIDTH_M = 2.0


def generate(cfg, features):
    fwd = Transformer.from_crs(4326, cfg.epsg, always_xy=True)
    inv = Transformer.from_crs(cfg.epsg, 4326, always_xy=True)
    to_utm = lambda g: shp_transform(fwd.transform, g)
    to_ll = lambda g: shp_transform(inv.transform, g)

    out = []
    for f in features:
        if f["category"] in POND_CATS and f["geom"].geom_type == "Polygon":
            out.append(("pond", f["geom"]))

    creek = [to_utm(f["geom"]) for f in features
             if f["category"] == "creek" and f["geom"].geom_type == "LineString"]
    if creek:
        buf = unary_union([ln.buffer(CREEK_HALFWIDTH_M, cap_style=2) for ln in creek])
        parts = [buf] if buf.geom_type == "Polygon" else list(buf.geoms)
        for p in parts:
            out.append(("creek", to_ll(p)))
    return out


def write_geojson(cfg, polys):
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"category": "water", "kind": kind},
         "geometry": mapping(g)} for kind, g in polys]}
    p = cfg.derived_dir / "water.geojson"
    p.write_text(json.dumps(gj))
    return p


def load(cfg):
    p = cfg.derived_dir / "water.geojson"
    if not p.exists():
        return []
    gj = json.loads(p.read_text())
    return [{"category": "water", "geom": shape(ft["geometry"]),
             "tags": {"kind": ft["properties"].get("kind", "")}}
            for ft in gj["features"] if shape(ft["geometry"]).is_valid]

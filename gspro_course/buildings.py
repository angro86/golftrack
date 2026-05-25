"""Per-footprint building heights from LIDAR (height-above-ground surface).

Gives the 6,500+ neighborhood footprints + clubhouse real heights so they
import as the skyline framing the holes.
"""
import json

import numpy as np
from shapely.geometry import mapping, shape
from shapely.ops import transform as shp_transform, unary_union
from pyproj import Transformer

from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox


def compute(cfg, features, res=2048):
    from skimage.draw import polygon as draw_polygon
    from gspro_course import lidar

    surf, cell, _n, _p = lidar.build_chm(cfg, features, res=res, mask_buildings=False)
    (xmin, ymin, xmax, ymax), (ccx, ccy) = utm_bbox(cfg)
    proj = Projector(cfg.epsg)

    # course boundary (UTM) to flag the clubhouse (largest building inside it)
    fwd = Transformer.from_crs(4326, cfg.epsg, always_xy=True)
    to_utm = lambda g: shp_transform(fwd.transform, g)
    bnd = [to_utm(f["geom"]) for f in features if f["category"] == "course_boundary"]
    boundary = unary_union(bnd) if bnd else None

    out = []
    for f in features:
        if f["category"] != "building" or f["geom"].geom_type != "Polygon":
            continue
        ring = list(f["geom"].exterior.coords)
        cc = np.array([(proj.xy(lo, la)[0] - xmin) / cell for lo, la in ring])
        rr = np.array([(ymax - proj.xy(lo, la)[1]) / cell for lo, la in ring])
        yy, xx = draw_polygon(rr, cc, shape=(res, res))
        if len(yy) < 3:
            continue
        vals = surf[yy, xx]
        vals = vals[vals > 0.5]
        if len(vals) < 3:
            continue
        h = float(np.percentile(vals, 75))
        if h < 2 or h > 60:
            h = float(np.clip(h, 2, 60))
        gu = to_utm(f["geom"])
        out.append({
            "geom": f["geom"],
            "height_m": round(h, 1),
            "levels": max(1, round(h / 3.2)),
            "area_m2": round(gu.area),
            "in_course": bool(boundary and gu.representative_point().within(boundary)),
            "tags": f["tags"],
        })

    # clubhouse = explicit tag, else the largest building inside the boundary
    club = None
    for b in out:
        t = b["tags"]
        if t.get("golf") == "clubhouse" or t.get("amenity") == "clubhouse" \
                or t.get("building") in ("clubhouse",):
            club = b
            break
    if club is None:
        inside = [b for b in out if b["in_course"]]
        if inside:
            club = max(inside, key=lambda b: b["area_m2"])
    for b in out:
        b["kind"] = "clubhouse" if b is club else "building"
    return out


def write_geojson(cfg, buildings):
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"category": "building", "kind": b["kind"],
                        "height_m": b["height_m"], "levels": b["levels"],
                        "area_m2": b["area_m2"], "in_course": b["in_course"]},
         "geometry": mapping(b["geom"])} for b in buildings]}
    out = cfg.derived_dir / "buildings.geojson"
    out.write_text(json.dumps(gj))
    return out


def load(cfg):
    p = cfg.derived_dir / "buildings.geojson"
    if not p.exists():
        return []
    gj = json.loads(p.read_text())
    return [{"category": "building", "geom": shape(ft["geometry"]),
             "tags": ft["properties"]} for ft in gj["features"]]

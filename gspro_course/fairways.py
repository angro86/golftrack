"""Generate fairway polygons for holes that OSM didn't map.

Buffers each hole centerline into a corridor, clips it to the course boundary,
subtracts greens/bunkers/water, and lets the detected tree crowns pinch the
edges so the fairway narrows through tree-lined holes. Holes that already have
an OSM fairway are left alone.
"""
import json

from shapely.geometry import Point, Polygon, MultiPolygon, shape, mapping
from shapely.ops import unary_union, transform as shp_transform
from pyproj import Transformer

HALF_WIDTH_M = 16.0   # ~32 m corridor
MIN_PIECE_AREA = 90.0


def _fill_holes(g):
    if g.geom_type == "Polygon":
        return Polygon(g.exterior)
    if g.geom_type == "MultiPolygon":
        return MultiPolygon([Polygon(p.exterior) for p in g.geoms])
    return g


def generate(cfg, features):
    fwd = Transformer.from_crs(4326, cfg.epsg, always_xy=True)
    inv = Transformer.from_crs(cfg.epsg, 4326, always_xy=True)
    to_utm = lambda g: shp_transform(fwd.transform, g)
    to_ll = lambda g: shp_transform(inv.transform, g)

    def union_cat(cats):
        gs = [to_utm(f["geom"]) for f in features
              if f["category"] in cats and f["geom"].geom_type == "Polygon"]
        return unary_union(gs) if gs else None

    boundary = union_cat({"course_boundary"})
    osm_fw = [to_utm(f["geom"]) for f in features if f["category"] == "fairway"]
    hazards = union_cat({"green", "water", "water_hazard", "lateral_water_hazard"})
    bunkers = union_cat({"bunker"})

    tj = cfg.derived_dir / "trees.json"
    trees = json.loads(tj.read_text())["trees"] if tj.exists() else []

    holes = sorted(
        [f for f in features if f["category"] == "hole"
         and f["tags"].get("ref", "").isdigit()],
        key=lambda f: int(f["tags"]["ref"]))

    results = []
    for h in holes:
        ref = int(h["tags"]["ref"])
        cl = to_utm(h["geom"])
        if any(cl.intersects(fw) for fw in osm_fw):
            continue  # OSM already maps this fairway

        corr = cl.buffer(HALF_WIDTH_M)
        if boundary is not None:
            corr = corr.intersection(boundary)
        for sub in (hazards, bunkers):
            if sub is not None and not sub.is_empty:
                corr = corr.difference(sub)

        reach = cl.buffer(HALF_WIDTH_M + 18)
        crowns = [Point(t["x_utm"], t["y_utm"]).buffer(max(t["crown_radius_m"], 2.0))
                  for t in trees if reach.contains(Point(t["x_utm"], t["y_utm"]))]
        if crowns:
            corr = corr.difference(unary_union(crowns))

        pieces = (list(corr.geoms) if corr.geom_type == "MultiPolygon"
                  else ([corr] if not corr.is_empty else []))
        keep = [p for p in pieces if p.intersects(cl) and p.area > MIN_PIECE_AREA]
        if not keep:
            continue
        fw = _fill_holes(unary_union(keep)).simplify(1.0)
        results.append((ref, to_ll(fw)))

    return results


def write_geojson(cfg, results):
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"category": "fairway", "ref": ref, "generated": True},
         "geometry": mapping(geom)} for ref, geom in results]}
    out = cfg.derived_dir / "fairways.geojson"
    out.write_text(json.dumps(gj))
    return out


def load_generated(cfg):
    p = cfg.derived_dir / "fairways.geojson"
    if not p.exists():
        return []
    gj = json.loads(p.read_text())
    feats = []
    for ft in gj["features"]:
        g = shape(ft["geometry"])
        if g.is_valid and not g.is_empty:
            feats.append({"category": "fairway", "geom": g,
                          "tags": {"ref": str(ft["properties"].get("ref", "")),
                                   "generated": "yes"}})
    return feats

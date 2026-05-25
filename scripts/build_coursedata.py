#!/usr/bin/env python3
"""Consolidate everything into one course_data.json (GreenKeeper reference).

Usage:
    python scripts/build_coursedata.py green-hills
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm
from gspro_course.geo import Projector, compass_bearing, compass_label


def _read(p):
    return json.loads(p.read_text()) if p.exists() else None


def main():
    cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "green-hills")
    cfg.ensure_dirs()
    d = cfg.derived_dir
    proj = Projector(cfg.epsg)
    features = osm.parse(osm.fetch(cfg))

    greens = [f for f in features if f["category"] == "green"]
    holes_geom = {int(f["tags"]["ref"]): f for f in features
                  if f["category"] == "hole" and f["tags"].get("ref", "").isdigit()}

    def nearest_green_center(end_xy):
        best, bd = None, 1e18
        for g in greens:
            c = g["geom"].centroid
            cx, cy = proj.xy(c.x, c.y)
            dist = (cx - end_xy[0]) ** 2 + (cy - end_xy[1]) ** 2
            if dist < bd:
                bd, best = dist, (round(c.y, 7), round(c.x, 7))
        return best

    back = {}
    bt = _read(d / "back_tees.geojson")
    if bt:
        for ft in bt["features"]:
            from shapely.geometry import shape
            c = shape(ft["geometry"]).centroid
            back[int(ft["properties"]["ref"])] = [round(c.y, 7), round(c.x, 7)]

    holes_report = {h["ref"]: h for h in (_read(d / "holes.json") or {}).get("holes", [])}
    terrain = _read(d / "terrain_meta.json") or {}
    sc = cfg.scorecard or {}
    tees = sc.get("tees", [])

    holes = []
    for ref in range(1, 19):
        if ref not in holes_geom:
            continue
        ll = list(holes_geom[ref]["geom"].coords)
        tee_xy = proj.xy(*ll[0])
        end_xy = proj.xy(*ll[-1])
        brg = compass_bearing(tee_xy, end_xy)
        rep = holes_report.get(ref, {})
        holes.append({
            "hole": ref,
            "par": rep.get("par"),
            "handicap": rep.get("hcp"),
            "yards": rep.get("yards"),
            "play_bearing_deg": round(brg),
            "faces": compass_label(brg),
            "tee_forward_latlon": [round(ll[0][1], 7), round(ll[0][0], 7)],
            "tee_black_latlon": back.get(ref),
            "green_center_latlon": nearest_green_center(end_xy),
        })

    counts = {c: sum(1 for f in features if f["category"] == c)
              for c in ("green", "tee", "bunker", "cartpath")}
    for name, f in (("trees", d / "trees.json"), ("buildings", d / "buildings.geojson"),
                    ("water", d / "water.geojson"), ("fairways", d / "fairways.geojson")):
        j = _read(f)
        if j:
            counts[name] = j.get("count") or len(j.get("features", j.get("trees", [])))

    out = {
        "course": cfg.name,
        "location": cfg.location,
        "architect": cfg.architect,
        "center_latlon": [cfg.lat, cfg.lon],
        "par": sc.get("par_by_hole") and sum(sc["par_by_hole"]),
        "tees": [{k: t.get(k) for k in ("name", "yards", "par", "rating", "slope")}
                 for t in tees],
        "terrain": {k: terrain.get(k) for k in
                    ("crs_epsg", "box_m", "heightmap_res", "meters_per_pixel",
                     "min_elev_m", "max_elev_m", "unity_terrain_height_m")},
        "feature_counts": counts,
        "holes": holes,
    }
    (d / "course_data.json").write_text(json.dumps(out, indent=2))
    print(f"== {cfg.name}: course_data.json ==")
    print(f"  {len(holes)} holes, par {out['par']}, "
          f"{tees[0]['yards'] if tees else '?'} yd ({tees[0]['name'] if tees else ''})")
    print(f"  feature counts: {counts}")
    print("wrote", d / "course_data.json")


if __name__ == "__main__":
    main()

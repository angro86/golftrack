"""Place the missing championship (longest) tee boxes.

Auto-estimates each black tee by extending the line of play backward from the
mapped tee by the scorecard yardage gap. Estimates are written to an editable
override file (config/<slug>-black-tees.yaml) so exact, locally-known positions
can be supplied (lat/lon) and used instead.
"""
import math

import yaml
from shapely.geometry import Polygon, mapping, shape
from pyproj import Transformer

from gspro_course.config import REPO_ROOT

M_TO_YD = 1.09361
DEFAULT_THRESHOLD_YD = 25.0
BOX_LEN_M = 11.0
BOX_WID_M = 9.0


def _overrides_path(cfg):
    return REPO_ROOT / "config" / f"{cfg.slug}-black-tees.yaml"


def load_overrides(cfg):
    p = _overrides_path(cfg)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    out = {}
    for ref, v in (data.get("black_tees") or {}).items():
        if v and v.get("lat") and v.get("lon"):
            out[int(ref)] = v
    return out


def _box(cx, cy, bearing_deg, inv):
    ux, uy = math.sin(math.radians(bearing_deg)), math.cos(math.radians(bearing_deg))
    vx, vy = -uy, ux
    hl, hw = BOX_LEN_M / 2, BOX_WID_M / 2
    corners = [(cx + ux * hl + vx * hw, cy + uy * hl + vy * hw),
               (cx + ux * hl - vx * hw, cy + uy * hl - vy * hw),
               (cx - ux * hl - vx * hw, cy - uy * hl - vy * hw),
               (cx - ux * hl + vx * hw, cy - uy * hl + vy * hw)]
    return Polygon([inv.transform(x, y) for x, y in corners])


def auto_estimate(cfg, features, threshold_yd=DEFAULT_THRESHOLD_YD):
    if not cfg.scorecard:
        return []
    fwd = Transformer.from_crs(4326, cfg.epsg, always_xy=True)
    inv = Transformer.from_crs(cfg.epsg, 4326, always_xy=True)
    yds = max(cfg.scorecard["tees"], key=lambda t: t["yards"])["holes_yards"]
    holes = {int(f["tags"]["ref"]): f for f in features
             if f["category"] == "hole" and f["tags"].get("ref", "").isdigit()}
    est = []
    for ref in range(1, 19):
        if ref not in holes:
            continue
        xy = [fwd.transform(lon, lat) for lon, lat in holes[ref]["geom"].coords]
        length = sum(math.dist(xy[i], xy[i + 1]) for i in range(len(xy) - 1))
        gap = yds[ref - 1] - length * M_TO_YD
        if gap <= threshold_yd:
            continue
        (x0, y0), (x1, y1) = xy[0], xy[1]
        bearing = (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360) % 360
        ux, uy = math.sin(math.radians(bearing)), math.cos(math.radians(bearing))
        ext = gap / M_TO_YD
        cx, cy = x0 - ux * ext, y0 - uy * ext
        lon, lat = inv.transform(cx, cy)
        est.append({"ref": ref, "lat": round(lat, 7), "lon": round(lon, 7),
                    "bearing": round(bearing, 1), "gap_yd": round(gap),
                    "card_yd": yds[ref - 1]})
    return est


def write_template(cfg, est):
    p = _overrides_path(cfg)
    if p.exists():
        return p
    lines = [
        "# Black/Blue Combo (longest) tee box centers.",
        "# Auto-estimated by extending the line of play back by the yardage gap.",
        "# CORRECT the lat/lon to the real tee (right-click it in Google Maps to",
        "# copy coords). bearing = play direction in degrees (0=N, 90=E).",
        "black_tees:",
    ]
    for e in est:
        lines.append(f"  {e['ref']}: {{lat: {e['lat']}, lon: {e['lon']}, "
                     f"bearing: {e['bearing']}}}   # gap {e['gap_yd']} yd "
                     f"-> card {e['card_yd']}")
    p.write_text("\n".join(lines) + "\n")
    return p


def generate(cfg, features):
    inv = Transformer.from_crs(cfg.epsg, 4326, always_xy=True)
    fwd = Transformer.from_crs(4326, cfg.epsg, always_xy=True)
    est = {e["ref"]: e for e in auto_estimate(cfg, features)}
    ov = load_overrides(cfg)
    results = []
    for ref in sorted(set(est) | set(ov)):
        if ref in ov:
            v = ov[ref]
            lat, lon = float(v["lat"]), float(v["lon"])
            bearing = float(v.get("bearing", est.get(ref, {}).get("bearing", 0)))
            source = "manual"
        else:
            e = est[ref]
            lat, lon, bearing = e["lat"], e["lon"], e["bearing"]
            source = "auto"
        cx, cy = fwd.transform(lon, lat)
        results.append({"ref": ref, "geom": _box(cx, cy, bearing, inv),
                        "source": source})
    return results


def write_geojson(cfg, results):
    import json
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"category": "tee", "tee": "black", "ref": r["ref"],
                        "source": r["source"]},
         "geometry": mapping(r["geom"])} for r in results]}
    out = cfg.derived_dir / "back_tees.geojson"
    out.write_text(json.dumps(gj))
    return out


def load(cfg):
    import json
    p = cfg.derived_dir / "back_tees.geojson"
    if not p.exists():
        return []
    gj = json.loads(p.read_text())
    return [{"category": "tee", "geom": shape(ft["geometry"]),
             "tags": {"tee": "black", "ref": str(ft["properties"].get("ref", "")),
                      "source": ft["properties"].get("source", "")}}
            for ft in gj["features"]]

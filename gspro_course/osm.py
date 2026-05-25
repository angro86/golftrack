"""Pull course + scenery features from OpenStreetMap via the Overpass API."""
import json
import time
from pathlib import Path

import requests
from shapely.geometry import LineString, Polygon, mapping

# OSM tags we treat as filled areas vs. open lines
AREA_GOLF = {"green", "tee", "bunker", "fairway", "rough", "water_hazard",
             "lateral_water_hazard", "driving_range", "clubhouse"}
LINE_GOLF = {"hole", "cartpath", "path"}


def build_query(lat, lon, course_r, scenery_r):
    return f"""[out:json][timeout:120];
(
  way(around:{course_r},{lat},{lon})["golf"];
  way(around:{course_r},{lat},{lon})["leisure"="golf_course"];
  relation(around:{course_r},{lat},{lon})["leisure"="golf_course"];
  way(around:{course_r},{lat},{lon})["natural"="water"];
  way(around:{course_r},{lat},{lon})["waterway"];
  way(around:{scenery_r},{lat},{lon})["building"];
  way(around:{scenery_r},{lat},{lon})["aeroway"];
);
out tags geom;"""


def fetch(cfg, force=False) -> dict:
    raw_path = cfg.raw_dir / "osm.json"
    if raw_path.exists() and not force:
        return json.loads(raw_path.read_text())
    cfg.ensure_dirs()
    query = build_query(cfg.lat, cfg.lon, cfg.course_radius_m, cfg.scenery_radius_m)
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(
                cfg.overpass_endpoint,
                data={"data": query},
                headers={"User-Agent": cfg.user_agent, "Accept": "application/json"},
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            raw_path.write_text(json.dumps(data))
            return data
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"Overpass fetch failed after retries: {last_err}")


def _geom_lonlat(el):
    return [(p["lon"], p["lat"]) for p in el.get("geometry", [])]


def categorize(el):
    t = el.get("tags", {})
    if "golf" in t:
        return t["golf"]
    if t.get("leisure") == "golf_course":
        return "course_boundary"
    if t.get("natural") == "water":
        return "water"
    if t.get("waterway"):
        return "creek"
    if t.get("aeroway"):
        return "aeroway:" + t["aeroway"]
    if "building" in t:
        return "building"
    return None


def parse(data: dict):
    """Return a list of features: {category, geom (shapely, lon/lat), tags}."""
    features = []
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        coords = _geom_lonlat(el)
        if len(coords) < 2:
            continue
        cat = categorize(el)
        if cat is None:
            continue
        base = cat.split(":")[0]
        is_area = (base in AREA_GOLF or base in ("course_boundary", "water",
                                                 "building"))
        try:
            if is_area:
                if coords[0] != coords[-1]:
                    coords = coords + [coords[0]]
                if len(coords) < 4:
                    continue
                geom = Polygon(coords)
            else:
                geom = LineString(coords)
        except Exception:  # noqa: BLE001
            continue
        features.append({"category": cat, "geom": geom, "tags": el.get("tags", {})})
    return features


def to_geojson(features) -> dict:
    out = {"type": "FeatureCollection", "features": []}
    for f in features:
        props = {"category": f["category"]}
        props.update(f["tags"])
        out["features"].append({
            "type": "Feature",
            "properties": props,
            "geometry": mapping(f["geom"]),
        })
    return out


def counts(features):
    from collections import Counter
    return dict(Counter(f["category"] for f in features))

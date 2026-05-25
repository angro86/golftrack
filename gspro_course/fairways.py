"""Detect fairways from the 0.3 m aerial as the lightest mown green grass.

Mown fairway reads brighter/lighter green than the rough in NAIP. We take the
green pixels inside the course, keep the brightest fraction, bridge mowing
stripes, drop greens/tees/bunkers/water + tree crowns, restrict to the hole
corridors, and polygonize into detailed fairway shapes.
"""
import json
import warnings

import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import transform as shp_transform, unary_union
from pyproj import Transformer

from gspro_course.terrain import utm_bbox


def _rasterize(polys_utm, xmin, ymax, cell, shp, dilate=0):
    from skimage.draw import polygon as draw_polygon
    from skimage.morphology import binary_dilation, disk
    m = np.zeros(shp, bool)
    for g in polys_utm:
        parts = [g] if g.geom_type == "Polygon" else (
            list(g.geoms) if g.geom_type == "MultiPolygon" else [])
        for gg in parts:
            xs, ys = gg.exterior.coords.xy
            cc = (np.asarray(xs) - xmin) / cell
            rr = (ymax - np.asarray(ys)) / cell
            yy, xx = draw_polygon(rr, cc, shape=shp)
            m[yy, xx] = True
    if dilate:
        m = binary_dilation(m, disk(dilate))
    return m


def generate(cfg, features, contrast=5.0, near_centerline_m=40,
             close_radius=4, bg_sigma=55):
    """Fairway = grass that is locally brighter/lusher than its surroundings.

    A global brightness cut fails (lighting varies hole to hole); instead we
    flag grass whose green channel exceeds the local mean of nearby grass —
    i.e. the consistent mown lanes that stand out from the rough beside them.
    """
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    from skimage.morphology import (closing, opening, disk,
                                    remove_small_objects, remove_small_holes)
    from skimage.draw import disk as draw_disk
    from rasterio.features import shapes as rio_shapes
    from rasterio.transform import from_origin

    rgb = np.asarray(Image.open(cfg.raw_dir / "naip.png").convert("RGB")).astype(float)
    px = rgb.shape[0]
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    cell = cfg.terrain_box_m / px
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    grass = (2 * G - R - B > 8) & (G > 60)

    fwd = Transformer.from_crs(4326, cfg.epsg, always_xy=True)
    inv = Transformer.from_crs(cfg.epsg, 4326, always_xy=True)
    to_utm = lambda g: shp_transform(fwd.transform, g)
    to_ll = lambda g: shp_transform(inv.transform, g)

    def upolys(cats):
        return [to_utm(f["geom"]) for f in features
                if f["category"] in cats and f["geom"].geom_type == "Polygon"]

    boundary = upolys({"course_boundary"})
    bmask = (_rasterize(boundary, xmin, ymax, cell, (px, px))
             if boundary else np.ones((px, px), bool))
    exclude = _rasterize(upolys({"green", "tee", "bunker", "water", "water_hazard",
                                 "lateral_water_hazard", "clubhouse", "building"}),
                         xmin, ymax, cell, (px, px), dilate=2)

    tmask = np.zeros((px, px), bool)
    tj = cfg.derived_dir / "trees.json"
    if tj.exists():
        for t in json.loads(tj.read_text())["trees"]:
            rr, cc = draw_disk(((ymax - t["y_utm"]) / cell, (t["x_utm"] - xmin) / cell),
                               max(t["crown_radius_m"] / cell, 1.5), shape=(px, px))
            tmask[rr, cc] = True

    cls = [to_utm(f["geom"]) for f in features if f["category"] == "hole"]
    corridor = (_rasterize([unary_union([c.buffer(near_centerline_m) for c in cls])],
                           xmin, ymax, cell, (px, px)) if cls else np.ones((px, px), bool))
    base = bmask & corridor & ~exclude & ~tmask
    if (base & grass).sum() < 1000:
        return []

    # local mean of green over nearby grass, then flag the brighter lanes
    gs = gaussian_filter(G, 2)
    gm = gaussian_filter(np.where(grass, gs, 0.0), bg_sigma)
    wt = gaussian_filter(grass.astype(float), bg_sigma)
    local_bg = gm / np.maximum(wt, 1e-6)
    fw = base & grass & ((gs - local_bg) > contrast)

    m2 = cell * cell
    fw = closing(fw, disk(close_radius))
    fw = remove_small_holes(fw, int(250 / m2))
    fw = opening(fw, disk(2))
    fw = remove_small_objects(fw, int(450 / m2))

    transform = from_origin(xmin, ymax, cell, cell)
    polys = []
    for geom, _v in rio_shapes(fw.astype(np.uint8), mask=fw, transform=transform):
        g = shape(geom)
        if g.area < 450:
            continue
        g = g.simplify(2.0)
        polys.append(to_ll(Polygon(g.exterior) if g.geom_type == "Polygon" else g))
    return polys


def write_geojson(cfg, polys):
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"category": "fairway", "source": "aerial"},
         "geometry": mapping(g)} for g in polys]}
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
                          "tags": {"source": "aerial"}})
    return feats

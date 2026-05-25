"""Stream USGS 3DEP LIDAR (EPT) and detect individual trees.

Pipeline: traverse the Entwine octree for our bbox -> decode LAZ nodes ->
reproject to UTM -> grid a canopy-top surface (DSM) -> subtract the bare-earth
DEM -> Canopy Height Model -> local-maxima treetops + watershed crowns. OSM
building footprints are burned out of the CHM so houses aren't read as trees.
"""
import json
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
from pyproj import Transformer

from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox

NOISE_CLASSES = {7, 18}  # low / high noise


def query_bbox_3857(cfg):
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    t = Transformer.from_crs(cfg.epsg, 3857, always_xy=True)
    xs, ys = [], []
    for ux in (xmin, xmax):
        for uy in (ymin, ymax):
            x, y = t.transform(ux, uy)
            xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


class EptReader:
    def __init__(self, ept_url, ua):
        self.base = ept_url.rsplit("/", 1)[0]
        self.ua = ua
        meta = requests.get(ept_url, headers={"User-Agent": ua}, timeout=40).json()
        self.cube = meta["bounds"]

    def _hier(self, key):
        r = requests.get(f"{self.base}/ept-hierarchy/{key}.json",
                         headers={"User-Agent": self.ua}, timeout=40)
        r.raise_for_status()
        return r.json()

    def _node_xy(self, d, x, y):
        side = (self.cube[3] - self.cube[0]) / (2 ** d)
        nx0 = self.cube[0] + x * side
        ny0 = self.cube[1] + y * side
        return (nx0, ny0, nx0 + side, ny0 + side)

    def nodes_in(self, bbox, max_depth):
        qx0, qy0, qx1, qy1 = bbox

        def hit(b):
            return not (b[2] < qx0 or b[0] > qx1 or b[3] < qy0 or b[1] > qy1)

        out, seen = [], set()

        def walk(hkey):
            if hkey in seen:
                return
            seen.add(hkey)
            for k, c in self._hier(hkey).items():
                d, x, y, _z = map(int, k.split("-"))
                if d > max_depth or not hit(self._node_xy(d, x, y)):
                    continue
                if c == -1:
                    walk(k)
                else:
                    out.append(k)

        walk("0-0-0-0")
        return sorted(set(out))

    def _fetch(self, key, bbox):
        try:
            import laspy
            content = requests.get(f"{self.base}/ept-data/{key}.laz",
                                   headers={"User-Agent": self.ua}, timeout=90).content
            las = laspy.read(BytesIO(content))
        except Exception:
            return None
        x = np.asarray(las.x); y = np.asarray(las.y); z = np.asarray(las.z)
        cls = np.asarray(las.classification)
        qx0, qy0, qx1, qy1 = bbox
        m = (x >= qx0) & (x <= qx1) & (y >= qy0) & (y <= qy1)
        m &= ~np.isin(cls, list(NOISE_CLASSES))
        return x[m], y[m], z[m], cls[m]

    def read_bbox(self, bbox, max_depth=12, workers=24):
        keys = self.nodes_in(bbox, max_depth)
        parts = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(lambda k: self._fetch(k, bbox), keys):
                if r is not None and len(r[0]):
                    parts.append(r)
        if not parts:
            raise RuntimeError("no LIDAR points returned")
        x = np.concatenate([p[0] for p in parts])
        y = np.concatenate([p[1] for p in parts])
        z = np.concatenate([p[2] for p in parts])
        cls = np.concatenate([p[3] for p in parts])
        return {"x": x, "y": y, "z": z, "cls": cls}, len(keys)


def _building_mask(features, cfg, res):
    from skimage.draw import polygon as draw_polygon
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    proj = Projector(cfg.epsg)
    cell = cfg.terrain_box_m / res
    mask = np.zeros((res, res), bool)
    for f in features:
        if f["category"] != "building" or f["geom"].geom_type != "Polygon":
            continue
        cc, rr = [], []
        for lon, lat in f["geom"].exterior.coords:
            x, y = proj.xy(lon, lat)
            cc.append((x - xmin) / cell)
            rr.append((ymax - y) / cell)
        yy, xx = draw_polygon(np.array(rr), np.array(cc), shape=mask.shape)
        mask[yy, xx] = True
    return mask


def build_chm(cfg, features, res=2048, mask_buildings=True):
    import rasterio
    from gspro_course import terrain

    reader = EptReader(cfg.ept_url, cfg.user_agent)
    bbox = query_bbox_3857(cfg)
    pts, n_nodes = reader.read_bbox(bbox, cfg.lidar_max_depth)

    to_utm = Transformer.from_crs(3857, cfg.epsg, always_xy=True)
    ux, uy = to_utm.transform(pts["x"], pts["y"])
    z = pts["z"]
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    cell = cfg.terrain_box_m / res

    col = np.clip(((ux - xmin) / cell).astype(int), 0, res - 1)
    row = np.clip(((ymax - uy) / cell).astype(int), 0, res - 1)
    dsm = np.full((res, res), -np.inf)
    np.maximum.at(dsm, (row, col), z)

    # bare-earth DTM from the terrain stage, resampled to the CHM grid
    dem_path = terrain.fetch_dem(cfg)
    with rasterio.open(dem_path) as ds:
        dem = ds.read(1).astype("float64")
    idx = (np.linspace(0, dem.shape[0] - 1, res)).astype(int)
    dtm = dem[np.ix_(idx, idx)]

    chm = np.where(np.isfinite(dsm), dsm - dtm, 0.0)
    chm[~np.isfinite(chm)] = 0.0
    chm = np.clip(chm, 0, 60)
    if mask_buildings:
        chm[_building_mask(features, cfg, res)] = 0.0
    return chm, cell, n_nodes, len(z)


def detect_trees(cfg, chm, cell):
    from scipy import ndimage as ndi
    from skimage.feature import peak_local_max
    from skimage.segmentation import watershed

    sm = ndi.gaussian_filter(chm, sigma=1.0)
    min_h = cfg.min_tree_height_m
    canopy = sm > min_h
    md = max(1, int(round(cfg.min_tree_spacing_m / cell)))
    peaks = peak_local_max(sm, min_distance=md, threshold_abs=min_h, labels=canopy)
    if len(peaks) == 0:
        return []
    markers = np.zeros(sm.shape, int)
    for i, (r, c) in enumerate(peaks, 1):
        markers[r, c] = i
    labels = watershed(-sm, markers, mask=canopy)
    areas = np.bincount(labels.ravel())

    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    inv = Transformer.from_crs(cfg.epsg, 4326, always_xy=True)
    trees = []
    for i, (r, c) in enumerate(peaks, 1):
        h = float(sm[r, c])
        if h > 55:  # likely not a tree
            continue
        area_cells = int(areas[i]) if i < len(areas) else 1
        crown_r = float(np.sqrt(max(area_cells, 1) * cell * cell / np.pi))
        crown_r = min(crown_r, 14.0)
        x = xmin + (c + 0.5) * cell
        y = ymax - (r + 0.5) * cell
        lon, lat = inv.transform(x, y)
        trees.append({
            "x_utm": round(x, 2), "y_utm": round(y, 2),
            "lon": round(lon, 7), "lat": round(lat, 7),
            "height_m": round(h, 1), "crown_radius_m": round(crown_r, 1),
            "bucket": "tall" if h >= 15 else ("mid" if h >= 6 else "shrub"),
        })
    return trees

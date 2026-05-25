"""Per-hole viewshed: what each tee can actually see (SFO, the bay, the city,
the hills), via line-of-sight over a wide-area DEM with earth-curvature.
"""
import math
import time

import numpy as np
import requests
from pyproj import Transformer

from gspro_course.geo import Projector

WIDE_BOX_M = 24000
WIDE_PX = 2049
EARTH_R = 6371000.0

# name: (lat, lon, target_elev_m | None=use DEM elevation there)
LANDMARKS = {
    "SFO airport": (37.6213, -122.3790, 3.0),
    "SF Bay": (37.6330, -122.3560, 0.0),
    "Downtown SF": (37.7790, -122.4180, 150.0),
}


class WideTerrain:
    def __init__(self, cfg, force=False):
        import rasterio
        self.proj = Projector(cfg.epsg)
        self.cx, self.cy = self.proj.xy(cfg.lon, cfg.lat)
        h = WIDE_BOX_M / 2
        self.xmin, self.ymax = self.cx - h, self.cy + h
        self.cell = WIDE_BOX_M / (WIDE_PX - 1)
        with rasterio.open(self._fetch(cfg, force)) as ds:
            z = ds.read(1).astype("float64")
        z[~np.isfinite(z)] = 0.0
        z[z < -1e5] = 0.0
        self.z = z
        self.n = z.shape[0]

    def _fetch(self, cfg, force):
        out = cfg.raw_dir / "wide_dem.tif"
        if out.exists() and not force:
            return out
        cfg.ensure_dirs()
        h = WIDE_BOX_M / 2
        params = {
            "bbox": f"{self.cx-h},{self.cy-h},{self.cx+h},{self.cy+h}",
            "bboxSR": cfg.epsg, "imageSR": cfg.epsg,
            "size": f"{WIDE_PX},{WIDE_PX}", "format": "tiff",
            "pixelType": "F32", "interpolation": "RSP_BilinearInterpolation",
            "f": "image",
        }
        url = cfg.dem_service.rstrip("/") + "/exportImage"
        last = None
        for attempt in range(4):
            try:
                r = requests.get(url, params=params,
                                 headers={"User-Agent": cfg.user_agent}, timeout=180)
                r.raise_for_status()
                if r.content[:2] not in (b"II", b"MM"):
                    raise RuntimeError(f"not a tiff: {r.content[:160]!r}")
                out.write_bytes(r.content)
                return out
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"wide DEM fetch failed: {last}")

    def elev(self, x, y):
        c = (x - self.xmin) / self.cell
        r = (self.ymax - y) / self.cell
        if r < 0 or c < 0 or r > self.n - 1 or c > self.n - 1:
            return None
        r0, c0 = int(r), int(c)
        r1, c1 = min(r0 + 1, self.n - 1), min(c0 + 1, self.n - 1)
        fr, fc = r - r0, c - c0
        return float(
            self.z[r0, c0] * (1 - fr) * (1 - fc) + self.z[r0, c1] * (1 - fr) * fc +
            self.z[r1, c0] * fr * (1 - fc) + self.z[r1, c1] * fr * fc)

    def visible(self, px, py, tx, ty, t_elev, eye=1.7, clearance=1.0, steps=700):
        pz = self.elev(px, py)
        if pz is None:
            return None
        tz = self.elev(tx, ty) if t_elev is None else t_elev
        dist = math.hypot(tx - px, ty - py)
        obs = pz + eye
        for i in range(1, steps):
            f = i / steps
            terr = self.elev(px + (tx - px) * f, py + (ty - py) * f)
            if terr is None:
                continue
            d = dist * f
            curv = d * (dist - d) / (2 * EARTH_R)
            los = obs + f * (tz - obs)
            if (terr - curv) > los + clearance:
                return False
        return True


def _bearing(p, q):
    return (math.degrees(math.atan2(q[0] - p[0], q[1] - p[1])) + 360) % 360


def analyze(cfg, features):
    wt = WideTerrain(cfg)
    proj = Projector(cfg.epsg)
    lm_xy = {name: (proj.xy(lon, lat), te) for name, (lat, lon, te) in LANDMARKS.items()}

    holes = sorted(
        [f for f in features if f["category"] == "hole"
         and f["tags"].get("ref", "").isdigit()],
        key=lambda f: int(f["tags"]["ref"]))

    rows = []
    for f in holes:
        ref = int(f["tags"]["ref"])
        cl = [proj.xy(lon, lat) for lon, lat in f["geom"].coords]
        tee, grn = cl[0], cl[-1]
        play = _bearing(tee, grn)
        vis = {}
        for name, ((tx, ty), te) in lm_xy.items():
            v = wt.visible(tee[0], tee[1], tx, ty, te)
            ahead = abs(((_bearing(tee, (tx, ty)) - play + 180) % 360) - 180) <= 60
            vis[name] = {"visible": bool(v), "ahead": ahead,
                         "bearing": round(_bearing(tee, (tx, ty)))}
        rows.append({"ref": ref, "tee_elev_m": round(wt.elev(*tee), 1),
                     "play_bearing": round(play), "views": vis})
    return wt, rows

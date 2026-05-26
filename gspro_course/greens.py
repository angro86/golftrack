"""High-resolution putting-surface contours from the raw LIDAR point cloud.

The 1 m base heightmap captures each green's overall tilt/tiers; this regrids
the greens from the dense 2023 point cloud (deeper octree level) at ~0.5 m to
recover the sub-meter micro-contour that matters for putting.
"""
import numpy as np
from pyproj import Transformer

from gspro_course.geo import Projector
from gspro_course.lidar import EptReader


def _green_bbox(geom_ll, cfg, collar):
    proj = Projector(cfg.epsg)
    xs, ys = [], []
    for lo, la in geom_ll.exterior.coords:
        x, y = proj.xy(lo, la)
        xs.append(x); ys.append(y)
    ux0, uy0 = min(xs) - collar, min(ys) - collar
    ux1, uy1 = max(xs) + collar, max(ys) + collar
    u2m = Transformer.from_crs(cfg.epsg, 3857, always_xy=True)
    cs, rs = [], []
    for ux in (ux0, ux1):
        for uy in (uy0, uy1):
            X, Y = u2m.transform(ux, uy)
            cs.append(X); rs.append(Y)
    return (min(cs), min(rs), max(cs), max(rs)), (ux0, uy0, ux1, uy1)


def highres(cfg, features, depth=14, gres=0.5, collar=6.0):
    from scipy.interpolate import griddata
    reader = EptReader(cfg.ept_url, cfg.user_agent)
    m2u = Transformer.from_crs(3857, cfg.epsg, always_xy=True)
    greens = [f for f in features if f["category"] == "green"]
    out = []
    for i, g in enumerate(greens, 1):
        bbox3857, (ux0, uy0, ux1, uy1) = _green_bbox(g["geom"], cfg, collar)
        try:
            pts, _n = reader.read_bbox(bbox3857, max_depth=depth, workers=16)
        except Exception:
            continue
        cls = pts["cls"]
        m = cls == 2                       # bare-earth (putting surface)
        if m.sum() < 50:
            m = np.isin(cls, [1, 2])
        gx, gy = m2u.transform(pts["x"][m], pts["y"][m])
        gz = pts["z"][m]
        area = (ux1 - ux0) * (uy1 - uy0)
        nx = max(int((ux1 - ux0) / gres) + 1, 4)
        ny = max(int((uy1 - uy0) / gres) + 1, 4)
        xs = np.linspace(ux0, ux1, nx)
        ys = np.linspace(uy1, uy0, ny)
        GX, GY = np.meshgrid(xs, ys)
        Z = griddata((gx, gy), gz, (GX, GY), method="linear")
        out.append({
            "ref": i, "grid": Z, "extent": (ux0, uy0, ux1, uy1),
            "gres": gres, "n_ground": int(m.sum()),
            "density_ppm2": round(m.sum() / max(area, 1), 1),
            "geom": g["geom"],
        })
    return out

"""Acquire a bare-earth DEM (USGS 3DEP) and build a Unity-ready heightmap."""
import json
import time

import numpy as np
import requests

from gspro_course.geo import Projector


def utm_bbox(cfg):
    """Square capture box (xmin, ymin, xmax, ymax) in the projected CRS."""
    proj = Projector(cfg.epsg)
    cx, cy = proj.xy(cfg.lon, cfg.lat)
    h = cfg.terrain_box_m / 2.0
    return (cx - h, cy - h, cx + h, cy + h), (cx, cy)


def fetch_dem(cfg, force=False):
    out = cfg.raw_dir / "dem.tif"
    if out.exists() and not force:
        return out
    cfg.ensure_dirs()
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    res = cfg.heightmap_res
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bboxSR": cfg.epsg,
        "imageSR": cfg.epsg,
        "size": f"{res},{res}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }
    url = cfg.dem_service.rstrip("/") + "/exportImage"
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, params=params,
                             headers={"User-Agent": cfg.user_agent}, timeout=180)
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "")
            if "image/tiff" not in ct and not r.content[:2] in (b"II", b"MM"):
                raise RuntimeError(f"unexpected response ({ct}): {r.content[:200]!r}")
            out.write_bytes(r.content)
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"DEM fetch failed: {last}")


def build_heightmap(cfg, force=False):
    import rasterio
    from PIL import Image

    dem_path = fetch_dem(cfg, force=force)
    with rasterio.open(dem_path) as ds:
        elev = ds.read(1).astype("float64")
        nodata = ds.nodata

    mask = np.isfinite(elev)
    if nodata is not None:
        mask &= elev != nodata
    mask &= elev > -1e6
    if not mask.all():
        elev[~mask] = np.median(elev[mask])

    zmin = float(elev[mask].min())
    zmax = float(elev[mask].max())
    span = max(zmax - zmin, 1e-6)

    norm = (elev - zmin) / span
    h16 = np.clip(np.round(norm * 65535.0), 0, 65535).astype("uint16")

    # 16-bit PNG (OPCD/Unity import)
    png_path = cfg.derived_dir / "heightmap.png"
    Image.fromarray(h16, mode="I;16").save(png_path)

    # 16-bit little-endian RAW (Unity Terrain "Import Raw")
    raw_path = cfg.derived_dir / "heightmap.raw"
    h16.astype("<u2").tofile(raw_path)

    meta = {
        "course": cfg.name,
        "crs_epsg": cfg.epsg,
        "box_m": cfg.terrain_box_m,
        "heightmap_res": int(h16.shape[0]),
        "meters_per_pixel": round(cfg.terrain_box_m / (h16.shape[0] - 1), 4),
        "min_elev_m": round(zmin, 2),
        "max_elev_m": round(zmax, 2),
        "height_span_m": round(span, 2),
        "unity_terrain_size_x_m": cfg.terrain_box_m,
        "unity_terrain_size_z_m": cfg.terrain_box_m,
        "unity_terrain_height_m": round(span, 2),
        "raw_format": "16-bit unsigned, little-endian, no header",
    }
    (cfg.derived_dir / "terrain_meta.json").write_text(json.dumps(meta, indent=2))
    return elev, mask, meta


def render_hillshade(cfg, elev, features, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    res = elev.shape[0]
    mpp = cfg.terrain_box_m / (res - 1)
    dy, dx = np.gradient(elev, mpp)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az, alt = np.radians(315.0), np.radians(45.0)
    hs = (np.sin(alt) * np.sin(slope) +
          np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    hs = np.clip(hs, 0, 1)

    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    proj = Projector(cfg.epsg)

    def to_px(x, y):
        return ((x - xmin) / cfg.terrain_box_m * (res - 1),
                (ymax - y) / cfg.terrain_box_m * (res - 1))

    fig, ax = plt.subplots(figsize=(13, 13), dpi=130)
    ax.imshow(hs, cmap="gray", extent=[0, res, res, 0], zorder=1)
    ax.imshow(elev, cmap="terrain", alpha=0.35, extent=[0, res, res, 0], zorder=2)

    for f in features:
        if f["category"] != "hole":
            continue
        pts = [to_px(*proj.xy(lon, lat)) for lon, lat in f["geom"].coords]
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                color="#cc2222", lw=1.4, zorder=3)
        ref = f["tags"].get("ref", "")
        mid = pts[len(pts) // 2]
        ax.text(mid[0], mid[1], str(ref), color="white", fontsize=8,
                fontweight="bold", ha="center", va="center", zorder=4,
                bbox=dict(boxstyle="circle,pad=0.2", fc="#cc2222", ec="white", lw=0.5))

    ax.set_xlim(0, res); ax.set_ylim(res, 0)
    ax.set_xticks([]); ax.set_yticks([])
    zmin, zmax = float(elev.min()), float(elev.max())
    ax.set_title(f"{cfg.name} — bare-earth terrain (USGS 3DEP 1 m)\n"
                 f"{cfg.terrain_box_m} m box · elevation {zmin:.0f}–{zmax:.0f} m "
                 f"(span {zmax - zmin:.0f} m)", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path

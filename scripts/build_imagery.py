#!/usr/bin/env python3
"""Phase acquire (imagery): USGS NAIP aerial -> overlay + spline validation.

Usage:
    python scripts/build_imagery.py green-hills [--force] [--px 4096]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, imagery
from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox
from gspro_course.splines import LAYERS, LINE_LAYERS


def overlay_splines(rgb, features, cfg, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    px = rgb.shape[0]
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    proj = Projector(cfg.epsg)
    box = cfg.terrain_box_m

    def to_px(lon, lat):
        x, y = proj.xy(lon, lat)
        return ((x - xmin) / box * px, (ymax - y) / box * px)

    fig, ax = plt.subplots(figsize=(14, 14), dpi=150)
    ax.imshow(rgb, extent=[0, px, px, 0], zorder=0)
    for f in features:
        spec = LAYERS.get(f["category"])
        if not spec:
            continue
        layer, fill, stroke, _smooth = spec
        g = f["geom"]
        coords = (list(g.exterior.coords) if g.geom_type == "Polygon"
                  else list(g.coords))
        pts = [to_px(lon, lat) for lon, lat in coords]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        if layer == "centerline":
            ax.plot(xs, ys, color="#ffffff", lw=1.2, ls="--", zorder=3, alpha=0.9)
        elif layer in LINE_LAYERS:
            ax.plot(xs, ys, color=stroke, lw=1.0, zorder=2, alpha=0.8)
        else:
            ax.plot(xs, ys, color=stroke, lw=1.3, zorder=2)

    ax.set_xlim(0, px); ax.set_ylim(px, 0)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{cfg.name} — NAIP aerial (0.3 m) with OSM splines overlaid\n"
                 f"(check the creek/ponds + the 14 un-mapped fairways)", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--px", type=int, default=4000)
    args = ap.parse_args()

    cfg = config.load(args.course)
    cfg.ensure_dirs()
    print(f"== {cfg.name}: NAIP imagery ==")

    tif = imagery.fetch_naip(cfg, px=args.px, force=args.force)
    rgb, nir, _ = imagery.load_rgb(tif)
    print("aerial:", rgb.shape, "bands incl NIR" if nir is not None else "RGB only")

    imagery.save_preview(rgb, cfg.preview_dir / "aerial.png")
    print("wrote", cfg.preview_dir / "aerial.png")

    veg = imagery.ndvi(rgb, nir)
    if veg is not None:
        from PIL import Image
        vimg = (np.clip((veg + 0.2) / 1.0, 0, 1) * 255).astype("uint8")
        Image.fromarray(vimg).resize((1600, 1600)).save(
            cfg.preview_dir / "ndvi.png")
        print("wrote", cfg.preview_dir / "ndvi.png",
              f"(veg fraction NDVI>0.2: {(veg > 0.2).mean():.0%})")

    features = osm.parse(osm.fetch(cfg))
    overlay_splines(rgb, features, cfg, cfg.preview_dir / "aerial_splines.png")
    print("wrote", cfg.preview_dir / "aerial_splines.png")


if __name__ == "__main__":
    main()

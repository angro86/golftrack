#!/usr/bin/env python3
"""Phase 2 (terrain): USGS 3DEP DEM -> Unity-ready 16-bit heightmap + preview.

Usage:
    python scripts/build_terrain.py green-hills [--force]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, terrain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    ap.add_argument("--force", action="store_true", help="re-download DEM")
    args = ap.parse_args()

    cfg = config.load(args.course)
    cfg.ensure_dirs()
    print(f"== {cfg.name}: terrain ==")

    elev, mask, meta = terrain.build_heightmap(cfg, force=args.force)
    print("heightmap:", json.dumps(meta, indent=2))

    # hole overlay for the preview (reuse cached OSM)
    features = osm.parse(osm.fetch(cfg))
    png = terrain.render_hillshade(cfg, elev, features,
                                   cfg.preview_dir / "terrain.png")
    print("wrote", png)
    print("wrote", cfg.derived_dir / "heightmap.png")
    print("wrote", cfg.derived_dir / "heightmap.raw")


if __name__ == "__main__":
    main()

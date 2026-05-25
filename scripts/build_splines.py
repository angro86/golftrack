#!/usr/bin/env python3
"""Phase features: OSM golf polygons -> Inkscape-layered SVG splines + preview.

Usage:
    python scripts/build_splines.py green-hills
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, splines, fairways, tees


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course")
    ap.add_argument("--force", action="store_true", help="re-download OSM data")
    args = ap.parse_args()

    cfg = config.load(args.course)
    cfg.ensure_dirs()
    print(f"== {cfg.name}: splines ==")

    # drop OSM's crude fairways in favour of the aerial-detected ones
    features = [f for f in osm.parse(osm.fetch(cfg, force=args.force))
                if f["category"] != "fairway"]
    features += fairways.load_generated(cfg) + tees.load(cfg)
    svg_path = cfg.derived_dir / "splines.svg"
    counts = splines.build(features, cfg, svg_path)
    print("splines per layer:", json.dumps(counts))
    print("wrote", svg_path)

    png = splines.render_preview(features, cfg, cfg.preview_dir / "splines.png")
    print("wrote", png)


if __name__ == "__main__":
    main()

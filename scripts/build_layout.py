#!/usr/bin/env python3
"""Phase 3 (features) + hole report + preview.

Pulls OSM data for a course, writes a GeoJSON of all features, a hole-by-hole
report, and a layout preview PNG.

Usage:
    python scripts/build_layout.py green-hills [--force]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gspro_course import config, osm, holes, render


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course", help="course slug or path to config yaml")
    ap.add_argument("--force", action="store_true", help="re-download OSM data")
    args = ap.parse_args()

    cfg = config.load(args.course)
    cfg.ensure_dirs()
    print(f"== {cfg.name} ({cfg.location}) ==")

    data = osm.fetch(cfg, force=args.force)
    features = osm.parse(data)
    print("OSM feature counts:", osm.counts(features))

    geojson = osm.to_geojson(features)
    gj_path = cfg.derived_dir / "features.geojson"
    gj_path.write_text(json.dumps(geojson))
    print("wrote", gj_path)

    report = holes.build(features, cfg)
    (cfg.derived_dir / "holes.json").write_text(json.dumps(report, indent=2))
    print()
    print(holes.format_table(report))
    print()

    png = render.render(features, report, cfg, cfg.preview_dir / "layout.png")
    print("wrote", png)


if __name__ == "__main__":
    main()

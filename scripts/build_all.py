#!/usr/bin/env python3
"""Run the whole pipeline for a course, in dependency order.

Usage:
    python scripts/build_all.py green-hills [--crops]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# (script, needs) — order matters (deps first)
STAGES = [
    "build_layout",     # OSM features, hole report, layout preview
    "build_terrain",    # USGS 3DEP DEM -> 16-bit heightmap
    "build_imagery",    # NAIP 0.3 m aerial overlay
    "build_trees",      # LIDAR canopy -> individual trees
    "build_backtees",   # championship tees (+ prune trees on the pads)
    "build_fairways",   # aerial-detected fairways
    "build_water",      # creek + ponds
    "build_buildings",  # LIDAR building heights
    "build_viewshed",   # per-hole SFO/bay/city line-of-sight
    "build_splines",    # Inkscape-layered SVG of all features
    "build_coursedata",  # consolidated course_data.json
]


def main():
    course = next((a for a in sys.argv[1:] if not a.startswith("-")), "green-hills")
    stages = STAGES + (["hole_crops"] if "--crops" in sys.argv else [])
    for i, stage in enumerate(stages, 1):
        print(f"\n{'='*64}\n[{i}/{len(stages)}] {stage} {course}\n{'='*64}")
        r = subprocess.run([PY, str(ROOT / "scripts" / f"{stage}.py"), course])
        if r.returncode != 0:
            print(f"!! {stage} failed (exit {r.returncode}) — stopping")
            sys.exit(r.returncode)
    print(f"\nDONE — outputs in courses/{course}/")


if __name__ == "__main__":
    main()

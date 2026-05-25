# golftrack — GSPro course builder

Build real golf courses for the **GSPro** simulator from public data, automating
as much of the pipeline as possible before the manual OPCD/Unity polish.

First target course: **Green Hills Country Club**, Millbrae CA (Alister MacKenzie, 1930).

## Why this exists

GSPro only loads courses built with the OPCD toolchain (Blender + Inkscape +
Unity + GreenKeeper), and the final 3D assembly is manual. This repo automates
everything *upstream* of that so the Unity build starts mostly done:

| Phase | Output | Status |
|-------|--------|--------|
| acquire | OSM features, USGS LIDAR, NAIP aerial | OSM + DEM + NAIP done |
| terrain | bare-earth heightmap (OPCD/Unity ready) | done (USGS 3DEP 1 m) |
| features | golf polygons → pre-traced Inkscape splines (SVG) | done (smoothed, layered) |
| trees | LIDAR canopy → individual tree positions (Arborist) | done (12,410 trees) |
| scenery | surrounding buildings / airport / water | done (viewshed + building heights) |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
# Pull OSM data, write features.geojson + hole report + preview PNG
.venv/bin/python scripts/build_layout.py green-hills

# Pull USGS 3DEP DEM, write 16-bit heightmap (PNG + RAW) + meta + hillshade
.venv/bin/python scripts/build_terrain.py green-hills

# Detect fairways from the aerial (consistent mown green)
.venv/bin/python scripts/build_fairways.py green-hills

# Place championship (black) tee boxes; edit config/<slug>-black-tees.yaml for exact spots
.venv/bin/python scripts/build_backtees.py green-hills

# Assemble water: ponds + buffered creek channel
.venv/bin/python scripts/build_water.py green-hills

# Per-hole viewshed to SFO / the bay / the city (wide-area DEM line-of-sight)
.venv/bin/python scripts/build_viewshed.py green-hills

# Per-footprint building heights from LIDAR (neighborhood + clubhouse)
.venv/bin/python scripts/build_buildings.py green-hills

# OSM + generated fairways -> Inkscape-layered SVG splines (smoothed) + preview
.venv/bin/python scripts/build_splines.py green-hills

# USGS NAIP aerial (0.3 m) -> georeferenced overlay + spline validation image
.venv/bin/python scripts/build_imagery.py green-hills

# Stream LIDAR point cloud -> canopy model -> individual trees (csv for Arborist)
.venv/bin/python scripts/build_trees.py green-hills

# Per-hole validation crops (aerial + trees + splines) to check vs the app
.venv/bin/python scripts/hole_crops.py green-hills
```

Outputs land in `courses/<slug>/`:
- `raw/` — downloaded source data (gitignored)
- `derived/` — geojson, hole report, (later) heightmaps + spline SVGs
- `preview/` — layout PNG

## Data sources

- **OpenStreetMap** (Overpass API) — fairways, greens, tees, bunkers, holes, water, buildings
- **USGS 3DEP LIDAR** (Entwine Point Tiles on AWS) — terrain + tree canopy
- **USDA NAIP** — aerial imagery overlay

Course parameters live in `config/<slug>.yaml`.

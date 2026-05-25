"""Toolkit for building real golf courses for the GSPro simulator from public data.

Pipeline phases:
  1. acquire  — pull OSM features + USGS LIDAR + aerial imagery by bounding box
  2. terrain  — LIDAR point cloud -> bare-earth heightmap (OPCD/Unity ready)
  3. features — OSM golf polygons -> pre-traced splines (SVG) for Inkscape
  4. trees    — LIDAR canopy -> individual tree positions for OPCD Arborist
  5. scenery  — surrounding buildings/airport/water for the view corridors
"""

__version__ = "0.1.0"

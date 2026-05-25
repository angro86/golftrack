import math
from pyproj import Transformer


def utm_epsg(lat: float, lon: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


class Projector:
    """Convert between WGS84 (lon/lat) and a projected CRS in meters."""

    def __init__(self, epsg: int):
        self.epsg = epsg
        self._fwd = Transformer.from_crs(4326, epsg, always_xy=True)
        self._inv = Transformer.from_crs(epsg, 4326, always_xy=True)

    def xy(self, lon: float, lat: float):
        return self._fwd.transform(lon, lat)

    def lonlat(self, x: float, y: float):
        return self._inv.transform(x, y)

    def ring_xy(self, lonlat_coords):
        return [self._fwd.transform(lon, lat) for lon, lat in lonlat_coords]


def line_length_m(xy_coords) -> float:
    total = 0.0
    for (x0, y0), (x1, y1) in zip(xy_coords, xy_coords[1:]):
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def compass_bearing(xy_from, xy_to) -> float:
    """Bearing in degrees (0=N, 90=E) from one projected point to another."""
    de = xy_to[0] - xy_from[0]
    dn = xy_to[1] - xy_from[1]
    return (math.degrees(math.atan2(de, dn)) + 360.0) % 360.0


def compass_label(bearing: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(bearing / 22.5) % 16]

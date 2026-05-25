"""Acquire USGS NAIP aerial imagery (~0.3 m) as a georeferenced overlay."""
import time

import numpy as np
import requests

from gspro_course.geo import Projector
from gspro_course.terrain import utm_bbox

NAIP_SERVICE = ("https://imagery.nationalmap.gov/arcgis/rest/services/"
                "USGSNAIPImagery/ImageServer")


def fetch_naip(cfg, px=4000, force=False):
    # PNG (lossless, compressed): the service 500s on large multiband tiffs.
    px = min(px, 4000)  # service export cap
    out = cfg.raw_dir / "naip.png"
    if out.exists() and not force:
        return out
    cfg.ensure_dirs()
    (xmin, ymin, xmax, ymax), _ = utm_bbox(cfg)
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bboxSR": cfg.epsg,
        "imageSR": cfg.epsg,
        "size": f"{px},{px}",
        "format": "png",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }
    last = None
    for attempt in range(4):
        try:
            r = requests.get(NAIP_SERVICE + "/exportImage", params=params,
                             headers={"User-Agent": cfg.user_agent}, timeout=240)
            r.raise_for_status()
            if r.content[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError(f"not a png: {r.content[:200]!r}")
            out.write_bytes(r.content)
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"NAIP fetch failed: {last}")


def load_rgb(png_path):
    """RGB array + (no NIR from rendered PNG); georef is the known UTM box."""
    from PIL import Image
    rgb = np.asarray(Image.open(png_path).convert("RGB"))
    return rgb.astype("uint8"), None, None


def ndvi(rgb, nir):
    """Vegetation index from NIR + red — a tree/canopy precursor."""
    if nir is None:
        return None
    red = rgb[..., 0].astype("float32")
    nir = nir.astype("float32")
    denom = nir + red
    out = np.zeros_like(red)
    np.divide(nir - red, denom, out=out, where=denom > 0)
    return out


def save_preview(rgb, out_path, max_px=2200):
    from PIL import Image
    img = Image.fromarray(rgb)
    if max(img.size) > max_px:
        scale = max_px / max(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    img.save(out_path)
    return out_path

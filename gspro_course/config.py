from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class CourseConfig:
    def __init__(self, data: dict):
        self._d = data
        c = data["course"]
        self.name = c["name"]
        self.slug = c["slug"]
        self.location = c.get("location", "")
        self.architect = c.get("architect", "")
        self.holes = c.get("holes")
        self.lat = data["center"]["lat"]
        self.lon = data["center"]["lon"]
        self.course_radius_m = data["course_radius_m"]
        self.scenery_radius_m = data["scenery_radius_m"]
        self.epsg = data["projected_epsg"]
        self.overpass_endpoint = data["overpass"]["endpoint"]
        self.user_agent = data["overpass"]["user_agent"]
        self.landmarks = data.get("landmarks", {})

    @property
    def course_dir(self) -> Path:
        return REPO_ROOT / "courses" / self.slug

    @property
    def raw_dir(self) -> Path:
        return self.course_dir / "raw"

    @property
    def derived_dir(self) -> Path:
        return self.course_dir / "derived"

    @property
    def preview_dir(self) -> Path:
        return self.course_dir / "preview"

    def ensure_dirs(self):
        for d in (self.raw_dir, self.derived_dir, self.preview_dir):
            d.mkdir(parents=True, exist_ok=True)


def load(slug_or_path: str) -> CourseConfig:
    p = Path(slug_or_path)
    if not p.exists():
        p = REPO_ROOT / "config" / f"{slug_or_path}.yaml"
    with open(p) as f:
        return CourseConfig(yaml.safe_load(f))

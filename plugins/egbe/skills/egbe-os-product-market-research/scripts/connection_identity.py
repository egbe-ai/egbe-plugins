"""Load opt-in identity from this catalog's shared project-local request helper."""
import importlib.util
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _helper():
    root = Path(__file__).resolve().parents[1]
    quickstart = "egbe-os-quickstart" if root.name.startswith("egbe-os-") else "quickstart"
    path = root.parent / quickstart / "scripts/egbe-curl.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("egbe_connection_request", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def connection_headers(url):
    helper = _helper()
    return helper.connection_headers(url) if helper else {}

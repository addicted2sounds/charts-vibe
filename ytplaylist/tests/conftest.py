from pathlib import Path
import importlib.util
import sys

import pytest

YTPLAYLIST_DIR = Path(__file__).resolve().parents[1]
if str(YTPLAYLIST_DIR) not in sys.path:
    sys.path.insert(0, str(YTPLAYLIST_DIR))


@pytest.fixture(scope="session")
def ytplaylist_app():
    app_path = YTPLAYLIST_DIR / "app.py"
    spec = importlib.util.spec_from_file_location("ytplaylist_app", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

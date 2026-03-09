from pathlib import Path
import importlib.util
import sys

import pytest

CHART_DIR = Path(__file__).resolve().parents[1]
if str(CHART_DIR) not in sys.path:
    sys.path.insert(0, str(CHART_DIR))


@pytest.fixture(scope="session")
def chart_app():
    app_path = CHART_DIR / "app.py"
    spec = importlib.util.spec_from_file_location("chart_processor_app", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

from pathlib import Path
import importlib.util
import sys
import types

import pytest

YTMUSIC_DIR = Path(__file__).resolve().parents[1]
if str(YTMUSIC_DIR) not in sys.path:
    sys.path.insert(0, str(YTMUSIC_DIR))


@pytest.fixture(scope="session")
def ytmusic_app():
    # Stub ytmusicapi so module import succeeds without the package installed.
    if "ytmusicapi" not in sys.modules:
        stub_module = types.ModuleType("ytmusicapi")
        
        class StubYTMusic:
            def search(self, *args, **kwargs):
                return []

        stub_module.YTMusic = StubYTMusic
        sys.modules["ytmusicapi"] = stub_module

    app_path = YTMUSIC_DIR / "app.py"
    spec = importlib.util.spec_from_file_location("ytmusic_app", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

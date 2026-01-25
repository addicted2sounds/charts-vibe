from pathlib import Path
import importlib.util
import sys

import pytest

SCRAPER_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_scraper_module(module_name, filename):
    utils_path = SCRAPER_DIR / "utils.py"
    utils_spec = importlib.util.spec_from_file_location("scraper_utils", utils_path)
    utils_module = importlib.util.module_from_spec(utils_spec)
    utils_spec.loader.exec_module(utils_module)

    previous_utils = sys.modules.get("utils")
    sys.modules["utils"] = utils_module

    try:
        module_path = SCRAPER_DIR / filename
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_utils is not None:
            sys.modules["utils"] = previous_utils
        else:
            sys.modules.pop("utils", None)


@pytest.fixture(scope="session")
def beatport_module():
    return _load_scraper_module("beatport_module", "beatport.py")


@pytest.fixture(scope="session")
def clubtone_module():
    return _load_scraper_module("clubtone_module", "clubtone.py")


@pytest.fixture
def beatport_html():
    return (FIXTURES_DIR / "beatport_top100.html").read_text(encoding="utf-8")


@pytest.fixture
def clubtone_html():
    return (FIXTURES_DIR / "clubtone_top100.html").read_text(encoding="utf-8")

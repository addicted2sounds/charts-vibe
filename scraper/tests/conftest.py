from pathlib import Path
import sys

import pytest

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def beatport_html():
    return (FIXTURES_DIR / "beatport_top100.html").read_text(encoding="utf-8")


@pytest.fixture
def clubtone_html():
    return (FIXTURES_DIR / "clubtone_top100.html").read_text(encoding="utf-8")

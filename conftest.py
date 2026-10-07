import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attribution import load_config, load_dataset  # noqa: E402

BASE_CFG = {
    "pre_period_weeks": 4, "gap_weeks": 1, "max_lookback_weeks": 10,
    "exclude_holiday_weeks": True, "exclude_promo_weeks": True, "min_valid_weeks": 3,
}


@pytest.fixture(scope="session")
def ds():
    return load_dataset()


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture
def bcfg():
    return dict(BASE_CFG)

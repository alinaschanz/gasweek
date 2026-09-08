"""talks to a public rpc. skipped unless GASWEEK_LIVE=1."""
import itertools
import os

import pytest

from gasweek.fees import fetch
from gasweek.rpc import Rpc

pytestmark = pytest.mark.skipif(os.environ.get("GASWEEK_LIVE") != "1", reason="set GASWEEK_LIVE=1")


def test_one_hour_of_blocks_has_sane_timestamps_and_fees():
    rows = fetch(Rpc(), 300)
    assert len(rows) == 300
    assert all(0 < r.base_fee_gwei < 10_000 for r in rows)
    gaps = [b.timestamp - a.timestamp for a, b in itertools.pairwise(rows)]
    assert 10 <= sum(gaps) / len(gaps) <= 14

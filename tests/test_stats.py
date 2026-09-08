"""pure functions: percentiles, bins, page planning, timestamp interpolation, svg output."""
import xml.etree.ElementTree as ET

from gasweek import fees, stats, svg
from gasweek.fees import BlockFee, interpolate, parse_page, plan_pages
from gasweek.stats import bar, bucket, by_hour, by_weekday, gwei, median, percentile, summarize


def rows_for(hours: int, start_ts: int = 1_757_289_600, fee=lambda i: 1.0):  # start = 2025-09-08 00:00 utc
    out = []
    for i in range(hours * 300):
        out.append(BlockFee(number=1000 + i, timestamp=start_ts + i * 12, base_fee_gwei=fee(i), gas_used_ratio=0.5))
    return out


def test_percentiles():
    assert percentile([5, 1, 3], 50) == 3
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([1, 2, 3, 4], 0) == 1
    assert percentile([1, 2, 3, 4], 100) == 4
    assert median([7]) == 7


def test_plan_pages_covers_the_window_newest_first():
    pages = plan_pages(latest=10_000, blocks=2_500)
    assert pages == [(10_000, 1024), (8_976, 1024), (7_952, 452)]
    assert sum(c for _, c in pages) == 2_500
    assert plan_pages(latest=5, blocks=100) == [(5, 6)]  # cannot go below the genesis block


def test_interpolate_between_anchors():
    anchors = {100: 1_000, 200: 2_200}
    assert interpolate(anchors, 100) == 1_000
    assert interpolate(anchors, 150) == 1_600
    assert interpolate(anchors, 250) == 2_200 + 12 * 50
    assert interpolate(anchors, 90) == 1_000 - 120


def test_parse_page_drops_the_predicted_next_block():
    page = {"oldestBlock": "0x10", "baseFeePerGas": ["0x3b9aca00", "0x77359400", "0x1"], "gasUsedRatio": [0.5, 1.0],
            "baseFeePerBlobGas": ["0x1", "0x2", "0x3"]}
    rows = parse_page(page)
    assert [r["number"] for r in rows] == [16, 17]
    assert rows[0]["base_fee_gwei"] == 1.0 and rows[1]["base_fee_gwei"] == 2.0
    assert rows[1]["blob_fee_gwei"] == 2e-9
    assert parse_page({"oldestBlock": "0x1", "baseFeePerGas": ["0x1", "0x1"], "gasUsedRatio": [0.1]})[0]["blob_fee_gwei"] is None


def test_hour_bins_follow_the_timezone():
    rows = rows_for(2)  # 00:00-02:00 utc
    utc = by_hour(rows)
    assert len(utc[0]) == 300 and len(utc[1]) == 300 and not utc[2]
    berlin = by_hour(rows, 2)
    assert len(berlin[2]) == 300 and len(berlin[3]) == 300 and not berlin[0]


def test_weekday_bins():
    rows = rows_for(24)
    days = by_weekday(rows)
    assert sum(len(v) for v in days.values()) == 24 * 300
    assert len([d for d, v in days.items() if v]) == 1


def test_bucket_is_fixed_width_and_sorted():
    rows = rows_for(1)
    b = bucket(rows, 1800)
    assert len(b) == 2 and all(len(v) == 150 for _, v in b)
    assert b[0][0] < b[1][0]


def test_summary_finds_cheapest_and_priciest_hour():
    rows = rows_for(24, fee=lambda i: 0.2 if (i // 300) == 4 else 2.0 if (i // 300) == 15 else 1.0)
    s = summarize(rows)
    assert s["cheapest_hour"] == 4 and s["priciest_hour"] == 15
    assert s["blocks"] == 7200 and s["median"] == 1.0
    assert s["blob_median"] is None


def test_formatting():
    assert gwei(0.0483) == "0.048" and gwei(2.5) == "2.50" and gwei(12.34) == "12.3" and gwei(250) == "250"
    assert bar(5, 10, 10) == "#####" and bar(0, 10) == ""


def test_svg_is_well_formed_xml():
    rows = rows_for(30, fee=lambda i: 0.5 + (i % 300) / 300)
    doc = svg.render(rows, tz_hours=2)
    root = ET.fromstring(doc)
    assert root.tag.endswith("svg")
    assert "utc+2" in doc and "polyline" in doc


def test_fetch_uses_pages_and_anchors(monkeypatch):
    calls = []

    class FakeRpc:
        def block_number(self):
            return 2047

        def call(self, method, params):
            calls.append((method, params))
            count, newest = int(params[0], 16), int(params[1], 16)
            oldest = newest - count + 1
            return {"oldestBlock": hex(oldest), "baseFeePerGas": ["0x3b9aca00"] * (count + 1), "gasUsedRatio": [0.5] * count}

        def block_timestamp(self, number):
            return 1_000_000 + number * 12

    rows = fees.fetch(FakeRpc(), 2048, workers=1)
    assert len(rows) == 2048 and rows[0].number == 0 and rows[-1].number == 2047
    assert [p[:2] for m, p in calls if m == "eth_feeHistory"] == [["0x400", "0x7ff"], ["0x400", "0x3ff"]]
    assert rows[1000].timestamp == 1_000_000 + 1000 * 12  # interpolation lands on the real 12 s grid
    assert stats.median([r.base_fee_gwei for r in rows]) == 1.0

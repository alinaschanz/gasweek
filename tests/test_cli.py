"""the command line, with the network replaced by canned blocks."""
import csv

from gasweek import cli
from gasweek.fees import BlockFee


def fake_rows(hours=3):
    start = 1_757_289_600
    return [BlockFee(number=100 + i, timestamp=start + 12 * i, base_fee_gwei=0.5 + (i % 7) / 10, gas_used_ratio=0.5,
                     blob_fee_gwei=0.001) for i in range(hours * 300)]


def test_parse_tz():
    assert cli.parse_tz("utc") == 0 and cli.parse_tz("+2") == 2 and cli.parse_tz("-5:30") == -5.5


def test_table_svg_csv_and_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "fetch", lambda rpc, blocks, tips=False: fake_rows())
    svg_path, csv_path, sum_path = tmp_path / "f.svg", tmp_path / "f.csv", tmp_path / "daily.csv"
    assert cli.main(["--hours", "3", "--tz", "+2", "--svg", str(svg_path), "--csv", str(csv_path),
                     "--summary-append", str(sum_path)]) == 0
    out = capsys.readouterr().out
    assert "cheapest hour" in out and "utc+2" in out and "blob median" in out
    assert svg_path.read_text(encoding="utf-8").startswith("<svg")
    with open(csv_path, encoding="utf-8") as f:
        assert sum(1 for _ in f) == 900 + 1
    # a rerun for the same day replaces the row; another day adds one, sorted by date
    assert cli.main(["--hours", "3", "--summary-append", str(sum_path), "--quiet"]) == 0
    with open(sum_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["blocks"] == "900" and rows[0]["cheapest_hour_utc"] != ""
    earlier = dict(cli.summarize(fake_rows()), to_ts=fake_rows()[0].timestamp - 86400)
    cli.append_summary(str(sum_path), earlier)
    with open(sum_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["date_utc"] for r in rows] == sorted(r["date_utc"] for r in rows) and len(rows) == 2


def test_tips_column_and_csv(monkeypatch, tmp_path, capsys):
    rows = [BlockFee(number=r.number, timestamp=r.timestamp, base_fee_gwei=r.base_fee_gwei, gas_used_ratio=r.gas_used_ratio,
                     blob_fee_gwei=r.blob_fee_gwei, tips_gwei=(0.01, 0.05, 0.4)) for r in fake_rows(2)]
    seen = {}
    monkeypatch.setattr(cli, "fetch", lambda rpc, blocks, tips=False: (seen.__setitem__("tips", tips), rows)[1])
    csv_path = tmp_path / "t.csv"
    assert cli.main(["--hours", "2", "--tips", "--csv", str(csv_path)]) == 0
    out = capsys.readouterr().out
    assert seen["tips"] is True and "priority fees paid: p10 0.010  p50 0.050  p90 0.400" in out and "tip p50" in out
    with open(csv_path, encoding="utf-8") as f:
        header, first = f.readline().strip(), f.readline().strip()
    assert header.endswith("tip_p10_gwei,tip_p50_gwei,tip_p90_gwei") and first.endswith("0.01,0.05,0.4")


def test_json_output(monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch", lambda rpc, blocks, tips=False: fake_rows(1))
    assert cli.main(["--hours", "1", "--json"]) == 0
    assert '"median"' in capsys.readouterr().out


def test_bad_tz_is_an_error():
    assert cli.main(["--tz", "berlin"]) == 2

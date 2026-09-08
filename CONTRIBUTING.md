# contributing

## the data contract

`data/daily.csv` is the part of this repository other people may depend on, so:

- one row per utc date, describing the 24 hours that ended at the daily run (00:17 utc).
  a rerun for the same date replaces the row, it never adds a twin.
- columns are only ever added at the end. renaming or reordering an existing column is a
  breaking change and needs a note in `data/README.md` and a version bump.
- base fees are exact (they come from `eth_feeHistory`); timestamps are interpolated inside
  1024-block pages, so a row can be off by seconds, never by minutes. if you find a page
  where that is not true, that is a bug, please open an issue with the block numbers.
- the chart is derived data and may change shape without notice.

## code

- python 3.10+, standard library only.
- `python -m pytest -q` must pass offline; `GASWEEK_LIVE=1 python -m pytest -q` talks to a
  public rpc.
- `ruff check .` with the settings in `pyproject.toml`.
- the daily workflow runs `python -m gasweek` twice (24 h summary, 7 d chart). anything that
  makes those slower than a few minutes on a public node will be reverted.

## ideas that would be welcome

priority fee percentiles next to the base fee, a blob fee panel in the chart, and the same
interface for l2s. see the open issues.

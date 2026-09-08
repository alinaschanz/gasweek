# changelog

all notable changes to gasweek. the format follows [keep a changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [semver](https://semver.org/) as far as a command line tool has an api.

## [unreleased]

- a pypi workflow: trusted publishing on a release, switched on by a repository variable

- the chart grows a third panel with the blob base fee when the rows carry it

- `--tips`: p10/p50/p90 priority fees per block from `eth_feeHistory` reward percentiles; a `tip p50` column per hour, three csv columns

## [0.1.0] - 2026-09-08

first cut: base fee by hour of day over the last week, table, svg and a daily dataset.

- `eth_feeHistory` in parallel pages with interpolated timestamps
- hour-of-day and weekday tables, percentiles, svg chart, csv and json
- daily workflow writing `data/daily.csv` and `data/last-7d.svg`

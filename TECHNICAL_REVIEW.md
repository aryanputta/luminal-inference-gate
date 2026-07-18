# Technical Review Package

## Scope

This prototype compares two real `luminal_bench` `FullBenchReport` JSON
artifacts. It is not a benchmark runner and it does not claim a performance
improvement by itself.

## Verified locally

- Python test suite: `5 passed`
- Python modules compile with `python3 -m py_compile`
- The upstream Luminal benchmark crate compiles with and without the Metal
  feature.
- The Metal run on this machine stops with `No Metal device found`; no numbers
  are published from that failed run.
- Different device names fail closed.
- Missing candidate benchmarks fail the comparison.
- Latency regressions above the configured threshold fail the comparison.

## Reproduce

Run prototype tests:

```bash
python3 -m pytest -q
```

Run the real upstream benchmark on a Metal-capable Mac:

```bash
cargo bench -p luminal_bench --features metal --bench patterns -- --noplot
```

Then compare two reports:

```bash
python3 inference_gate.py baseline/bench_report.json candidate/bench_report.json \
  --threshold 5 --markdown-output inference-regression.md \
  --json-output inference-regression.json
```

## Security and privacy boundaries

- No Brain files, private workspace paths, outreach records, or credentials are
  included.
- The comparator reads only caller-provided JSON reports.
- The prototype accepts no browser-triggered shell commands, repository URLs, or
  compiler flags.
- A report is not evidence of a live run unless its provenance fields identify
  the hardware, timestamps, and source artifacts.

## Review decision requested

Review the comparator semantics, report schema assumptions, failure behavior,
and provenance requirements. Do not treat the repository as proof of a
performance gain until a real same-device baseline and candidate are produced.

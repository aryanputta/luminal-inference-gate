# Luminal DocGuard

DocGuard checks whether marked Rust examples in Luminal's MDX documentation still compile against the exact repository revision under review. It intentionally separates three states: `passed` means Cargo checked the snippet, `not_executed` means the fence is contextual, and `not_run` means the caller did not request compilation.

## Run

From the Luminal repository checkout:

```bash
python -m pip install markdown-it-py
python /path/to/docguard.py \
  --docs-root docs \
  --repo-root . \
  --config /path/to/docguard-config.json \
  --output docguard-report.json \
  --run
```

The tool uses an isolated temporary Cargo package and `cargo check --offline`. It does not accept arbitrary shell commands, repository URLs, or compiler flags. CI should use a dependency cache and upload the JSON report as an artifact.

## Inference Regression Gate

The higher-value production path consumes the existing `luminal_bench` full reports:

```bash
python inference_gate.py baseline/bench_report.json target/criterion/pattern_report.json \
  --threshold 5 --markdown-output inference-regression.md
```

It fails closed when hardware differs, a benchmark disappears, or latency exceeds
the configured threshold. It reports latency, throughput, and TFLOPS deltas while
preserving the baseline and candidate timestamps.

The baseline must be a real `luminal_bench` artifact produced on the same device;
the gate refuses to compare different hardware. No benchmark numbers are included
in this repository until they have been produced by the actual backend.

Serve `viewer/` with `python -m http.server 8787 --directory viewer` after placing a report at `viewer/report.json`. The viewer is static and labels cached evidence clearly.

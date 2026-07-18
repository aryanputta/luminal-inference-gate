"""Compare two luminal_bench FullBenchReport artifacts for CI regressions."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Comparison:
    key: str
    baseline_us: float
    candidate_us: float
    latency_delta_pct: float
    baseline_tflops: float
    candidate_tflops: float
    throughput_delta_pct: float
    status: str


def _pct(candidate: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0 if candidate == 0 else 100.0
    return (candidate - baseline) / baseline * 100.0


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any], threshold_pct: float = 5.0) -> dict[str, Any]:
    """Return a deterministic comparison and fail closed on incompatible runs."""
    base_hw = baseline.get("hardware", {})
    cand_hw = candidate.get("hardware", {})
    if base_hw.get("device_name") != cand_hw.get("device_name"):
        raise ValueError("baseline and candidate use different devices")
    base = {f"{r['pattern']}/{r['size']}": r for r in baseline.get("results", [])}
    cand = {f"{r['pattern']}/{r['size']}": r for r in candidate.get("results", [])}
    missing = sorted(set(base) - set(cand))
    added = sorted(set(cand) - set(base))
    comparisons: list[Comparison] = []
    for key in sorted(set(base) & set(cand)):
        b, c = base[key], cand[key]
        latency = _pct(float(c["time_us"]), float(b["time_us"]))
        throughput = _pct(float(c["throughput_gbps"]), float(b["throughput_gbps"]))
        status = "regressed" if latency > threshold_pct else "improved" if latency < -threshold_pct else "stable"
        comparisons.append(Comparison(key, float(b["time_us"]), float(c["time_us"]), latency, float(b["tflops"]), float(c["tflops"]), throughput, status))
    regressions = [c.key for c in comparisons if c.status == "regressed"]
    return {
        "schema_version": 1,
        "hardware": cand_hw,
        "threshold_pct": threshold_pct,
        "baseline_timestamp": baseline.get("timestamp"),
        "candidate_timestamp": candidate.get("timestamp"),
        "missing_in_candidate": missing,
        "new_in_candidate": added,
        "regressions": regressions,
        "status": "failed" if regressions or missing else "passed",
        "comparisons": [c.__dict__ for c in comparisons],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"## Inference regression gate: **{result['status'].upper()}**",
        f"Hardware: `{result['hardware'].get('device_name', 'unknown')}` | threshold: `{result['threshold_pct']:.1f}%` latency",
        "",
        "| Benchmark | Baseline us | Candidate us | Latency delta | Throughput delta | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in result["comparisons"]:
        lines.append(f"| `{row['key']}` | {row['baseline_us']:.2f} | {row['candidate_us']:.2f} | {row['latency_delta_pct']:+.2f}% | {row['throughput_delta_pct']:+.2f}% | {row['status']} |")
    if result["missing_in_candidate"]:
        lines.extend(["", "Missing in candidate: " + ", ".join(f"`{x}`" for x in result["missing_in_candidate"])])
    if result["new_in_candidate"]:
        lines.extend(["", "New in candidate: " + ", ".join(f"`{x}`" for x in result["new_in_candidate"])])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate Luminal inference benchmark regressions.")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--threshold", type=float, default=5.0)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    result = compare_reports(json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()), args.threshold)
    if args.json_output:
        args.json_output.write_text(json.dumps(result, indent=2) + "\n")
    markdown = render_markdown(result)
    if args.markdown_output:
        args.markdown_output.write_text(markdown)
    print(markdown, end="")
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

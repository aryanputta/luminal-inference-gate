import pytest

from inference_gate import compare_reports, render_markdown


def report(device: str = "Test GPU", time_us: float = 100.0, throughput: float = 10.0) -> dict:
    return {
        "hardware": {"device_name": device, "memory_gb": 24.0, "peak_bandwidth_gbps": 500.0, "peak_tflops": 10.0},
        "timestamp": "2026-07-18 00:00:00",
        "results": [{"pattern": "matmul", "size": "small", "time_us": time_us, "throughput_gbps": throughput, "tflops": 1.0}],
    }


def test_regression_fails_when_latency_exceeds_threshold() -> None:
    result = compare_reports(report(), report(time_us=106.0, throughput=9.4), threshold_pct=5.0)
    assert result["status"] == "failed"
    assert result["regressions"] == ["matmul/small"]
    assert "REGRESSION" not in render_markdown(result)


def test_improvement_passes_and_reports_delta() -> None:
    result = compare_reports(report(), report(time_us=94.0, throughput=10.6), threshold_pct=5.0)
    assert result["status"] == "passed"
    assert result["comparisons"][0]["status"] == "improved"
    assert "-6.00%" in render_markdown(result)


def test_mismatched_hardware_fails_closed() -> None:
    with pytest.raises(ValueError, match="different devices"):
        compare_reports(report(), report(device="Other GPU"))


def test_duplicate_benchmark_keys_fail_closed() -> None:
    duplicate = report()
    duplicate["results"].append(dict(duplicate["results"][0]))
    with pytest.raises(ValueError, match="duplicate benchmark key"):
        compare_reports(duplicate, report())


def test_empty_report_and_invalid_threshold_fail_closed() -> None:
    empty = report()
    empty["results"] = []
    with pytest.raises(ValueError, match="no benchmark results"):
        compare_reports(empty, report())
    with pytest.raises(ValueError, match="non-negative"):
        compare_reports(report(), report(), threshold_pct=-1)

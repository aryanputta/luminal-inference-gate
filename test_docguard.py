import json
from pathlib import Path

from docguard import build_report, extract_snippets


def test_extracts_only_rust_fences_with_source_lines(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.mdx").write_text("```rust\nlet x = 1;\n```\n\n```bash\necho hi\n```\n")
    snippets = extract_snippets(docs, {"executable": {}, "ignored": {}})
    assert len(snippets) == 1
    assert snippets[0].line_start == 1
    assert snippets[0].mode == "contextual"


def test_report_keeps_contextual_snippets_out_of_pass_count(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.mdx").write_text("```rust\nlet x = 1;\n```\n")
    report = build_report(docs, tmp_path, None, run=False, timeout=5)
    assert report["summary"]["counts"]["not_executed"] == 1
    assert report["summary"]["exit_code"] == 0


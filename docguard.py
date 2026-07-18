"""MDX Rust conformance scanner for Luminal documentation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from markdown_it import MarkdownIt
except ImportError as exc:  # pragma: no cover - surfaced as a useful CLI error
    raise SystemExit("Install dependencies with: uv sync") from exc


TOOL_VERSION = "0.1.0"


@dataclass(frozen=True)
class Snippet:
    snippet_id: str
    path: str
    language: str
    line_start: int
    line_end: int
    code: str
    mode: str
    reason: str | None = None


def _load_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"executable": {}, "ignored": {}}
    return json.loads(path.read_text())


def extract_snippets(docs_root: Path, config: dict[str, Any]) -> list[Snippet]:
    parser = MarkdownIt("commonmark")
    executable = config.get("executable", {})
    ignored = config.get("ignored", {})
    snippets: list[Snippet] = []
    for path in sorted(docs_root.rglob("*.mdx")):
        relative = path.relative_to(docs_root).as_posix()
        tokens = parser.parse(path.read_text(encoding="utf-8"))
        for index, token in enumerate(tokens):
            if token.type != "fence":
                continue
            language = token.info.strip().split()[0] if token.info.strip() else ""
            if language != "rust":
                continue
            start = (token.map or [0, 0])[0] + 1
            end = (token.map or [0, 0])[1]
            key = f"{relative}:{start}"
            mode = "contextual"
            reason = "Rust fence is not marked as a complete executable example."
            if key in executable:
                mode = "executable"
                reason = None
            if key in ignored:
                mode = "ignored_with_reason"
                reason = str(ignored[key])
            digest = hashlib.sha256(token.content.encode()).hexdigest()[:12]
            snippets.append(
                Snippet(
                    snippet_id=f"{relative}:{start}:{digest}",
                    path=relative,
                    language=language,
                    line_start=start,
                    line_end=end,
                    code=token.content,
                    mode=mode,
                    reason=reason,
                )
            )
    return snippets


def _wrapper(code: str) -> str:
    """Keep imports and statements verbatim while providing a main function."""
    if "fn main" in code:
        return code
    return f"fn main() {{\n{code}\n}}\n"


def _cargo_manifest(repo_root: Path) -> str:
    return f'''[package]\nname = "docguard_snippet"\nversion = "0.0.0"\nedition = "2024"\n\n[dependencies]\nluminal = {{ path = "{repo_root.as_posix()}" }}\n'''


def compile_snippet(snippet: Snippet, repo_root: Path, timeout: int) -> dict[str, Any]:
    if shutil.which("cargo") is None:
        return {"status": "tool_unavailable", "diagnostic": "cargo was not found on PATH"}
    with tempfile.TemporaryDirectory(prefix="docguard-") as temp:
        root = Path(temp)
        (root / "src").mkdir()
        (root / "Cargo.toml").write_text(_cargo_manifest(repo_root))
        (root / "src/main.rs").write_text(_wrapper(snippet.code))
        started = time.monotonic()
        try:
            result = subprocess.run(
                ["cargo", "check", "--offline", "--color", "never", "--manifest-path", str(root / "Cargo.toml")],
                cwd=repo_root,
                text=True,
                capture_output=True,
                timeout=timeout,
                env={**os.environ, "CARGO_TERM_COLOR": "never"},
            )
        except subprocess.TimeoutExpired as exc:
            return {"status": "timeout", "duration_ms": int((time.monotonic() - started) * 1000), "diagnostic": str(exc)}
        diagnostic = (result.stderr or result.stdout).strip()
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "diagnostic": diagnostic[-12000:],
        }


def build_report(docs_root: Path, repo_root: Path, config_path: Path | None, run: bool, timeout: int) -> dict[str, Any]:
    config = _load_config(config_path)
    snippets = extract_snippets(docs_root, config)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, capture_output=True, check=False).stdout.strip() or "unknown"
    results: list[dict[str, Any]] = []
    for snippet in snippets:
        item = {
            "id": snippet.snippet_id,
            "path": snippet.path,
            "line_start": snippet.line_start,
            "line_end": snippet.line_end,
            "mode": snippet.mode,
            "reason": snippet.reason,
            "source_sha256": hashlib.sha256(snippet.code.encode()).hexdigest(),
        }
        if snippet.mode == "ignored_with_reason":
            item["result"] = {"status": "ignored"}
        elif snippet.mode == "contextual":
            item["result"] = {"status": "not_executed"}
        elif run:
            item["result"] = compile_snippet(snippet, repo_root, timeout)
        else:
            item["result"] = {"status": "not_run", "diagnostic": "Run with --run to execute cargo check."}
        results.append(item)
    counts = {status: sum(item["result"]["status"] == status for item in results) for status in {item["result"]["status"] for item in results}}
    return {
        "schema_version": 1,
        "tool": {"name": "luminal-docguard", "version": TOOL_VERSION},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": {"path": repo_root.name, "commit": commit},
        "docs_root": docs_root.name,
        "execution": {"requested": run, "timeout_seconds": timeout},
        "summary": {"total_rust_fences": len(results), "counts": counts, "exit_code": 1 if any(item["result"]["status"] == "failed" for item in results) else 0},
        "snippets": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Find Rust API drift in Luminal MDX documentation.")
    parser.add_argument("--docs-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="Run cargo check for executable snippets")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    report = build_report(args.docs_root, args.repo_root, args.config, args.run, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))
    return int(report["summary"]["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

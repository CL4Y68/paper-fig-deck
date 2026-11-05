# -*- coding: utf-8 -*-
"""Keep the hand-written numbers in the docs honest.

docs/index.html quotes a test count and a pipeline step count. Both drifted
repeatedly (78 -> 85 -> 96 -> 100 tests) because they were updated by hand, so
CI now recomputes them from the code and fails on any mismatch.

Run: python tools/check_docs.py        # exit 1 when a number is stale
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def count_tests() -> int:
    """Number of collected pytest tests (same set CI runs)."""
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("pytest --collect-only failed:\n" + (r.stdout + r.stderr)[-2000:])
    total = 0
    for line in r.stdout.splitlines():
        m = re.match(r"tests/[^:]+: (\d+)\s*$", line.strip())
        if m:
            total += int(m.group(1))
    if not total:
        raise SystemExit("could not parse the test count from pytest --collect-only")
    return total


def pipeline_steps() -> int:
    """0 (validate) + the highest [N/M] marker printed by the driver."""
    src = (ROOT / "pipeline" / "run_pipeline.py").read_text(encoding="utf-8")
    marked = [int(m[0]) for m in re.findall(r"\[(\d+)/(\d+)\]", src)]
    if not marked:
        raise SystemExit("no [N/M] step markers found in run_pipeline.py")
    return max(marked) + 1          # + the validation step


def main() -> int:
    tests = count_tests()
    steps = pipeline_steps()
    problems: list[str] = []

    html_path = ROOT / "docs" / "index.html"
    html = html_path.read_text(encoding="utf-8")

    checks = [
        (r"(\d+)\s*项测试", tests, "docs/index.html tagline"),
        (r'<div class="n">(\d+)</div><div class="l">自动化测试项', tests,
         "docs/index.html KPI card"),
        (r"一次构建的\s*(\d+)\s*个步骤", steps, "docs/index.html step heading"),
    ]
    for pattern, expected, where in checks:
        found = [int(x) for x in re.findall(pattern, html)]
        if not found:
            problems.append(f"{where}: pattern {pattern!r} not found (rename it in the check)")
        for value in found:
            if value != expected:
                problems.append(f"{where}: says {value}, code says {expected}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for value in (int(x) for x in re.findall(r"\|\s*(\d+)\s*步\s*\|", readme)):
        if value != steps:
            problems.append(f"README.md step table: says {value}, code says {steps}")

    if problems:
        print("docs numbers are stale:")
        for p in problems:
            print("  -", p)
        print(f"\nexpected: tests={tests}, steps={steps}")
        return 1
    print(f"docs numbers ok (tests={tests}, steps={steps})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail if a module's line coverage is below a floor.

    python scripts/check_coverage.py reports/coverage.json attribution/baseline.py 95
"""
import json
import sys
from pathlib import Path

report, target, floor = sys.argv[1], sys.argv[2], float(sys.argv[3])
files = json.loads(Path(report).read_text())["files"]
match = [v for f, v in files.items() if Path(f).as_posix().endswith(target)]
if not match:
    sys.exit(f"{target} not found in {report}")
pct = match[0]["summary"]["percent_covered"]
print(f"{target}: {pct:.1f}% line coverage (floor {floor}%)")
sys.exit(0 if pct >= floor else 1)

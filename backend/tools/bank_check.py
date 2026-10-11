"""CLI: проверить все семейства банка. Код возврата 1, если хоть одно не прошло."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.assessment.bank.base import families
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import load_all

REPORT = Path(__file__).resolve().parents[2] / "reports" / "bank_check.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=None)
    args = ap.parse_args()
    load_all()
    reports = [check_family(f) for f in families(args.spec)]
    for r in reports:
        mark = "OK " if r.ok else "ERR"
        print(f"{mark} {r.code:<40} uniq={r.unique_prompt_share:.2f} space≈{r.space_estimate:>12.0f} {'; '.join(r.errors)}")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2))
    print(f"итого: {sum(r.ok for r in reports)}/{len(reports)} прошли; отчёт {REPORT}")
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())

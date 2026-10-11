"""make validate: полный прогон лаборатории → reports/validation.json и строка lab_runs (если БД доступна)."""
import argparse
import json
from pathlib import Path

import app.db.all_models  # noqa: F401
from app.config.params import PARAMS
from app.lab.report import run_all


def default_out() -> Path:
    cwd = Path.cwd()
    root = cwd.parent if cwd.name == "backend" else cwd
    return root / "reports" / "validation.json"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=PARAMS.lab_max_pop, help="размер синтетической популяции")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--no-llm", action="store_true", help="не вызывать LLM-решатель и судью")
    ap.add_argument("--out", type=Path, default=default_out())
    args = ap.parse_args()
    results = run_all(args.n, args.seed, with_llm=not args.no_llm)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str, allow_nan=False), encoding="utf-8")
    for h in results["headline"]:
        value = f"{h['value']:.0%}" if h["format"] == "percent" else f"{h['value']:.2f}"
        print(f"{h['title']}: {value} ({h['note']})")
    print(f"отчёт: {args.out} · {results['duration_s']} с")
    try:
        from app.db.session import _session_factory
        from app.lab.service import record

        with _session_factory()() as db:
            record(db, json.loads(json.dumps(results, default=str)))
        print("записано в lab_runs")
    except Exception as e:  # отчёт уже на диске; без БД страница лаборатории просто покажет прошлый прогон
        print(f"lab_runs не обновлена: {type(e).__name__}")

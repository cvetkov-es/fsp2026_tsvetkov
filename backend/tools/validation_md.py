"""Сборка docs/validation.md из reports/validation.json.

Запуск (из каталога backend): uv run python -m tools.validation_md
Числа не переписываются руками: источник — отчёт лаборатории.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reports" / "validation.json"
OUT = ROOT / "docs" / "validation.md"


def pct(v: float | None) -> str:
    return "—" if v is None else f"{round(v * 100)}%"


def num(v: float | None, digits: int = 2) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([head, sep, body])


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    t, m, cal, mk = d["test"], d["matching"], d["calibration"], d["market"]
    titles = {b["key"]: b["title"] for b in d["charts"]["ndcg_bars"]}
    out: list[str] = []
    out.append("# Валидация и результаты")
    out.append("")
    out.append(f"Отчёт лаборатории от {d['generated_at'][:10]}, популяция {d['population']} синтетических кандидатов. "
               "Источник: `reports/validation.json`, страница `/lab`. Симуляция со скрытой истиной, реальные данные не используются.")
    out.append("")
    out.append("## Четыре числа")
    out.append("")
    for h in d["headline"]:
        value = pct(h["value"]) if h["format"] == "percent" else num(h["value"])
        out.append(f"- **{h['title']}**: {value}, {h['note'].rstrip('.')}.")
    out.append("")
    out.append("## Тест")
    out.append("")
    out.append(f"Верных решений всего {pct(t['accuracy'])}, вдали от порога {pct(t['accuracy_far'])}, у порога {pct(t['accuracy_near'])}. "
               f"Повторный тест даёт то же решение в {pct(t['retest_agreement'])} случаев (κ = {num(t['retest_kappa'])}). "
                f"Экспресс-теста хватает для уверенного решения в {pct(t['express_decided_share'])} случаев, "
                f"точность этих решений {pct(t['accuracy_express_decided'])}.")
    out.append("")
    out.append(table(["Грейд", "N", "Ложные подтверждения", "Ложные отказы", "Длина, сред.", "Экспресс"],
                     [[g, str(v["n"]), pct(v["false_positive"]), pct(v["false_negative"]),
                       num(v["len_full"]["mean"], 1), num(v["len_express"]["mean"], 1)] for g, v in t["by_grade"].items()]))
    out.append("")
    out.append("κ по расстоянию до порога: " + ", ".join(
        f"{b['dist_from']}–{b['dist_to'] or '∞'}: {num(b['kappa'])}" for b in t["kappa_by_distance"]) + ".")
    out.append("")
    leak = t["leak"]
    out.append(f"Эксперимент «утечка»: раскрыто {pct(leak['leaked_share'])} банка. Ложные подтверждения у нашей генерации "
               f"{pct(leak['generated_bank_false_positive'])}, у статичного банка {pct(leak['static_bank_false_positive'])}, "
               f"у кандидата без утечки {pct(leak['honest_false_positive'])}.")
    out.append("")
    out.append("## Подбор")
    out.append("")
    out.append(f"Кандидатов {m['n_people']}, потребностей {m['n_needs']}, отложенная выборка {m['holdout_needs']} потребностей.")
    out.append("")
    out.append(table(["Ранжирование", "nDCG@10", "P@10", "MRR", "nDCG отложенная"],
                     [[titles.get(k, k), num(v["all"]["ndcg"]["mean"]), num(v["all"]["p_at_k"]["mean"]),
                       num(v["all"]["mrr"]["mean"]), num(v["holdout"]["ndcg"]["mean"])] for k, v in m["rankers"].items()]))
    out.append("")
    out.append("Ablation (nDCG@10): " + ", ".join(f"{titles.get(k, k)} {num(v['mean'])}" for k, v in m["ablation"].items()) + ".")
    out.append("")
    out.append("Контрольные случаи:")
    for c in m["paired"]:
        out.append(f"- {'✓' if c['passed'] else '✗'} {c['case']}")
    out.append("")
    b, inv, f = m["blocks"], m["invariance"], m["fairness"]
    out.append(f"Правило блоков: каждый кандидат в одном блоке {'да' if b['each_candidate_one_block'] else 'нет'}, "
               f"неподтверждённый никогда не выше подтверждённого {'да' if b['unconfirmed_never_above_confirmed'] else 'нет'}. "
               f"Смена города не меняет порядок в {pct(inv['city_changed_same_order_share'])} случаев, "
               f"смена псевдонима в {pct(inv['pseudonym_changed_same_order_share'])}.")
    out.append("")
    out.append(f"Справедливость (доля «без ФСП / с ФСП» в топ-10 при равной силе теста): "
               f"{', '.join(num(x['ratio']) for x in f['by_test_tier'])}. Доля онлайн-отборщиков в топ-10 "
               f"{pct(f['farmers_share_top10'])} при {pct(f.get('farmers_share_relevant'))} среди релевантных.")
    out.append("")
    out.append("## Калибровка и рынок")
    out.append("")
    out.append(f"Экспертный порог смещён на {cal['shift']} логита. Ошибка после калибровки: " +
               ", ".join(f"N={x['n']}: {num(x['calibrated_error'])}" for x in cal["by_n"]) + ".")
    out.append("")
    out.append(table(["Вариант рынка", "Приглашений на потребность", "Принято", "Ниже порога", "p95 на кандидата", "Качество найма"],
                     [[k, num(v["invites_per_need"], 1), pct(v["acceptance_rate"]), pct(v["below_threshold_share"]),
                       num(v.get("invites_per_candidate_p95"), 1), num(v["hired_relevance"])] for k, v in mk.items()]))
    out.append("")
    llm = d.get("llm", {})
    out.append("## Проверка модели")
    out.append("")
    for name, block in llm.items():
        if not isinstance(block, dict) or block.get("skipped"):
            out.append(f"- **{name}**: пропущено в этом прогоне.")
        elif "agree_a" in block:
            models = block.get("models", {})
            out.append(f"- **{name}**: согласие моделей {models.get('a')} {pct(block['agree_a'])} и {models.get('b')} "
                       f"{pct(block['agree_b'])}, заданий {block.get('n')}, подозрительных ключей {len(block.get('suspect_keys', []))}.")
        else:
            out.append(f"- **{name}**: выполнено.")
    out.append("")
    ai = d.get("ai_skill_policies")
    if isinstance(ai, dict) and "policies" in ai:
        out.append("## «Работа с ИИ»: три политики")
        out.append("")
        out.append(table(["Политика", "Подтверждено", "Точность", "Принятые ошибки ИИ", "Отклонённые верные", "Минут"],
                         [[x["title"], pct(x["pass_rate"]), pct(x["accuracy"]), pct(x["miss_weighted"]),
                           pct(x["false_reject"]), num(x["minutes"], 0)] for x in ai["policies"]]))
        out.append("")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"docs/validation.md записан: {len(out)} строк")


if __name__ == "__main__":
    main()

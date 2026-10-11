"""Симуляция рынка (процесс 8): приглашения по нашей подборке с квотой и агрегатом вилки против вариантов.

Варианты:
- ours — квота QUOTA_L1 на потребность, работодатель видит «вилка в ожиданиях у X из Y» и поднимает вилку
  на 10%, если она покрывает ожидания меньше чем у половины кандидатов;
- no_fork_info — та же квота, без агрегата (вилка не меняется);
- no_quota — без квоты и без агрегата: работодатель приглашает всех подходящих сразу;
- random_order — квота и агрегат как у ours, но порядок приглашений случайный (вклад ранжирования).
"""
import random
from statistics import median

from app.config.params import PARAMS
from app.lab.metrics import mean, quantile
from app.lab.population import NOW, make_needs, make_people, observe, thresholds
from app.lab.rubric import relevance
from app.matching.scoring import rank

DAYS = 21


def _simulate(people, needs, variant: str, seed: int) -> dict:
    rng = random.Random(seed)
    by_ref = {p.ref: p for p in people}
    quota = 10**6 if variant == "no_quota" else PARAMS.quota_l1
    invites, answered, accepted, wasted = 0, 0, 0, 0
    per_candidate: dict[str, int] = {}
    filled_day: dict[str, int] = {}
    hired_relevance: list[int] = []
    raised = 0  # сколько раз агрегат «вилка в ожиданиях у X из Y» убедил работодателя поднять вилку
    t = thresholds()
    for n in needs:
        pool = [p.facts for p in people if p.spec == n.facts.specialization]
        order = [r.c.ref for r in rank(pool, n.facts, NOW) if r.block <= 3]
        if variant == "random_order":
            rng.shuffle(order)
        fork = n.facts.salary_to_net
        if variant in ("ours", "random_order"):
            with_thr = [by_ref[r].threshold_net for r in order if by_ref[r].threshold_net]
            if with_thr and sum(fork >= x for x in with_thr) / len(with_thr) < 0.5:
                fork = int(fork * 1.1)
                raised += 1
        pending: list[tuple[int, str]] = []  # (день ответа, ref)
        cursor = 0
        for day in range(DAYS):
            if n.key in filled_day:
                break
            while len(pending) < quota and cursor < len(order):
                ref = order[cursor]
                cursor += 1
                p = by_ref[ref]
                invites += 1
                per_candidate[ref] = per_candidate.get(ref, 0) + 1
                if p.threshold_net and fork < p.threshold_net:
                    wasted += 1
                silent = not (p.open_window and p.active) and rng.random() < 0.7
                delay = PARAMS.invite_ttl_days if silent else rng.randint(1, 4)
                pending.append((day + delay, ref if not silent else "-" + ref))
            due = [x for x in pending if x[0] <= day]
            pending = [x for x in pending if x[0] > day]
            for _, ref in due:
                if ref.startswith("-"):
                    continue  # истекло без ответа
                p = by_ref[ref]
                answered += 1
                gap = 0 if not p.threshold_net else (p.threshold_net - fork) / p.threshold_net
                if gap <= 0:
                    ok = rng.random() < 0.75
                elif gap <= PARAMS.hard_salary_gap:
                    ok = rng.random() < 0.5 * 0.5  # встречное условие и согласие компании на v2
                else:
                    ok = rng.random() < 0.05
                if ok:
                    accepted += 1
                    if n.key not in filled_day:
                        filled_day[n.key] = day
                        hired_relevance.append(relevance(p, n.facts, t))
    return {
        "invitations": invites, "acceptance_rate": accepted / answered if answered else 0.0,
        "below_threshold_share": wasted / invites if invites else 0.0,
        "needs_filled_share": len(filled_day) / len(needs),
        "median_days_to_fill": median(filled_day.values()) if filled_day else None,
        "invites_per_candidate_p95": quantile(list(per_candidate.values()), 0.95) if per_candidate else 0,
        "candidates_invited_share": len(per_candidate) / len(people),
        "invites_per_need": invites / len(needs),
        # Качество найма по скрытой истине (0–3): согласие ещё не успех, важно, кого наняли
        "hired_relevance": mean(hired_relevance) if hired_relevance else None,
        # Если вилки и так покрывают ожидания большинства, агрегат не срабатывает и ours совпадает с no_fork_info
        "fork_raised_share": raised / len(needs),
    }


def market(seed: int, n_people: int = 600, n_needs: int = 30) -> dict:
    people = observe(make_people(n_people, seed + 2000), seed + 2000)
    needs = make_needs(n_needs, seed + 2000)
    return {v: _simulate(people, needs, v, seed) for v in ("ours", "no_fork_info", "no_quota", "random_order")}

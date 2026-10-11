"""Живая проверка LLM на синтетике: разбор вакансии, черновик резюме, сводка. Не входит в CI.

Запуск: make llm-smoke (нужны LLM_API_KEY и LLM_BASE_URL; ключ не печатается).
"""
import json
import time

from app.candidates.resume.service import SYSTEM as RESUME_SYSTEM
from app.candidates.resume.service import ResumeLLM
from app.employers.need_parse import parse_need_text
from app.llm.deps import get_llm
from app.llm.masking import mask
from app.llm.names import person_names
from app.matching.summary import SYSTEM as SUMMARY_SYSTEM
from app.matching.summary import SummaryLLM, fact_check
from tests.llm.samples import SAMPLES

VACANCY = """Python-разработчик в платёжную платформу
Ищем middle+ бэкенд-разработчика, удалёнка. Требования: Python, FastAPI, PostgreSQL, Docker.
Будет плюсом: Kafka. Вилка 250–350 тыс. до вычета НДФЛ."""
FACTS = {"грейд": "Middle подтверждён тестом · сильнее 82% категории", "стек": "Стек: Python ✓, Docker — заявлено",
         "ФСП": "Истории ФСП нет — оценка навыков по тесту", "чего не хватает": ["Docker: заявлено, не подтверждено"],
         "готовность": "вилка покрывает ожидания · окно поиска открыто до 20.10"}


def timed(title, fn):
    t = time.perf_counter()
    out = fn()
    print(f"— {title}: {time.perf_counter() - t:.1f} с")
    return out


if __name__ == "__main__":
    llm = get_llm()
    if not llm.enabled:
        raise SystemExit("LLM выключен: задайте LLM_API_KEY и LLM_BASE_URL")
    print(f"профиль {llm.settings.llm_profile}")
    d = timed("вакансия", lambda: parse_need_text(VACANCY, llm))
    print(d.model_dump_json(exclude_none=True))
    text = SAMPLES["hh"]
    masked = mask(text, person_names(text)).text
    res = timed("резюме (замаскированное)", lambda: llm.json("pd", RESUME_SYSTEM, masked, ResumeLLM))
    print(res[1] if res else "нет ответа", res[0].model_dump_json() if res else "")
    res = timed("сводка", lambda: llm.json("runtime", SUMMARY_SYSTEM, json.dumps(FACTS, ensure_ascii=False), SummaryLLM))
    if res:
        print(res[1], res[0].text, "| факты:", "ок" if fact_check(res[0].text, FACTS) else "ОТКЛОНЕНО")

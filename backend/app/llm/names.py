"""ФИО в тексте резюме: эвристика первых строк и NER natasha в отдельном процессе.

Модель natasha занимает около 160 МБ. В подпроцессе она не остаётся в памяти воркера API после разбора.
"""
import fcntl
import json
import logging
import re
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.common.subproc import child_limits, safe_env
from app.config.params import PARAMS
from app.config.settings import get_settings

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]
# Один NER за раз на контейнер: модель ~225 МБ; параллельные резюме, в том числе из разных воркеров, ждут очереди
NER_LOCK = threading.Lock()
NER_LOCK_FILE = Path(tempfile.gettempdir()) / "fsp-ner.lock"


@contextmanager
def _ner_slot():
    with NER_LOCK, open(NER_LOCK_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
_WORD = re.compile(r"^[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?$")
# Слова, с которых начинаются заголовки и должности, а не имена
_NOT_NAMES = frozenset({
    "резюме", "опыт", "работы", "навыки", "контакты", "образование", "желаемая", "должность", "обо", "мне",
    "ключевые", "языки", "проекты", "достижения", "дополнительная", "информация", "профессиональные",
    "сертификаты", "курсы", "разработчик", "аналитик", "инженер", "программист", "ведущий", "старший",
    "младший", "специалист", "руководитель", "россия", "москва", "занятость", "график",
})


def heuristic_names(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:5]
    out = []
    for ln in lines:
        words = ln.split()
        if 2 <= len(words) <= 3 and all(_WORD.match(w) for w in words) and not {w.lower() for w in words} & _NOT_NAMES:
            out.append(ln)
    return out


def natasha_names(text: str) -> list[str] | None:
    """Имена по NER. None — NER не отработал: маскирование неполное, вызывающий решает, что делать."""
    try:
        with _ner_slot():
            r = subprocess.run([sys.executable, "-m", "app.llm.names"], input=text.encode(), capture_output=True,
                               timeout=PARAMS.ner_timeout_s, cwd=BACKEND_DIR, check=True, env=safe_env(),
                               preexec_fn=child_limits(PARAMS.ner_mem_mb))
        return [n for n in json.loads(r.stdout) if len(n) >= 3]
    except subprocess.TimeoutExpired:
        log.warning("NER: timeout %s с", PARAMS.ner_timeout_s)
    except subprocess.CalledProcessError as e:
        log.warning("NER: код %s: %s", e.returncode, (e.stderr or b"")[-300:].decode(errors="replace"))
    except (OSError, ValueError) as e:
        log.warning("NER: %s", type(e).__name__)
    return None


@dataclass(frozen=True)
class NameScan:
    names: list[str]  # всё, что маскируется перед LLM
    full_name: str | None  # владелец резюме: имя из первых строк, а не руководитель из описания проекта
    complete: bool  # False — NER выключен или не отработал: маскирование неполное


def scan_names(text: str) -> NameScan:
    heur = heuristic_names(text)
    if not get_settings().ner_enabled:
        # NER выключен: ФИО из тела резюме могли остаться незамеченными — маскирование неполное, в LLM текст не уходит
        return NameScan(heur, heur[0] if heur else None, False)
    ner = natasha_names(text)
    head = "\n".join([ln for ln in text.splitlines() if ln.strip()][:5])
    full = heur[0] if heur else next((n for n in ner or [] if n in head), None)
    return NameScan(list(dict.fromkeys(heur + (ner or []))), full, ner is not None)


def person_names(text: str) -> list[str]:
    return scan_names(text).names


def _main() -> None:
    from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter

    doc = Doc(sys.stdin.buffer.read().decode())
    doc.segment(Segmenter())
    doc.tag_ner(NewsNERTagger(NewsEmbedding()))
    print(json.dumps([s.text for s in doc.spans if s.type == "PER"], ensure_ascii=False))


if __name__ == "__main__":
    _main()

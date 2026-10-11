"""Лимиты стенда согласованы с параметрами разбора резюме (план 04b, ревью): nginx и память контейнеров."""
import re
from pathlib import Path

from app.config.params import PARAMS

ROOT = Path(__file__).resolve().parents[2]
WORKER_MB = 300  # тёплый воркер uvicorn с reportlab и openai (замер: ~90 МБ после старта) — с запасом
NER_RSS_MB = 230  # подпроцесс natasha (замер 08.10: 223 МБ RSS); один на контейнер (flock)


def _mb(value: str) -> int:
    n, unit = re.fullmatch(r"(\d+)([mg])", value).groups()
    return int(n) * (1024 if unit == "g" else 1)


def test_nginx_accepts_resume_and_waits_for_parsing():
    conf = (ROOT / "deploy" / "nginx.conf").read_text()
    body = re.search(r"client_max_body_size\s+(\d+)m", conf)
    read = re.search(r"proxy_read_timeout\s+(\d+)s", conf)
    assert body and int(body.group(1)) > PARAMS.resume_max_mb
    worst = PARAMS.pdf_parse_timeout_s + PARAMS.ner_timeout_s + 4 * PARAMS.llm_timeout_pd_s  # 2 модели × повтор
    assert read and int(read.group(1)) >= worst


def test_compose_memory_fits_stand_and_ner():
    compose = (ROOT / "docker-compose.yml").read_text()
    limits = {m.group(1): _mb(m.group(2)) for m in re.finditer(r"(?m)^  (\w+):\n(?:    .*\n)*?    mem_limit: (\w+)", compose)}
    assert sum(limits.values()) <= 1536  # спецификация 5.8: все сервисы ≤ 1,5 ГБ
    assert limits["api"] >= 2 * WORKER_MB + NER_RSS_MB  # два воркера и один NER на контейнер


def test_nginx_proxies_builtin_mocks_and_api_calls_itself():
    conf = (ROOT / "deploy" / "nginx.conf").read_text()
    assert re.search(r"location /mock/ \{\s*proxy_pass http://api:8000;", conf)
    compose = (ROOT / "docker-compose.yml").read_text()
    assert re.search(r"FSP_SERVER_BASE: http://api:8000", compose)


def test_env_example_keeps_builtin_fsp_mock():
    """FSP_ID_ISSUER в шаблоне .env отключил бы встроенный мок: вход через FSP ID на чистом стенде не работал бы."""
    lines = [ln.strip() for ln in (ROOT / ".env.example").read_text().splitlines()]
    assert not [ln for ln in lines if ln.startswith(("FSP_ID_ISSUER=", "FSP_API_URL="))]

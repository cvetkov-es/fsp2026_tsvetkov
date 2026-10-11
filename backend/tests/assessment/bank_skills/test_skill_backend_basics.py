import base64
import json
import re
from email.utils import parsedate_to_datetime

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from ._helpers import assert_mcq_form, make, skill_codes

CODES = skill_codes("backend_basics")
SEEDS = range(40)
MCQ = ("sk.be.basic_auth_header", "sk.be.status_class", "sk.be.rest_route_for_action", "sk.be.content_type_choice", "sk.be.compatible_change",
       "sk.be.grpc_to_http_status")


@pytest.mark.parametrize("code", CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


@pytest.mark.parametrize("code", MCQ)
def test_mcq_form(code):
    assert_mcq_form(code)


def test_volume_and_areas():
    assert len(CODES) == 10
    assert sorted(REGISTRY[c].level for c in CODES) == [1, 1, 2, 2, 2, 2, 3, 3, 3, 4]
    assert {REGISTRY[c].area for c in CODES} == {"http", "api"}
    assert not any(c.startswith("be.") for c in CODES)


URL_RX = re.compile(r"^(\w+)://([^/:?#]+)(?::(\d+))?(/[^?#]*)?(?:\?([^#]*))?(?:#(.*))?$")


def test_url_parts():
    for seed in SEEDS:
        inst = make("sk.be.url_parts", seed)
        _, host, _, path, query, _ = URL_RX.fullmatch(inst.prompt.code).groups()
        params = dict(p.split("=", 1) for p in query.split("&"))
        if "хост" in inst.prompt.text:
            assert inst.answer == host
        elif "путь" in inst.prompt.text:
            assert inst.answer == path
        else:
            key = re.search(r"параметра (\w+)", inst.prompt.text).group(1)
            assert inst.answer == params[key]


def test_status_class_by_first_digit():
    for seed in SEEDS:
        inst = make("sk.be.status_class", seed)
        code = re.search(r"кодом (\d{3})", inst.prompt.text).group(1)
        assert inst.prompt.options[inst.answer].startswith(f"{code[0]}xx")


def test_rest_route_matches_table():
    from app.assessment.bank.families.skill_backend_basics import ACTIONS

    for seed in SEEDS:
        inst = make("sk.be.rest_route_for_action", seed)
        for text, correct, _ in ACTIONS:
            m = re.fullmatch(re.escape(text).replace(r"\{id\}", r"(\d+)"), inst.prompt.text.split(". ")[0])
            if m:
                assert inst.prompt.options[inst.answer] == correct.format(id=m.group(1))
                break
        else:
            raise AssertionError(inst.prompt.text)


CONTENT = {"объект": "application/json", "файл": "multipart/form-data", "HTML-форма": "application/x-www-form-urlencoded",
           "CSV": "text/csv"}


def test_content_type():
    for seed in SEEDS:
        inst = make("sk.be.content_type_choice", seed)
        hits = [v for k, v in CONTENT.items() if k in inst.prompt.text]
        assert len(hits) == 1 and inst.prompt.options[inst.answer] == hits[0]


def test_json_counts():
    for seed in SEEDS:
        inst = make("sk.be.json_count_fields", seed)
        doc = json.loads(inst.prompt.code)
        oid = int(re.search(r"id (\d+)", inst.prompt.text).group(1))
        order = next(o for o in doc["orders"] if o["id"] == oid)
        if "items" in inst.prompt.text:
            assert inst.answer == len(order["items"])
        else:
            numeric = [k for k, v in order.items() if isinstance(v, int | float) and not isinstance(v, bool)]
            assert inst.answer == len(numeric)


def test_basic_auth_header_is_choice_without_tools():
    for seed in SEEDS:
        inst = make("sk.be.basic_auth_header", seed)
        login, password = re.search(r"логин (\S+), пароль (\S+)\.", inst.prompt.text).groups()
        assert inst.kind == "choice" and "base64" not in inst.prompt.text  # без утилит: правила теста их запрещают
        key = "Basic " + base64.b64encode(f"{login}:{password}".encode()).decode()
        assert inst.prompt.options[inst.answer] == key


def test_url_params_are_meaningful():
    from app.assessment.bank.families.skill_backend_basics import QUERY_PARAMS

    for seed in SEEDS:
        query = make("sk.be.url_parts", seed).prompt.code.split("?")[1].split("#")[0]
        for pair in query.split("&"):
            k, v = pair.split("=")
            assert v in QUERY_PARAMS[k]


def test_retry_after_seconds():
    for seed in SEEDS:
        inst = make("sk.be.retry_after_seconds", seed)
        date = parsedate_to_datetime(re.search(r"^Date: (.+)$", inst.prompt.code, re.M).group(1))
        retry = re.search(r"^Retry-After: (.+)$", inst.prompt.code, re.M).group(1)
        expected = int(retry) if retry.isdigit() else int((parsedate_to_datetime(retry) - date).total_seconds())
        assert inst.answer == expected


def test_backoff_total_wait():
    for seed in SEEDS:
        inst = make("sk.be.backoff_total_wait", seed)
        b, m, c, k = (float(x) for x in re.search(
            r"base = ([\d.]+) с, множитель ([\d.]+), потолок ([\d.]+) с.*?до (\d+)-й", inst.prompt.text).groups())
        wait, delay = 0.0, b
        for _ in range(int(k)):
            wait += min(delay, c)
            delay *= m
        assert inst.answer == pytest.approx(wait)


def test_compatible_change_is_optional_field():
    for seed in SEEDS:
        inst = make("sk.be.compatible_change", seed)
        assert "необязательное" in inst.prompt.options[inst.answer]
        assert sum("необязательное" in o for o in inst.prompt.options) == 1


GRPC = {"NOT_FOUND": "404", "INVALID_ARGUMENT": "400", "UNAUTHENTICATED": "401", "PERMISSION_DENIED": "403",
        "UNAVAILABLE": "503", "DEADLINE_EXCEEDED": "504", "ALREADY_EXISTS": "409", "RESOURCE_EXHAUSTED": "429"}


def test_grpc_to_http():
    for seed in SEEDS:
        inst = make("sk.be.grpc_to_http_status", seed)
        code = re.search(r"статус ([A-Z_]+)", inst.prompt.text).group(1)
        assert inst.prompt.options[inst.answer] == GRPC[code]

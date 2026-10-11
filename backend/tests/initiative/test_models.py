from sqlalchemy import inspect

from app.config.params import PARAMS


def test_new_tables_and_contact_links(db):
    insp = inspect(db.get_bind())
    tables = set(insp.get_table_names())
    assert {"signals", "employer_tasks", "task_submissions", "vacancies", "applications"} <= tables
    cols = {c["name"] for c in insp.get_columns("contacts")}
    assert {"vacancy_id", "task_submission_id"} <= cols


def test_new_params():
    assert (PARAMS.signal_ttl_days, PARAMS.demand_window_days) == (90, 30)
    assert (PARAMS.task_text_max, PARAMS.task_answer_max, PARAMS.task_ttl_days, PARAMS.vacancy_text_max) == (2000, 5000, 14, 4000)

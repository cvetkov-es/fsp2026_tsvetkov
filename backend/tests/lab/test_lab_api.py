from app.config.params import PARAMS
from app.lab.matching_validation import validate_matching
from app.lab.models import LabRun
from app.lab.report import charts, headline
from app.lab.service import run_pending
from app.lab.test_validation import validate_test
from tests.candidates.test_profile import login


def test_headline_and_charts_from_small_run():
    test = validate_test(60, seed=2, oc_per_point=8, leak_n=40)
    matching = validate_matching(120, 6, seed=2)
    h = headline(test, matching)
    assert [x["key"] for x in h] == ["accuracy_far", "retest", "ndcg", "leak"]
    assert all(0 <= x["value"] <= 1 for x in h)
    c = charts(test, matching)
    assert len(c["oc_curve"]) == 17 and {b["group"] for b in c["ndcg_bars"]} == {"ranker", "ablation"}


def test_queue_run_and_public_latest(client, db):
    assert client.get("/api/v1/lab/latest").json() == {"run": None, "results": None, "active": None, "failed": None,
                                                       "max_population": PARAMS.lab_max_pop}
    assert client.post("/api/v1/lab/runs", json={"population": 500}).status_code == 401
    login(client, db)
    assert client.post("/api/v1/lab/runs", json={"population": 100000}).status_code == 422
    run = client.post("/api/v1/lab/runs", json={"population": 500}).json()
    assert run["status"] == "queued"
    assert client.post("/api/v1/lab/runs", json={"population": 500}).json()["code"] == "lab_busy"
    done = run_pending(db, runner=lambda n, with_llm: {"population": n, "headline": [], "with_llm": with_llm})
    assert done.status == "done" and done.results["with_llm"] is False
    client.cookies.clear()
    latest = client.get("/api/v1/lab/latest").json()
    assert latest["run"]["status"] == "done" and latest["results"]["population"] == 500 and latest["active"] is None


def test_failed_run_is_reported(client, db):
    db.add(LabRun(kind="ui", population=100))
    db.commit()

    def boom(n, with_llm):
        raise RuntimeError("сбой")

    run = run_pending(db, runner=boom)
    assert run.status == "failed" and run.error == "RuntimeError"
    assert client.get(f"/api/v1/lab/runs/{run.id}").json()["status"] == "failed"


def test_headline_notes_survive_empty_bins():
    test = validate_test(60, seed=2, oc_per_point=8, leak_n=40)
    matching = validate_matching(120, 6, seed=2)
    test["accuracy_near"] = float("nan")
    test["retest_kappa"] = float("nan")
    notes = " ".join(h["note"] for h in headline(test, matching))
    assert "nan" not in notes and "—" in notes

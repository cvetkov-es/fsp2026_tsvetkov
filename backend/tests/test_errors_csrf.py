from fastapi.testclient import TestClient

from app.common.errors import AppError
from app.main import create_app


def _app_with_routes():
    app = create_app()

    @app.get("/api/v1/_boom")
    def boom():
        raise AppError(409, "email_taken", "Email уже зарегистрирован")

    @app.post("/api/v1/_echo")
    def echo():
        return {"ok": True}

    return app


def test_app_error_is_problem_json():
    c = TestClient(_app_with_routes())
    r = c.get("/api/v1/_boom")
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "email_taken" and body["status"] == 409 and body["title"]


def test_validation_error_is_problem_json():
    app = create_app()

    @app.get("/api/v1/_needs_int")
    def needs_int(x: int):
        return {"x": x}

    r = TestClient(app).get("/api/v1/_needs_int?x=abc")
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"


def test_post_without_csrf_header_is_rejected():
    c = TestClient(_app_with_routes())
    r = c.post("/api/v1/_echo")
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    r2 = c.post("/api/v1/_echo", headers={"X-Requested-With": "fsp"})
    assert r2.status_code == 200

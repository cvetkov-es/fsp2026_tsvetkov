# deploy/smoke.py
"""Смоук-тест стенда: python deploy/smoke.py https://<домен> (или http://localhost:8080). Выход 1 — что-то не так."""
import sys

import httpx

H = {"X-Requested-With": "fsp"}


def main(base: str) -> int:
    c = httpx.Client(base_url=base.rstrip("/") + "/api/v1", headers=H, timeout=15, follow_redirects=True)
    checks: list[tuple[str, bool]] = []
    checks.append(("health", c.get("/health").json().get("status") == "ok"))
    personas = c.get("/demo/personas").json()
    checks.append(("демо-персоны", {p["role"] for p in personas} >= {"candidate", "employer"}))
    emp = next(p for p in personas if p["role"] == "employer")
    checks.append(("вход работодателем", c.post("/demo/login-as", json={"user_id": emp["id"]}).status_code == 200))
    needs = c.get("/employer/needs").json()
    checks.append(("потребности засева", len(needs) >= 3))
    sel = c.get(f"/employer/needs/{needs[0]['id']}/selection")
    checks.append(("подборка", sel.status_code == 200 and len(sel.json()["blocks"]) >= 1))
    checks.append(("карта", c.get("/employer/map").status_code == 200))
    checks.append(("лаборатория", c.get("/lab/latest").status_code == 200))
    for name, ok in checks:
        print(("OK  " if ok else "ERR ") + name)
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"))

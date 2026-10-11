from datetime import date

import httpx

from app.auth.models import ExternalIdentity
from app.config.settings import get_settings
from app.fsp.sync import FSP_PROVIDER, apply_snapshot
from app.mocks.fsp.fixtures import ATHLETES, payload_for

TODAY = date(2026, 10, 10)
SUB = {a["family_name"]: a["sub"] for a in ATHLETES}


def link(db, profile, sub: str):
    """Кандидат с привязанным FSP ID и снимком из фикстур мока — без OIDC-флоу."""
    db.add(ExternalIdentity(user_id=profile.user_id, provider=FSP_PROVIDER, issuer=get_settings().fsp_issuer,
                            subject=sub))
    db.flush()
    apply_snapshot(db, profile.user_id, payload_for(sub), today=TODAY)
    db.commit()
    return profile


class FakeHttp:
    def __init__(self, payload: dict | None = None, fail: bool = False):
        self.payload, self.fail, self.calls = payload, fail, []

    def get(self, url, headers=None):
        self.calls.append((url, headers or {}))
        if self.fail:
            raise httpx.ConnectError("ФСП недоступен")
        return httpx.Response(200, json=self.payload, request=httpx.Request("GET", url))

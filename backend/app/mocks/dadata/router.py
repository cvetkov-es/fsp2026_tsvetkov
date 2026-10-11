"""Мок DaData findById/party: любой ИНН с верной суммой — действующая организация, кроме ликвидированных из фикстуры."""
import re

from fastapi import APIRouter, Body

from app.llm.masking import inn_ok

router = APIRouter()
LIQUIDATED = frozenset({"5403003003"})


@router.post("/suggestions/api/4_1/rs/findById/party")
def find_by_id(body: dict = Body(...)) -> dict:
    inn = re.sub(r"\D", "", str(body.get("query", "")))
    if not inn_ok(inn):
        return {"suggestions": []}
    status = "LIQUIDATED" if inn in LIQUIDATED else "ACTIVE"
    return {"suggestions": [{"value": f"ООО «Компания {inn[-4:]}»",
                             "data": {"inn": inn, "ogrn": f"1{inn}{inn[:2]}", "state": {"status": status}}}]}

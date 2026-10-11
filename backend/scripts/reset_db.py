"""Сброс dev-БД: схема public с нуля. Только локальная БД — защита от запуска против стенда."""
from sqlalchemy import text

from app.db.session import get_engine

if __name__ == "__main__":
    eng = get_engine()
    url = eng.url
    if not (url.host in (None, "localhost", "127.0.0.1") or str(url.query.get("host", "")).startswith("/")):
        raise SystemExit(f"Отказ: {url.render_as_string(hide_password=True)} — не локальная БД")
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    print("схема public пересоздана")

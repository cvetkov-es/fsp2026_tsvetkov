"""Выгрузка текстов согласий в docs/privacy.md между маркерами <!-- consents --> и <!-- /consents -->.

Запуск (из каталога backend): uv run python -m tools.consents_md
Тексты берутся из app.auth.consents, а не копируются вручную.
"""
from pathlib import Path

from app.auth.consents import CONSENT_TEXTS

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "privacy.md"
START, END = "<!-- consents -->", "<!-- /consents -->"


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit("в docs/privacy.md нет маркеров consents")
    block: list[str] = []
    for c in CONSENT_TEXTS.values():
        block.append(f"**{c.title}** (редакция {c.version})")
        block.append("")
        block.append(c.body)
        block.append("")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    DOC.write_text(f"{head}{START}\n\n{chr(10).join(block).rstrip()}\n\n{END}{tail}", encoding="utf-8")
    print(f"docs/privacy.md: выгружено согласий {len(CONSENT_TEXTS)}")


if __name__ == "__main__":
    main()

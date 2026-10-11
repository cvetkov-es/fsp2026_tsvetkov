"""Сборка PDF документации: Markdown в HTML, затем печать в PDF через headless Chromium.

Запуск без установки в проект:
    uvx --with markdown --with playwright python tools/docs_pdf.py docs/fsp-hiring-docs.pdf
Первый раз нужен браузер: uvx --from playwright playwright install chromium

Диаграммы Mermaid отрисовываются в браузере перед печатью.
"""
import sys
from pathlib import Path

ORDER = [
    "README.md", "docs/architecture.md", "docs/testing.md", "docs/matching.md", "docs/validation.md",
    "docs/integrations.md", "docs/privacy.md", "docs/llm.md", "docs/build-and-run.md", "docs/security.md",
]
ROOT = Path(__file__).resolve().parents[1]

HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; line-height: 1.55; color: #1C1D22; }}
  h1, h2, h3 {{ color: #310F53; }} code, pre {{ font-family: ui-monospace, monospace; background: #f5f3f7; }}
  pre {{ padding: 12px; border-radius: 8px; overflow-x: auto; }} table {{ border-collapse: collapse; }}
  td, th {{ border: 1px solid #ddd; padding: 6px 10px; }} a {{ color: #FF0053; }}
</style></head><body>{body}
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{ startOnLoad: true }});</script>
</body></html>"""


def main() -> None:
    import markdown
    from playwright.sync_api import sync_playwright

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/fsp-hiring-docs.pdf")
    body: list[str] = []
    for rel in ORDER:
        path = ROOT / rel
        if path.exists():
            body.append(markdown.markdown(path.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "toc"]))
    html = HTML.format(body="\n<hr>\n".join(body))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(out), format="A4", print_background=True, margin={"top": "20mm", "bottom": "20mm", "left": "16mm", "right": "16mm"})
        browser.close()
    print(f"PDF собран: {out}")


if __name__ == "__main__":
    main()

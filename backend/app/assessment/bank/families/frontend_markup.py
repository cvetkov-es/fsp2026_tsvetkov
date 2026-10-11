"""Семейства Frontend · HTML, CSS, доступность.

CSS-расчёты — только по формулам спецификаций с целыми пикселями: параметры подбираются так, чтобы
результат был целым, а округление браузера не влияло на ответ.
"""
import math
import random
import re

from app.assessment.bank.base import Generated, Prompt, family, mcq, rows_space

SITES = ("интернет-магазина книг", "городской библиотеки", "службы доставки", "фитнес-клуба", "онлайн-школы",
         "кофейни", "турагентства", "автосервиса", "кинотеатра", "ветеринарной клиники", "банка",
         "музея", "цветочного магазина", "клиники")
PAGES = ("главной странице", "странице каталога", "странице контактов", "странице «О нас»", "странице акций",
         "странице отзывов")

# --- fe.markup.semantic_tag -------------------------------------------------------
# (шаблоны, правильный тег, пул дистракторов — из него берутся три)
SEMANTIC_ROWS = (
    (("На {page} сайта {site} нужно разметить главное меню со ссылками на разделы сайта. Какой тег подходит "
      "по смыслу?",
      "На {page} сайта {site} в шапке есть блок ссылок на основные разделы — главная навигация. Каким тегом "
      "его разметить?"),
     "<nav>", ("<div>", "<section>", "<aside>", "<span>")),
    (("На {page} сайта {site} нужно разметить основное содержимое — то, ради чего пришёл посетитель. Такой "
      "блок на странице один. Какой тег подходит по смыслу?",
      "На {page} сайта {site} нужно разметить центральную часть с уникальным содержимым этой страницы (без "
      "шапки, меню и подвала). Каким тегом её разметить?"),
     "<main>", ("<div>", "<section>", "<article>", "<span>")),
    (("На {page} сайта {site} выводятся новости. Каждая новость — самостоятельная запись, которую можно "
      "распространять отдельно (например, в RSS). Каким тегом разметить одну новость?",
      "На {page} сайта {site} показаны записи блога: у каждой заголовок, дата и текст, и каждая имеет смысл "
      "сама по себе, вне страницы. Каким тегом разметить одну запись?"),
     "<article>", ("<div>", "<section>", "<aside>", "<span>")),
    (("На {page} сайта {site} есть элемент «Добавить в избранное»: по нажатию выполняется действие на этой "
      "же странице, перехода по ссылке нет. Каким тегом его разметить?",
      "На {page} сайта {site} элемент «Показать ещё» подгружает следующие карточки на ту же страницу, адрес "
      "страницы не меняется. Каким тегом его разметить?"),
     "<button>", ("<div>", "<span>", "<a>", "<label>")),
    (("На {page} сайта {site} внизу — контакты, реквизиты и копирайт. Каким тегом разметить этот блок?",
      "На {page} сайта {site} в самом низу — адрес, телефон и ссылка на политику конфиденциальности. Какой "
      "тег подходит по смыслу?"),
     "<footer>", ("<div>", "<section>", "<aside>", "<span>")),
    (("На {page} сайта {site} сбоку — колонка с рекламой и подпиской на рассылку, лишь косвенно связанная с "
      "основным содержимым. Каким тегом её разметить?",
      "На {page} сайта {site} рядом с основным текстом — врезка с дополнительными фактами, без которых текст "
      "понятен. Какой тег подходит по смыслу?"),
     "<aside>", ("<div>", "<section>", "<footer>", "<span>")),
    (("На {page} сайта {site} вверху — вводная часть с логотипом, названием сайта и поиском. Каким тегом её "
      "разметить?",
      "На {page} сайта {site} нужно разметить вводный блок: логотип, название и строку поиска. Какой тег "
      "подходит по смыслу?"),
     "<header>", ("<head>", "<div>", "<section>", "<span>")),
)


@family(code="fe.markup.semantic_tag", specialization="frontend", area="markup", level=1, fmt="mcq",
        space_size=rows_space(SEMANTIC_ROWS, {"site": len(SITES), "page": len(PAGES)}, extra=24 * math.comb(4, 3)),
        median_time_s=30)
def semantic_tag(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(SEMANTIC_ROWS)
    text = rng.choice(templates).format(site=rng.choice(SITES), page=rng.choice(PAGES))
    return mcq(rng, text, correct, rng.sample(pool, 3))


# --- fe.markup.content_box_width --------------------------------------------------
CSS_CLASSES = ("card", "panel", "tile", "banner", "badge", "modal", "tooltip", "notice")
CSS_COLORS = ("#ccc", "#999", "#333", "#e0e0e0", "red", "teal", "navy", "gray")


def _padding(rng: random.Random) -> tuple[str, int]:
    """Сокращённая запись padding (1–4 значения) и сумма левого и правого отступа."""
    v = [rng.randrange(4, 33, 2) for _ in range(4)]
    form = rng.randint(1, 4)
    if form == 1:
        return f"{v[0]}px", 2 * v[0]
    if form == 2:
        return f"{v[0]}px {v[1]}px", 2 * v[1]
    if form == 3:
        return f"{v[0]}px {v[1]}px {v[2]}px", 2 * v[1]
    return f"{v[0]}px {v[1]}px {v[2]}px {v[3]}px", v[1] + v[3]


def _box_css(rng: random.Random, sizing: str, width: int, padding: str, border: int) -> str:
    return "\n".join([f".{rng.choice(CSS_CLASSES)} {{", f"  box-sizing: {sizing};", f"  width: {width}px;",
                      f"  padding: {padding};", f"  border: {border}px solid {rng.choice(CSS_COLORS)};",
                      f"  margin: {rng.randrange(4, 41, 2)}px;", "}"])


def _numbers_in(css: str) -> set[int]:
    return {int(x) for x in re.findall(r"(\d+)px", css)}


@family(code="fe.markup.content_box_width", specialization="frontend", area="markup", level=1, fmt="calc",
        # класс × цвет × ширина × padding (нижняя оценка: одно значение) × рамка × margin
        space_size=len(CSS_CLASSES) * len(CSS_COLORS) * 41 * 15 * 5 * 19, median_time_s=40)
def content_box_width(rng: random.Random) -> Generated:
    while True:
        width = rng.randrange(120, 521, 10)
        padding, horizontal = _padding(rng)
        border = rng.randint(1, 5)
        css = _box_css(rng, "content-box", width, padding, border)
        answer = width + horizontal + 2 * border
        if answer not in _numbers_in(css):
            break
    cls = css.split()[0]
    text = (f"Чему равна ширина элемента {cls} от левого до правого края рамки (border), в пикселях? "
            "Внешние отступы (margin) не считаются.")
    return Generated("number", Prompt(text=text, code=css, language="css", answer_hint="Целое число пикселей"),
                     answer, ("content_box",))


# --- fe.markup.specificity_winner -------------------------------------------------
SPEC_TAGS = ("p", "label", "span", "a", "h2", "button")  # теги, допустимые прямо внутри div
SPEC_IDS = ("intro", "main-title", "promo", "total", "hint", "status")
SPEC_CLASSES = ("lead", "note", "active", "accent", "muted", "large", "warning", "primary")
SPEC_PARENTS = ("card", "content", "sidebar", "list", "panel")
SPEC_ATTRS = (("role", "hint"), ("state", "open"), ("kind", "info"), ("size", "big"))
SPEC_COLORS = ("red", "blue", "green", "orange", "purple", "teal", "brown", "gray")
# селекторы, которые выбирают элемент: шаблон → специфичность (id, классы и атрибуты, типы)
SPEC_SELECTORS = (
    ("#{id}", (1, 0, 0)), ("{tag}#{id}", (1, 0, 1)), (".{pc} #{id}", (1, 1, 0)),
    (".{c1}", (0, 1, 0)), (".{c1}.{c2}", (0, 2, 0)), ("{tag}.{c1}", (0, 1, 1)),
    ('[data-{attr}="{val}"]', (0, 1, 0)), ("{tag}[data-{attr}]", (0, 1, 1)), (".{pc} {tag}", (0, 1, 1)),
    (".{pc} .{c1}.{c2}", (0, 3, 0)), ("div {tag}", (0, 0, 2)), ("{tag}", (0, 0, 1)),
    ("div.{pc} > {tag}.{c2}", (0, 2, 2)), (".{pc} > .{c2}", (0, 2, 0)),
)


def _spec_rules(rng: random.Random) -> list[tuple[str, tuple[int, int, int]]]:
    while True:
        picked = rng.sample(SPEC_SELECTORS, 4)
        if len({s for _, s in picked}) == 4:
            return picked


@family(code="fe.markup.specificity_winner", specialization="frontend", area="markup", level=2, fmt="calc",
        # нижняя оценка: тег × id × пара классов × родитель × атрибут × набор селекторов × цвета
        space_size=len(SPEC_TAGS) * len(SPEC_IDS) * math.perm(len(SPEC_CLASSES), 2) * len(SPEC_PARENTS)
        * len(SPEC_ATTRS) * math.comb(len(SPEC_SELECTORS), 4) // 4 * math.perm(len(SPEC_COLORS), 4),
        median_time_s=55)
def specificity_winner(rng: random.Random) -> Generated:
    tag, id_, pc = rng.choice(SPEC_TAGS), rng.choice(SPEC_IDS), rng.choice(SPEC_PARENTS)
    c1, c2 = rng.sample(SPEC_CLASSES, 2)
    attr, val = rng.choice(SPEC_ATTRS)
    rules = _spec_rules(rng)
    colors = rng.sample(SPEC_COLORS, 4)
    fields = {"tag": tag, "id": id_, "pc": pc, "c1": c1, "c2": c2, "attr": attr, "val": val}
    lines = [f"  {sel.format(**fields)} {{ color: {color}; }}" for (sel, _), color in zip(rules, colors, strict=True)]
    winner = colors[max(range(4), key=lambda i: rules[i][1])]
    code = "\n".join([f'<div class="{pc}">',
                      f'  <{tag} id="{id_}" class="{c1} {c2}" data-{attr}="{val}">Текст</{tag}>',
                      "</div>", "", "<style>", *lines, "</style>"])
    return mcq(rng, "Какого цвета будет текст элемента? Других стилей на странице нет.", winner,
               [c for c in colors if c != winner], code=code, language="html",
               radicals=("specificity", 4))


# --- fe.markup.border_box_content -------------------------------------------------
@family(code="fe.markup.border_box_content", specialization="frontend", area="markup", level=2, fmt="calc",
        space_size=len(CSS_CLASSES) * len(CSS_COLORS) * 41 * 15 * 5 * 19, median_time_s=50)
def border_box_content(rng: random.Random) -> Generated:
    while True:
        width = rng.randrange(120, 521, 10)
        padding, horizontal = _padding(rng)
        border = rng.randint(1, 5)
        css = _box_css(rng, "border-box", width, padding, border)
        answer = width - horizontal - 2 * border
        if answer not in _numbers_in(css):
            break
    cls = css.split()[0]
    text = f"Какой будет ширина области содержимого (content) элемента {cls}, в пикселях?"
    return Generated("number", Prompt(text=text, code=css, language="css", answer_hint="Целое число пикселей"),
                     answer, ("border_box",))


# --- fe.markup.alt_text -------------------------------------------------------------
DECOR = ("волнистая линия", "ряд точек", "узор из листьев", "градиентная полоса", "орнамент", "пунктир",
         "цепочка звёздочек", "тонкая двойная линия")
CHART_METRICS = (("выручка", "выросла", "снизилась"), ("число заказов", "выросло", "снизилось"),
                 ("средний чек", "вырос", "снизился"), ("посещаемость", "выросла", "снизилась"),
                 ("число подписчиков", "выросло", "снизилось"))
CHART_PERIODS = ("2025 год", "первый квартал", "полгода", "март", "неделю")
COMPANIES = ("Ромашка", "Северный ветер", "Кит", "Альфа-Тур", "Зелёный дом", "Маяк", "Пчёлка", "Орбита",
             "Бриз", "Кедр", "Сокол", "Янтарь", "Полюс", "Ладья", "Вектор", "Гавань")
LOGO_LOOKS = ("синий круг с буквой", "зелёный лист на белом фоне", "красная звезда", "чёрный квадрат с надписью")
NO_ALT = "Атрибут alt не указывать"


def _alt_decor(rng: random.Random) -> tuple[str, str, list[str]]:
    decor = rng.choice(DECOR)
    text = rng.choice((
        "На {page} сайта {site} между разделами стоит декоративная картинка-разделитель: {decor}. Смысловой "
        "нагрузки она не несёт. Какой атрибут alt ей нужен?",
        "На {page} сайта {site} в углу карточек — декоративное изображение ({decor}), которое ничего не "
        "сообщает посетителю. Какой alt нужен такому изображению?",
    )).format(page=rng.choice(PAGES), site=rng.choice(SITES), decor=decor)
    wrong = ['alt="Разделитель"', f'alt="Декоративный элемент: {decor}"', NO_ALT, 'alt="divider.png"']
    return text, 'alt=""', wrong


def _alt_chart(rng: random.Random) -> tuple[str, str, list[str]]:
    metric, up, down = rng.choice(CHART_METRICS)
    a, b = rng.sample(range(20, 400, 5), 2)
    verb = up if b > a else down
    period = rng.choice(CHART_PERIODS)
    text = (f"На {rng.choice(PAGES)} сайта {rng.choice(SITES)} — изображение графика: {metric} {verb} с {a} до {b} "
            f"за {period}. В тексте страницы этих данных нет. Какой alt подходит изображению?")
    correct = f'alt="{metric[0].upper() + metric[1:]} {verb} с {a} до {b} за {period}"'
    wrong = ['alt="График"', 'alt="Столбчатая диаграмма синего цвета с подписями осей"', 'alt=""',
             'alt="chart.png"']
    return text, correct, wrong


def _alt_logo(rng: random.Random) -> tuple[str, str, list[str]]:
    company = rng.choice(COMPANIES)
    text = (f"На {rng.choice(PAGES)} сайта {rng.choice(SITES)} логотип компании «{company}» — единственное "
            "содержимое ссылки на главную страницу. Какой alt нужен изображению логотипа?")
    correct = rng.choice((f'alt="{company} — на главную"', f'alt="{company}: главная страница"'))
    wrong = ['alt="Логотип"', f'alt="Логотип: {rng.choice(LOGO_LOOKS)}"', 'alt=""', 'alt="logo.svg"']
    return text, correct, wrong


@family(code="fe.markup.alt_text", specialization="frontend", area="markup", level=2, fmt="mcq",
        # нижняя оценка — ветвь «декоративное»: шаблон × страница × сайт × вид × выбор дистракторов × порядок
        space_size=2 * len(PAGES) * len(SITES) * len(DECOR) * math.comb(4, 3) * 24 * 3, median_time_s=50)
def alt_text(rng: random.Random) -> Generated:
    text, correct, wrong = rng.choice((_alt_decor, _alt_chart, _alt_logo))(rng)
    return mcq(rng, text, correct, rng.sample(wrong, 3), radicals=("alt_text", 4))


# --- fe.markup.flex_grow_width ------------------------------------------------------
FLEX_CONTAINERS = ("row", "toolbar", "header", "layout", "footer-bar")
FLEX_ITEMS = (("a", "b", "c"), ("left", "main", "right"), ("logo", "search", "menu"), ("first", "second", "third"))
FLEX_GAPS = (0, 8, 10, 12, 16, 20, 24)


@family(code="fe.markup.flex_grow_width", specialization="frontend", area="markup", level=3, fmt="calc",
        # нижняя оценка: два элемента — имена × (рост, basis) обоих × gap × единица свободного места × вопрос
        space_size=len(FLEX_CONTAINERS) * len(FLEX_ITEMS) * (4 * 21) ** 2 * len(FLEX_GAPS) * 56 * 2,
        median_time_s=85)
def flex_grow_width(rng: random.Random) -> Generated:
    container = rng.choice(FLEX_CONTAINERS)
    names = rng.choice(FLEX_ITEMS)[:rng.randint(2, 3)]
    while True:
        grows = [rng.randint(0, 3) for _ in names]
        if sum(grows) == 0:
            continue
        bases = [rng.randrange(0, 201, 10) for _ in names]
        gap, unit = rng.choice(FLEX_GAPS), rng.randint(5, 60)
        width = sum(bases) + gap * (len(names) - 1) + unit * sum(grows)  # свободное место делится нацело
        growing = [i for i, g in enumerate(grows) if g > 0]
        # элемент без роста (ширина = flex-basis) спрашиваем редко: это не расчёт распределения
        k = rng.randrange(len(names)) if rng.random() < 0.06 else rng.choice(growing)
        answer = bases[k] + unit * grows[k]
        # без роста ширина равна собственному flex-basis — это вход, а не утечка ключа
        others = {width, gap, *grows, *(x for i, x in enumerate(bases) if i != k or grows[k])}
        if answer > 0 and answer not in others:
            break
    css = "\n".join([f".{container} {{", "  display: flex;", f"  width: {width}px;", f"  gap: {gap}px;", "}",
                     *(f".{n} {{ flex-grow: {g}; flex-basis: {b}px; }}"
                       for n, g, b in zip(names, grows, bases, strict=True))])
    items = ", ".join(f".{n}" for n in names)
    text = (f"Элементы {items} — дочерние элементы .{container} в этом порядке. У контейнера нет padding и border, "
            "элементы пустые (без содержимого), у них нет padding, border и margin, min-width и max-width не "
            "заданы. Какой будет ширина "
            f"элемента .{names[k]} в пикселях?")
    return Generated("number", Prompt(text=text, code=css, language="css", answer_hint="Целое число пикселей"),
                     answer, ("flex_grow",))


# --- fe.markup.margin_collapse ------------------------------------------------------
COLLAPSE_PAIRS = (("first", "second"), ("intro", "body"), ("summary", "details"), ("hero", "features"),
                  ("notice", "form"), ("title-block", "content"))
MARGINS = tuple(range(4, 49, 2))


def _margin_decl(rng: random.Random, side: str, value: int) -> str:
    """Вертикальный отступ одной стороны — отдельным свойством или в сокращённой записи margin."""
    other = rng.choice(MARGINS)
    form = rng.choice(("single", "two", "three", "four"))
    if form == "single":
        return f"margin-{side}: {value}px;"
    if form == "two" and side == "top":
        return f"margin: {value}px 0;"  # top и bottom одинаковые
    if form in ("two", "three"):
        return f"margin: {value if side == 'top' else other}px 0 {other if side == 'top' else value}px;"
    return f"margin: {value if side == 'top' else other}px {rng.choice((0, 8, 16))}px " \
           f"{other if side == 'top' else value}px 0;"


def _decorations(rng: random.Random) -> list[str]:
    out = []
    if rng.random() < 0.6:
        out.append(f"padding: {rng.randrange(4, 33, 4)}px;")
    if rng.random() < 0.6:
        out.append(f"border: {rng.randint(1, 3)}px solid {rng.choice(CSS_COLORS)};")
    return out


@family(code="fe.markup.margin_collapse", specialization="frontend", area="markup", level=3, fmt="calc",
        # нижняя оценка: пара имён × два различных отступа × вид записи каждого
        space_size=len(COLLAPSE_PAIRS) * math.perm(len(MARGINS), 2) * 3 * 3 * 4, median_time_s=70)
def margin_collapse(rng: random.Random) -> Generated:
    a, b = rng.choice(COLLAPSE_PAIRS)
    bottom, top = rng.sample(MARGINS, 2)
    blocks = []
    for name, decl in ((a, _margin_decl(rng, "bottom", bottom)), (b, _margin_decl(rng, "top", top))):
        blocks += [f".{name} {{", *(f"  {d}" for d in [decl, *_decorations(rng)]), "}"]
    code = "\n".join([f'<div class="{a}">…</div>', f'<div class="{b}">…</div>', "", "<style>", *blocks, "</style>"])
    text = (f"Два блока div идут друг за другом в обычном потоке внутри обычного блочного контейнера (не flex "
            f"и не grid), между ними ничего нет. Какое расстояние по вертикали будет между нижним краем рамки "
            f".{a} и верхним краем рамки .{b}, в пикселях?")
    return Generated("number", Prompt(text=text, code=code, language="html", answer_hint="Целое число пикселей"),
                     max(bottom, top), ("margin_collapse",))


# --- fe.markup.icon_button_label -----------------------------------------------------
ICON_ACTIONS = (("Удалить из корзины", "trash", "removeItem"), ("Закрыть окно", "close", "closeModal"),
                ("Добавить в избранное", "heart", "addFavorite"), ("Открыть меню", "menu", "openMenu"),
                ("Найти", "search", "openSearch"), ("Поделиться", "share", "share"),
                ("Скачать отчёт", "download", "downloadReport"), ("Следующий слайд", "arrow-right", "nextSlide"),
                ("Воспроизвести", "play", "play"), ("Открыть настройки", "gear", "openSettings"))
ICON_CORRECT = ('Добавить кнопке aria-label="{action}"', 'Добавить кнопке атрибут aria-label="{action}"')
ICON_WRONG = (  # ни один не даёт кнопке доступного имени
    'Добавить элементу <svg> role="img"', 'Добавить кнопке tabindex="0"',
    'Добавить элементу <svg> атрибут data-label="{action}"', "Добавить внутрь кнопки комментарий <!-- {action} -->",
    'Добавить кнопке aria-hidden="true"',
)


@family(code="fe.markup.icon_button_label", specialization="frontend", area="markup", level=3, fmt="mcq",
        space_size=len(ICON_ACTIONS) * len(PAGES) * len(SITES) * len(ICON_CORRECT) * math.comb(len(ICON_WRONG), 3)
        * 24, median_time_s=60)
def icon_button_label(rng: random.Random) -> Generated:
    action, icon, fn = rng.choice(ICON_ACTIONS)
    code = "\n".join([f'<button class="icon-btn" type="button" onclick="{fn}()">',
                      f'  <svg class="icon icon-{icon}" viewBox="0 0 24 24" width="24" height="24">',
                      f'    <use href="#{icon}"></use>', "  </svg>", "</button>"])
    text = (f"Кнопка «{action}» на {rng.choice(PAGES)} сайта {rng.choice(SITES)} содержит только иконку, текста "
            "в ней нет. Скринридер объявляет её просто как «кнопка». Как дать кнопке понятное доступное имя?")
    return mcq(rng, text, rng.choice(ICON_CORRECT).format(action=action),
               [w.format(action=action) for w in rng.sample(ICON_WRONG, 3)], code=code, language="html")


# --- fe.markup.cascade_important ----------------------------------------------------
def _cascade(rng: random.Random) -> tuple[list[tuple[str, tuple, bool]], tuple[bool] | None]:
    """Правила (селектор, специфичность, !important) и встроенный стиль (!important?) или None."""
    while True:
        inline = (rng.random() < 0.25,) if rng.random() < 0.5 else None
        rules = [(sel, spec, rng.random() < 0.35) for sel, spec in rng.sample(SPEC_SELECTORS, 4 - bool(inline))]
        if any(imp for *_, imp in rules) or (inline and inline[0]):
            return rules, inline


@family(code="fe.markup.cascade_important", specialization="frontend", area="markup", level=4, fmt="calc",
        # нижняя оценка: тег × id × классы × родитель × атрибут × тройка селекторов × цвета
        space_size=len(SPEC_TAGS) * len(SPEC_IDS) * math.perm(len(SPEC_CLASSES), 2) * len(SPEC_PARENTS)
        * len(SPEC_ATTRS) * math.comb(len(SPEC_SELECTORS), 3) * math.perm(len(SPEC_COLORS), 4),
        median_time_s=100)
def cascade_important(rng: random.Random) -> Generated:
    tag, id_, pc = rng.choice(SPEC_TAGS), rng.choice(SPEC_IDS), rng.choice(SPEC_PARENTS)
    c1, c2 = rng.sample(SPEC_CLASSES, 2)
    attr, val = rng.choice(SPEC_ATTRS)
    rules, inline = _cascade(rng)
    colors = rng.sample(SPEC_COLORS, 4)
    fields = {"tag": tag, "id": id_, "pc": pc, "c1": c1, "c2": c2, "attr": attr, "val": val}
    # порядок каскада: важность, затем встроенный стиль, затем специфичность, затем порядок в коде
    ranked = [((imp, 0, spec, i), colors[i]) for i, (_, spec, imp) in enumerate(rules)]
    style = ""
    if inline:
        style = f' style="color: {colors[3]}{" !important" if inline[0] else ""};"'
        ranked.append(((inline[0], 1, (0, 0, 0), 99), colors[3]))
    winner = max(ranked)[1]
    lines = [f"  {sel.format(**fields)} {{ color: {colors[i]}{' !important' if imp else ''}; }}"
             for i, (sel, _, imp) in enumerate(rules)]
    code = "\n".join([f'<div class="{pc}">',
                      f'  <{tag} id="{id_}" class="{c1} {c2}" data-{attr}="{val}"{style}>Текст</{tag}>',
                      "</div>", "", "<style>", *lines, "</style>"])
    return mcq(rng, "Какого цвета будет текст элемента? Других стилей на странице нет.", winner,
               [c for c in colors if c != winner], code=code, language="html", radicals=("cascade", "important"))


# --- fe.markup.grid_fr_width ----------------------------------------------------------
GRID_CONTAINERS = ("grid", "layout", "gallery", "dashboard", "page")
GRID_GAPS = (0, 8, 12, 16, 20, 24, 32)
ORDINALS = ("первой", "второй", "третьей", "четвёртой")


@family(code="fe.markup.grid_fr_width", specialization="frontend", area="markup", level=4, fmt="calc",
        # нижняя оценка: три колонки «px fr fr» — контейнер × px × два fr × gap × единица fr × вопрос
        space_size=len(GRID_CONTAINERS) * 23 * 9 * len(GRID_GAPS) * 101 * 2, median_time_s=100)
def grid_fr_width(rng: random.Random) -> Generated:
    container = rng.choice(GRID_CONTAINERS)
    while True:
        n = rng.randint(3, 4)
        cols = [("px", rng.randrange(80, 301, 10)) if rng.random() < 0.4 else ("fr", rng.randint(1, 3))
                for _ in range(n)]
        frs = [i for i, (u, _) in enumerate(cols) if u == "fr"]
        if not frs or len(frs) == n:
            continue
        gap, unit = rng.choice(GRID_GAPS), rng.randint(20, 120)
        width = sum(v for u, v in cols if u == "px") + gap * (n - 1) + unit * sum(v for u, v in cols if u == "fr")
        k = rng.choice(frs)
        answer = unit * cols[k][1]
        if answer not in {width, gap, *(v for _, v in cols)}:
            break
    template = " ".join(f"{v}{u}" for u, v in cols)
    css = "\n".join([f".{container} {{", "  display: grid;", f"  width: {width}px;",
                     f"  grid-template-columns: {template};", f"  column-gap: {gap}px;", "}"])
    text = (f"У контейнера .{container} нет padding и border, ячейки пустые. Какой будет ширина {ORDINALS[k]} "
            "колонки в пикселях?")
    return Generated("number", Prompt(text=text, code=css, language="css", answer_hint="Целое число пикселей"),
                     answer, ("grid_fr",))


# --- fe.markup.positive_tabindex ------------------------------------------------------
TABINDEX_FORMS = (
    ("login", (("email", "Эл. почта"), ("password", "Пароль")), "Войти"),
    ("signup", (("name", "Имя"), ("email", "Эл. почта"), ("password", "Пароль")), "Зарегистрироваться"),
    ("feedback", (("name", "Имя"), ("phone", "Телефон"), ("message", "Сообщение")), "Отправить"),
    ("order", (("address", "Адрес"), ("date", "Дата"), ("comment", "Комментарий")), "Оформить"),
    ("search", (("query", "Запрос"), ("city", "Город")), "Найти"),
)
TABINDEX_CORRECT = (
    "Элементы с tabindex > 0 получают фокус раньше всех остальных, порядок ломается; нужен порядок DOM "
    "и только tabindex 0 и -1",
    "Положительный tabindex ставит элемент в начало обхода всей страницы; правильно — порядок в DOM, "
    "tabindex только 0 или -1",
    "Такие элементы фокусируются первыми на всей странице, вне порядка DOM; нужно упорядочить разметку, "
    "а tabindex > 0 убрать",
)
TABINDEX_WRONG = (
    "Ничем не плохо: положительный tabindex — рекомендуемый способ задать порядок; нужно расставить его "
    "на всех элементах страницы",
    "Плохо тем, что tabindex не работает у input; нужно обернуть каждое поле в ссылку <a> с тем же "
    "tabindex",
    "Это влияет лишь на мобильные браузеры без клавиатуры; на десктопе положительные значения безопасны, "
    "их можно оставить",
    "Порядок фокуса задаёт CSS-свойство order, а tabindex игнорируется; нужно заменить tabindex на order "
    "у полей формы",
)


@family(code="fe.markup.positive_tabindex", specialization="frontend", area="markup", level=4, fmt="mcq",
        # нижняя оценка: форма из двух полей и кнопки — значения tabindex (3 различных из 1..9) × формулировки
        space_size=len(TABINDEX_FORMS) * math.perm(9, 3) * len(TABINDEX_CORRECT) * math.comb(len(TABINDEX_WRONG), 3)
        * 24, median_time_s=90)
def positive_tabindex(rng: random.Random) -> Generated:
    form, fields, submit = rng.choice(TABINDEX_FORMS)
    values = rng.sample(range(1, 10), len(fields) + 1)
    code = "\n".join([f'<form class="{form}">',
                      *(f'  <label>{label} <input name="{name}" tabindex="{v}"></label>'
                        for (name, label), v in zip(fields, values, strict=False)),
                      f'  <button type="submit" tabindex="{values[-1]}">{submit}</button>', "</form>",
                      '<div class="modal" role="dialog" aria-modal="true">',
                      '  <button type="button">Закрыть</button>', "</div>"])
    text = ("Чтобы задать порядок обхода формы с клавиатуры, разработчик расставил её элементам положительные "
            "tabindex. На странице есть и другие интерактивные элементы: меню, ссылки, модальное окно. Чем это "
            "плохо и как правильно?")
    return mcq(rng, text, rng.choice(TABINDEX_CORRECT), rng.sample(TABINDEX_WRONG, 3), code=code, language="html")


# --- fe.markup.stacking_context -------------------------------------------------------
STACK_NAMES = (("menu", "dropdown", "header", "banner"), ("card", "tooltip", "sidebar", "footer"),
               ("modal", "close-btn", "toast", "overlay"), ("panel", "popup", "toolbar", "notice"))
# как родитель создаёт (или не создаёт) контекст наложения: правило CSS и уровень группы в корне
STACK_PARENT = {
    "z": "position: relative; z-index: {za};",
    "opacity": "position: relative; opacity: 0.9;",
    "transform": "position: relative; transform: translateX(0);",
    "none": "position: relative;",
}
SIBLING_Z = (-3, -2, -1, *range(1, 10))
CHILD_Z = (*range(2, 10), 50, 100, 999)
LARGE_Z = (50, 100, 999)
# «без контекста» реже: там верный ответ совпадает с наивным «больше z-index — выше»
STACK_KIND_WEIGHTS = {"z": 3, "opacity": 2, "transform": 2, "none": 1}
CHILD_TOP_SHARE = 0.35  # в ветвях с контекстом потомок с большим z-index наверху лишь в этой доле


def _stack_levels(rng: random.Random, kind: str) -> tuple[int, int, int, int]:
    """z родителя, потомка и двух соседей. С контекстом у потомка всегда самый большой z-index,
    а наверху он только если наверху группа родителя."""
    child_top = rng.random() < CHILD_TOP_SHARE
    while True:
        za, zb, zd = rng.randint(1, 9), *rng.sample(SIBLING_Z, 2)
        zc = rng.choice(CHILD_Z if kind == "none" else LARGE_Z)
        group = {"z": za, "opacity": 0, "transform": 0, "none": zc}[kind]
        if len({group, zb, zd}) < 3 or zc in (zb, zd):
            continue
        if kind == "none" or (group > max(zb, zd)) == child_top:
            return za, zc, zb, zd


@family(code="fe.markup.stacking_context", specialization="frontend", area="markup", level=5, fmt="calc",
        # нижняя оценка: имена × вид родителя × z соседей × z потомка (без z родителя)
        space_size=len(STACK_NAMES) * len(STACK_PARENT) * math.perm(len(SIBLING_Z), 2) * len(LARGE_Z) * 24,
        median_time_s=140)
def stacking_context(rng: random.Random) -> Generated:
    parent, child, b, c = rng.choice(STACK_NAMES)
    kind = rng.choices(tuple(STACK_KIND_WEIGHTS), weights=tuple(STACK_KIND_WEIGHTS.values()))[0]
    za, zc, zb, zd = _stack_levels(rng, kind)
    # уровень группы родителя в корневом контексте; без контекста потомок участвует сам
    levels = {child: {"z": za, "opacity": 0, "transform": 0, "none": zc}[kind], b: zb, c: zd}
    top = max(levels, key=levels.get)
    css = [f".{parent} {{ {STACK_PARENT[kind].format(za=za)} }}",
           f".{child} {{ position: absolute; z-index: {zc}; }}",
           f".{b} {{ position: relative; z-index: {zb}; }}", f".{c} {{ position: relative; z-index: {zd}; }}"]
    code = "\n".join([f'<div class="{parent}">', f'  <div class="{child}"></div>', "</div>",
                      f'<div class="{b}"></div>', f'<div class="{c}"></div>', "", "<style>", *css, "</style>"])
    text = ("Считайте, что все четыре блока перекрываются в одной точке; других стилей нет. Какой элемент будет "
            "виден сверху в этой точке?")
    return mcq(rng, text, f".{top}", [f".{n}" for n in (parent, child, b, c) if n != top], code=code,
               language="html", radicals=("stacking_context", 4))


# --- fe.markup.contrast_ratio ---------------------------------------------------------
def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_channel(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@family(code="fe.markup.contrast_ratio", specialization="frontend", area="markup", level=5, fmt="calc",
        # нижняя оценка: пары цветов (каналы по 256 значений), часть отбрасывается у границы округления
        space_size=256**6 // 100, median_time_s=130)
def contrast_ratio(rng: random.Random) -> Generated:
    while True:
        fg, bg = (tuple(rng.randrange(256) for _ in range(3)) for _ in range(2))
        lf, lb = (round(_relative_luminance(x), 4) for x in (fg, bg))
        if not (0.002 <= min(lf, lb) and max(lf, lb) < 0.99995):
            continue
        hi, lo = max(lf, lb), min(lf, lb)
        ratio = (hi + 0.05) / (lo + 0.05)
        frac = ratio * 10 - round(ratio * 10)
        # далеко от границы округления, и «забытые» +0.05 дают другой ответ
        if abs(frac) < 0.4 and round(hi / lo, 1) != round(ratio, 1):
            break
    hex_fg, hex_bg = ("#" + "".join(f"{x:02x}" for x in rgb) for rgb in (fg, bg))
    text = (f"Текст цвета {hex_fg} (относительная яркость {lf:.4f}) лежит на фоне {hex_bg} (относительная "
            f"яркость {lb:.4f}). Каков коэффициент контраста по WCAG 2.x? Округлите до одного знака после запятой.")
    return Generated("number", Prompt(text=text, answer_hint="Число с одним знаком после запятой, например 4.5"),
                     round(ratio, 1), ("wcag_contrast",))

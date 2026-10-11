"""Семейства Frontend · отладка и тестирование."""
import json
import math
import random

from app.assessment.bank.base import Generated, Prompt, Table, family, mcq
from app.assessment.bank.jsrun import JsError, run_js_snippet


def _numbered(lines: list[str]) -> str:
    return "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, start=1))


def _line_answer(text: str, lines: list[str], key: int, radicals: tuple, language: str = "jsx") -> Generated:
    """Задание «найди строку»: код в prompt.code, нумерация — в подсказке формата ответа (как в Backend)."""
    return Generated("line", Prompt(text=text, code="\n".join(lines), language=language,
                                    answer_hint=f"Номер строки:\n{_numbered(lines)}"), key, radicals)


COMPONENTS = ("UserCard", "OrderList", "CartItem", "ProfileHeader", "PriceTag", "SearchResults", "ProductTile",
              "Avatar")

# --- fe.debug.stack_trace_line --------------------------------------------------------
HELPERS = (("formatPrice", "format.ts"), ("getInitials", "names.ts"), ("parseDate", "dates.ts"),
           ("toCurrency", "money.ts"), ("pickAvatar", "avatar.ts"))
REACT_FRAMES = ("renderWithHooks", "mountIndeterminateComponent", "beginWork", "updateFunctionComponent")
PROPS = ("name", "price", "items", "avatarUrl", "title", "id")
ERRORS = (
    "TypeError: Cannot read properties of undefined (reading '{prop}')",
    "TypeError: Cannot read properties of null (reading 'map')",
    "TypeError: {fn} is not a function",
    "ReferenceError: {var} is not defined",
)
UNDEFINED_FNS = ("formatPrice", "onSelect", "getInitials", "toCurrency")
UNDEFINED_VARS = ("currentUser", "basePrice", "theme", "locale")


@family(code="fe.debug.stack_trace_line", specialization="frontend", area="debug", level=1, fmt="bug",
        # компонент × строка и столбец × вспомогательная функция (или нет) × внутренние кадры × сообщение
        space_size=len(COMPONENTS) * 116 * 38 * (1 + len(HELPERS)) * 4 * len(ERRORS), median_time_s=35)
def stack_trace_line(rng: random.Random) -> Generated:
    comp = rng.choice(COMPONENTS)
    line, app_line = rng.sample(range(5, 121), 2)
    error = rng.choice(ERRORS).format(prop=rng.choice(PROPS), fn=rng.choice(UNDEFINED_FNS),
                                      var=rng.choice(UNDEFINED_VARS))
    inner = rng.sample(REACT_FRAMES, rng.randint(2, 3))
    rows = [error]
    if rng.random() < 0.5:  # исключение выброшено во вспомогательной функции, вызванной из компонента
        helper, helper_file = rng.choice(HELPERS)
        rows.append(f"    at {helper} (src/utils/{helper_file}:{app_line}:{rng.randint(3, 40)})")
    rows += [f"    at {comp} (src/components/{comp}.tsx:{line}:{rng.randint(3, 40)})",
             *(f"    at {fn} (react-dom.development.js:{rng.randint(10000, 30000)}:{rng.randint(5, 30)})"
               for fn in inner)]
    text = (f"При открытии страницы в консоли браузера — ошибка со стеком вызовов (см. ниже). Какую строку файла "
            f"{comp}.tsx указывает стек?")
    return Generated("line", Prompt(text=text, code="\n".join(rows), language="text", answer_hint="Номер строки"),
                     line, ("browser_stack_trace",))


# --- fe.debug.text_matcher ---------------------------------------------------------------
MATCHER_TEXTS = ("Корзина пуста", "Добро пожаловать", "Заказ оформлен", "Нет результатов", "Профиль сохранён",
                 "Введите пароль", "Скидка 10%", "Оплата прошла", "Список пуст", "Готово", "Ошибка сети",
                 "Сессия истекла")
MATCHER_TITLES = ("показывает сообщение", "выводит текст", "рендерит подпись")
MATCHER_CORRECT = ("expect(screen.getByText('{text}')).toBeInTheDocument()",
                   "expect(screen.queryByText('{text}')).not.toBeNull()")
MATCHER_WRONG = (
    "expect(screen.getByText('{text}')).toBeEmptyDOMElement()",
    "expect(container.querySelector('{text}')).toBeTruthy()",
    "expect(document.title).toBe('{text}')",
    "expect(screen.getByText('{text}')).toBeFalsy()",
    "expect(screen.getAllByRole('{text}')).toHaveLength(1)",
)


@family(code="fe.debug.text_matcher", specialization="frontend", area="debug", level=1, fmt="mcq",
        space_size=len(COMPONENTS) * len(MATCHER_TEXTS) * len(MATCHER_TITLES) * len(MATCHER_CORRECT)
        * math.comb(len(MATCHER_WRONG), 3) * 24,
        median_time_s=40)
def text_matcher(rng: random.Random) -> Generated:
    comp, text = rng.choice(COMPONENTS), rng.choice(MATCHER_TEXTS)
    code = "\n".join(["import { render, screen } from '@testing-library/react';", "",
                      f"test('{comp} {rng.choice(MATCHER_TITLES)}', () => {{", f"  const {{ container }} = render(<{comp} />);",
                      "  // какая проверка?", "});"])
    prompt = (f"Компонент {comp} сразу при рендере показывает текст «{text}». Какая проверка в тесте корректно "
              "убедится, что этот текст есть на экране?")
    return mcq(rng, prompt, rng.choice(MATCHER_CORRECT).format(text=text),
               [w.format(text=text) for w in rng.sample(MATCHER_WRONG, 3)], code=code, language="jsx")


# --- fe.debug.pagination_slice_count ---------------------------------------------------------
PAGE_FUNCS = ("getPage", "pageSlice", "paginate", "takePage")
PAGE_CONSTS = ("PAGE_SIZE", "PER_PAGE", "LIMIT")
PAGE_ARRAYS = ("items", "rows", "orders", "products")


@family(code="fe.debug.pagination_slice_count", specialization="frontend", area="debug", level=2, fmt="calc",
        # имена × размер страницы × длина массива × выбор страницы (последняя, следующая за ней, средняя)
        space_size=len(PAGE_FUNCS) * len(PAGE_CONSTS) * len(PAGE_ARRAYS) * 23 * 194 * 3, median_time_s=45)
def pagination_slice_count(rng: random.Random) -> Generated:
    fn, const, arr = rng.choice(PAGE_FUNCS), rng.choice(PAGE_CONSTS), rng.choice(PAGE_ARRAYS)
    size = rng.randint(3, 25)
    kind = rng.choices(("last", "after", "middle"), weights=(7, 1, 2))[0]  # ответ 0 («после последней») — редкость
    while True:  # вид страницы выбран заранее: перебор не меняет долю видов
        n = rng.randint(7, 200)
        pages = math.ceil(n / size)
        if kind == "middle" and pages < 3:
            continue
        page = {"last": pages, "after": pages + 1, "middle": rng.randint(2, max(2, pages - 1))}[kind]
        answer = max(0, min(n, page * size) - (page - 1) * size)
        if kind != "last" or answer not in (size, n, page):
            break
    code = "\n".join([f"const {const} = {size};", "", f"function {fn}({arr}, page) {{",
                      f"  return {arr}.slice((page - 1) * {const}, page * {const});", "}"])
    text = f"Длина массива {arr} — {n}. Сколько элементов вернёт {fn}({arr}, {page})?"
    return Generated("number", Prompt(text=text, code=code, language="javascript", answer_hint="Целое число"),
                     answer, ("slice_pagination",))


# --- fe.debug.which_expect_fails ------------------------------------------------------------
def _price_case(rng: random.Random, failing: bool) -> tuple[str, str]:
    rest = rng.randint(50, 99) if failing else rng.randint(0, 49)  # Math.round округляет рубли вверх с 50 копеек
    cents = rng.randint(1, 999) * 100 + rest
    return f"formatPrice({cents})", f"'{cents // 100}.{cents % 100:02d}'"


def _clamp_cases(rng: random.Random) -> list[tuple[str, str]]:
    """Падает x ≤ lo (нижняя граница сдвинута на 1); среди проходящих всегда есть обрезка сверху,
    поэтому «ожидаемое равно границе» не выделяет падающую проверку."""
    def case(kind: str) -> tuple[str, str]:
        lo = rng.randint(0, 50)
        hi = lo + rng.randint(10, 100)
        x = {"below": rng.randint(lo - 30, lo), "inside": rng.randint(lo + 1, hi), "above": rng.randint(hi + 1, hi + 50)}[kind]
        return f"clamp({x}, {lo}, {hi})", str(min(max(x, lo), hi))
    return [case("below"), case("above"), case(rng.choice(("inside", "above"))), case("inside")]


PALINDROMES = ("level", "noon", "civic", "radar", "kayak", "madam", "refer", "rotor")
WORDS = ("hello", "table", "react", "world", "pixel", "candy", "train", "lemon")


def _palindrome_cases(rng: random.Random) -> list[tuple[str, str]]:
    """Падает палиндром с заглавной буквой (сравнение с учётом регистра); среди проходящих есть
    и слово с заглавной буквой — «заглавная» не выдаёт ключ."""
    p_fail, p_ok = rng.sample(PALINDROMES, 2)
    w1, w2 = rng.sample(WORDS, 2)
    return [(f"isPalindrome('{p_fail.capitalize()}')", "true"), (f"isPalindrome('{p_ok}')", "true"),
            (f"isPalindrome('{w1.capitalize()}')", "false"), (f"isPalindrome('{w2}')", "false")]


def _percent_case(rng: random.Random, failing: bool) -> tuple[str, str]:
    while True:  # дробная часть процента — далеко от .5 и от целого: ответ не зависит от погрешности float
        total = rng.randint(7, 400)
        part = rng.randint(1, total - 1)
        frac = (100 * part % total) / total
        if (0.55 <= frac <= 0.95) if failing else (0.05 <= frac <= 0.45):
            return f"percentOf({part}, {total})", str(100 * part // total)


def _cases(case):
    return lambda rng: [case(rng, True), *(case(rng, False) for _ in range(3))]


EXPECT_TEMPLATES = {  # имя → (код с ошибкой, генератор проверок: первая падает, остальные проходят)
    "formatPrice": ("// Копейки → строка «рубли.копейки», рубли — целая часть (без округления)\n"
                    "function formatPrice(cents) {\n"
                    "  return `${Math.round(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;\n}",
                    _cases(_price_case)),
    "clamp": ("// Ограничивает x отрезком [lo, hi] (оба конца включены)\nfunction clamp(x, lo, hi) {\n"
              "  return Math.min(Math.max(x, lo + 1), hi);\n}", _clamp_cases),
    "isPalindrome": ("// Палиндром ли слово — без учёта регистра букв\nfunction isPalindrome(s) {\n"
                     "  return s === s.split('').reverse().join('');\n}", _palindrome_cases),
    "percentOf": ("// Целый процент part от total, округление вниз\nfunction percentOf(part, total) {\n"
                  "  return Math.round((part / total) * 100);\n}", _cases(_percent_case)),
}


def _expect_passes(code: str, call: str, expected: str) -> bool:
    try:
        actual = run_js_snippet(code + f"\nconsole.log(JSON.stringify({call}) === JSON.stringify({expected}));")
    except JsError:
        return False
    return actual == "true"


@family(code="fe.debug.which_expect_fails", specialization="frontend", area="debug", level=2, fmt="bug",
        # нижняя оценка — шаблон isPalindrome: два палиндрома × два слова × порядок
        space_size=math.perm(len(PALINDROMES), 2) * math.perm(len(WORDS), 2) * 24, median_time_s=60)
def which_expect_fails(rng: random.Random) -> Generated:
    name = rng.choice(sorted(EXPECT_TEMPLATES))
    code, case = EXPECT_TEMPLATES[name]
    while True:
        cases = case(rng)
        lines = [f"expect({call}).toBe({expected})" for call, expected in cases]
        # ключ вычисляется исполнением настоящего JS: падает ровно одна проверка
        if len(set(lines)) == 4 and [_expect_passes(code, c, e) for c, e in cases] == [False, True, True, True]:
            break
    return mcq(rng, "Функция должна работать так, как описано в комментарии. Какая из проверок упадёт?",
               lines[0], lines[1:], code=code, language="javascript", radicals=("which_expect_fails", 4))


# --- fe.debug.onclick_called_line --------------------------------------------------------------
ONCLICK_COMPONENTS = (("Toggle", "open", "setOpen", "toggle", ("Показать", "Открыть", "Развернуть")),
                      ("LikeButton", "liked", "setLiked", "handleLike", ("Нравится", "Лайк", "Отметить")),
                      ("Accordion", "expanded", "setExpanded", "onToggle", ("Подробнее", "Ещё", "Детали")),
                      ("Modal", "visible", "setVisible", "close", ("Закрыть", "Скрыть", "Отмена")),
                      ("Menu", "shown", "setShown", "toggleMenu", ("Меню", "Навигация", "Разделы")))
ONCLICK_CLASSES = ("panel", "box", "wrapper", "controls", "toolbar", "card")
ONCLICK_PROPS = ("onChange", "onSearch", "onInput")
ONCLICK_EVENTS = ("e", "ev", "event")
ONCLICK_PLACEHOLDERS = ("Поиск", "Имя", "Комментарий", "Город", "Email", "Заметка")


@family(code="fe.debug.onclick_called_line", specialization="frontend", area="debug", level=2, fmt="bug",
        # компонент × подпись × класс × проп × имя события × placeholder × начальное значение × константа × крестик
        # (порядок строк JSX не считаем)
        space_size=len(ONCLICK_COMPONENTS) * 3 * len(ONCLICK_CLASSES) * len(ONCLICK_PROPS) * len(ONCLICK_EVENTS)
        * len(ONCLICK_PLACEHOLDERS) * 2 * 2 * 2, median_time_s=50)
def onclick_called_line(rng: random.Random) -> Generated:
    comp, var, setter, handle, labels = rng.choice(ONCLICK_COMPONENTS)
    label, prop, ev = rng.choice(labels), rng.choice(ONCLICK_PROPS), rng.choice(ONCLICK_EVENTS)
    with_const = rng.random() < 0.5
    head = [f"function {comp}({{ {prop} }}) {{", f"  const [{var}, {setter}] = useState({rng.choice(('false', 'true'))});"]
    if with_const:
        head.append(f"  const label = '{label}';")
    head += ["", f"  function {handle}() {{", f"    {setter}(!{var});", "  }", "", "  return (",
             f'    <div className="{rng.choice(ONCLICK_CLASSES)}">']
    jsx = [f"      <button onClick={{{handle}()}}>{'{label}' if with_const else label}</button>",
           f'      <input placeholder="{rng.choice(ONCLICK_PLACEHOLDERS)}" onChange={{({ev}) => {prop}({ev}.target.value)}} />']
    if rng.random() < 0.5:
        jsx.append(f"      <span onClick={{() => {setter}(false)}}>×</span>")
    rng.shuffle(jsx)
    lines = [*head, *jsx, "    </div>", "  );", "}"]
    key = next(i for i, ln in enumerate(lines, 1) if f"onClick={{{handle}()}}" in ln)
    text = ("Компонент падает уже при первом рендере с ошибкой React «Too many re-renders». В какой строке "
            "ошибка?")
    return _line_answer(text, lines, key, ("handler_called_in_render",))


# --- fe.debug.missing_await_test -------------------------------------------------------------------
AWAIT_FETCHERS = (("fetchUser", "name", "'Анна'"), ("loadOrder", "status", "'paid'"), ("getCart", "total", "1990"),
                  ("fetchRates", "usd", "92"), ("loadProfile", "city", "'Омск'"))
AWAIT_FORMS = {
    "then": ("test('{title}', () => {{", "  {fetch}({id}).then((data) => {{", "    expect(data.{field}).toBe({value});",
             "  }});", "}});"),
    "async": ("test('{title}', async () => {{", "  const promise = {fetch}({id});",
              "  promise.then((data) => expect(data.{field}).toBe({value}));", "}});"),
    "waitFor": ("test('{title}', () => {{", "  render(<Profile id={{{id}}} />);",
                "  waitFor(() => expect(screen.getByText({value})).toBeInTheDocument());", "}});"),
}
AWAIT_TITLES = ("загружает данные", "показывает результат", "получает ответ API")
AWAIT_CORRECT = (
    "Тест не ждёт промис и завершается раньше, чем выполнится expect; нужен await или return",
    "Проверка выполняется уже после завершения теста и не учитывается; нужен await промиса",
)
AWAIT_WRONG = (
    "toBe сравнивает только типы значений, поэтому неверные данные того же типа проходят проверку",
    "Jest выполняет expect внутри then только при запуске с флагом --runInBand",
    "Промис отклоняется, а отклонённые промисы Jest считает успешно пройденными тестами",
    "Jest кэширует прошлый успешный результат, пока не изменится сам файл теста",
)


@family(code="fe.debug.missing_await_test", specialization="frontend", area="debug", level=3, fmt="mcq",
        space_size=len(AWAIT_FORMS) * len(AWAIT_FETCHERS) * len(AWAIT_TITLES) * 99 * len(AWAIT_CORRECT)
        * math.comb(len(AWAIT_WRONG), 3) * 24, median_time_s=70)
def missing_await_test(rng: random.Random) -> Generated:
    fetch, field, value = rng.choice(AWAIT_FETCHERS)
    form = rng.choice(sorted(AWAIT_FORMS))
    code = "\n".join(ln.format(title=rng.choice(AWAIT_TITLES), fetch=fetch, id=rng.randint(1, 99), field=field,
                               value=value) for ln in AWAIT_FORMS[form])
    text = (f"Тест всегда зелёный — даже когда {fetch} возвращает неверные данные или компонент сломан. "
            "Почему?")
    return mcq(rng, text, rng.choice(AWAIT_CORRECT), rng.sample(AWAIT_WRONG, 3), code=code, language="jsx")


# --- fe.debug.optional_chaining_line ------------------------------------------------------------
OPT_FIELDS = (("city", "address", "Омск"), ("phone", "contacts", "+7 900 000-00-00"), ("company", "job", "Ромашка"),
              ("plan", "subscription", "pro"), ("theme", "settings", "dark"), ("avatar", "profile", "a.png"))
OPT_FUNCS = ("formatUser", "renderCard", "describe", "toLabel", "summary")
OPT_NAMES = ("Анна", "Олег", "Ирина", "Павел", "Мария")


@family(code="fe.debug.optional_chaining_line", specialization="frontend", area="debug", level=3, fmt="bug",
        # функция × имя × выбор и порядок 4 полей × падающее поле × вид остальных (есть / нет с ?.) × комментарий
        space_size=len(OPT_FUNCS) * len(OPT_NAMES) * math.perm(len(OPT_FIELDS), 4) * 4 * 3**3 * 2, median_time_s=75)
def optional_chaining_line(rng: random.Random) -> Generated:
    fn = rng.choice(OPT_FUNCS)
    fields = rng.sample(OPT_FIELDS, rng.randint(4, 5))
    fail = rng.randrange(len(fields))
    present, body, missing_optional = {}, [], 0
    for i, (var, parent, value) in enumerate(fields):
        if i == fail:  # родителя нет во входе, а обращение прямое — здесь TypeError
            body.append(f"  const {var} = user.{parent}.{var};")
            continue
        kind = rng.choice(("present_direct", "present_optional", "missing_optional"))
        if kind != "missing_optional":
            present[parent] = (var, value)
        else:
            missing_optional += 1
        op = "." if kind == "present_direct" else "?."
        body.append(f"  const {var} = user.{parent}{op}{var}{' ?? ' + repr('—') if op == '?.' else ''};")
    if not missing_optional:  # хотя бы одно отсутствующее поле читается безопасно — «нет поля» не выдаёт ключ
        j = next(i for i in range(len(fields)) if i != fail)
        var, parent, _ = fields[j]
        present.pop(parent, None)
        body[j] = f"  const {var} = user.{parent}?.{var} ?? '—';"
    head = [f"function {fn}(user) {{"]
    if rng.random() < 0.5:
        head.append("  // поля профиля могут отсутствовать")
    head.append("  const name = user.name;")
    vars_ = ", ".join(["name", *(v for v, _, _ in fields)])
    arg = ", ".join([f"name: '{rng.choice(OPT_NAMES)}'",
                     *(f"{parent}: {{ {var}: '{value}' }}" for parent, (var, value) in present.items())])
    lines = [*head, *body, f"  return [{vars_}].join(' | ');", "}", "", f"{fn}({{ {arg} }});"]
    key = len(head) + 1 + fail
    text = (f"Вызов в последней строке завершается ошибкой TypeError. В какой строке функции {fn} она "
            "возникает?")
    return _line_answer(text, lines, key, ("optional_chaining",), language="javascript")


# --- fe.debug.flaky_snapshot -------------------------------------------------------------------------
SNAP_SOURCES = ("<p>Сгенерировано: {Date.now()}</p>", "<input id={`field-${Math.random()}`} />",
                "<span>{new Date().toLocaleTimeString()}</span>")
SNAP_TITLES = ("Профиль", "Заказ", "Отчёт", "Корзина", "Настройки", "Новости")
SNAP_CLASSES = ("card", "panel", "box", "widget")
SNAPSHOT_CORRECT = (
    "В разметку попадает текущее время или случайное число, снимок каждый раз иной; их надо зафиксировать",
    "Значение в рендере меняется от запуска к запуску; замокать время или Math.random либо передать через props",
)
SNAPSHOT_WRONG = (
    "Снимки нестабильны по своей природе; их нужно перезаписывать флагом -u перед каждым запуском набора тестов",
    "Тест запускается параллельно с другими тестами и мешает им; нужно всегда запускать Jest с флагом --runInBand",
    "render отдаёт контейнер асинхронно; перед toMatchSnapshot нужен await, иначе снимок получится неполным",
    "Снимок хранит стили, а CSS-модули меняют имена классов при каждом запуске",
)


@family(code="fe.debug.flaky_snapshot", specialization="frontend", area="debug", level=3, fmt="mcq",
        space_size=len(SNAP_SOURCES) * len(COMPONENTS) * len(SNAP_TITLES) * len(SNAP_CLASSES) * len(SNAPSHOT_CORRECT)
        * math.comb(len(SNAPSHOT_WRONG), 3) * 24, median_time_s=70)
def flaky_snapshot(rng: random.Random) -> Generated:
    comp = rng.choice(COMPONENTS)
    code = "\n".join([f"function {comp}() {{", "  return (", f'    <div className="{rng.choice(SNAP_CLASSES)}">',
                      f"      <h2>{rng.choice(SNAP_TITLES)}</h2>", f"      {rng.choice(SNAP_SOURCES)}", "    </div>",
                      "  );", "}", "", f"test('{comp} совпадает со снимком', () => {{",
                      f"  const {{ container }} = render(<{comp} />);", "  expect(container).toMatchSnapshot();", "});"])
    text = "Снимок-тест то проходит, то падает, хотя код не меняли. Почему и как это исправить?"
    return mcq(rng, text, rng.choice(SNAPSHOT_CORRECT), rng.sample(SNAPSHOT_WRONG, 3), code=code, language="jsx")


# --- fe.debug.long_component_bug ----------------------------------------------------------------------
PAGINATE_TEMPLATE = (
    "function {fn}({items}, {per}, {page}) {{",
    "  const total = {items}.length;",
    "  const pages = Math.ceil(total / {per});",
    "  if ({page} < 1 || {page} > pages) {{",
    "    return {{ items: [], pages, hasNext: false }};",
    "  }}",
    "  const start = ({page} - 1) * {per};",
    "  const end = start + {per};",
    "  const slice = {items}.slice(start, end);",
    "  const hasNext = end < total;",
    "  return {{ items: slice, pages, hasNext }};",
    "}}",
)
# номер строки шаблона (с 1) → (как правильно, как с ошибкой); исправление — только в этой строке
PAGINATE_MUTATIONS = {
    3: ("Math.ceil(total / {per})", "Math.floor(total / {per})"),
    4: ("{page} > pages", "{page} >= pages"),
    7: ("({page} - 1) * {per}", "{page} * {per}"),
    10: ("end < total", "end <= total"),
}
PAGINATE_NAMES = (("paginate", "items", "perPage", "page"), ("getPage", "rows", "size", "pageNo"),
                  ("pageOf", "list", "limit", "n"), ("slicePage", "data", "perPage", "num"))


def _paginate_py(xs: list[int], per: int, page: int) -> dict:
    pages = math.ceil(len(xs) / per)
    if page < 1 or page > pages:
        return {"items": [], "pages": pages, "hasNext": False}
    start, end = (page - 1) * per, page * per
    return {"items": xs[start:end], "pages": pages, "hasNext": end < len(xs)}


@family(code="fe.debug.long_component_bug", specialization="frontend", area="debug", level=4, fmt="bug",
        # имена × мутация × комментарий × пример (нижняя оценка: длина, размер страницы, номер, 5 значений)
        space_size=len(PAGINATE_NAMES) * len(PAGINATE_MUTATIONS) * 2 * 11 * 4 * 3 * 99**5, median_time_s=110)
def long_component_bug(rng: random.Random) -> Generated:
    fn, items, per, page = rng.choice(PAGINATE_NAMES)
    names = {"fn": fn, "items": items, "per": per, "page": page}
    line = rng.choice(sorted(PAGINATE_MUTATIONS))
    right, wrong = (t.format(**names) for t in PAGINATE_MUTATIONS[line])
    lines = [t.format(**names) for t in PAGINATE_TEMPLATE]
    lines[line - 1] = lines[line - 1].replace(right, wrong)
    comment = rng.random() < 0.5
    if comment:
        lines.insert(0, f"// {page} нумеруется с 1; hasNext — есть ли следующая страница")
    code = "\n".join(lines)
    while True:  # пример должен проявлять ошибку
        xs = rng.sample(range(1, 100), rng.randint(5, 15))
        size = rng.randint(2, 5)
        n = rng.randint(1, math.ceil(len(xs) / size))
        call = f"{fn}([{', '.join(map(str, xs))}], {size}, {n})"
        expected = _paginate_py(xs, size, n)
        if run_js_snippet(code + f"\nconsole.log(JSON.stringify({call}));") != json.dumps(expected, separators=(",", ":")):
            break
    shown = json.dumps(expected, separators=(", ", ": "))
    text = (f"Функция {fn} возвращает элементы страницы (нумерация с 1), число страниц и признак следующей "
            f"страницы. Пример: {call} должен вернуть {shown}, но результат другой. В какой строке ошибка?")
    return _line_answer(text, lines, line + comment, ("paginate_bug", len(PAGINATE_TEMPLATE)), language="javascript")


# --- fe.debug.profiler_hotspot -------------------------------------------------------------------------
PROFILER_COMPONENTS = ("Header", "ProductCard", "Sidebar", "PriceChart", "CommentList", "Footer", "SearchBar",
                       "Avatar", "CartBadge", "Filters")
PROFILER_COLUMNS = ("Компонент", "Рендеров", "Среднее время, мс", "Пропсы между рендерами")
STABLE, CHANGING = "не меняются", "меняются каждый раз"


def _profiler_rows(rng: random.Random) -> tuple[list[tuple], str]:
    """Четыре строки профайлера и компонент, который выгоднее всего мемоизировать.

    Ловушка (в большинстве заданий): больше всего суммарного времени — у компонента с меняющимися
    пропсами; memo ему не поможет."""
    trap = rng.random() < 0.6
    while True:
        names = rng.sample(PROFILER_COMPONENTS, 4)
        flags = [STABLE, STABLE, rng.choice((STABLE, CHANGING)), CHANGING]
        rng.shuffle(flags)
        rows = [(n, rng.randint(5, 400), round(rng.uniform(0.2, 20.0), 1), f) for n, f in zip(names, flags, strict=True)]
        total = {n: r * t for n, r, t, _ in rows}
        stable = sorted((n for n, *_, f in rows if f == STABLE), key=total.get, reverse=True)
        best = stable[0]
        if total[best] < 1.2 * total[stable[1]]:
            continue
        if (max(total, key=total.get) != best) == trap:
            return rows, best


@family(code="fe.debug.profiler_hotspot", specialization="frontend", area="debug", level=4, fmt="calc",
        # нижняя оценка: имена × флаги × числа рендеров и времена (только первые две строки)
        space_size=math.perm(len(PROFILER_COMPONENTS), 4) * 4 * (396 * 199) ** 2 // 1000, median_time_s=90)
def profiler_hotspot(rng: random.Random) -> Generated:
    rows, best = _profiler_rows(rng)
    text = ("Профайлер React записал сессию (таблица). Какой один компонент выгоднее всего обернуть в React.memo, "
            "чтобы сильнее всего сократить суммарное время рендеров?")
    return mcq(rng, text, best, [n for n, *_ in rows if n != best], tables=(Table("Профайлер", PROFILER_COLUMNS, tuple(rows)),),
               radicals=("profiler_memo", 4))


# --- fe.debug.fake_timers ------------------------------------------------------------------------------
TIMER_COMPONENTS = (("SearchBox", "onSearch"), ("AutoSave", "onSave"), ("FilterInput", "onFilter"),
                    ("AddressField", "onAddress"))
TIMER_QUERIES = ("кофе", "чай", "Москва", "отчёт", "заказ", "react")
TIMER_TITLES = ("вызывает колбэк после ввода", "сообщает о вводе", "отправляет значение")
TIMER_CORRECT = (
    "Колбэк сработает по таймеру через {d} мс, а проверка идёт сразу; нужны useFakeTimers и advanceTimersByTime({d})",
    "Проверка идёт раньше, чем истекут {d} мс; включить jest.useFakeTimers() и продвинуть время на {d} мс",
)
TIMER_WRONG = (
    "fireEvent.change не вызывает обработчик onChange у поля ввода; вместо него нужен userEvent.click по самому полю",
    "toHaveBeenCalledWith не работает с функциями из jest.fn(); нужно вручную сравнивать всё содержимое mock.calls",
    "debounce в принципе нельзя проверить в тестах Jest; его нужно убрать из компонента перед тестированием",
    "Перед fireEvent.change нужен await: иначе событие не успеет дойти до компонента",
)


@family(code="fe.debug.fake_timers", specialization="frontend", area="debug", level=4, fmt="mcq",
        space_size=len(TIMER_COMPONENTS) * 9 * len(TIMER_QUERIES) * len(TIMER_TITLES) * len(TIMER_CORRECT)
        * math.comb(len(TIMER_WRONG), 3) * 24, median_time_s=90)
def fake_timers(rng: random.Random) -> Generated:
    comp, cb = rng.choice(TIMER_COMPONENTS)
    delay, q = rng.randrange(200, 1001, 100), rng.choice(TIMER_QUERIES)
    code = "\n".join([f"test('{comp} {rng.choice(TIMER_TITLES)}', () => {{", f"  const {cb} = jest.fn();",
                      f"  render(<{comp} {cb}={{{cb}}} delay={{{delay}}} />);",
                      f"  fireEvent.change(screen.getByRole('textbox'), {{ target: {{ value: '{q}' }} }});",
                      f"  expect({cb}).toHaveBeenCalledWith('{q}');", "});"])
    text = (f"{comp} вызывает {cb} через debounce — спустя delay мс после последнего ввода. Тест падает с "
            f"сообщением, что {cb} не был вызван. Почему и как это исправить?")
    return mcq(rng, text, rng.choice(TIMER_CORRECT).format(d=delay), rng.sample(TIMER_WRONG, 3), code=code,
               language="jsx")


# --- fe.debug.ui_race_line -----------------------------------------------------------------------------
RACE_NAMES = (("latestQuery", "renderResults", "/api/search", "onSearchInput"),
              ("lastTerm", "showSuggestions", "/api/suggest", "handleInput"),
              ("currentText", "drawHits", "/api/find", "onType"),
              ("pendingQuery", "paintList", "/api/lookup", "onQuery"))


RACE_QUERIES = ("query", "text", "term")
RACE_RESPONSES = ("response", "res", "reply")
RACE_EVENTS = ("event", "e", "ev")
RACE_SPINNERS = ("showSpinner", "setLoading", "toggleLoader")


@family(code="fe.debug.ui_race_line", specialization="frontend", area="debug", level=5, fmt="bug",
        # имена × переменные запроса, ответа и события × индикатор × trim × проверка пустого × комментарий × limit
        space_size=len(RACE_NAMES) * len(RACE_QUERIES) * len(RACE_RESPONSES) * len(RACE_EVENTS) * len(RACE_SPINNERS)
        * 2 * 2 * 2 * 46, median_time_s=130)
def ui_race_line(rng: random.Random) -> Generated:
    latest, render_fn, url, handler = rng.choice(RACE_NAMES)
    q, resp, ev, spinner = (rng.choice(RACE_QUERIES), rng.choice(RACE_RESPONSES), rng.choice(RACE_EVENTS),
                            rng.choice(RACE_SPINNERS))
    trim = ".trim()" if rng.random() < 0.5 else ""
    lines = [f"let {latest} = '';", "", f"async function {handler}({ev}) {{", f"  const {q} = {ev}.target.value{trim};"]
    if rng.random() < 0.5:
        lines.append(f"  if (!{q}) return;")
    lines.append(f"  {latest} = {q};")
    if rng.random() < 0.5:
        lines.append("  // показываем индикатор загрузки")
    lines += [f"  {spinner}(true);", f"  const {resp} = await fetch(`{url}?q=${{encodeURIComponent({q})}}"
              f"&limit={rng.randint(5, 50)}`);", f"  const results = await {resp}.json();"]
    key = len(lines) + 1
    lines += [f"  {render_fn}(results);", f"  {spinner}(false);", "}", "",
              f"searchInput.addEventListener('input', {handler});"]
    text = ("Пользователь быстро печатает запрос, а ответы сервера приходят в разном порядке. Иногда на экране "
            "остаются результаты для более раннего текста. В какой строке ошибка?")
    return _line_answer(text, lines, key, ("stale_response_race",), language="javascript")


# --- fe.debug.listener_leak ------------------------------------------------------------------------------
LISTENER_EVENTS = (("resize", "width", "setWidth", "window.innerWidth", "onResize", ""),
                   ("scroll", "offset", "setOffset", "window.scrollY", "onScroll", ""),
                   ("online", "online", "setOnline", "navigator.onLine", "onOnline", ""),
                   ("keydown", "lastKey", "setLastKey", "event.key", "onKeyDown", "event"))
LISTENER_COMPONENTS = ("SidePanel", "Toolbar", "StatusBar", "Hints", "Overlay")
LISTENER_CORRECT = (
    "Эффект подписывается на событие, но не отписывается: вернуть из эффекта очистку с removeEventListener",
    "Обработчик остаётся на window после размонтирования; эффект должен возвращать removeEventListener",
)
LISTENER_WRONG = (
    "React сам снимает обработчики window при размонтировании, поэтому утечку даёт useState, а вовсе не подписка",
    "Нужно перенести addEventListener прямо в тело компонента, чтобы подписка обновлялась на каждом рендере",
    "Достаточно обернуть обработчик в useCallback — тогда повторные подписки на это событие уже не создаются",
    "Пустой массив зависимостей запускает эффект на каждом рендере; в нём нужно указать [window]",
)
LISTENER_PLACES = (("выдвижной панели", "её"), ("модальном окне", "его"), ("отдельной вкладке", "её"),
                   ("всплывающей подсказке", "её"))  # место и местоимение в согласовании
LISTENER_CLASSES = ("hint", "status", "value", "meta", "info")


@family(code="fe.debug.listener_leak", specialization="frontend", area="debug", level=5, fmt="mcq",
        space_size=len(LISTENER_EVENTS) * len(LISTENER_COMPONENTS) * 3 * len(LISTENER_PLACES) * len(LISTENER_CLASSES)
        * len(LISTENER_CORRECT)
        * math.comb(len(LISTENER_WRONG), 3) * 24, median_time_s=120)
def listener_leak(rng: random.Random) -> Generated:
    event, var, setter, value, handler, param = rng.choice(LISTENER_EVENTS)
    comp = rng.choice(LISTENER_COMPONENTS)
    init = {"resize": "window.innerWidth", "scroll": "0", "online": "navigator.onLine", "keydown": "''"}[event]
    tag = rng.choice(("p", "span", "div"))
    code = "\n".join([f"function {comp}() {{", f"  const [{var}, {setter}] = useState({init});", "",
                      "  useEffect(() => {", f"    function {handler}({param}) {{", f"      {setter}({value});",
                      "    }", f"    window.addEventListener('{event}', {handler});", "  }, []);", "",
                      f'  return <{tag} className="{rng.choice(LISTENER_CLASSES)}">{{String({var})}}</{tag}>;', "}"])
    place, pronoun = rng.choice(LISTENER_PLACES)
    text = (f"Компонент {comp} показывается в {place}; пользователь часто открывает и закрывает {pronoun}. "
            f"Со временем {handler} срабатывает много раз на одно событие, а память страницы растёт. Почему и как "
            "это исправить?")
    return mcq(rng, text, rng.choice(LISTENER_CORRECT), rng.sample(LISTENER_WRONG, 3), code=code, language="jsx")

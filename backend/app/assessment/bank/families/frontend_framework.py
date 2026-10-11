"""Семейства Frontend · фреймворк и состояние (React).

Поведение React описано для production-сборки без StrictMode (в StrictMode эффекты и рендеры в разработке
вызываются дважды) и для React 18+ с автоматическим батчингом обновлений.
"""
import math
import random

from app.assessment.bank.base import Generated, Prompt, Table, family, mcq

FIRST_NAMES = ("Анна", "Олег", "Ирина", "Павел", "Мария", "Иван", "Ольга", "Пётр", "Елена", "Денис")
FEMALE = frozenset({"Анна", "Ирина", "Мария", "Ольга", "Елена"})
LAST_NAMES = ("Петров", "Смирнов", "Козлов", "Орлов", "Волков", "Зайцев", "Лебедев", "Соколов")
UI_LABELS = ("Поиск по каталогу", "Доставка и оплата", "Отзывы", "Ваша оценка", "Настройки профиля", "Тарифы")


def _person(rng: random.Random) -> tuple[str, str]:
    """Имя и фамилия в согласованном роде: «Анна Петрова», «Олег Петров»."""
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    return first, last + "а" if first in FEMALE else last

# --- fe.framework.props_vs_state --------------------------------------------------
PVS_OPTIONS = {
    "derive": "Вычислять при каждом рендере из props, в state не хранить",
    "state": "Хранить в useState этого компонента и менять в обработчиках",
    "copy": "Скопировать props в state через useState(props) при первом рендере",
    "sync": "Синхронизировать копию в state с props через useEffect",
    "module": "Объявить переменную модуля вне компонента и хранить её там",
}


def _usage_user(rng: random.Random) -> str:
    first, last = _person(rng)
    return f'<UserCard firstName="{first}" lastName="{last}" />'


def _usage_price(rng: random.Random) -> str:
    return f"<PriceTag price={{{rng.randrange(100, 10001, 10)}}} discount={{{rng.randrange(5, 51, 5)}}} />"


def _usage_cart(rng: random.Random) -> str:
    items = ", ".join(f"{{ id: {rng.randint(1, 999)}, price: {rng.randrange(50, 5001, 50)}, qty: {rng.randint(1, 5)} }}"
                      for _ in range(2))
    return f"<CartSummary items={{[{items}]}} />"


def _usage_initials(rng: random.Random) -> str:
    first, last = _person(rng)
    return f'<Avatar name="{first} {last}" size={{{rng.randrange(24, 97, 8)}}} />'


DERIVED_CONTEXTS = (  # (компонент, props, что показать, пример использования)
    ("UserCard", "firstName и lastName", "полное имя", _usage_user),
    ("PriceTag", "price и discount (в процентах)", "цену со скидкой", _usage_price),
    ("CartSummary", "items (позиции с ценой и количеством)", "итоговую сумму", _usage_cart),
    ("Avatar", "name", "инициалы", _usage_initials),
)


def _usage_internal(comp: str, rng: random.Random) -> str:
    return f'<{comp} id="{comp.lower()}-{rng.randint(1, 999)}" label="{rng.choice(UI_LABELS)}" />'


INTERNAL_CONTEXTS = (  # (компонент, что помнить)
    ("SearchBox", "текст, который пользователь вводит в поле поиска"),
    ("Accordion", "раскрыт ли раздел (меняется по клику на его заголовок)"),
    ("Tabs", "какая вкладка сейчас выбрана (переключается кликом)"),
    ("Rating", "сколько звёзд выбрал пользователь"),
)


@family(code="fe.framework.props_vs_state", specialization="frontend", area="framework", level=1, fmt="mcq",
        # нижняя оценка — ветвь «внутреннее состояние»: компонент × id × подпись × 3 из 4 дистракторов × порядок
        space_size=len(INTERNAL_CONTEXTS) * 999 * len(UI_LABELS) * math.comb(4, 3) * 24 // 2, median_time_s=35)
def props_vs_state(rng: random.Random) -> Generated:
    if rng.random() < 0.5:
        comp, props, derived, usage = rng.choice(DERIVED_CONTEXTS)
        text = (f"Компонент {comp} получает через props {props}. Нужно показать {derived} — значение, которое "
                "однозначно вычисляется из этих props. Как правильно поступить с этим значением?")
        code, correct = usage(rng), "derive"
    else:
        comp, what = rng.choice(INTERNAL_CONTEXTS)
        text = (f"Компонент {comp} должен помнить {what}. Родителю это значение не нужно, из props его не "
                "вычислить. Где его хранить?")
        code, correct = _usage_internal(comp, rng), "state"
    wrong = rng.sample(sorted(k for k in PVS_OPTIONS if k != correct), 3)
    return mcq(rng, text, PVS_OPTIONS[correct], [PVS_OPTIONS[k] for k in wrong], code=code, language="jsx",
               radicals=("props_vs_state", 4))


# --- fe.framework.list_keys ------------------------------------------------------------
LIST_ENTITIES = (("tasks", "task", "title"), ("contacts", "contact", "name"), ("products", "product", "name"),
                 ("cities", "city", "name"), ("songs", "song", "title"), ("rooms", "room", "label"),
                 ("books", "book", "title"), ("players", "player", "nickname"))
LIST_ACTIONS = ("сортирует список по алфавиту", "удаляет первую строку", "добавляет новую строку в начало списка",
                "перетаскивает последнюю строку наверх")
LIST_FIELDS = ("note", "comment", "amount", "price")
INDEX_NAMES = ("index", "i", "idx")
LIST_KEYS_CORRECT = (
    "Ключ — индекс: React сопоставляет строки по позиции, состояние полей остаётся на месте; нужен key из id",
    "Индекс меняется при перестановке, и DOM-узлы с их состоянием достаются другим строкам; нужен key из id",
)
LIST_KEYS_WRONG = (
    "key влияет только на скорость рендера, а не на поведение списка; нужно обернуть каждую строку в React.memo",
    "Ключи должны меняться при каждом рендере; нужен key={Math.random()}, чтобы React заново создавал все строки "
    "списка",
    "React не поддерживает defaultValue внутри списков; нужно заменить input на textarea с тем же значением",
    "Порядок нарушает метод map; нужно перебирать элементы обычным циклом for и складывать готовые строки в "
    "массив",
)


@family(code="fe.framework.list_keys", specialization="frontend", area="framework", level=1, fmt="mcq",
        space_size=len(LIST_ENTITIES) * len(LIST_ACTIONS) * len(LIST_FIELDS) * len(INDEX_NAMES)
        * len(LIST_KEYS_CORRECT) * math.comb(len(LIST_KEYS_WRONG), 3) * 24, median_time_s=40)
def list_keys(rng: random.Random) -> Generated:
    items, item, title = rng.choice(LIST_ENTITIES)
    field, idx = rng.choice(LIST_FIELDS), rng.choice(INDEX_NAMES)
    code = "\n".join([f"{items}.map(({item}, {idx}) => (", f"  <li key={{{idx}}}>",
                      f"    {{{item}.{title}}} <input defaultValue={{{item}.{field}}} />", "  </li>", "))"])
    text = (f"Список выводится так, как в коде. Пользователь вписывает значения в поля нескольких строк, затем "
            f"{rng.choice(LIST_ACTIONS)}. Введённые значения оказываются не у тех строк. В чём причина и как "
            "исправить?")
    return mcq(rng, text, rng.choice(LIST_KEYS_CORRECT), rng.sample(LIST_KEYS_WRONG, 3), code=code, language="jsx")


# --- fe.framework.stale_setstate_count ----------------------------------------------------
STATE_NAMES = (("count", "setCount"), ("clicks", "setClicks"), ("score", "setScore"), ("likes", "setLikes"),
               ("total", "setTotal"), ("points", "setPoints"))
COMPONENTS = ("Counter", "LikeButton", "ScoreBoard", "Clicker", "Stepper", "Tally")


def _state_component(comp: str, var: str, setter: str, start: int, calls: list[str]) -> str:
    return "\n".join([f"function {comp}() {{", f"  const [{var}, {setter}] = useState({start});", "",
                      "  function handleClick() {", *(f"    {c};" for c in calls), "  }", "",
                      f"  return <button onClick={{handleClick}}>{{{var}}}</button>;", "}"])


@family(code="fe.framework.stale_setstate_count", specialization="frontend", area="framework", level=2,
        fmt="calc", median_time_s=50,
        # нижняя оценка: компонент × имена × начальное значение × два вызова с приращениями 1..5
        space_size=len(COMPONENTS) * len(STATE_NAMES) * 51 * 5**2)
def stale_setstate_count(rng: random.Random) -> Generated:
    comp = rng.choice(COMPONENTS)
    var, setter = rng.choice(STATE_NAMES)
    while True:
        start = rng.randint(0, 50)
        deltas = [rng.randint(1, 5) for _ in range(rng.randint(2, 5))]
        answer = start + deltas[-1]  # все вызовы видят одно значение из замыкания — остаётся последний
        if answer not in {start, *deltas}:
            break
    code = _state_component(comp, var, setter, start, [f"{setter}({var} + {d})" for d in deltas])
    text = f"Пользователь один раз нажал кнопку. Какое значение {var} будет показано после следующего рендера?"
    return Generated("number", Prompt(text=text, code=code, language="jsx", answer_hint="Целое число"),
                     answer, ("stale_closure_setstate",))


# --- fe.framework.functional_update_count -------------------------------------------------
PREV_NAMES = ("c", "prev", "n", "x")


@family(code="fe.framework.functional_update_count", specialization="frontend", area="framework", level=2,
        fmt="calc", median_time_s=50,
        space_size=len(COMPONENTS) * len(STATE_NAMES) * len(PREV_NAMES) * 51 * 5**2)
def functional_update_count(rng: random.Random) -> Generated:
    comp = rng.choice(COMPONENTS)
    var, setter = rng.choice(STATE_NAMES)
    p = rng.choice(PREV_NAMES)
    while True:
        start = rng.randint(0, 50)
        deltas = [rng.randint(1, 5) for _ in range(rng.randint(2, 5))]
        answer = start + sum(deltas)  # функциональное обновление получает результат предыдущего
        if answer not in {start, *deltas}:
            break
    code = _state_component(comp, var, setter, start, [f"{setter}(({p}) => {p} + {d})" for d in deltas])
    text = f"Пользователь один раз нажал кнопку. Какое значение {var} будет показано после следующего рендера?"
    return Generated("number", Prompt(text=text, code=code, language="jsx", answer_hint="Целое число"),
                     answer, ("functional_update",))


# --- fe.framework.controlled_input ----------------------------------------------------------
INPUT_STATES = (("name", "setName"), ("query", "setQuery"), ("email", "setEmail"), ("city", "setCity"),
                ("title", "setTitle"), ("login", "setLogin"))
INPUT_COMPONENTS = ("NameField", "SearchInput", "EmailForm", "CityPicker", "TitleEditor", "LoginForm")
INPUT_INITIALS = ("Анна", "Москва", "черновик", "user", "заказ", "отчёт", "test", "привет")
INPUT_TYPED = ("abc", "123", "да", "xyz", "ок", "777")
CONTROLLED_CORRECT = "«{init}» — текст не изменится: value без onChange не даёт редактировать поле"
CONTROLLED_WRONG = (
    "«{init}{typed}» — текст допишется в поле, но состояние {var} не обновится",
    "«{typed}» — поле очистится и покажет только набранное",
    "«{init}{typed}» — текст допишется, а React сам обновит состояние {var} по атрибуту value",
    "Пустое поле — React сбросит value при первом же нажатии, потому что у поля нет обработчика onChange",
)


@family(code="fe.framework.controlled_input", specialization="frontend", area="framework", level=2, fmt="mcq",
        space_size=len(INPUT_COMPONENTS) * len(INPUT_STATES) * len(INPUT_INITIALS) * len(INPUT_TYPED)
        * math.comb(len(CONTROLLED_WRONG), 3) * 24, median_time_s=45)
def controlled_input(rng: random.Random) -> Generated:
    comp = rng.choice(INPUT_COMPONENTS)
    var, setter = rng.choice(INPUT_STATES)
    init, typed = rng.choice(INPUT_INITIALS), rng.choice(INPUT_TYPED)
    code = "\n".join([f"function {comp}() {{", f"  const [{var}, {setter}] = useState('{init}');",
                      f"  return <input value={{{var}}} />;", "}"])
    fields = {"init": init, "typed": typed, "var": var}
    return mcq(rng, f"Пользователь ставит курсор в конец поля и набирает «{typed}». Что он увидит в поле?",
               CONTROLLED_CORRECT.format(**fields), [w.format(**fields) for w in rng.sample(CONTROLLED_WRONG, 3)],
               code=code, language="jsx")


# --- fe.framework.effect_runs ---------------------------------------------------------------
EFFECT_PROPS = (  # (компонент, проп a и его значения, проп b и его значения)
    ("Profile", "userId", (1, 2, 3, 7), "tab", ("info", "posts", "likes")),
    ("Results", "query", ("js", "css", "react"), "page", (1, 2, 3)),
    ("ChatRoom", "roomId", ("general", "random", "help"), "muted", ("true", "false")),
    ("Chart", "range", ("day", "week", "month"), "theme", ("light", "dark")),
)
# какие зависимости у эффекта: None — массива нет (эффект после каждого рендера)
EFFECT_DEPS = {"a": 3, "b": 2, "ab": 2, "[]": 1, "none": 1}


def _effect_rows(rng: random.Random, va: tuple, vb: tuple) -> list[tuple]:
    rows = [(1, rng.choice(va), rng.choice(vb))]
    for n in range(2, rng.randint(4, 7) + 1):
        a, b = rows[-1][1], rows[-1][2]
        change = rng.choice(("a", "b", "both", "none", "a", "b"))
        if change in ("a", "both"):
            a = rng.choice([v for v in va if v != a])
        if change in ("b", "both"):
            b = rng.choice([v for v in vb if v != b])
        rows.append((n, a, b))
    return rows


@family(code="fe.framework.effect_runs", specialization="frontend", area="framework", level=3, fmt="calc",
        # нижняя оценка: компонент × зависимости × четыре рендера, у каждого из трёх обновлений ≥ 4 исхода
        space_size=len(EFFECT_PROPS) * len(EFFECT_DEPS) * 6 * 4**3 * 4, median_time_s=80)
def effect_runs(rng: random.Random) -> Generated:
    comp, a, va, b, vb = rng.choice(EFFECT_PROPS)
    deps_kind = rng.choices(tuple(EFFECT_DEPS), weights=tuple(EFFECT_DEPS.values()))[0]
    deps = {"a": [a], "b": [b], "ab": [a, b], "[]": [], "none": None}[deps_kind]
    rows = _effect_rows(rng, va, vb)
    runs = 1 + sum(deps is None or any(prev[i] != cur[i] for i, d in ((1, a), (2, b)) if d in deps)
                   for prev, cur in zip(rows, rows[1:], strict=False))
    close = "  });" if deps is None else f"  }}, [{', '.join(deps)}]);"
    code = "\n".join([f"function {comp}({{ {a}, {b} }}) {{", "  useEffect(() => {",
                      f"    console.log('effect', {a}, {b});", close, "  return null;", "}"])
    text = ("Компонент отрендерился несколько раз подряд с props из таблицы (первый рендер — монтирование, "
            "размонтирования не было). Сколько раз выполнится функция эффекта? Production-сборка, без StrictMode.")
    table = Table("Рендеры", ("рендер", a, b), tuple(rows))
    return Generated("number", Prompt(text=text, code=code, language="jsx", tables=(table,),
                                      answer_hint="Целое число"), runs, ("effect_deps",))


def _numbered(lines: list[str]) -> str:
    return "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, start=1))


def _line_answer(text: str, lines: list[str], key: int, radicals: tuple) -> Generated:
    """Задание «найди строку»: код в prompt.code, нумерация — в подсказке формата ответа (как в Backend)."""
    return Generated("line", Prompt(text=text, code="\n".join(lines), language="jsx",
                                    answer_hint=f"Номер строки:\n{_numbered(lines)}"), key, radicals)


# --- fe.framework.stale_interval_line -------------------------------------------------------
INTERVAL_COMPONENTS = (("Timer", "seconds", "setSeconds", "Прошло секунд"), ("Clock", "ticks", "setTicks", "Тиков"),
                       ("Poller", "polls", "setPolls", "Опросов"), ("Stopwatch", "elapsed", "setElapsed", "Прошло"),
                       ("Progress", "percent", "setPercent", "Готово, %"), ("Pulse", "beats", "setBeats", "Ударов"))
INTERVAL_MS = (100, 200, 250, 500, 1000, 1500, 2000)
INTERVAL_EXTRAS = ("none", "ref", "comment", "ref+comment", "title_effect")
INTERVAL_IDS = ("id", "timer", "handle", "intervalId")
INTERVAL_STARTS = range(0, 21)


@family(code="fe.framework.stale_interval_line", specialization="frontend", area="framework", level=3, fmt="bug",
        # компонент × период × шаг × начальное значение × имя интервала × вариант окружения (5 + 4 с другим return)
        space_size=len(INTERVAL_COMPONENTS) * len(INTERVAL_MS) * 9 * len(INTERVAL_STARTS) * len(INTERVAL_IDS) * 9,
        median_time_s=80)
def stale_interval_line(rng: random.Random) -> Generated:
    comp, var, setter, label = rng.choice(INTERVAL_COMPONENTS)
    ms, step = rng.choice(INTERVAL_MS), rng.randint(1, 9)
    extra = rng.choice(INTERVAL_EXTRAS)
    ref, tid = "ref" in extra, rng.choice(INTERVAL_IDS)
    head = [f"function {comp}() {{", f"  const [{var}, {setter}] = useState({rng.choice(INTERVAL_STARTS)});"]
    if ref:
        head.append("  const boxRef = useRef(null);")
    head.append("")
    if extra == "title_effect":  # эффект, который читает значение правильно (зависимость указана)
        head += ["  useEffect(() => {", f"    document.title = `{label}: ${{{var}}}`;", f"  }}, [{var}]);"]
    if "comment" in extra:
        head.append(f"  // обновление раз в {ms} мс")
    body = ["  useEffect(() => {", f"    const {tid} = setInterval(() => {{", f"      {setter}({var} + {step});",
            f"    }}, {ms});", f"    return () => clearInterval({tid});", "  }, []);", ""]
    tail = [f"  return <p{' ref={boxRef}' if ref else ''}>{label}: {{{var}}}</p>;", "}"]
    if rng.random() < 0.5 and extra != "title_effect":
        tail = [f"  const text = `{label}: ${{{var}}}`;", f"  return <p{' ref={boxRef}' if ref else ''}>{{text}}</p>;",
                "}"]
    lines = head + body + tail
    key = len(head) + 3
    text = (f"Значение {var} должно расти на {step} каждые {ms} мс, а интервал — создаваться один раз, при "
            "монтировании компонента. На практике значение увеличивается один раз и дальше не меняется. "
            "В какой строке ошибка?")
    return _line_answer(text, lines, key, ("stale_interval_closure",))


# --- fe.framework.lift_state -----------------------------------------------------------------
LIFT_CONTEXTS = (  # (родитель, где сейчас состояние, кому оно тоже нужно, что это, переменная, сеттер, значения, JSX)
    ("ProductsPage", "SearchBar", "ProductList", "текст фильтра", "filter", "setFilter",
     ("''", "'чай'", "'кофе'", "'сок'", "'хлеб'"), "<input value={{filter}} onChange={{(e) => setFilter(e.target.value)}} />"),
    ("Planner", "Calendar", "EventList", "выбранная дата", "date", "setDate",
     ("'2026-10-01'", "'2026-10-15'", "'2026-11-02'", "'2026-12-31'"), "<DatePicker value={{date}} onSelect={{setDate}} />"),
    ("MusicApp", "Player", "Playlist", "текущий трек", "trackId", "setTrackId",
     ("1", "3", "7", "12", "null"), "<Controls trackId={{trackId}} onNext={{() => setTrackId(trackId + 1)}} />"),
    ("Settings", "Tabs", "TabPanel", "активная вкладка", "tab", "setTab",
     ("'general'", "'privacy'", "'sound'", "'account'"), "<TabList active={{tab}} onChange={{setTab}} />"),
    ("Shop", "CartButton", "CartBadge", "число товаров в корзине", "count", "setCount",
     ("0", "1", "2", "5"), "<button onClick={{() => setCount(count + 1)}}>В корзину</button>"),
    ("Converter", "CelsiusInput", "FahrenheitView", "температура", "celsius", "setCelsius",
     ("0", "20", "36.6", "100"), "<input value={{celsius}} onChange={{(e) => setCelsius(e.target.value)}} />"),
)
HEADER_TITLES = ("Главная", "Каталог", "Профиль", "Отчёты", "Настройки", "Корзина", "Помощь", "Новости")
FOOTER_YEARS = range(2020, 2027)
LIFT_CORRECT = ("Поднять состояние в {parent} и передать его в {holder} и {consumer} через props",
                "Поднять useState в общего родителя {parent}, детям передавать значение и сеттер")
LIFT_WRONG = (
    "Хранить копию значения в {consumer} и синхронизировать её с {holder} через useEffect",
    "Записывать значение из {holder} в глобальную переменную window и читать её в {consumer}",
    "Читать значение в {consumer} через ref на DOM-узел, который рендерит {holder}",
    "Вызывать функцию {holder}() прямо внутри {consumer}, чтобы получить её состояние",
)


@family(code="fe.framework.lift_state", specialization="frontend", area="framework", level=3, fmt="mcq",
        space_size=sum(len(c[6]) for c in LIFT_CONTEXTS) * len(HEADER_TITLES) * len(FOOTER_YEARS) * len(LIFT_CORRECT)
        * math.comb(len(LIFT_WRONG), 3) * 24, median_time_s=70)
def lift_state(rng: random.Random) -> Generated:
    parent, holder, consumer, what, var, setter, inits, jsx = rng.choice(LIFT_CONTEXTS)
    code = "\n".join([f"function {holder}() {{", f"  const [{var}, {setter}] = useState({rng.choice(inits)});",
                      f"  return {jsx.format()};", "}", "", f"function {consumer}() {{",
                      f"  // здесь тоже нужно {var}", "  return null;", "}", "", f"function {parent}() {{", "  return (",
                      "    <>", f'      <Header title="{rng.choice(HEADER_TITLES)}" />', f"      <{holder} />",
                      f"      <{consumer} />", f"      <Footer year={{{rng.choice(FOOTER_YEARS)}}} />", "    </>", "  );",
                      "}"])
    text = (f"Внутри {parent} рядом стоят {holder} и {consumer}. Сейчас {what} хранится в состоянии {holder}, а "
            f"{consumer} тоже должен получать это значение и обновляться вместе с ним. Как правильно организовать "
            "данные?")
    names = {"parent": parent, "holder": holder, "consumer": consumer}
    return mcq(rng, text, rng.choice(LIFT_CORRECT).format(**names),
               [w.format(**names) for w in rng.sample(LIFT_WRONG, 3)], code=code, language="jsx")


# --- fe.framework.memo_rerenders --------------------------------------------------------------
MEMO_COLORS = ("red", "blue", "green", "gray", "teal")
MEMO_WORDS = ("Заказы", "Погода", "Итоги", "Новости", "Задачи", "Профиль")
MEMO_PARENTS = ("Dashboard", "Page", "App", "Layout", "Screen")
MEMO_CHILDREN = (  # (компонент, проп, литерал — новый объект/массив/функция на каждом рендере родителя)
    ("Badge", "style", lambda rng, setter: f"{{ color: '{rng.choice(MEMO_COLORS)}' }}"),
    ("Avatar", "user", lambda rng, setter: f"{{ name: '{rng.choice(FIRST_NAMES)}' }}"),
    ("Tags", "items", lambda rng, setter: f"['{rng.choice(MEMO_COLORS)}', '{rng.choice(MEMO_WORDS)}']"),
    ("ResetButton", "onReset", lambda rng, setter: f"() => {setter}(0)"),
)


@family(code="fe.framework.memo_rerenders", specialization="frontend", area="framework", level=4, fmt="calc",
        # родитель × состояние × заголовок × число нажатий × ребёнок (нижняя оценка значений литерала) × порядок
        space_size=len(MEMO_PARENTS) * len(STATE_NAMES) * len(MEMO_WORDS) * 16 * 4 * 5 * 6, median_time_s=100)
def memo_rerenders(rng: random.Random) -> Generated:
    child, prop, literal = rng.choice(MEMO_CHILDREN)
    var, setter = rng.choice(STATE_NAMES)
    parent, clicks = rng.choice(MEMO_PARENTS), rng.randint(5, 20)  # 5–20: «N раз» согласуется для всех N
    jsx = [f'      <Title text="{rng.choice(MEMO_WORDS)}" />',
           f"      <button onClick={{() => {setter}({var} + 1)}}>{{{var}}}</button>",
           f"      <{child} {prop}={{{literal(rng, setter)}}} />"]
    rng.shuffle(jsx)
    code = "\n".join([
        f"const {child} = React.memo(function {child}({{ {prop} }}) {{", f"  console.log('render {child}');",
        "  return null;", "});", "", "const Title = React.memo(function Title({ text }) {",
        "  console.log('render Title');", "  return <h2>{text}</h2>;", "});", "",
        f"function {parent}() {{", f"  const [{var}, {setter}] = useState(0);", "  return (", "    <>", *jsx,
        "    </>", "  );", "}",
    ])
    text = (f"Пользователь нажал кнопку {clicks} раз. Сколько раз всего в консоль выведется «render {child}», "
            "включая первый рендер? Production-сборка, без StrictMode.")
    return Generated("number", Prompt(text=text, code=code, language="jsx", answer_hint="Целое число"),
                     clicks + 1, ("memo_new_literal_prop",))


# --- fe.framework.effect_cleanup_order -------------------------------------------------------
EFFECT_ENTITIES = (  # (компонент, проп, значения, действие эффекта, действие очистки, вызовы в коде)
    ("ChatRoom", "roomId", ("general", "random", "help", "news", "dev", "music"),
     "подключение к комнате {x}", "отключение от комнаты {x}", ("connect", "disconnect")),
    ("Ticker", "symbol", ("SBER", "GAZP", "YDEX", "LKOH", "MGNT", "TCSG"),
     "подписка на котировки {x}", "отписка от котировок {x}", ("subscribe", "unsubscribe")),
    ("MapView", "city", ("Омск", "Тула", "Казань", "Пермь", "Сочи", "Тверь"),
     "загрузка карты города {x}", "освобождение карты города {x}", ("loadMap", "disposeMap")),
    ("Player", "trackId", ("7", "12", "31", "45", "88", "93"),
     "запуск трека {x}", "остановка трека {x}", ("play", "stop")),
)


def _shuffled_order(rng: random.Random, steps: list[str]) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """Показ шагов в перемешанном порядке (не совпадающем с правильным) и ключ — номера показанных шагов."""
    order = list(range(len(steps)))
    while order == sorted(order):
        rng.shuffle(order)
    shown = tuple(steps[i] for i in order)
    return shown, tuple(order.index(i) + 1 for i in range(len(steps)))


@family(code="fe.framework.effect_cleanup_order", specialization="frontend", area="framework", level=4,
        fmt="order", median_time_s=110,
        space_size=len(EFFECT_ENTITIES) * math.perm(6, 2) * 2 * (math.factorial(6) - 1))
def effect_cleanup_order(rng: random.Random) -> Generated:
    comp, prop, values, effect, cleanup, (on, off) = rng.choice(EFFECT_ENTITIES)
    x1, x2 = rng.sample(values, 2)
    eff = lambda x: f"Эффект: {effect.format(x=x)}"  # noqa: E731
    cln = lambda x: f"Очистка: {cleanup.format(x=x)}"  # noqa: E731
    if rng.random() < 0.5:
        scenario = f"затем перерисовывается с {prop} = {x2} и после этого размонтируется"
        steps = [f"Рендер с {prop} = {x1}", eff(x1), f"Рендер с {prop} = {x2}", cln(x1), eff(x2),
                 f"Очистка при размонтировании: {cleanup.format(x=x2)}"]
    else:
        scenario = (f"затем перерисовывается ещё раз с тем же {prop}, а затем с {prop} = {x2}, после чего остаётся "
                    "на экране")
        steps = [f"Рендер с {prop} = {x1}", eff(x1), f"Повторный рендер с тем же {prop} = {x1}",
                 f"Рендер с {prop} = {x2}", cln(x1), eff(x2)]
    shown, answer = _shuffled_order(rng, steps)
    code = "\n".join([f"function {comp}({{ {prop} }}) {{", "  useEffect(() => {", f"    {on}({prop});",
                      f"    return () => {off}({prop});", f"  }}, [{prop}]);", f"  return <div>{{{prop}}}</div>;", "}"])
    text = (f"Компонент {comp} монтируется с {prop} = {x1}, {scenario}. Расположите события в том порядке, в "
            "котором они произойдут. Production-сборка, без StrictMode.")
    return Generated("order", Prompt(text=text, code=code, language="jsx", steps=shown,
                                     answer_hint="Номера всех шагов через пробел, например: 2 1 3 …"),
                     answer, ("effect_lifecycle", 6))


# --- fe.framework.fetch_race_line ------------------------------------------------------------
FETCH_CONTEXTS = (  # (компонент, проп, состояние, сеттер, адрес, компонент показа, что переключают)
    ("Profile", "userId", "profile", "setProfile", "/api/users/", "ProfileCard", "профили пользователей"),
    ("OrderDetails", "orderId", "order", "setOrder", "/api/orders/", "OrderView", "заказы в списке"),
    ("Weather", "city", "forecast", "setForecast", "/api/weather?city=", "ForecastTable", "города"),
    ("ProductPage", "productId", "product", "setProduct", "/api/products/", "ProductInfo", "товары"),
    ("Search", "query", "results", "setResults", "/api/search?q=", "ResultList", "поисковые запросы"),
)
CANCEL_FLAGS = ("cancelled", "ignore", "stale", "outdated")
DATA_NAMES = ("data", "json", "payload", "body")
RES_NAMES = ("res", "response", "r")
VIEW_PROPS = ("data", "value", "item")
FETCH_COMMENTS = ("  // загрузка данных при смене {prop}", "  // запрос к API при каждом новом {prop}",
                  "  // подгружаем данные для текущего {prop}")


@family(code="fe.framework.fetch_race_line", specialization="frontend", area="framework", level=4, fmt="bug",
        # контекст × флаг × имена параметров × версия API × проп показа × (пустая строка, комментарий или нет,
        # проверка пустого значения, форма очистки)
        space_size=len(FETCH_CONTEXTS) * len(CANCEL_FLAGS) * len(DATA_NAMES) * len(RES_NAMES) * 3 * len(VIEW_PROPS)
        * 2 * (1 + len(FETCH_COMMENTS)) * 2 * 2, median_time_s=110)
def fetch_race_line(rng: random.Random) -> Generated:
    comp, prop, var, setter, url, view, what = rng.choice(FETCH_CONTEXTS)
    flag, data, res = rng.choice(CANCEL_FLAGS), rng.choice(DATA_NAMES), rng.choice(RES_NAMES)
    url = url.replace("/api/", f"/api/v{rng.randint(1, 3)}/")
    lines = [f"function {comp}({{ {prop} }}) {{", f"  const [{var}, {setter}] = useState(null);"]
    if rng.random() < 0.5:
        lines.append("")
    if rng.random() < 0.75:
        lines.append(rng.choice(FETCH_COMMENTS).format(prop=prop))
    lines.append("  useEffect(() => {")
    if rng.random() < 0.5:
        lines.append(f"    if (!{prop}) return;")
    lines += [f"    let {flag} = false;", f"    fetch(`{url}${{{prop}}}`)", f"      .then(({res}) => {res}.json())",
              f"      .then(({data}) => {{"]
    key = len(lines) + 1
    lines += [f"        {setter}({data});", "      });"]
    one_line_cleanup = rng.random() < 0.5
    lines += ([f"    return () => {{ {flag} = true; }};"] if one_line_cleanup
              else ["    return () => {", f"      {flag} = true;", "    };"])
    lines += [f"  }}, [{prop}]);", *([""] if one_line_cleanup else []),  # компонент не длиннее 18 строк
              f"  return <{view} {rng.choice(VIEW_PROPS)}={{{var}}} />;", "}"]
    text = (f"Пользователь быстро переключает {what}: {prop} меняется несколько раз подряд, а ответы сервера "
            f"приходят в разном порядке. Иногда на экране остаются данные для предыдущего значения {prop}. "
            "В какой строке ошибка?")
    return _line_answer(text, lines, key, ("fetch_race",))


# --- fe.framework.context_rerender ------------------------------------------------------------
CONTEXT_SETS = (  # (контекст, редкое значение, начальные, частое значение, его действие, потребитель редкого)
    ("AppContext", "theme", ("'light'", "'dark'", "'sepia'"), "cart", "addToCart", "ThemedButton"),
    ("UiContext", "locale", ("'ru'", "'en'", "'kk'"), "notifications", "pushNotification", "LocalizedLabel"),
    ("SessionContext", "user", ("null", "guest", "demoUser"), "messages", "addMessage", "UserBadge"),
    ("SettingsContext", "fontSize", ("14", "16", "18"), "ticks", "addTick", "TextBlock"),
)
CONTEXT_LABELS = ("Купить", "Сохранить", "Отмена", "Далее", "Назад", "Открыть")
CONTEXT_CORRECT = (
    "value — новый объект на каждом изменении, все потребители перерисовываются; разделить контекст, value "
    "мемоизировать",
    "Любая смена value перерисовывает всех, кто читает контекст; вынести редко меняющееся значение в свой "
    "контекст",
)
CONTEXT_WRONG = (
    "Обернуть {consumer} в React.memo: memo не даст контексту перерисовать компонент, если его props при этом "
    "не менялись",
    "Причина в отсутствии key у компонентов {consumer}; каждому нужно задать стабильный key из данных списка",
    "useContext перерисовывает компонент при любом рендере родителя; читать значение нужно из localStorage",
    "Перенести Provider внутрь каждого {consumer}, чтобы у каждого компонента было своё отдельное значение "
    "контекста",
)


@family(code="fe.framework.context_rerender", specialization="frontend", area="framework", level=5, fmt="mcq",
        # набор × начальное значение × порядок четырёх полей value × подпись × формулировка × дистракторы × порядок
        space_size=len(CONTEXT_SETS) * 3 * 24 * len(CONTEXT_LABELS) * len(CONTEXT_CORRECT)
        * math.comb(len(CONTEXT_WRONG), 3) * 24, median_time_s=140)
def context_rerender(rng: random.Random) -> Generated:
    ctx, rare, inits, often, action, consumer = rng.choice(CONTEXT_SETS)
    set_rare = "set" + rare[0].upper() + rare[1:]
    set_often = "set" + often[0].upper() + often[1:]
    fields = [rare, set_rare, often, action]
    rng.shuffle(fields)
    code = "\n".join([
        f"const {ctx} = createContext(null);", "", "function AppProvider({ children }) {",
        f"  const [{rare}, {set_rare}] = useState({rng.choice(inits)});",
        f"  const [{often}, {set_often}] = useState([]);",
        f"  const {action} = (item) => {set_often}([...{often}, item]);", "  return (",
        f"    <{ctx}.Provider value={{{{ {', '.join(fields)} }}}}>", "      {children}", f"    </{ctx}.Provider>",
        "  );", "}", "", f"function {consumer}({{ label }}) {{", f"  const {{ {rare} }} = useContext({ctx});",
        f"  return <span data-{rare.lower()}={{{rare}}}>{{label}}</span>;", "}", "",
        f'// на странице сотни <{consumer} label="{rng.choice(CONTEXT_LABELS)}" /> и других',
    ])
    text = (f"Профилирование показывает: при каждом вызове {action} перерисовываются все {consumer}, хотя {rare} не "
            "меняется. В чём причина и как это исправить?")
    names = {"consumer": consumer}
    return mcq(rng, text, rng.choice(CONTEXT_CORRECT).format(**names),
               [w.format(**names) for w in rng.sample(CONTEXT_WRONG, 3)], code=code, language="jsx")


# --- fe.framework.hydration_mismatch ------------------------------------------------------------
HYDRATION_SOURCES = (  # (строки до return, JSX) — значение в рендере разное на сервере и в браузере
    (("  const now = Date.now();",), "<p className=\"{cls}\">{label}: {{now}}</p>"),
    (("  const id = Math.random().toString(36).slice(2);",),
     "<>\n      <label htmlFor={{id}}>{label}</label>\n      <input id={{id}} className=\"{cls}\" />\n    </>"),
    (("  const time = new Date().toLocaleTimeString();",), "<span className=\"{cls}\">{label}: {{time}}</span>"),
    (("  const wide = typeof window !== 'undefined' && window.innerWidth > 768;",),
     "<div className=\"{cls}\">{{wide ? <Sidebar /> : null}}{label}</div>"),
)
HYDRATION_COMPONENTS = ("Header", "OrderInfo", "Clock", "SearchForm", "Banner", "Footer")
HYDRATION_LABELS = ("Обновлено", "Время", "Поиск", "Статус", "Сейчас", "Заказ", "Email", "Город")
HYDRATION_CLASSES = ("title", "meta", "field", "status", "info")
HYDRATION_CORRECT = (
    "Рендер на сервере и в браузере даёт разный результат; значение вычислять в useEffect после монтирования",
    "Значение в рендере разное на сервере и на клиенте; брать его из данных сервера или считать в useEffect",
)
HYDRATION_WRONG = (
    "Гидратация не поддерживает функциональные компоненты; компонент нужно переписать на класс с render()",
    "Причина в StrictMode, который рендерит компонент дважды; предупреждение пропадёт, если отключить StrictMode",
    "Компонент нужно обернуть в React.memo — тогда на клиенте он не будет рендериться повторно при гидратации",
    "У корневого элемента нет key; нужно добавить key, чтобы React сопоставил разметку сервера и клиента",
)


@family(code="fe.framework.hydration_mismatch", specialization="frontend", area="framework", level=5, fmt="mcq",
        space_size=len(HYDRATION_SOURCES) * len(HYDRATION_COMPONENTS) * len(HYDRATION_LABELS) * len(HYDRATION_CLASSES)
        * len(HYDRATION_CORRECT) * math.comb(len(HYDRATION_WRONG), 3) * 24, median_time_s=130)
def hydration_mismatch(rng: random.Random) -> Generated:
    pre, jsx = rng.choice(HYDRATION_SOURCES)
    comp = rng.choice(HYDRATION_COMPONENTS)
    body = jsx.format(label=rng.choice(HYDRATION_LABELS), cls=rng.choice(HYDRATION_CLASSES))
    code = "\n".join([f"function {comp}() {{", *pre, f"  return {body};" if "\n" not in body
                      else f"  return (\n    {body}\n  );", "}"])
    text = ("Компонент рендерится на сервере (SSR) и затем гидратируется в браузере. В консоли браузера — "
            "предупреждение о несовпадении разметки сервера и клиента (hydration mismatch). В чём причина и как "
            "исправить?")
    return mcq(rng, text, rng.choice(HYDRATION_CORRECT), rng.sample(HYDRATION_WRONG, 3), code=code, language="jsx")

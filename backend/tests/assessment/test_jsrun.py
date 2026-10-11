# backend/tests/assessment/test_jsrun.py
import pytest

from app.assessment.bank.jsrun import JsError, run_js_snippet


def test_event_loop_order_matches_browser():
    code = """
    console.log('start');
    setTimeout(() => console.log('t0'), 0);
    Promise.resolve().then(() => { console.log('m1'); setTimeout(() => console.log('t-in-m'), 0) });
    setTimeout(() => { console.log('t10'); Promise.resolve().then(() => console.log('m-in-t')) }, 10);
    console.log('end');
    """
    assert run_js_snippet(code).split("\n") == ["start", "end", "m1", "t0", "t-in-m", "t10", "m-in-t"]


def test_values_formatting():
    assert run_js_snippet("console.log(typeof null, [1,2], '5' + 3, '5' - 3)") == 'object [1,2] 53 2'


def test_primitives_print_like_a_browser_console():
    """undefined, NaN, Infinity и BigInt печатаются как в консоли браузера, а не как JSON (пусто / null)."""
    out = run_js_snippet("console.log(undefined, NaN, 'a' - 1, 1 / 0, 10n, true, null, 'x')")
    assert out == "undefined NaN NaN Infinity 10n true null x"


def test_async_await_resumes_as_microtask():
    code = """
    async function f() { console.log('f1'); await null; console.log('f2'); }
    setTimeout(() => console.log('t'), 0);
    f();
    Promise.resolve().then(() => console.log('p'));
    console.log('s');
    """
    assert run_js_snippet(code).split("\n") == ["f1", "s", "f2", "p", "t"]


def test_infinite_loop_is_interrupted():
    with pytest.raises(JsError):
        run_js_snippet("while (true) {}", timeout_ms=200)


def test_exception_surfaces():
    with pytest.raises(JsError):
        run_js_snippet("null.x")



def test_timers_fire_by_absolute_time():
    """Таймер, поставленный внутри другого, срабатывает по моменту «сейчас + задержка», как в браузере."""
    code = """
    setTimeout(() => { console.log('A'); setTimeout(() => console.log('C'), 5); }, 8);
    setTimeout(() => console.log('B'), 10);
    """
    assert run_js_snippet(code).split("\n") == ["A", "B", "C"]  # A в 8, B в 10, C в 13

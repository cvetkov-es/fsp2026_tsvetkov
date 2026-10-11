"""Исполнение НАШЕГО шаблонного JS (генераторы банка) в QuickJS.

Код кандидата здесь никогда не исполняется. Таймеры эмулируются виртуальными часами: после
синхронного кода опустошается очередь микрозадач, затем таймеры по (момент срабатывания = «сейчас» +
задержка, порядок постановки), после каждого — снова микрозадачи. Этого достаточно для заданий про
event loop (setInterval и время исполнения кода не моделируются).
"""
import quickjs

# console.log печатает примитивы как консоль браузера (undefined, NaN, 10n), объекты и массивы — JSON
_PRELUDE = """
var __out = [];
function __fmt(x) {
  if (typeof x === 'string') return x;
  if (typeof x === 'bigint') return String(x) + 'n';
  if (x === null || typeof x === 'object') return JSON.stringify(x);
  return String(x);
}
var console = { log: (...a) => __out.push(a.map(__fmt).join(' ')) };
var __timers = []; var __seq = 0; var __now = 0;
function setTimeout(fn, ms) { __timers.push({ fn: fn, at: __now + (ms || 0), seq: __seq++ }); return __seq; }
function __nextTimer() {
  if (!__timers.length) return false;
  __timers.sort((a, b) => a.at - b.at || a.seq - b.seq);
  var t = __timers.shift(); __now = t.at; t.fn(); return true;
}
"""


class JsError(Exception):
    pass


def _drain(ctx) -> None:
    while ctx.execute_pending_job():
        pass


def run_js_snippet(code: str, timeout_ms: int = 1000) -> str:
    ctx = quickjs.Context()
    ctx.set_time_limit(timeout_ms / 1000)
    ctx.set_memory_limit(32 * 1024 * 1024)
    try:
        ctx.eval(_PRELUDE)
        ctx.eval(code)
        _drain(ctx)
        for _ in range(1000):
            if not ctx.eval("__nextTimer()"):
                break
            _drain(ctx)
        return ctx.eval("__out.join('\\n')")
    except quickjs.JSException as e:
        raise JsError(str(e)) from e

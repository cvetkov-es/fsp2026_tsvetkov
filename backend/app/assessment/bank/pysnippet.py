"""Исполнение НАШЕГО шаблонного Python-кода для вычисления ключа «что выведет код».

Код кандидата здесь никогда не исполняется: на вход приходят только строки из генераторов банка.
"""
import io

_SAFE_BUILTINS = {
    "print": print, "len": len, "range": range, "sum": sum, "sorted": sorted, "min": min,
    "max": max, "list": list, "dict": dict, "set": set, "tuple": tuple, "str": str, "int": int,
    "enumerate": enumerate, "zip": zip, "reversed": reversed, "abs": abs,
    "hash": hash, "__build_class__": __build_class__, "__name__": "snippet",  # для class-сниппетов
}


def run_python_snippet(code: str) -> str:
    # Свой print в свой буфер: redirect_stdout подменяет sys.stdout на весь процесс,
    # и при генерации из нескольких потоков вывод попадал в чужой буфер (неверные ключи)
    buf = io.StringIO()

    def _print(*args, sep=" ", end="\n"):
        print(*args, sep=sep, end=end, file=buf)

    builtins = {**_SAFE_BUILTINS, "print": _print}
    exec(compile(code, "<snippet>", "exec"), {"__builtins__": builtins}, {})  # noqa: S102
    return buf.getvalue().rstrip("\n")

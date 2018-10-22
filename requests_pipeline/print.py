import json
from objectify_json import ObjectifyJSON
from .colors import *
from .terminal import TTY_COLUMNS
from .thread_local import ThreadLocalData

THREAD = ThreadLocalData()


def print_thread(*args, **kwargs):
    THREAD.print(*args, **kwargs)


def print_row(char: str):
    print_thread(char * TTY_COLUMNS)


def println_any(data, name=None):
    if isinstance(data, ObjectifyJSON):
        data = data._data
    if not data:
        return

    if name:
        print_thread(cyan(name))

    def _default(o):
        rv = repr(o)
        if isinstance(rv, str):
            try:
                return json.loads(rv)
            except:
                pass
            try:
                return eval(rv)
            except:
                pass
        return rv

    if isinstance(data, (list, tuple, dict)):
        print_thread(
            json.dumps(data, indent=2, ensure_ascii=False, default=_default))
    else:
        print_thread(data)


def print_inline(name, data, color=cyan):
    if isinstance(data, ObjectifyJSON):
        data = data._data
    if isinstance(data, str) and not data:
        return
    print_thread("{}: {}".format(color(name), data))

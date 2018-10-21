import threading
from collections import defaultdict
from io import StringIO


def setdefaultattr(obj, name, value):
    if not hasattr(obj, name):
        setattr(obj, name, value)
    return getattr(obj, name)


class ThreadLocalData:
    def __init__(self):
        self.threads_data = defaultdict(threading.local)

    @property
    def thread_local(self):
        thread_id = threading.get_ident()
        local = self.threads_data[thread_id]
        return local

    def del_thread_local(self):
        thread_id = threading.get_ident()
        self.threads_data.pop(thread_id, None)

    def setdefault(self, name, value):
        return setdefaultattr(self.thread_local, name, value)

    def get_property(self, name):
        rv = getattr(self.thread_local, name)
        if not rv:
            raise Exception("{} has not been set".format(name))
        return rv

    @property
    def stdout(self):
        return self.setdefault("__stdout", StringIO())

    @property
    def stderr(self):
        return self.setdefault("__stderr", StringIO())

    def get_stdout_value(self):
        return self.stdout.getvalue()

    def get_stderr_value(self):
        return self.stderr.getvalue()

    def print(self, *args, **kwargs):
        print(*args, file=self.stdout, **kwargs)

    def log(self, *args, **kwargs):
        print(*args, file=self.stderr, **kwargs)

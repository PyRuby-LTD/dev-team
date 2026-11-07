"""What every backlog read and write shares: the strict YAML loader, item IDs and the write lock."""
from contextlib import contextmanager
import fcntl
import os
import re
import threading

import yaml


class InvalidRecord(ValueError):
    pass


class StrictLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise InvalidRecord("mapping keys must be strings")
            if key in result:
                raise InvalidRecord(f"duplicate key {key!r}; keep one value")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


ID = re.compile(r"[A-Z][A-Z0-9]*-[A-Za-z0-9][A-Za-z0-9_-]*\Z")

# The terminal UI and the harness write from different threads.
WRITE = threading.RLock()
HELD_LOCKS = threading.local()


@contextmanager
def mutation(root):
    """Take the process lock before WRITE; reuse it for nested calls on this thread."""
    held = getattr(HELD_LOCKS, "roots", None)
    if held is None:
        held = HELD_LOCKS.roots = set()
    key = (os.getpid(), root)
    if key in held:
        with WRITE:
            yield
        return
    lock = root / "log" / "backlog.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        held.add(key)
        try:
            with WRITE:
                yield
        finally:
            held.remove(key)
            fcntl.flock(handle, fcntl.LOCK_UN)


def valid_id(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None

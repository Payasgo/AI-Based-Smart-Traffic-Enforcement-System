"""Cross-instance/process lock for the shared evidence CSV."""
import os
import threading
from contextlib import contextmanager
from pathlib import Path

_LOCAL_LOCKS = {}
_LOCAL_GUARD = threading.Lock()
_STATE = threading.local()


def _thread_lock(path):
    key = str(Path(path).resolve()).casefold()
    with _LOCAL_GUARD:
        return key, _LOCAL_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def evidence_file_lock(csv_path):
    key, local = _thread_lock(str(Path(csv_path).resolve()) + ".lock")
    with local:
        depths = getattr(_STATE, "depths", {})
        depth = depths.get(key, 0)
        if depth:
            depths[key] = depth + 1
            _STATE.depths = depths
            try:
                yield
            finally:
                depths[key] -= 1
            return

        lock_path = key
        Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                unlock = lambda: (handle.seek(0), msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1))
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            depths[key] = 1
            _STATE.depths = depths
            try:
                yield
            finally:
                depths.pop(key, None)
                unlock()
        finally:
            handle.close()

"""Cross-instance/process lock for a shared evidence CSV.

Uses an OS file lock so the dashboard review process and camera worker
threads/processes cannot overwrite or append the CSV simultaneously.
"""
import os
import threading
from contextlib import contextmanager
from pathlib import Path

_LOCAL_LOCKS = {}
_LOCAL_GUARD = threading.Lock()


def _thread_lock(path):
    key = str(Path(path).resolve()).casefold()
    with _LOCAL_GUARD:
        return _LOCAL_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def evidence_file_lock(csv_path):
    lock_path = str(Path(csv_path).resolve()) + ".lock"
    local = _thread_lock(lock_path)
    with local:
        handle = open(lock_path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

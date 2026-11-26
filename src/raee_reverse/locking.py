"""Cross-process exclusive lock. In-process threads also take Store's RLock."""

from __future__ import annotations

import os
from pathlib import Path


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = open(path, "a+b")
        self._fh.seek(0, os.SEEK_END)
        if self._fh.tell() == 0:
            self._fh.write(b"\0")
            self._fh.flush()

    def acquire(self) -> None:
        if os.name == "nt":
            _win_file_lock(self._fh, lock=True)
        else:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)

    def release(self) -> None:
        if os.name == "nt":
            _win_file_lock(self._fh, lock=False)
        else:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)

    def close(self) -> None:
        self._fh.close()


def _win_file_lock(fh, *, lock: bool) -> None:
    """Wait for one byte at the start of the file, then return.

    ``msvcrt.LK_LOCK`` does not wait that way. If the byte is busy it sleeps
    a full second and tries again. Store readers now take this lock, including
    the worker's ``get_task`` before a one-second sleeper. That collision makes
    the parent's next claim wait one second, so the second dev task starts only
    after the first has finished. ``LockFileEx`` without ``LOCKFILE_FAIL_IMMEDIATELY``
    returns as soon as the previous holder unlocks.
    """
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_void_p),
            ("InternalHigh", ctypes.c_void_p),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    kernel32.LockFileEx.restype = wintypes.BOOL
    kernel32.UnlockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    kernel32.UnlockFileEx.restype = wintypes.BOOL
    handle = wintypes.HANDLE(msvcrt.get_osfhandle(fh.fileno()))
    overlapped = _Overlapped()
    exclusive = 0x00000002
    if lock:
        ok = kernel32.LockFileEx(handle, exclusive, 0, 1, 0, ctypes.byref(overlapped))
        failed = "LockFileEx"
    else:
        ok = kernel32.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(overlapped))
        failed = "UnlockFileEx"
    if not ok:
        err = ctypes.get_last_error()
        raise OSError(err, f"{failed} failed")

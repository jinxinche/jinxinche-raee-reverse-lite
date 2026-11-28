"""Install a seccomp filter, optionally set rlimits, then exec the target.

The filter returns EPERM from socket() unless the domain is AF_UNIX. It is not
installed on failure, and this process does not exec in that case. A missing
filter is not network isolation.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import platform
import sys
from ctypes import c_int, c_uint8, c_uint16, c_uint32, c_ulong

PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
SECCOMP_RET_ALLOW = 0x7FFF0000
SECCOMP_RET_ERRNO = 0x00050000
EPERM = 1
BPF_LD = 0x00
BPF_W = 0x00
BPF_ABS = 0x20
BPF_JMP = 0x05
BPF_JEQ = 0x10
BPF_K = 0x00
BPF_RET = 0x06
AF_UNIX = 1

# (audit arch, socket syscall number). A wrong number fails open in the probe:
# the connect succeeds and that mechanism is not confirmed.
_ARCH = {
    "x86_64": (0xC000003E, 41),
    "amd64": (0xC000003E, 41),
    "aarch64": (0xC00000B7, 198),
    "arm64": (0xC00000B7, 198),
}


class _Filter(ctypes.Structure):
    _fields_ = [
        ("code", c_uint16),
        ("jt", c_uint8),
        ("jf", c_uint8),
        ("k", c_uint32),
    ]


class _Program(ctypes.Structure):
    _fields_ = [("len", c_uint16), ("filter", ctypes.POINTER(_Filter))]


def _instruction(code: int, k: int, jt: int = 0, jf: int = 0) -> _Filter:
    return _Filter(code, jt, jf, k)


def socket_filter():
    """BPF program for this machine, or None when no profile exists."""
    profile = _ARCH.get(platform.machine().lower())
    if profile is None or sys.platform != "linux":
        return None
    audit_arch, sys_socket = profile
    # 0 arch, 1 jeq arch, 2 deny wrong arch, 3 nr, 4 jeq socket,
    # 5 arg0, 6 jeq AF_UNIX, 7 deny, 8 allow.
    rows = [
        _instruction(BPF_LD | BPF_W | BPF_ABS, 4),
        _instruction(BPF_JMP | BPF_JEQ | BPF_K, audit_arch, jt=1, jf=0),
        _instruction(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        _instruction(BPF_LD | BPF_W | BPF_ABS, 0),
        _instruction(BPF_JMP | BPF_JEQ | BPF_K, sys_socket, jt=0, jf=3),
        _instruction(BPF_LD | BPF_W | BPF_ABS, 16),
        _instruction(BPF_JMP | BPF_JEQ | BPF_K, AF_UNIX, jt=1, jf=0),
        _instruction(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        _instruction(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    ]
    array = (_Filter * len(rows))(*rows)
    program = _Program(len(rows), array)
    program._keep = array
    return program


def install_socket_filter() -> tuple[bool, str]:
    program = socket_filter()
    if program is None:
        return False, f"no seccomp profile for {sys.platform} {platform.machine()}"
    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        return False, "libc was not found"
    libc = ctypes.CDLL(libc_name, use_errno=True)
    libc.prctl.argtypes = [c_int, c_ulong, c_ulong, c_ulong, c_ulong]
    libc.prctl.restype = c_int
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        return False, f"PR_SET_NO_NEW_PRIVS failed errno {ctypes.get_errno()}"
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.addressof(program), 0, 0) != 0:
        return False, f"PR_SET_SECCOMP failed errno {ctypes.get_errno()}"
    return True, ""


def apply_rlimits(spec_json: str) -> None:
    import resource

    spec = json.loads(spec_json)
    names = {
        "cpu": "RLIMIT_CPU",
        "fsize": "RLIMIT_FSIZE",
        "as": "RLIMIT_AS",
        "nofile": "RLIMIT_NOFILE",
        "nproc": "RLIMIT_NPROC",
    }
    for key, value in spec.items():
        limit = getattr(resource, names.get(key, ""), None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, (int(value), int(value)))
        except (OSError, ValueError):
            continue


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--" not in args:
        sys.stderr.write("isolation_exec: missing --\n")
        return 2
    target = args[args.index("--") + 1 :]
    if not target or not target[0]:
        sys.stderr.write("isolation_exec: missing target\n")
        return 2
    if os.environ.get("RRL_RLIMITS"):
        apply_rlimits(os.environ["RRL_RLIMITS"])
    if os.environ.get("RRL_SECCOMP", "1") != "0":
        installed, detail = install_socket_filter()
        if not installed:
            sys.stderr.write("seccomp filter was not installed: " + detail + "\n")
            return 3
    try:
        os.execv(target[0], target)
    except OSError as exc:
        sys.stderr.write(f"exec failed: {exc}\n")
        return 4
    return 4


if __name__ == "__main__":
    raise SystemExit(main())

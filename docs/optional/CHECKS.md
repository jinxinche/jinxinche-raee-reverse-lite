# Optional checks

These three checks were run on this tree. Earlier phase evidence files were not edited. `unshare -n` remains the probe recorded in Phase 0. This run's connect probe is separate and is the only basis for `network_isolated`.

## Network isolation

Host: Linux x86_64, Python 3.12.3.
`network_isolated` is true. `network_namespace` is true. `accepted_pass` is false.
Baseline connect: ok. Probe reason: connect failed inside unshare-rn.
`unshare -n` available: false.
`unshare -n` detail: unshare: unshare failed: Operation not permitted
Attempt `unshare-rn`: confirmed. namespace=true.
Attempt `bwrap-unshare-net`: not_tried. namespace=false.
Attempt `seccomp-prctl`: not_tried. namespace=false.
Sandboxed target stdout:

```
STARTED
CONNECT_FAIL 101
```

Record: `docs/evidence/network_isolation.json`. Mechanism field: `unshare-rn`.

## Backup static engine

r2pipe version: 2.1.0. radare2 on PATH: true. rizin on PATH: false.
Selected binary: `radare2`. angr selected: false. angr installed: false.
rizin apt-cache policy:

```
apt-cache policy rizin exited 0 with empty output; apt-cache show exited 100: E: No packages found
```

Ghidra was executed in this run: false. Source: `docs/evidence/zlib_phase2.json`. Export sha256: `06dae92957e9a8267de9acce7835e47ff3d359f1eba300cea9d197ee8027db4d`.
Pinned minigzip sha256: `e5990e7d1b34bcbb8d7f9aff732887ba90d63c0e5d3e92f58a0156f5e7cec636`. Rebuilt minigzip sha256: `e5990e7d1b34bcbb8d7f9aff732887ba90d63c0e5d3e92f58a0156f5e7cec636`. `same_binary` is true.
`parity_executed` is true. `identical` is False. `accepted_pass` is false.
Every normalized disagreement is listed in `docs/evidence/engine_parity_zlib.json`. Counts: only_ghidra=7, only_backup=6, entry_disagreements=162, entry_matches=0.
Names only in the Ghidra export: _ITM_deregisterTMCloneTable, _ITM_registerTMCloneTable, __cxa_finalize, __gmon_start__, __libc_start_main, _start, frame_dummy
Names only in the backup list: entry.init0, entry0, fcn.00001210, file_compress.cold, gz_compress.cold, main.cold
Program entry disagreement: `{"ghidra": 1054672, "backup": 6096, "missing": false}`.
The 132 single-address entry disagreements differ by ghidra_minus_backup=1048576. After subtracting that constant, identical is False, entry_matches=132, remaining entry_disagreements=30.
Backup program entry matches the ELF header: True. Analysis commands: ['aa', 'aflj', 'iej'].

## Radare2 6.0.7 function names

Upstream `radare2 6.0.7 1 @ linux-x86-64` analyzed the pinned minigzip with `aa`. `main_recovered` is true. Names that contain main: sym.main.cold, main. Functions named main: main.
`offset` is in the first aflj entry: false. `addr` is in the first aflj entry: true. The addr type is `int`.
The parser kept a function only when offset was an int. Radare2 6.0.7 aflj stores the address in addr and omits offset, so every function, including main, was dropped and the test saw no name ending in main.
The Ubuntu 26.04 package `radare2 6.0.7+ds-1` was executed here: false. the resolute amd64v3 package requires GLIBC_2.42 and did not start on this host.
`accepted_pass` is false. Record: `docs/evidence/radare2_607_main.json`.

## Compiler gzip bytes

gcc: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0. clang: Ubuntu clang version 18.1.3 (1ubuntu1).
Requested CFLAGS for both trees: `-O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN`.
`same_flags` is True. `identical` is True. `accepted_pass` is false.
gcc configure_exit=0 make_exit=0 minigzip sha256 `e5990e7d1b34bcbb8d7f9aff732887ba90d63c0e5d3e92f58a0156f5e7cec636` makefile CFLAGS `-O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN`.
gcc compile line: `gcc -O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN  -c -o crc32.o crc32.c`
gcc Makefile CFLAGS is not the make override. Configure appended flags that were already in the environment. The compile line is the command that ran.
clang configure_exit=0 make_exit=0 minigzip sha256 `a5aade18660eac8fb188725126aad33ba2bec58e5bbee0841aa06b06384db87c` makefile CFLAGS `-O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN`.
clang compile line: `clang -O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN  -c -o crc32.o crc32.c`
clang Makefile CFLAGS is not the make override. Configure appended flags that were already in the environment. The compile line is the command that ran.
Per-input gzip sha256:

- empty: equal=true gcc `59869db34853933b239f1e2219cf7d431da006aa919635478511fabbfc8849d2` clang `59869db34853933b239f1e2219cf7d431da006aa919635478511fabbfc8849d2` first_mismatch_offset=None
- abc: equal=true gcc `a058a4f3405f909f3a49df0cb75d96198d371ae7913e5ef6b8114a382746ee5a` clang `a058a4f3405f909f3a49df0cb75d96198d371ae7913e5ef6b8114a382746ee5a` first_mismatch_offset=None
- hello: equal=true gcc `f901eda57fd86d4239806fd4b76f64036c1c20711267a7bc776ab2aa45069b2a` clang `f901eda57fd86d4239806fd4b76f64036c1c20711267a7bc776ab2aa45069b2a` first_mismatch_offset=None
- range4096: equal=true gcc `69c95331538d28682cd5e646c37fb1530c7385609624f0b87cd9226cde4098dc` clang `69c95331538d28682cd5e646c37fb1530c7385609624f0b87cd9226cde4098dc` first_mismatch_offset=None

Record: `docs/evidence/compiler_gzip_bytes.json`.


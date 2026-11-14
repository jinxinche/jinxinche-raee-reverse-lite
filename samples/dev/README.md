# Synthetic dev sample

`checksum_cli.c` is a development sample written for this repository. It is not the frozen real target. The real target remains zlib 1.4 `minigzip`, chosen in `docs/phase0/TARGETS.md` and not yet built or optimised.

Build:

```bash
gcc -O0 -g -o checksum_cli checksum_cli.c
```

`abc` on stdin prints `count=3 sum=294`. `--fail` prints the same line and exits 3. That exit is a behavior failure, not an infrastructure error.

# GitHub Actions for 0a74bedfd7e60db03cc89d95765a800e688703a5

Both workflow runs for this commit completed with every job successful. This does not erase the failure of `12735f05`.

| Run | Event | URL | Conclusion |
| --- | --- | --- | --- |
| 43586941928 | push | https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43586941928 | success |
| 43586944166 | pull_request | https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43586944166 | success |

All six jobs succeeded in each run: `ubuntu-latest`, `windows-latest`, and `macos-latest`, each on Python 3.11 and 3.15. Each job installed the package and ran `python -m pytest` plus the collection-floor check.

The macOS Python 3.15 jobs were the last to finish (setup-python took longer). Their conclusion is success, not a skip.

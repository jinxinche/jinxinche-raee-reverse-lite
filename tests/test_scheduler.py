import os
import signal
import subprocess
import sys
import time

from raee_reverse.scheduler import Scheduler
from raee_reverse.store import Store


def _submit(store, task_id, handler, **kwargs):
    return store.submit_task(
        task_id=task_id,
        handler=handler,
        deps=kwargs.get("deps", []),
        owner="test",
        inputs_version="test",
        timeout_seconds=kwargs.get("timeout", 5),
        max_attempts=kwargs.get("attempts", 1),
        resource_class=kwargs.get("resource_class", "dev"),
    )


def test_dependencies_retries_cancel_and_exclusivity(store):
    _submit(store, "first", "ok")
    _submit(store, "second", "ok", deps=["first"])
    assert store.get_task("second")["state"] == "BLOCKED"
    report = Scheduler(store).run(max_workers=2)
    tasks = {task["id"]: task for task in report["tasks"]}
    assert tasks["first"]["schedule_succeeded"] is True
    assert tasks["second"]["schedule_succeeded"] is True
    assert tasks["second"]["evidence_accepted_pass"] is False

    _submit(store, "bad", "deterministic_fail", attempts=3)
    _submit(store, "after-bad", "ok", deps=["bad"])
    Scheduler(store).run(max_workers=2)
    assert store.get_task("bad")["state"] == "FAILED"
    assert store.get_task("bad")["failure_class"] == "deterministic"
    assert store.get_task("bad")["attempts"] == 1
    assert store.get_task("after-bad")["state"] == "BLOCKED"
    assert store.get_task("after-bad")["blocked_reason"] == "dependency_not_succeeded"
    assert store.get_task("after-bad")["schedule_succeeded"] is False

    _submit(store, "flaky", "infra_then_ok", attempts=2)
    Scheduler(store).run(max_workers=1)
    flaky = store.get_task("flaky")
    assert flaky["schedule_succeeded"] is True
    assert flaky["attempts"] == 2
    assert flaky["checkpoint"]["tried"] is True
    assert any(event["event_type"] == "task_transition" for event in store.list_events())

    _submit(store, "slow", "spin_until_cancel", timeout=5)
    holder = {}

    def _run():
        holder["report"] = Scheduler(store).run(max_workers=1)

    import threading

    thread = threading.Thread(target=_run)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline and store.get_task("slow")["state"] != "RUNNING":
        time.sleep(0.02)
    assert store.request_cancel("slow") in {"RUNNING", "CANCELLED"}
    thread.join(timeout=10)
    assert store.get_task("slow")["state"] == "CANCELLED"
    assert store.get_task("slow")["schedule_succeeded"] is False


def test_task_reads_stay_consistent_beside_a_writer(store):
    """A task read must not share the connection with an open write.

    One sqlite connection is used by every thread. Overlapping statements are
    SQLITE_MISUSE. This loop fails on that code with InterfaceError, a missing
    task, or a row whose JSON columns are None.
    """
    import threading

    _submit(store, "t", "ok")
    errors = []

    def writer():
        for n in range(200):
            try:
                store.set_checkpoint("t", {"n": n})
            except Exception as exc:
                errors.append(exc)

    def reader():
        for _ in range(200):
            try:
                task = store.get_task("t")
                if task["id"] != "t" or not isinstance(task["deps"], list):
                    errors.append(AssertionError("torn task row"))
                if not any(item["id"] == "t" for item in store.list_tasks()):
                    errors.append(AssertionError("task missing from list"))
            except Exception as exc:
                errors.append(exc)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert store.get_task("t")["checkpoint"]["n"] == 199


def test_perf_task_does_not_share_a_batch(store):
    _submit(store, "measure", "ok", resource_class="perf")
    _submit(store, "dev", "ok")
    report = Scheduler(store).run(max_workers=4)
    assert report["actual_concurrency"] == 1
    assert report["batches"] >= 2
    measure = store.get_task("measure")
    dev = store.get_task("dev")
    assert measure["schedule_succeeded"] and dev["schedule_succeeded"]
    order = sorted(
        [(measure["started_at"], measure["ended_at"]), (dev["started_at"], dev["ended_at"])]
    )
    assert order[0][1] <= order[1][0]


def test_dev_tasks_can_overlap(store):
    _submit(store, "a", "sleeper", timeout=10)
    _submit(store, "b", "sleeper", timeout=10)
    report = Scheduler(store).run(max_workers=2)
    assert report["actual_concurrency"] == 2
    starts = []
    ends = []
    for task_id in ("a", "b"):
        artifact = store.get_task(task_id)["artifact"]
        starts.append(artifact["started"])
        ends.append(artifact["ended"])
    assert min(ends) > max(starts)


def test_timeout_is_infra_and_not_success(store):
    _submit(store, "late", "sleep_long", timeout=0.4, attempts=1)
    Scheduler(store).run(max_workers=1)
    task = store.get_task("late")
    assert task["state"] == "FAILED"
    assert task["failure_class"] == "infra"
    assert task["exit_status"] == "timeout"
    assert task["schedule_succeeded"] is False
    assert task["evidence_accepted_pass"] is False


def test_kill_and_recover_does_not_mark_success(tmp_path):
    store = Store(tmp_path / "ledger")
    try:
        _submit(store, "crash", "checkpoint_and_wait", timeout=30, attempts=2)
        store.begin_attempt("crash")
        if os.name != "posix":
            actions = store.recover_running()
            assert actions[0]["to"] == "QUEUED"
            assert store.get_task("crash")["schedule_succeeded"] is False
            assert store.get_task("crash")["evidence_accepted_pass"] is False
            store.verify_integrity()
            return

        env = os.environ.copy()
        root = str(store.root)
        proc = subprocess.Popen(
            [sys.executable, "-m", "raee_reverse.taskproc", "--root", root, "--task", "crash"],
            cwd=root,
            env=env,
            start_new_session=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            if (store.get_task("crash").get("checkpoint") or {}).get("phase") == "waiting":
                break
            time.sleep(0.05)
        assert store.get_task("crash")["checkpoint"]["phase"] == "waiting"
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
        assert store.get_task("crash")["state"] == "RUNNING"
        actions = store.recover_running()
        assert actions[0]["to"] == "QUEUED"
        assert actions[0]["accepted_pass"] is False
        recovered = store.get_task("crash")
        assert recovered["state"] == "QUEUED"
        assert recovered["schedule_succeeded"] is False
        assert recovered["checkpoint"]["phase"] == "waiting"
        store.verify_integrity()
    finally:
        store.close()

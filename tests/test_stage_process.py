"""process.py: start/alive/kill9/tail/reattach against a dummy `python -c "sleep"` child.
No `uv run`, no real act — a fast, disposable stand-in, isolated under tmp_path."""

import sys
import time

import pytest

from lipica import runstate
from lipica.stage import process


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(runstate, "RUN_DIR", tmp_path / "run")
    return tmp_path


def _sleeper(seconds: float = 20) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def test_start_writes_pid_and_log_under_run_dir_nb(scratch):
    d = process.start("t1", _sleeper())
    try:
        assert d.alive()
        assert (scratch / "run" / "nb" / "t1.pid").read_text().strip() == str(d.pid)
        assert (scratch / "run" / "nb" / "t1.log").exists()
    finally:
        d.kill9()


def test_kill9_actually_kills_the_process_and_confirms_it(scratch):
    d = process.start("t2", _sleeper())
    assert d.alive()
    assert process.reattach("t2") is not None

    assert d.kill9(timeout=5) is True
    assert d.alive() is False
    assert process.reattach("t2") is None  # the pid file is cleared once confirmed dead


def test_kill9_on_an_already_dead_process_is_a_harmless_true(scratch):
    d = process.start("t3", [sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 5
    while d.alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert d.kill9(timeout=2) is True


def test_alive_alone_detects_a_normal_exit_without_kill9(scratch):
    """A process that finishes on its own (a CLI command completing, a queue running out — the common
    case in every notebook's live panel, never routed through `kill9()`) stays a zombie until *something*
    reaps it: `alive()` must do that itself, or it reports `True` forever."""
    d = process.start("t3b", [sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 5
    while d.alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert d.alive() is False


def test_reattach_finds_a_worker_started_in_a_previous_handle(scratch):
    started = process.start("t4", _sleeper())
    try:
        found = process.reattach("t4")
        assert found is not None
        assert found.pid == started.pid
        assert found.alive()
    finally:
        started.kill9()


def test_reattach_with_no_pid_file_is_none(scratch):
    assert process.reattach("never-started") is None


def test_tail_returns_the_workers_own_output(scratch):
    d = process.start("t5", [sys.executable, "-c", "print('hello from worker')"])
    deadline = time.monotonic() + 5
    while d.alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert "hello from worker" in d.tail()


def test_tail_of_a_worker_with_no_output_yet_is_empty_not_an_error(scratch):
    d = process.start("t6", _sleeper())
    try:
        assert d.tail() == ""
    finally:
        d.kill9()


def test_env_overrides_reach_the_child(scratch):
    d = process.start(
        "t7",
        [sys.executable, "-c", "import os; print(os.environ.get('LIPICA_TEST_MARKER'))"],
        env={"LIPICA_TEST_MARKER": "here"},
    )
    deadline = time.monotonic() + 5
    while d.alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert "here" in d.tail()

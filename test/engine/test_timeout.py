"""Tests of amac.engine.timeout: time_limited decorator."""

import threading
import time

import pytest

from amac.engine.profile import Program
from amac.engine.timeout import time_limited
from amac.instance import Instance
from amac.utils.exception import ExecuteTimeout


class Worker:
    """Minimal object with what time_limited needs: name and program."""

    name = "worker"

    def __init__(self, timeout=None):
        self.program = Program(name=self.name, timeout=timeout)

    @time_limited
    def collect(self, instance, seconds=0.0):
        time.sleep(seconds)
        return "done"

    @time_limited
    def calculate(self, instance):
        raise RuntimeError("failed")


@pytest.fixture
def instance(tmp_path):
    return Instance.factory_instance(workdir=tmp_path)


def test_no_timeout_runs_and_records(instance):
    """Without timeout, the method runs and its duration is recorded."""
    assert Worker().collect(instance, 0.01) == "done"
    assert instance.duree.steps["collect"] >= 0.01


def test_timeout_not_reached(instance):
    """A method shorter than the timeout returns normally."""
    assert Worker(timeout=5).collect(instance) == "done"


def test_timeout_exceeded(instance):
    """A method longer than the timeout raises ExecuteTimeout."""
    with pytest.raises(ExecuteTimeout, match="worker: collect exceeded 0.1 s"):
        Worker(timeout=0.1).collect(instance, 2.0)
    assert "collect" in instance.duree.steps


def test_duration_recorded_on_error(instance):
    """The duration is recorded even if the method fails."""
    with pytest.raises(RuntimeError, match="failed"):
        Worker().calculate(instance)
    assert "calculate" in instance.duree.steps


def test_timeout_ignored_outside_main_thread(instance):
    """Outside the main thread, the timeout is ignored with a warning."""
    outcome = {}

    def run():
        with pytest.warns(RuntimeWarning, match="timeout ignored"):
            outcome["value"] = Worker(timeout=0.05).collect(instance, 0.1)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    assert outcome["value"] == "done"

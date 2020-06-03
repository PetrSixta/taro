"""
Tests :mod:`runner` module
"""
import time
from threading import Thread

import pytest

import taro.runner as runner
from taro import persistence
from taro.execution import ExecutionState as ExSt, ExecutionError
from taro.runner import RunnerJobInstance
from taro.test.execution import TestExecution  # TODO package import


@pytest.fixture(autouse=True)
def disable_persistence():
    persistence.disable()


def test_executed():
    execution = TestExecution()
    assert execution.executed_count() == 0

    runner.run('j', execution)
    assert execution.executed_count() == 1


def test_state_changes():
    instance = runner.run('j', TestExecution())
    assert instance.lifecycle.state() == ExSt.COMPLETED
    assert instance.lifecycle.states() == [ExSt.CREATED, ExSt.RUNNING, ExSt.COMPLETED]


def test_state_created():
    instance = RunnerJobInstance('j', TestExecution())
    assert instance.lifecycle.state() == ExSt.CREATED


def test_pending():
    instance = RunnerJobInstance('j', TestExecution())
    latch = instance.create_latch(ExSt.PENDING)
    t = Thread(target=instance.run)
    t.start()

    wait_for_pending_state(instance)

    assert instance.lifecycle.state() == ExSt.PENDING

    latch()
    t.join(timeout=1)

    assert instance.lifecycle.state() == ExSt.COMPLETED
    assert instance.lifecycle.states() == [ExSt.CREATED, ExSt.PENDING, ExSt.RUNNING, ExSt.COMPLETED]


def test_cancellation_after_start():  # TODO unreliable test relying on timing (stopped before latch fully released)?
    instance = RunnerJobInstance('j', TestExecution())
    latch = instance.create_latch(ExSt.PENDING)
    t = Thread(target=instance.run)
    t.start()

    wait_for_pending_state(instance)
    latch()

    instance.stop()
    t.join(timeout=1)

    assert instance.lifecycle.state() == ExSt.CANCELLED
    assert instance.lifecycle.states() == [ExSt.CREATED, ExSt.PENDING, ExSt.CANCELLED]


def test_cancellation_before_start():
    instance = RunnerJobInstance('j', TestExecution())
    instance.create_latch(ExSt.PENDING)
    t = Thread(target=instance.run)

    instance.stop()
    t.start()
    t.join(timeout=1)

    assert instance.lifecycle.state() == ExSt.CANCELLED
    assert instance.lifecycle.states() == [ExSt.CREATED, ExSt.CANCELLED]


def test_error():
    execution = TestExecution()
    exception = Exception()
    execution.raise_exception(exception)
    instance = runner.run('j', execution)

    assert instance.lifecycle.state() == ExSt.ERROR
    assert isinstance(instance.exec_error, ExecutionError)
    assert instance.exec_error.exec_state == ExSt.ERROR
    assert instance.exec_error.unexpected_error == exception


def wait_for_pending_state(instance: RunnerJobInstance):
    """
    Wait for the job to reach waiting state
    """
    wait_count = 0
    while instance.lifecycle.state() != ExSt.PENDING:
        time.sleep(0.1)
        wait_count += 1
        if wait_count > 10:
            assert False  # Hasn't reached PENDING state

"""
Execution framework defines an abstraction for an execution of a task.
It consists of:
 1. Possible states of execution
 2. A structure for conveying of error conditions
 3. An interface for implementing various types of executions
"""

import abc
import datetime
from collections import OrderedDict
from enum import Enum, auto
from typing import Tuple, List, Iterable, Set, Optional

from taro import util
from taro.util import utc_now


class ExecutionStateGroup(Enum):
    BEFORE_EXECUTION = auto()
    EXECUTING = auto()
    TERMINAL = auto()
    NOT_COMPLETED = auto()
    NOT_EXECUTED = auto()
    FAILURE = auto()


class ExecutionState(Enum):
    NONE = {}
    CREATED = {ExecutionStateGroup.BEFORE_EXECUTION}

    PENDING = {ExecutionStateGroup.BEFORE_EXECUTION}  # Until released
    WAITING = {ExecutionStateGroup.BEFORE_EXECUTION}  # Wait for another job
    # ON_HOLD or same as pending?

    TRIGGERED = {ExecutionStateGroup.EXECUTING}  # Start request sent, start confirmation not (yet) received
    STARTED = {ExecutionStateGroup.EXECUTING}
    RUNNING = {ExecutionStateGroup.EXECUTING}

    COMPLETED = {ExecutionStateGroup.TERMINAL}

    STOPPED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.NOT_COMPLETED}
    INTERRUPTED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.NOT_COMPLETED}

    DISABLED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.NOT_EXECUTED}
    CANCELLED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.NOT_EXECUTED}
    SKIPPED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.NOT_EXECUTED}
    SUSPENDED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.NOT_EXECUTED}  # Temporarily disabled

    START_FAILED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.FAILURE}
    FAILED = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.FAILURE}
    ERROR = {ExecutionStateGroup.TERMINAL, ExecutionStateGroup.FAILURE}

    def __new__(cls, *args, **kwds):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, groups: Set[ExecutionStateGroup]):
        self.groups = groups

    def is_before_execution(self):
        return ExecutionStateGroup.BEFORE_EXECUTION in self.groups

    def is_executing(self):
        return ExecutionStateGroup.EXECUTING in self.groups

    def is_incomplete(self):
        return ExecutionStateGroup.NOT_COMPLETED in self.groups

    def is_unexecuted(self):
        return ExecutionStateGroup.NOT_EXECUTED in self.groups

    def is_terminal(self) -> bool:
        return ExecutionStateGroup.TERMINAL in self.groups

    def is_failure(self) -> bool:
        return ExecutionStateGroup.FAILURE in self.groups


class ExecutionError(Exception):

    @classmethod
    def from_unexpected_error(cls, e: Exception):
        return cls("Unexpected error", ExecutionState.ERROR, unexpected_error=e)

    def __init__(self, message: str, exec_state: ExecutionState, unexpected_error: Exception = None, **kwargs):
        if not exec_state.is_failure():
            raise ValueError('exec_state must be a failure', exec_state)
        super().__init__(message)
        self.message = message
        self.exec_state = exec_state
        self.unexpected_error = unexpected_error
        self.params = kwargs


class Execution(abc.ABC):

    @property
    @abc.abstractmethod
    def is_async(self) -> bool:
        """
        SYNCHRONOUS TASK
            - finishes after the call of the execute() method
            - execution state is changed to RUNNING before the call of the execute() method

        ASYNCHRONOUS TASK
            - need not to finish after the call of the execute() method
            - execution state is changed to TRIGGER before the call of the execute() method

        :return: whether this execution is asynchronous
        """

    @abc.abstractmethod
    def execute(self) -> ExecutionState:
        """
        Executes a task

        :return: state after the execution of this method
        :raises ExecutionError: when execution failed
        :raises Exception: on unexpected failure
        """

    @property
    @abc.abstractmethod
    def status(self):
        """
        If progress monitoring is not supported then this method will always return None otherwise:
         - if executing -> current progress
         - when finished -> result

        :return: progress/result or None
        """

    @abc.abstractmethod
    def stop(self):
        """
        If not yet executed: Do not execute
        If already executing: Stop running execution GRACEFULLY
        If execution finished: Ignore
        """

    @abc.abstractmethod
    def interrupt(self):
        """
        If not yet executed: Do not execute
        If already executing: Stop running execution IMMEDIATELY
        If execution finished: Ignore
        """


class OutputExecution(Execution):

    @abc.abstractmethod
    def add_output_observer(self, observer):
        """
        Register output observer

        :param observer observer to register
        """

    @abc.abstractmethod
    def remove_output_observer(self, observer):
        """
        De-register output observer

        :param observer observer to de-register
        """


class ExecutionLifecycle:

    def __init__(self, *state_changes: Tuple[ExecutionState, datetime.datetime]):
        self._state_changes: OrderedDict[ExecutionState, datetime.datetime] = OrderedDict(state_changes)

    def __copy__(self):
        copied = ExecutionLifecycle()
        copied._state_changes = self._state_changes
        return copied

    def __deepcopy__(self, memo):
        return ExecutionLifecycle(*self.state_changes())

    def state(self):
        return next(reversed(self._state_changes.keys()), ExecutionState.NONE)

    def states(self) -> List[ExecutionState]:
        return list(self._state_changes.keys())

    def state_changes(self) -> Iterable[Tuple[ExecutionState, datetime.datetime]]:
        return ((state, changed) for state, changed in self._state_changes.items())

    def changed(self, state: ExecutionState) -> datetime.datetime:
        return self._state_changes[state]

    def last_changed(self):
        return next(reversed(self._state_changes.values()), None)

    def first_executing_state(self) -> Optional[ExecutionState]:
        return next((state for state in self._state_changes if state.is_executing()), None)

    def executed(self) -> bool:
        return self.first_executing_state() is not None

    def execution_started(self) -> Optional[datetime.datetime]:
        return self._state_changes.get(self.first_executing_state())

    def execution_finished(self) -> Optional[datetime.datetime]:
        state = self.state()
        if not state.is_terminal():
            return None
        return self.changed(state)

    def execution_time(self) -> Optional[datetime.timedelta]:
        started = self.execution_started()
        if not started:
            return None

        finished = self.execution_finished() or util.utc_now()
        return finished - started

    def __repr__(self) -> str:
        return "{}({!r})".format(
            self.__class__.__name__, self._state_changes)


class ExecutionLifecycleManagement(ExecutionLifecycle):

    def __init__(self, *state_changes: Tuple[ExecutionState, datetime.datetime]):
        super().__init__(*state_changes)

    def set_state(self, new_state) -> bool:
        if not new_state or new_state == ExecutionState.NONE or self.state() == new_state:
            return False
        else:
            self._state_changes[new_state] = utc_now()
            return True


class ExecutionOutputObserver(abc.ABC):

    def output_update(self, output):
        """Executed when new output line is available"""

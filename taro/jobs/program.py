"""
TODO: Preserve stderr
 - https://stackoverflow.com/questions/31833897/python-read-from-subprocess-stdout-and-stderr-separately-while-preserving-order
 - https://stackoverflow.com/questions/12270645/can-you-make-a-python-subprocess-output-stdout-and-stderr-as-usual-but-also-cap
"""
import io
import logging
import sys
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from typing import Union

from taro.jobs.execution import ExecutionState, ExecutionError, OutputExecution, ExecutionOutputObserver

USE_SHELL = False  # For testing only

log = logging.getLogger(__name__)


class ProgramExecution(OutputExecution):

    def __init__(self, args, read_output: bool):
        self.args = args
        self.read_output: bool = read_output
        self._popen: Union[Popen, None] = None
        self._status = None
        self._stopped: bool = False
        self._interrupted: bool = False
        self._output_observers = []

    @property
    def is_async(self) -> bool:
        return False

    def execute(self) -> ExecutionState:
        ret_code = -1
        if not self._stopped and not self._interrupted:
            stdout = PIPE if self.read_output else None
            stderr = STDOUT if self.read_output else None
            try:
                self._popen = Popen(" ".join(self.args) if USE_SHELL else self.args, stdout=stdout, stderr=stderr,
                                    shell=USE_SHELL)
                output_reader = None
                if self.read_output:
                    output_reader = Thread(target=self._read_output, name='Output-Reader', daemon=True)
                    output_reader.start()

                # print(psutil.Process(self.popen.pid).memory_info().rss)

                ret_code = self._popen.wait()
                if output_reader:
                    output_reader.join(timeout=1)
                if ret_code == 0:
                    return ExecutionState.COMPLETED
            except KeyboardInterrupt:
                return ExecutionState.STOPPED
            except FileNotFoundError as e:
                sys.stderr.write(str(e) + "\n")
                raise ExecutionError(str(e), ExecutionState.FAILED) from e
            except SystemExit as e:
                raise ExecutionError('System exit', ExecutionState.INTERRUPTED) from e

        if self._stopped:
            return ExecutionState.STOPPED
        if self._interrupted:
            return ExecutionState.INTERRUPTED
        raise ExecutionError("Process returned non-zero code " + str(ret_code), ExecutionState.FAILED)

    @property
    def status(self):
        return self._status

    def stop(self):
        self._stopped = True
        if self._popen:
            self._popen.terminate()

    def interrupt(self):
        self._interrupted = True
        if self._popen:
            self._popen.terminate()

    def add_output_observer(self, observer):
        self._output_observers.append(observer)

    def remove_output_observer(self, observer):
        self._output_observers.remove(observer)

    def _read_output(self):
        for line in io.TextIOWrapper(self._popen.stdout, encoding="utf-8"):
            line_stripped = line.rstrip()
            self._status = line_stripped
            print(line_stripped)
            self._notify_output_observers(line_stripped)

    def _notify_output_observers(self, output):
        for observer in self._output_observers:
            # noinspection PyBroadException
            try:
                if isinstance(observer, ExecutionOutputObserver):
                    observer.output_update(output)
                elif callable(observer):
                    observer(output)
                else:
                    log.warning("event=[unsupported_output_observer] observer=[%s]", observer)
            except BaseException:
                log.exception("event=[state_observer_exception]")

"""Wall-time limit and measure for the methods of a Software."""

import functools
import signal
import threading
import time
import warnings

from amac.utils.exception import ExecuteTimeout


def time_limited(method):
    """Measure and limit the wall time of ``method(self, instance, ...)``.

    The duration is recorded in ``instance.duree.steps`` under the name of
    the method, even if the method fails. The limit is
    ``self.program.timeout``; it uses ``SIGALRM``, which interrupts Python
    code as well as the wait on a subprocess (which ``subprocess.run``
    then kills).

    Without timeout, or outside the main thread (where ``SIGALRM`` is not
    available), the method runs without limit.

    Raises:
        ExecuteTimeout: If the method runs longer than the timeout.
    """

    @functools.wraps(method)
    def wrapper(self, instance, *args, **kwargs):
        timeout = self.program.timeout
        start = time.perf_counter()
        try:
            if timeout is None:
                return method(self, instance, *args, **kwargs)
            if threading.current_thread() is not threading.main_thread():
                warnings.warn(
                    f"{self.name}: timeout ignored outside the main thread",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return method(self, instance, *args, **kwargs)

            def on_alarm(signum, frame):
                raise ExecuteTimeout(f"{self.name}: {method.__name__} exceeded {timeout} s")

            previous = signal.signal(signal.SIGALRM, on_alarm)
            signal.setitimer(signal.ITIMER_REAL, timeout)
            try:
                return method(self, instance, *args, **kwargs)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous)
        finally:
            instance.duree.add_step(
                method.__name__,
                time.perf_counter() - start,
            )

    return wrapper

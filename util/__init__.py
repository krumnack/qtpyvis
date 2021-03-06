"""
.. moduleauthor:: Rasmus Diederichsen, Ulf Krumnack

.. module:: util

This module collects miscellaneous utilities.


Internal requirements: just submodules:
 - util.check
 - util.error
 - util.logging


External requirements:
 - packaging (via .check)
"""

from dltb.util import error
from dltb.util.logging import RecorderHandler
from . import check

#
# async
#

from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4,
                               thread_name_prefix='async')

runner = None

# FIXME[old]: currently not used
def run_async(function, *args, **kwargs):
    _executor.submit(function, *args, **kwargs)


# FIXME[old]: currently not used
def async_decorator(function):
    """A decorator to enforce asyncronous execution.
    """
    def wrapper(*args, **kwargs):
        runner.runTask(function, *args, **kwargs)
        # run_async(function, *args, **kwargs)
    return wrapper

#
# timer loop  (FIXME[question]: what is the idea here?)
#

import time, threading

# FIXME[problem]: resources requires stuff from base (while base)
# also requires stuff from util) -> cyclic import!
#  => disentangle, maybe split into several (sub)packages
#from . import resource

_timer = None
_timer_callbacks = []

def _timer_loop():
    #resources.update()
    for callback in _timer_callbacks:
        callback()
    if _timer is not None:
        start_timer()

def start_timer(timer_callback = None):
    global _timer
    if timer_callback is not None:
        add_timer_callback(timer_callback)
    _timer = threading.Timer(1, _timer_loop)
    _timer.start()
    
def stop_timer():
    global _timer
    if _timer is not None:
        _timer.cancel()
    _timer = None
    print("Timer stopped.")

def add_timer_callback(callback):
    global _timer_callbacks
    _timer_callbacks.append(callback)

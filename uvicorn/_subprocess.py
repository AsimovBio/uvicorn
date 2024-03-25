"""
Some light wrappers around Python's multiprocessing, to deal with cleanly
starting child processes.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
from multiprocessing.context import SpawnProcess
from socket import socket
from typing import Callable

from uvicorn.config import Config

import logging

logger = logging.getLogger("uvicorn.error")

multiprocessing.allow_connection_pickling()
spawn = multiprocessing.get_context("spawn")


def get_subprocess(
    config: Config,
    target: Callable[..., None],
    sockets: list[socket],
) -> SpawnProcess:
    """
    Called in the parent process, to instantiate a new child process instance.
    The child is not yet started at this point.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    """
    # We pass across the stdin fileno, and reopen it in the child process.
    # This is required for some debugging environments.
    logger.debug("top of subprocess")
    try:
        stdin_fileno = sys.stdin.fileno()
    # The `sys.stdin` can be `None`, see https://docs.python.org/3/library/sys.html#sys.__stdin__.
    except (AttributeError, OSError):
        stdin_fileno = None

    kwargs = {
        "config": config,
        "target": target,
        "sockets": sockets,
        "stdin_fileno": stdin_fileno,
    }
    logger.debug("spawning process in of get_subprocess")
    return spawn.Process(target=subprocess_started, kwargs=kwargs)


def subprocess_started(
    config: Config,
    target: Callable[..., None],
    sockets: list[socket],
    stdin_fileno: int | None,
) -> None:
    """
    Called when the child process starts.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    * stdin_fileno - The file number of sys.stdin, so that it can be reattached
                     to the child process.
    """
    logger.debug("top of get_subprocess")
    # Re-open stdin.
    if stdin_fileno is not None:
        sys.stdin = os.fdopen(stdin_fileno)

    # Logging needs to be setup again for each child.
    config.configure_logging()

    # Now we can call into `Server.run(sockets=sockets)`
    logger.debug("about to actually call server.run in get_subprocess")
    target(sockets=sockets)

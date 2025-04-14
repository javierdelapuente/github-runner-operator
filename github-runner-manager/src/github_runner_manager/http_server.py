#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The HTTP server for github-runner-manager.

The HTTP server for request to the github-runner-manager.
"""

import getpass
import grp
import os
from dataclasses import dataclass
from threading import Lock

from flask import Flask, request

from github_runner_manager.configuration import ApplicationConfiguration, UserInfo
from github_runner_manager.errors import LockError
from github_runner_manager.manager.runner_manager import FlushMode
from github_runner_manager.manager.runner_scaler import RunnerScaler

APP_CONFIG_NAME = "app_config"
OPENSTACK_CONFIG_NAME = "openstack_config"

app = Flask(__name__)

# Pylint thinks this is a constant which needs to be upper case. This is a global variable.
_lock = None  # pylint: disable=invalid-name


@app.route("/health", methods=["GET"])
def get_health() -> tuple[str, int]:
    """Get the health of the HTTP server.

    Returns:
        A empty response.
    """
    return ("", 204)


@app.route("/runner/flush", methods=["POST"])
def flush_runner() -> tuple[str, int]:
    """Flush the runners.

    The logic of this function will be implemented in a future PR.

    HTTP header args:
        flush-busy(bool): Whether to flush busy runners.

    Returns:
        A empty response.
    """
    app_config = app.config[APP_CONFIG_NAME]

    flush_busy_str = request.args.get("flush-busy")
    flush_busy = False
    if flush_busy_str in ("True", "true"):
        flush_busy = True

    lock = get_lock()

    lock_state = "locked" if lock.locked() else "unlocked"
    app.logger.info("Attempting to acquire the lock: %s", lock_state)
    with lock:
        app.logger.info("Flushing runners...")
        user = UserInfo(getpass.getuser(), grp.getgrgid(os.getgid()))
        runner_scaler: RunnerScaler = RunnerScaler.build(app_config, user)
        app.logger.info("Flushing busy: %s", flush_busy)
        flush_mode = FlushMode.FLUSH_BUSY if flush_busy else FlushMode.FLUSH_IDLE
        num_flushed = runner_scaler.flush(flush_mode)
        app.logger.info("Flushed %s runners", num_flushed)
    return ("", 204)


def get_lock() -> Lock:
    """Get the lock representing modification access to the set of runners.

    Raises:
        LockError: The lock is missing.

    Returns:
        The lock.
    """
    if _lock is not None:
        return _lock
    raise LockError("Lock not configured")


@dataclass
class FlaskArgs:
    """Arguments for Flask HTTP server.

    Attributes:
        host: The hostname to listen on for the HTTP server.
        port: The port to listen on for the HTTP server.
        debug: Start the flask HTTP server in debug mode.
    """

    host: str
    port: int
    debug: bool


def start_http_server(
    app_config: ApplicationConfiguration,
    lock: Lock,
    flask_args: FlaskArgs,
) -> None:
    """Start the HTTP server for interacting with the github-runner-manager service.

    Args:
        app_config: The application configuration.
        lock: The lock representing modification access to the managed set of runners.
        flask_args: The arguments for the flask HTTP server.
    """
    # The lock is passed from the caller, hence the need to update the global variable.
    global _lock  # pylint: disable=global-statement
    _lock = lock
    app.config[APP_CONFIG_NAME] = app_config
    app.run(
        host=flask_args.host,
        port=flask_args.port,
        debug=flask_args.debug,
        use_reloader=False,
    )

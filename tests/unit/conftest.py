# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
import secrets
import typing
import unittest.mock
from pathlib import Path

import pytest
from github_runner_manager.manager.runner_scaler import RunnerScaler

import utilities
from tests.unit.mock import MockGhapiClient, MockLxdClient, MockRepoPolicyComplianceClient


@pytest.fixture(name="exec_command")
def exec_command_fixture():
    return unittest.mock.MagicMock(return_value=("", 0))


@pytest.fixture(name="lxd_exec_command")
def lxd_exec_command_fixture():
    return unittest.mock.MagicMock(return_value=("", 0))


@pytest.fixture(name="runner_binary_path")
def runner_binary_path_fixture(tmp_path):
    return tmp_path / "github-runner-app"


def disk_usage_mock(total_disk: int):
    """Mock disk usage factory.

    Args:
        total_disk: Total disk size in bytes.

    Returns:
        A disk usage magic mock instance.
    """
    disk = unittest.mock.MagicMock()
    disk.total = total_disk
    disk_usage = unittest.mock.MagicMock(return_value=disk)
    return disk_usage


@pytest.fixture(autouse=True)
def mocks(monkeypatch, tmp_path, exec_command, lxd_exec_command, runner_binary_path):
    runner_scaler_mock = unittest.mock.MagicMock(spec=RunnerScaler)

    cron_path = tmp_path / "cron.d"
    cron_path.mkdir()

    monkeypatch.setattr(
        "charm.GithubRunnerCharm.service_token_path", tmp_path / "mock_service_token"
    )
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.repo_check_web_service_path",
        tmp_path / "repo_policy_compliance_service",
    )
    monkeypatch.setattr(
        "charm.GithubRunnerCharm.repo_check_systemd_service", tmp_path / "systemd_service"
    )
    monkeypatch.setattr("charm.RunnerScaler", runner_scaler_mock)
    monkeypatch.setattr("charm.GithubRunnerCharm.kernel_module_path", tmp_path / "modules")
    monkeypatch.setattr("charm.GithubRunnerCharm._update_kernel", lambda self, now: None)
    monkeypatch.setattr("charm.execute_command", exec_command)
    monkeypatch.setattr("charm.shutil", unittest.mock.MagicMock())
    monkeypatch.setattr("charm.shutil.disk_usage", disk_usage_mock(30 * 1024 * 1024 * 1024))
    monkeypatch.setattr("charm_state.CHARM_STATE_PATH", Path(tmp_path / "charm_state.json"))
    monkeypatch.setattr("event_timer.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("event_timer.execute_command", exec_command)
    monkeypatch.setattr(
        "firewall.Firewall.get_host_ip", unittest.mock.MagicMock(return_value="10.0.0.1")
    )
    monkeypatch.setattr("firewall.Firewall.refresh_firewall", unittest.mock.MagicMock())
    monkeypatch.setattr("runner.execute_command", lxd_exec_command)
    monkeypatch.setattr("runner.shared_fs", unittest.mock.MagicMock())
    monkeypatch.setattr(
        "github_runner_manager.metrics.events.METRICS_LOG_PATH", Path(tmp_path / "metrics.log")
    )
    monkeypatch.setattr("runner.time", unittest.mock.MagicMock())
    monkeypatch.setattr("github_runner_manager.github_client.GhApi", MockGhapiClient)
    monkeypatch.setattr("runner_manager_type.jinja2", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager_type.LxdClient", MockLxdClient)
    monkeypatch.setattr("runner_manager.github_metrics", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.runner_logs", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.LxdClient", MockLxdClient)
    monkeypatch.setattr("runner_manager.shared_fs", unittest.mock.MagicMock())
    monkeypatch.setattr("runner_manager.execute_command", exec_command)
    monkeypatch.setattr("runner_manager.LXDRunnerManager.runner_bin_path", runner_binary_path)
    monkeypatch.setattr("runner_manager.LXDRunnerManager.cron_path", cron_path)
    monkeypatch.setattr(
        "runner_manager.RepoPolicyComplianceClient", MockRepoPolicyComplianceClient
    )
    monkeypatch.setattr("github_runner_manager.utilities.time", unittest.mock.MagicMock())


@pytest.fixture(autouse=True, name="cloud_name")
def cloud_name_fixture() -> str:
    """The testing cloud name."""
    return "microstack"


@pytest.fixture(name="clouds_yaml")
def clouds_yaml_fixture(cloud_name: str) -> dict:
    """Testing clouds.yaml."""
    return {
        "clouds": {
            cloud_name: {
                "auth": {
                    "auth_url": secrets.token_hex(16),
                    "project_name": secrets.token_hex(16),
                    "project_domain_name": secrets.token_hex(16),
                    "username": secrets.token_hex(16),
                    "user_domain_name": secrets.token_hex(16),
                    "password": secrets.token_hex(16),
                }
            }
        }
    }


@pytest.fixture(name="multi_clouds_yaml")
def multi_clouds_yaml_fixture(clouds_yaml: dict) -> dict:
    """Testing clouds.yaml with multiple clouds."""
    multi_clouds_yaml = copy.deepcopy(clouds_yaml)
    multi_clouds_yaml["clouds"]["unused_cloud"] = {
        "auth": {
            "auth_url": secrets.token_hex(16),
            "project_name": secrets.token_hex(16),
            "project_domain_name": secrets.token_hex(16),
            "username": secrets.token_hex(16),
            "user_domain_name": secrets.token_hex(16),
            "password": secrets.token_hex(16),
        }
    }
    return multi_clouds_yaml


@pytest.fixture(name="skip_retry")
def skip_retry_fixture(monkeypatch: pytest.MonkeyPatch):
    """Fixture for skipping retry for functions with retry decorator."""

    def patched_retry(*args, **kwargs):
        """A fallthrough decorator.

        Args:
            args: Positional arguments placeholder.
            kwargs: Keyword arguments placeholder.

        Returns:
            The fallthrough decorator.
        """

        def patched_retry_decorator(func: typing.Callable):
            """The fallthrough decorator.

            Args:
                func: The function to decorate.

            Returns:
                the function without any additional features.
            """
            return func

        return patched_retry_decorator

    monkeypatch.setattr(utilities, "retry", patched_retry)

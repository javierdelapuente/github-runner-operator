# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used by Runner class."""


from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from github_runner_manager.types_.github import GitHubPath

from charm_state import SSHDebugConnection


@dataclass
class RunnerNameByHealth:
    """Set of runners instance by health state.

    Attributes:
        healthy: Runners that are correctly running runner script.
        unhealthy: Runners that are not running runner script.
    """

    healthy: tuple[str, ...]
    unhealthy: tuple[str, ...]


@dataclass
class ProxySetting:
    """Represent HTTP-related proxy settings.

    Attributes:
        no_proxy: The comma separated URLs to not go through proxy.
        http: HTTP proxy URL.
        https: HTTPS proxy URL.
        aproxy_address: Aproxy URL.
    """

    no_proxy: Optional[str]
    http: Optional[str]
    https: Optional[str]
    aproxy_address: Optional[str]


@dataclass
# The instance attributes are all required and is better standalone each.
class RunnerConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration for runner.

    Attributes:
        app_name: Application name of the charm.
        issue_metrics: Whether to issue metrics.
        labels: Custom runner labels.
        lxd_storage_path: Path to be used as LXD storage.
        name: Name of the runner.
        path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization
            name.
        proxies: HTTP(S) proxy settings.
        dockerhub_mirror: URL of dockerhub mirror to use.
        ssh_debug_connections: The SSH debug server connections metadata.
    """

    app_name: str
    issue_metrics: bool
    labels: tuple[str]
    lxd_storage_path: Path
    name: str
    path: GitHubPath
    proxies: ProxySetting
    dockerhub_mirror: str | None = None
    ssh_debug_connections: list[SSHDebugConnection] | None = None


@dataclass
class RunnerStatus:
    """Status of runner.

    Attributes:
        runner_id: ID of the runner.
        exist: Whether the runner instance exists on LXD.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    runner_id: Optional[int] = None
    exist: bool = False
    online: bool = False
    busy: bool = False


@dataclass
class RunnerGithubInfo:
    """GitHub info of a runner.

    Attributes:
        runner_name: Name of the runner.
        runner_id: ID of the runner assigned by GitHub.
        online: Whether GitHub marks this runner as online.
        busy: Whether GitHub marks this runner as busy.
    """

    runner_name: str
    runner_id: int
    online: bool
    busy: bool

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for github-runner charm with a fork repo.

Tests a path change in the repo.
"""

import pytest
from github.Repository import Repository
from juju.application import Application
from juju.model import Model

from charm_state import PATH_CONFIG_NAME
from tests.integration.helpers.common import reconcile
from tests.integration.helpers.lxd import ensure_charm_has_runner, get_runner_names


@pytest.mark.openstack
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_path_config_change(
    model: Model,
    app_with_forked_repo: Application,
    github_repository: Repository,
    path: str,
) -> None:
    """
    arrange: A working application with one runner in a forked repository.
    act: Change the path configuration to the main repository and reconcile runners.
    assert: No runners connected to the forked repository and one runner in the main repository.
    """
    unit = app_with_forked_repo.units[0]
    await ensure_charm_has_runner(app=app_with_forked_repo, model=model)

    await app_with_forked_repo.set_config({PATH_CONFIG_NAME: path})

    await reconcile(app=app_with_forked_repo, model=model)

    runner_names = await get_runner_names(unit)
    assert len(runner_names) == 1
    runner_name = runner_names[0]

    runners_in_repo = github_repository.get_self_hosted_runners()

    runner_in_repo_with_same_name = tuple(
        filter(lambda runner: runner.name == runner_name, runners_in_repo)
    )

    assert len(runner_in_repo_with_same_name) == 1
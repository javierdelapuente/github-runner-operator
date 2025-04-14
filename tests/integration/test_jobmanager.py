# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Testing for jobmanager platform."""

import json
import logging
import socket
from typing import AsyncIterator

import pytest
import pytest_asyncio
from github_runner_manager.reactive.consumer import JobDetails
from jobmanager_client.models.job import Job
from jobmanager_client.models.v1_jobs_job_id_token_post200_response import (
    V1JobsJobIdTokenPost200Response,
)
from juju.application import Application
from pytest_httpserver import HTTPServer
from pytest_operator.plugin import OpsTest

from charm_state import BASE_VIRTUAL_MACHINES_CONFIG_NAME, MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME
from tests.integration.helpers.charm_metrics import (
    clear_metrics_log,
)
from tests.integration.helpers.common import reconcile
from tests.integration.utils_reactive import (
    add_to_queue,
    assert_queue_is_empty,
    clear_queue,
    get_mongodb_uri,
)

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.openstack


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("0.0.0.0", 8000)


@pytest_asyncio.fixture(name="app")
async def app_fixture(
    ops_test: OpsTest, app_for_jobmanager: Application
) -> AsyncIterator[Application]:
    """Setup the reactive charm with 1 virtual machine and tear down afterwards."""
    mongodb_uri = await get_mongodb_uri(ops_test, app_for_jobmanager)
    clear_queue(mongodb_uri, app_for_jobmanager.name)
    assert_queue_is_empty(mongodb_uri, app_for_jobmanager.name)

    await app_for_jobmanager.set_config(
        {
            BASE_VIRTUAL_MACHINES_CONFIG_NAME: "0",
            MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "1",
        }
    )
    await reconcile(app_for_jobmanager, app_for_jobmanager.model)
    await clear_metrics_log(app_for_jobmanager.units[0])

    yield app_for_jobmanager

    # Call reconcile to enable cleanup of any runner spawned
    await app_for_jobmanager.set_config({MAX_TOTAL_VIRTUAL_MACHINES_CONFIG_NAME: "0"})
    await reconcile(app_for_jobmanager, app_for_jobmanager.model)


@pytest.mark.abort_on_fail
async def test_jobmanager(
    monkeypatch: pytest.MonkeyPatch,
    app: Application,
    ops_test: OpsTest,
    httpserver: HTTPServer,
):
    """
    arrange: TODO.
    act: TODO.
    assert: TODO.
    """
    logger.info("Start of test_jobmanager test")

    # put in a fixture
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    logger.info("IP Address to use: %s", ip_address)
    s.close()

    # put in a fixture
    port = 8000
    base_url = f"http://{ip_address}:{port}"

    mongodb_uri = await get_mongodb_uri(ops_test, app)
    labels = {app.name, "x64"}

    job_id = 99
    job_path = f"/v1/jobs/{job_id}"
    job_url = f"{base_url}{job_path}"

    job = JobDetails(
        labels=labels,
        url=job_url,
    )

    returned_job = Job(job_id=job_id, status="PENDING")
    httpserver.expect_oneshot_request(job_path).respond_with_json(returned_job.to_dict())

    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=10) as waiting:
        add_to_queue(
            json.dumps(json.loads(job.json()) | {"ignored_noise": "foobar"}),
            mongodb_uri,
            app.name,
        )
        logger.info("JAVI Waiting for first pending")
    assert waiting.result

    logger.info("JAVI Elapsed time: %s sec", (waiting.elapsed_time))
    logger.info("JAVI server log: %s ", (httpserver.log))
    logger.info("JAVI matchers: %s ", (httpserver.format_matchers()))

    # ok, now a pending matcher for a while until the runner sends alive
    _ = httpserver.expect_request(job_path).respond_with_json(returned_job.to_dict())

    logger.info("JAVI Elapsed time: %s sec", (waiting.elapsed_time))
    logger.info("JAVI server log: %s ", (httpserver.log))
    logger.info("JAVI matchers: %s ", (httpserver.format_matchers()))

    token_path = f"/v1/jobs/{job_id}/token"
    returned_token = V1JobsJobIdTokenPost200Response(token="token")
    httpserver.expect_oneshot_request(token_path).respond_with_json(returned_token.to_dict())
    with httpserver.wait(raise_assertions=False, stop_on_nohandler=False, timeout=10) as waiting:
        logger.info("JAVI waiting for get token")
    assert waiting.result

    logger.info("JAVI Elapsed time: %s sec", (waiting.elapsed_time))
    logger.info("JAVI server log: %s ", (httpserver.log))
    logger.info("JAVI matchers: %s ", (httpserver.format_matchers()))

    assert False, "end of test not finished"

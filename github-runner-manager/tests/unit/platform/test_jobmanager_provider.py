#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.


"""Test for the jobmanager provider module."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from jobmanager_client.models.job import Job
from jobmanager_client.models.v1_jobs_job_id_health_get200_response import (
    V1JobsJobIdHealthGet200Response,
)
from jobmanager_client.models.v1_jobs_job_id_token_post200_response import (
    V1JobsJobIdTokenPost200Response,
)
from jobmanager_client.rest import ApiException, NotFoundException

from github_runner_manager.manager.models import InstanceID, RunnerIdentity, RunnerMetadata
from github_runner_manager.platform.jobmanager_provider import JobManagerPlatform, JobStatus
from github_runner_manager.platform.platform_provider import (
    PlatformApiError,
    PlatformRunnerHealth,
    RunnersHealthResponse,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunnerLabel


def test_get_runner_context_succeeds(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock the client api to return a token.
    act: Call get_runner_context.
    assert: The correct token and the correct runner are returned..
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.return_value = V1JobsJobIdTokenPost200Response(token="mytoken")

    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    instance_id = InstanceID.build(prefix="unit-0")
    labels = ["label"]
    platform = JobManagerPlatform()

    context, runner = platform.get_runner_context(metadata, instance_id, labels)

    assert "builder-agent" in context.shell_run_script
    assert runner.labels == [SelfHostedRunnerLabel(name="label")]
    assert runner.identity.metadata == metadata
    assert runner.status == GitHubRunnerStatus.OFFLINE
    assert not runner.busy


@pytest.mark.parametrize(
    "api_return_value, error_message",
    [
        pytest.param(V1JobsJobIdTokenPost200Response(), "Empty token", id="No token"),
        pytest.param(ApiException, "API error", id="Exception from api"),
    ],
)
def test_get_runner_context_fails(
    monkeypatch: pytest.MonkeyPatch, api_return_value, error_message
):
    """
    arrange: Mock the jobmanager client to return different error conditions.
    act: Call get_runner_context.
    assert: PlatformApiError should be raised with the expected message.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = [api_return_value]

    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    instance_id = InstanceID.build(prefix="unit-0")
    labels = ["label"]
    platform = JobManagerPlatform()

    with pytest.raises(PlatformApiError) as exc:
        _context, _runner = platform.get_runner_context(metadata, instance_id, labels)

    assert error_message in str(exc.value)


@pytest.mark.parametrize(
    "api_return_value, picked_up",
    [
        pytest.param(Job(status=JobStatus.IN_PROGRESS.value), True, id="in progress job"),
        pytest.param(Job(status=JobStatus.PENDING.value), False, id="pending job"),
    ],
)
def test_check_job_been_picked_up(monkeypatch: pytest.MonkeyPatch, api_return_value, picked_up):
    """
    arrange: Prepare a job return for the jobmanager client.
    act: call check_job_been_picked_up.
    assert: Depending on the state of the job, it will be picked or not accordingly.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = [api_return_value]

    platform = JobManagerPlatform()
    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    job_url = "http://example.com/v1/jobs/3"

    assert platform.check_job_been_picked_up(metadata, job_url) == picked_up


def test_check_job_been_picked_fails(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: The jobmanager client raises an exception when called.
    act: call check_job_been_picked_up.
    assert: The PlatformApiError exception is raised from the jobmanager provider.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = ApiException

    platform = JobManagerPlatform()
    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    job_url = "http://example.com/v1/jobs/3"

    with pytest.raises(PlatformApiError):
        platform.check_job_been_picked_up(metadata, job_url)


@pytest.mark.parametrize(
    "job_status,job_deletable,expected_online,expected_busy,expected_deletable",
    [
        pytest.param("PENDING", False, False, True, False, id="pending runner"),
        pytest.param("IN_PROGRESS", False, True, True, False, id="in progress runner"),
        pytest.param("COMPLETED", False, True, True, False, id="completed not deletabule runner"),
        pytest.param("COMPLETED", True, True, False, True, id="completed and deletable runner"),
    ],
)
def test_get_runner_health(
    monkeypatch: pytest.MonkeyPatch,
    job_status: str,
    job_deletable: bool,
    expected_online: bool,
    expected_busy: bool,
    expected_deletable: bool,
):
    """
    arrange: Given job health information from the jobmanager.
    act: Call JobManagerPlatform.get_runner_health.
    assert: Assert the correct health state is reported.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)

    api_return_value = V1JobsJobIdHealthGet200Response(
        label="label",
        status=job_status,
        deletable=job_deletable,
    )
    call_api_mock.side_effect = [api_return_value]

    platform = JobManagerPlatform()
    instance_id = InstanceID.build(prefix="unit-0")
    metadata = RunnerMetadata(
        platform_name="jobmanager", runner_id="3", url="http://jobmanager.example.com"
    )
    identity = RunnerIdentity(instance_id=instance_id, metadata=metadata)
    runner_health = platform.get_runner_health(identity)

    assert runner_health
    assert runner_health.online is expected_online
    assert runner_health.busy is expected_busy
    assert runner_health.deletable is expected_deletable


@pytest.mark.parametrize(
    "requested_runners,jobmanager_side_effects,expected_health_response",
    [
        pytest.param(
            [],
            [],
            RunnersHealthResponse(),
            id="Nothing requested, nothing in jobmanager, nothing replied.",
        ),
        pytest.param(
            [
                identity_1 := RunnerIdentity(
                    instance_id=InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(
                        platform_name="jobmanager",
                        runner_id="1",
                        url="http://jobmanager.example.com",
                    ),
                ),
                identity_2 := RunnerIdentity(
                    instance_id=InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(
                        platform_name="jobmanager",
                        runner_id="2",
                        url="http://jobmanager.example.com",
                    ),
                ),
            ],
            [
                V1JobsJobIdHealthGet200Response(
                    label="label",
                    status="IN_PROGRESS",
                    deletable=False,
                ),
                ApiException,
            ],
            RunnersHealthResponse(
                requested_runners=[
                    PlatformRunnerHealth(
                        identity=identity_1,
                        online=True,
                        busy=True,
                        deletable=False,
                    ),
                ],
                failed_requested_runners=[
                    identity_2,
                ],
            ),
            id="Two requested. One of the request failed.",
        ),
        pytest.param(
            [
                identity_1 := RunnerIdentity(
                    instance_id=InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(
                        platform_name="jobmanager",
                        runner_id="1",
                        url="http://jobmanager.example.com",
                    ),
                ),
                identity_2 := RunnerIdentity(
                    instance_id=InstanceID.build(prefix="unit-0"),
                    metadata=RunnerMetadata(
                        platform_name="jobmanager",
                        runner_id="2",
                        url="http://jobmanager.example.com",
                    ),
                ),
            ],
            [
                V1JobsJobIdHealthGet200Response(
                    label="label",
                    status="FAILED",
                    deletable=True,
                ),
                NotFoundException,
            ],
            RunnersHealthResponse(
                requested_runners=[
                    PlatformRunnerHealth(
                        identity=identity_1,
                        online=True,
                        busy=False,
                        deletable=True,
                    ),
                    PlatformRunnerHealth(
                        identity=identity_2,
                        online=False,
                        busy=False,
                        deletable=False,
                    ),
                ],
            ),
            id="Two requested. One deletable, one not found in jobmanager.",
        ),
    ],
)
def test_get_runners_health(
    monkeypatch: pytest.MonkeyPatch,
    requested_runners: list[RunnerIdentity],
    jobmanager_side_effects: Any,
    expected_health_response: RunnersHealthResponse,
):
    """
    arrange: Given some requested runner identities, and replies from the jobmanager.
    act: Call get_runners_health.
    assert: The expected health response with the correct requested_runners and
        runners with failed requests.
    """
    call_api_mock = MagicMock()
    monkeypatch.setattr("jobmanager_client.ApiClient.call_api", call_api_mock)
    call_api_mock.side_effect = jobmanager_side_effects

    platform = JobManagerPlatform()
    runners_health_response = platform.get_runners_health(requested_runners)

    expected_health_response = expected_health_response
    assert runners_health_response == expected_health_response

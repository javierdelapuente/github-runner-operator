# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""JobManager platform provider."""

import logging
from typing import Iterable

import jobmanager_client
from jobmanager_client.models.v1_jobs_job_id_token_post_request import V1JobsJobIdTokenPostRequest
from jobmanager_client.rest import ApiException
from pydantic import HttpUrl

from github_runner_manager.errors import PlatformApiError
from github_runner_manager.manager.models import InstanceID, RunnerMetadata
from github_runner_manager.platform.platform_provider import (
    JobInfo,
    PlatformProvider,
    PlatformRunnerState,
)
from github_runner_manager.types_.github import GitHubRunnerStatus, SelfHostedRunner

logger = logging.getLogger(__name__)


class JobManagerPlatform(PlatformProvider):
    """Manage self-hosted runner on the JobManager."""

    @classmethod
    def build(cls) -> "JobManagerPlatform":
        """Build a new instance of the JobManagerPlatform.

        Returns:
            New JobManagerPlatform.
        """
        return cls()

    def get_runners(
        self, states: Iterable[PlatformRunnerState] | None = None
    ) -> tuple[SelfHostedRunner, ...]:
        """Get info on self-hosted runners of certain states.

        This method will disappear in a following PR.

        Args:
            states: Filter the runners for these states. If None, all runners are returned.

        Returns:
            Empty list of runners, as jobmanager will not implement this functionality.
        """
        # TODO for now return empty so the reconciliation can work.
        logger.warning("jobmanager.get_runners not implemented")
        return ()

    def delete_runners(self, runners: list[SelfHostedRunner]) -> None:
        """Delete runners.

        Args:
            runners: list of runners to delete.
        """
        # TODO for now do not do any work so the reconciliation can work.
        logger.warning("jobmanager.delete_runners not implemented")

    def get_runner_token(
        self, metadata: RunnerMetadata, instance_id: InstanceID, labels: list[str]
    ) -> tuple[str, SelfHostedRunner]:
        """Get a one time token for a runner.

        This token is used for registering self-hosted runners.

        Args:
            instance_id: Instance ID of the runner.
            metadata: Metadata for the runner.
            labels: Labels for the runner.

        Raises:
            PlatformApiError: Problem with the underlying API.

        Returns:
            New runner token.
        """
        configuration = jobmanager_client.Configuration(host=metadata.url)
        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.DefaultApi(api_client)
            try:
                # Retrieve jobs
                jobrequest = V1JobsJobIdTokenPostRequest(job_id=int(metadata.runner_id))
                response = api_instance.v1_jobs_job_id_token_post(
                    int(metadata.runner_id), jobrequest
                )
                if response.token:
                    return (
                        response.token,
                        SelfHostedRunner(
                            busy=False,
                            id=int(metadata.runner_id),
                            metadata=metadata,
                            labels=[],
                            os="",
                            status=GitHubRunnerStatus.OFFLINE,
                            instance_id=instance_id,
                        ),
                    )
                raise PlatformApiError("Empty token from jobmanager API")
            except ApiException as exc:
                raise PlatformApiError from exc

    def get_removal_token(self) -> str:
        """Get removal token from Platform.

        This token is used for removing self-hosted runners.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

    def check_job_been_picked_up(self, metadata: RunnerMetadata, job_url: HttpUrl) -> bool:
        """Check if the job has already been picked up.

        Args:
            job_url: The URL of the job.
            metadata: Metadata for the runner.

        Raises:
            PlatformApiError: Problem with the underlying client.

        Returns:
            True if the job has been picked up, False otherwise.
        """
        configuration = jobmanager_client.Configuration(host=metadata.url)

        with jobmanager_client.ApiClient(configuration) as api_client:
            api_instance = jobmanager_client.DefaultApi(api_client)
            try:
                job = api_instance.v1_jobs_job_id_get(int(metadata.runner_id))
                if job.status != "PENDING":
                    return True
            except ApiException as exc:
                logger.exception("Error calling jobmanager api to get job information.")
                raise PlatformApiError from exc
            return False

    def get_job_info(
        self, metadata: RunnerMetadata, repository: str, workflow_run_id: str, runner: InstanceID
    ) -> JobInfo:
        """Get the Job info from the provider.

        Args:
            metadata: Metadata for the runner.
            repository: repository to get the job from.
            workflow_run_id: workflow run id of the job.
            runner: runner to get the job from.

        Raises:
            NotImplementedError: Work in progress.
        """
        raise NotImplementedError

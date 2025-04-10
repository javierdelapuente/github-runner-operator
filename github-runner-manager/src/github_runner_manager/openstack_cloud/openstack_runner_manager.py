# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for self-hosted runner on OpenStack."""

import logging
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import fabric
import invoke
import jinja2
import paramiko
from fabric import Connection as SSHConnection

from github_runner_manager import constants
from github_runner_manager.configuration import SupportServiceConfig
from github_runner_manager.errors import (
    KeyfileError,
    MissingServerConfigError,
    OpenStackError,
    OpenstackHealthCheckError,
    RunnerCreateError,
    RunnerStartError,
    SSHError,
)
from github_runner_manager.manager.cloud_runner_manager import (
    CloudInitStatus,
    CloudRunnerInstance,
    CloudRunnerManager,
    CloudRunnerState,
)
from github_runner_manager.manager.models import InstanceID
from github_runner_manager.manager.runner_manager import HealthState
from github_runner_manager.metrics import runner as runner_metrics
from github_runner_manager.openstack_cloud import health_checks
from github_runner_manager.openstack_cloud.constants import (
    CREATE_SERVER_TIMEOUT,
    METRICS_EXCHANGE_PATH,
    RUNNER_LISTENER_PROCESS,
    RUNNER_WORKER_PROCESS,
)
from github_runner_manager.openstack_cloud.openstack_cloud import (
    OpenstackCloud,
    OpenStackCredentials,
    OpenstackInstance,
)
from github_runner_manager.repo_policy_compliance_client import RepoPolicyComplianceClient
from github_runner_manager.utilities import retry, set_env_var

logger = logging.getLogger(__name__)

_CONFIG_SCRIPT_PATH = Path("/home/ubuntu/actions-runner/config.sh")

RUNNER_APPLICATION = Path("/home/ubuntu/actions-runner")
PRE_JOB_SCRIPT = RUNNER_APPLICATION / "pre-job.sh"

RUNNER_STARTUP_PROCESS = "/home/ubuntu/actions-runner/run.sh"

OUTDATED_METRICS_STORAGE_IN_SECONDS = CREATE_SERVER_TIMEOUT + 30  # add a bit on top of the timeout

HEALTH_CHECK_ERROR_LOG_MSG = "Health check could not be completed for %s"


class _GithubRunnerRemoveError(Exception):
    """Represents an error while SSH into a runner and running the remove script."""


@dataclass
class OpenStackServerConfig:
    """Configuration for OpenStack server.

    Attributes:
        image: The image name for runners to use.
        flavor: The flavor name for runners to use.
        network: The network name for runners to use.
    """

    image: str
    flavor: str
    network: str


@dataclass
class OpenStackRunnerManagerConfig:
    """Configuration for OpenStack runner manager.

    Attributes:
        prefix: The prefix of the runner names.
        credentials: The OpenStack authorization information.
        server_config: The configuration for OpenStack server.
        service_config: The configuration for supporting services.
    """

    prefix: str
    credentials: OpenStackCredentials
    server_config: OpenStackServerConfig | None
    service_config: SupportServiceConfig


@dataclass
class _RunnerHealth:
    """Runners with health state.

    Attributes:
        healthy: The list of healthy runners.
        unhealthy:  The list of unhealthy runners.
        unknown: The list of runners whose health state could not be determined.
    """

    healthy: tuple[OpenstackInstance, ...]
    unhealthy: tuple[OpenstackInstance, ...]
    unknown: tuple[OpenstackInstance, ...]


class OpenStackRunnerManager(CloudRunnerManager):
    """Manage self-hosted runner on OpenStack cloud.

    Attributes:
        name_prefix: The name prefix of the runners created.
    """

    def __init__(
        self,
        config: OpenStackRunnerManagerConfig,
    ) -> None:
        """Construct the object.

        Args:
            config: The configuration for the openstack runner manager.
        """
        self._config = config
        self._credentials = config.credentials
        self._openstack_cloud = OpenstackCloud(
            credentials=self._credentials,
            prefix=self.name_prefix,
            system_user=constants.RUNNER_MANAGER_USER,
            proxy_command=config.service_config.manager_proxy_command,
        )
        # Setting the env var to this process and any child process spawned.
        proxies = config.service_config.proxy_config
        if proxies and (no_proxy := proxies.no_proxy):
            set_env_var("NO_PROXY", no_proxy)
        if proxies and (http_proxy := proxies.http):
            set_env_var("HTTP_PROXY", http_proxy)
        if proxies and (https_proxy := proxies.https):
            set_env_var("HTTPS_PROXY", https_proxy)

    @property
    def name_prefix(self) -> str:
        """The prefix of runner names.

        Returns:
            The prefix of the runner names managed by this class.
        """
        return self._config.prefix

    def create_runner(self, instance_id: InstanceID, registration_jittoken: str) -> None:
        """Create a self-hosted runner.

        Args:
            instance_id: Instance ID for the runner to create.
            registration_jittoken: The JIT GitHub registration token for registering runners.

        Raises:
            MissingServerConfigError: Unable to create runner due to missing configuration.
            RunnerCreateError: Unable to create runner due to OpenStack issues.
        """
        if (server_config := self._config.server_config) is None:
            raise MissingServerConfigError("Missing server configuration to create runners")

        cloud_init = self._generate_cloud_init(registration_jittoken=registration_jittoken)
        try:
            instance = self._openstack_cloud.launch_instance(
                instance_id=instance_id,
                image=server_config.image,
                flavor=server_config.flavor,
                network=server_config.network,
                cloud_init=cloud_init,
            )
        except OpenStackError as err:
            raise RunnerCreateError(f"Failed to create {instance_id} openstack runner") from err

        logger.info("Waiting for runner process to startup: %s", instance.instance_id)
        self._wait_runner_startup(instance)
        logger.info("Waiting for runner process to be running: %s", instance.instance_id)
        self._wait_runner_running(instance)

        logger.info("Runner %s created successfully", instance.instance_id)

    def get_runners(
        self, states: Sequence[CloudRunnerState] | None = None
    ) -> tuple[CloudRunnerInstance, ...]:
        """Get self-hosted runners by state.

        Args:
            states: Filter for the runners with these github states. If None all states will be
                included.

        Returns:
            Information on the runner instances.
        """
        instances = self._openstack_cloud.get_instances()
        runners = []
        for instance in instances:
            try:
                healthy = health_checks.check_runner(
                    openstack_cloud=self._openstack_cloud, instance=instance
                )
            except OpenstackHealthCheckError:
                logger.exception(HEALTH_CHECK_ERROR_LOG_MSG, instance.instance_id.name)
                healthy = None
            runners.append(
                CloudRunnerInstance(
                    name=instance.instance_id.name,
                    instance_id=instance.instance_id,
                    health=HealthState.from_value(healthy),
                    state=CloudRunnerState.from_openstack_server_status(instance.status),
                )
            )
        if states is None:
            return tuple(runners)

        state_set = set(states)
        return tuple(runner for runner in runners if runner.state in state_set)

    def delete_runner(
        self, instance_id: InstanceID, remove_token: str
    ) -> runner_metrics.RunnerMetrics | None:
        """Delete self-hosted runners.

        Args:
            instance_id: The instance id of the runner to delete.
            remove_token: The GitHub remove token.

        Returns:
            Any metrics collected during the deletion of the runner.
        """
        logger.debug("Delete instance %s", instance_id)
        instance = self._openstack_cloud.get_instance(instance_id)
        if instance is None:
            logger.warning(
                "Unable to delete instance %s as it is not found",
                instance_id,
            )
            return None

        logger.debug(
            "Metrics extracted, deleting instance %s %s", instance_id, instance.instance_id
        )
        pulled_metrics = self._delete_runner(instance, remove_token)
        logger.debug("Instance deleted successfully %s %s", instance_id, instance.instance_id)
        logger.debug("Extract metrics for runner %s %s", instance_id, instance.instance_id)
        return pulled_metrics.to_runner_metrics(instance.instance_id, instance.created_at)

    def flush_runners(
        self, remove_token: str, busy: bool = False
    ) -> Iterable[runner_metrics.RunnerMetrics]:
        """Remove idle and/or busy runners.

        Args:
            remove_token:
            busy: If false, only idle runners are removed. If true, both idle and busy runners are
                removed.

        Returns:
            Any metrics retrieved from flushed runners.
        """
        instance_list = self._openstack_cloud.get_instances()
        for instance in instance_list:
            try:
                logger.debug(
                    "Checking runner state and flushing %s %s",
                    instance.server_id,
                    instance.instance_id,
                )
                self._check_state_and_flush(instance, busy)
            except SSHError:
                logger.warning(
                    "Unable to determine state of  %s and kill runner process due to SSH issues",
                    instance.instance_id,
                )
                continue
        logger.debug("Runners successfully flushed, cleaning up.")
        return self.cleanup(remove_token)

    def cleanup(self, remove_token: str) -> Iterable[runner_metrics.RunnerMetrics]:
        """Cleanup runner and resource on the cloud.

        Args:
            remove_token: The GitHub remove token.

        Returns:
            Any metrics retrieved from cleanup runners.
        """
        logger.debug("Getting runner healths for cleanup.")
        runners = self._get_runners_health()

        healthy_runner_names = {runner.instance_id for runner in runners.healthy}
        unhealthy_runner_names = {runner.instance_id for runner in runners.unhealthy}
        unknown_runner_names = {runner.instance_id for runner in runners.unknown}
        logger.debug("Healthy runners: %s", healthy_runner_names)
        logger.debug("Unhealthy runners: %s", unhealthy_runner_names)
        logger.debug("Unknown health runners: %s", unknown_runner_names)

        logger.debug("Deleting unhealthy runners.")
        extracted_runner_metrics = []
        for runner in runners.unhealthy:
            pulled_metrics = self._delete_runner(runner, remove_token)
            runner_metric = pulled_metrics.to_runner_metrics(runner.instance_id, runner.created_at)
            if not runner_metric:
                logger.error("No metrics returned after deleting %s", runner.instance_id)
            else:
                extracted_runner_metrics.append(runner_metric)
        logger.debug("Cleaning up runner resources.")
        self._openstack_cloud.cleanup()
        logger.debug("Cleanup completed successfully.")

        logger.debug("Extracting metrics.")
        return extracted_runner_metrics

    def _delete_runner(
        self, instance: OpenstackInstance, remove_token: str
    ) -> runner_metrics.PulledMetrics:
        """Delete self-hosted runners by openstack instance.

        Args:
            instance: The OpenStack instance.
            remove_token: The GitHub remove token.
        """
        pulled_metrics = runner_metrics.PulledMetrics()
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
            pulled_metrics = runner_metrics.pull_runner_metrics(instance.instance_id, ssh_conn)

            try:
                logger.info("Running runner removal script for %s", instance.instance_id)
                OpenStackRunnerManager._run_runner_removal_script(
                    instance.instance_id.name, ssh_conn, remove_token
                )
            except _GithubRunnerRemoveError:
                logger.warning(
                    "Unable to run github runner removal script for %s",
                    instance.instance_id,
                    stack_info=True,
                )
        except SSHError:
            logger.exception(
                "Failed to get SSH connection while removing %s", instance.instance_id
            )
            logger.warning(
                "Skipping runner remove script for %s due to SSH issues", instance.instance_id
            )

        try:
            self._openstack_cloud.delete_instance(instance.instance_id)
        except OpenStackError:
            logger.exception(
                "Unable to delete openstack instance for runner %s", instance.instance_id
            )
        return pulled_metrics

    def _get_runners_health(self) -> _RunnerHealth:
        """Get runners by health state.

        Returns:
            Runners by health state.
        """
        runner_list = self._openstack_cloud.get_instances()

        healthy, unhealthy, unknown = [], [], []
        for runner in runner_list:
            try:
                if health_checks.check_runner(
                    openstack_cloud=self._openstack_cloud, instance=runner
                ):
                    healthy.append(runner)
                else:
                    unhealthy.append(runner)
            except OpenstackHealthCheckError:
                logger.exception(HEALTH_CHECK_ERROR_LOG_MSG, runner.instance_id)
                unknown.append(runner)
        return _RunnerHealth(
            healthy=tuple(healthy), unhealthy=tuple(unhealthy), unknown=tuple(unknown)
        )

    def _generate_cloud_init(self, registration_jittoken: str) -> str:
        """Generate cloud init userdata.

        This is the script the openstack server runs on startup.

        Args:
            registration_jittoken: The JIT GitHub runner registration token.

        Returns:
            The cloud init userdata for openstack instance.
        """
        jinja = jinja2.Environment(
            loader=jinja2.PackageLoader("github_runner_manager", "templates"), autoescape=True
        )

        service_config = self._config.service_config
        runner_http_proxy = (
            service_config.runner_proxy_config.proxy_address
            if service_config.runner_proxy_config
            else None
        )
        ssh_debug_info = (
            secrets.choice(service_config.ssh_debug_connections)
            if service_config.ssh_debug_connections
            else None
        )
        env_contents = jinja.get_template("env.j2").render(
            pre_job_script=str(PRE_JOB_SCRIPT),
            dockerhub_mirror=service_config.dockerhub_mirror or "",
            ssh_debug_info=ssh_debug_info,
            tmate_server_proxy=runner_http_proxy,
        )
        pre_job_contents_dict = {
            "issue_metrics": True,
            "metrics_exchange_path": str(METRICS_EXCHANGE_PATH),
            "do_repo_policy_check": False,
        }
        repo_policy = self._get_repo_policy_compliance_client()
        if repo_policy is not None:
            pre_job_contents_dict.update(
                {
                    "repo_policy_base_url": repo_policy.base_url,
                    "repo_policy_one_time_token": repo_policy.get_one_time_token(),
                    "do_repo_policy_check": True,
                }
            )

        pre_job_contents = jinja.get_template("pre-job.j2").render(pre_job_contents_dict)

        aproxy_address = (
            service_config.runner_proxy_config.proxy_address if service_config.use_aproxy else None
        )
        return jinja.get_template("openstack-userdata.sh.j2").render(
            jittoken=registration_jittoken,
            env_contents=env_contents,
            pre_job_contents=pre_job_contents,
            metrics_exchange_path=str(METRICS_EXCHANGE_PATH),
            aproxy_address=aproxy_address,
            dockerhub_mirror=service_config.dockerhub_mirror,
            ssh_debug_info=ssh_debug_info,
            runner_proxy_config=service_config.runner_proxy_config,
        )

    def _get_repo_policy_compliance_client(self) -> RepoPolicyComplianceClient | None:
        """Get repo policy compliance client.

        Returns:
            The repo policy compliance client.
        """
        if (service_config := self._config.service_config).repo_policy_compliance is not None:
            return RepoPolicyComplianceClient(
                service_config.repo_policy_compliance.url,
                service_config.repo_policy_compliance.token,
            )
        return None

    @retry(tries=3, delay=5, backoff=2, local_logger=logger)
    def _check_state_and_flush(self, instance: OpenstackInstance, busy: bool) -> None:
        """Kill runner process depending on idle or busy.

        Due to update to runner state has some delay with GitHub API. The state of the runner is
        determined by which runner processes are running. If the Runner.Worker process is running,
        the runner is deemed to be busy.

        Raises:
            SSHError: Unable to check the state of the runner and kill the runner process due to
                SSH failure.

        Args:
            instance: The openstack instance to kill the runner process.
            busy: Kill the process if runner is busy, else only kill runner
                process if runner is idle.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except KeyfileError:
            logger.exception(
                "Health check failed due to unable to find keyfile for %s", instance.instance_id
            )
            return
        except SSHError:
            logger.exception(
                "SSH connection failure with %s during flushing", instance.instance_id
            )
            raise

        # Using a single command to determine the state and kill the process if needed.
        # This makes it more robust when network is unstable.
        if busy:
            logger.info("Attempting to kill all runner process on %s", instance.instance_id)
            # kill both Runner.Listener and Runner.Worker processes.
            # This kills pre-job.sh, a child process of Runner.Worker.
            kill_command = (
                f"pgrep -x {RUNNER_LISTENER_PROCESS} && "
                f"kill $(pgrep -x {RUNNER_LISTENER_PROCESS});"
                f"pgrep -x {RUNNER_WORKER_PROCESS} && kill $(pgrep -x {RUNNER_WORKER_PROCESS});"
            )
        else:
            logger.info(
                "Attempting to kill runner process on %s if not busy", instance.instance_id
            )
            # Only kill Runner.Listener if Runner.Worker does not exist.
            kill_command = (
                f"! pgrep -x {RUNNER_WORKER_PROCESS} && pgrep -x {RUNNER_LISTENER_PROCESS} && "
                f"kill $(pgrep -x {RUNNER_LISTENER_PROCESS})"
            )
        logger.info("Running kill process command: %s", kill_command)
        # Checking the result of kill command is not useful, as the exit code does not reveal much.
        result: fabric.Result = ssh_conn.run(kill_command, warn=True, timeout=30, hide=True)
        logger.info(
            "Kill process command output, ok: %s code %s, out: %s, err: %s",
            result.ok,
            result.return_code,
            result.stdout,
            result.stderr,
        )

    @retry(tries=10, delay=60, local_logger=logger)
    def _wait_runner_startup(self, instance: OpenstackInstance) -> None:
        """Wait until runner is startup.

        Args:
            instance: The runner instance.

        Raises:
            RunnerStartError: The runner startup process was not found on the runner.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SSHError as err:
            raise RunnerStartError(
                f"Failed to SSH to {instance.instance_id} during creation possible due to setup "
                "not completed"
            ) from err

        logger.debug("Running `cloud-init status` on instance %s.", instance.instance_id)
        result: invoke.runners.Result = ssh_conn.run("cloud-init status", warn=True, timeout=60)
        if not result.ok:
            logger.warning(
                "cloud-init status command failed on %s: %s.", instance.instance_id, result.stderr
            )
            raise RunnerStartError(f"Runner startup process not found on {instance.instance_id}")
        # A short running job may have already completed and exited the runner, hence check the
        # condition via cloud-init status check.
        if CloudInitStatus.DONE in result.stdout:
            return
        logger.debug("Running `ps aux` on instance %s.", instance.instance_id)
        result = ssh_conn.run("ps aux", warn=True, timeout=60, hide=True)
        if not result.ok:
            logger.warning("SSH run of `ps aux` failed on %s", instance.instance_id)
            raise RunnerStartError(f"Unable to SSH run `ps aux` on {instance.instance_id}")
        # Runner startup process is the parent process of runner.Listener and runner.Worker which
        # starts up much faster.
        if RUNNER_STARTUP_PROCESS not in result.stdout:
            logger.warning("Runner startup process not found on %s", instance.instance_id)
            raise RunnerStartError(f"Runner startup process not found on {instance.instance_id}")
        logger.info("Runner startup process found to be healthy on %s", instance.instance_id)

    @retry(tries=5, delay=60, local_logger=logger)
    def _wait_runner_running(self, instance: OpenstackInstance) -> None:
        """Wait until runner is running.

        Args:
            instance: The runner instance.

        Raises:
            RunnerStartError: The runner process was not found on the runner.
        """
        try:
            ssh_conn = self._openstack_cloud.get_ssh_connection(instance)
        except SSHError as err:
            raise RunnerStartError(
                f"Failed to SSH connect to {instance.instance_id} openstack runner"
            ) from err

        try:
            healthy = health_checks.check_active_runner(
                ssh_conn=ssh_conn, instance=instance, accept_finished_job=True
            )
        except OpenstackHealthCheckError as exc:
            raise RunnerStartError(
                f"Failed to check health of runner process on {instance.instance_id}"
            ) from exc
        if not healthy:
            logger.info("Runner %s not considered healthy", instance.instance_id)
            raise RunnerStartError(
                f"Runner {instance.instance_id} failed to initialize after starting"
            )

        logger.info("Runner %s found to be healthy", instance.instance_id)

    @staticmethod
    def _run_runner_removal_script(
        instance_id: InstanceID, ssh_conn: SSHConnection, remove_token: str
    ) -> None:
        """Run Github runner removal script.

        Args:
            instance_id: The name of the runner instance.
            ssh_conn: The SSH connection to the runner instance.
            remove_token: The GitHub instance removal token.

        Raises:
            _GithubRunnerRemoveError: Unable to remove runner from GitHub.
        """
        try:
            result = ssh_conn.run(
                f"{_CONFIG_SCRIPT_PATH} remove --token {remove_token}",
                warn=True,
                timeout=60,
                hide=True,
            )
            if result.ok:
                return

            logger.warning(
                (
                    "Unable to run removal script on instance %s, "
                    "exit code: %s, stdout: %s, stderr: %s"
                ),
                instance_id,
                result.return_code,
                result.stdout,
                result.stderr,
            )
            raise _GithubRunnerRemoveError(f"Failed to remove runner {instance_id} from Github.")
        except (
            paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.SSHException,
            TimeoutError,
        ) as exc:
            raise _GithubRunnerRemoveError(
                f"Failed to remove runner {instance_id} from Github."
            ) from exc

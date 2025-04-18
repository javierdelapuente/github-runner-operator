#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module responsible for consuming jobs from the message queue."""
import contextlib
import logging
import signal
import sys
from contextlib import closing
from time import sleep
from types import FrameType
from typing import Generator, cast

from kombu import Connection, Message
from kombu.exceptions import KombuError
from kombu.simple import SimpleQueue
from pydantic import BaseModel, HttpUrl, ValidationError, validator

from github_runner_manager.manager.models import RunnerMetadata
from github_runner_manager.manager.runner_manager import RunnerManager
from github_runner_manager.platform.platform_provider import PlatformProvider
from github_runner_manager.reactive.types_ import QueueConfig

logger = logging.getLogger(__name__)

Labels = set[str]

# This control message is for testing. The reactive process will stop consuming messages
# when the message is sent. This message does not come from the router.
END_PROCESSING_PAYLOAD = "__END__"


class JobDetails(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        url: The URL of the job to check its status.
    """

    labels: Labels
    url: HttpUrl

    @validator("url")
    @classmethod
    def check_job_url_path_is_not_empty(cls, v: HttpUrl) -> HttpUrl:
        """Check that the job_url path is not empty.

        Args:
            v: The job_url to check.

        Returns:
            The job_url if it is valid.

        Raises:
            ValueError: If the job_url path is empty.
        """
        if not v.path:
            raise ValueError("path must be provided")
        return v


class JobError(Exception):
    """Raised when a job error occurs."""


class QueueError(Exception):
    """Raised when an error when communicating with the queue occurs."""


def get_queue_size(queue_config: QueueConfig) -> int:
    """Get the size of the message queue.

    Args:
        queue_config: The configuration for the message queue.

    Returns:
        The size of the queue.

    Raises:
        QueueError: If an error when communicating with the queue occurs.
    """
    try:
        with Connection(queue_config.mongodb_uri) as conn:
            with closing(SimpleQueue(conn, queue_config.queue_name)) as simple_queue:
                return simple_queue.qsize()
    except KombuError as exc:
        raise QueueError("Error when communicating with the queue") from exc


def consume(
    queue_config: QueueConfig,
    runner_manager: RunnerManager,
    platform_provider: PlatformProvider,
    supported_labels: Labels,
) -> None:
    """Consume a job from the message queue.

    Log the job details and acknowledge the message.
    If the job details are invalid, reject the message and raise an error.

    Args:
        queue_config: The configuration for the message queue.
        runner_manager: The runner manager used to create the runner.
        platform_provider: Platform provider.
        supported_labels: The supported labels for the runner. If the job has unsupported labels,
            the message is requeued.

    Raises:
        QueueError: If an error when communicating with the queue occurs.
    """
    try:
        with (
            Connection(queue_config.mongodb_uri) as conn,
            closing(SimpleQueue(conn, queue_config.queue_name)) as simple_queue,
            signal_handler(signal.SIGTERM),
        ):
            # Get messages until we can spawn a runner.
            while True:
                msg = simple_queue.get(block=True)
                # Payload to stop the processing
                if msg.payload == END_PROCESSING_PAYLOAD:
                    msg.ack()
                    break
                job_details = _parse_job_details(msg)
                if not _validate_labels(
                    labels=job_details.labels, supported_labels=supported_labels
                ):
                    logger.error(
                        "Found unsupported job labels in %s. "
                        "Will not spawn a runner and reject the message.",
                        job_details.labels,
                    )
                    # We currently do not expect this to happen, but we should handle it.
                    # We do not want to requeue the message as it will be rejected again.
                    # This may change in the future when messages for multiple
                    # flavours are sent to the same queue.
                    msg.reject(requeue=False)
                    continue
                # Defaults as github, needed to select the platform provider.
                metadata = RunnerMetadata()
                if platform_provider.check_job_been_picked_up(
                    metadata=metadata, job_url=job_details.url
                ):
                    msg.ack()
                    continue
                _spawn_runner(
                    runner_manager=runner_manager,
                    job_url=job_details.url,
                    msg=msg,
                    platform_provider=platform_provider,
                )
                break
    except KombuError as exc:
        raise QueueError("Error when communicating with the queue") from exc


def _parse_job_details(msg: Message) -> JobDetails:
    """Parse JobDetails from a message."""
    try:
        job_details = cast(JobDetails, JobDetails.parse_raw(msg.payload))
    except ValidationError as exc:
        logger.error("Found invalid job details, will reject the message.")
        msg.reject(requeue=False)
        raise JobError(f"Invalid job details: {msg.payload}") from exc
    logger.info(
        "Received job with labels %s and job_url %s",
        job_details.labels,
        job_details.url,
    )
    return job_details


def _validate_labels(labels: Labels, supported_labels: Labels) -> bool:
    """Validate the labels of the job.

    Args:
        labels: The labels of the job.
        supported_labels: The supported labels for the runner.

    Returns:
        True if the labels are valid, False otherwise.
    """
    return {label.lower() for label in labels} <= {label.lower() for label in supported_labels}


def _spawn_runner(
    runner_manager: RunnerManager,
    job_url: HttpUrl,
    msg: Message,
    platform_provider: PlatformProvider,
) -> None:
    """Spawn a runner.

    A runner is only spawned if the job has not yet been picked up by a runner.
    After spawning a runner, it is checked if the job has been picked up.

    If the job has been picked up, the message is acknowledged.
    If the job has not been picked up after 5 minutes, the message is rejected and requeued.

    Args:
        runner_manager: The runner manager to use.
        job_url: The URL of the job.
        msg: The message to acknowledge or reject.
        platform_provider: Platform provider.
    """
    metadata = RunnerMetadata()
    instance_ids = runner_manager.create_runners(1, metadata=metadata, reactive=True)
    if not instance_ids:
        logger.error("Failed to spawn a runner. Will reject the message.")
        msg.reject(requeue=True)
        return
    for _ in range(10):
        if platform_provider.check_job_been_picked_up(metadata=metadata, job_url=job_url):
            msg.ack()
            break
        sleep(30)
    else:
        msg.reject(requeue=True)


@contextlib.contextmanager
def signal_handler(signal_code: signal.Signals) -> Generator[None, None, None]:
    """Set a signal handler and after the context, restore the default handler.

    The signal handler exits the process.

    Args:
        signal_code: The signal code to handle.
    """
    _set_signal_handler(signal_code)
    try:
        yield
    finally:
        _restore_signal_handler(signal_code)


def _set_signal_handler(signal_code: signal.Signals) -> None:
    """Set a signal handler which exits the process.

    Args:
        signal_code: The signal code to handle.
    """

    def sigterm_handler(signal_code: int, _: FrameType | None) -> None:
        """Handle a signal.

        Call sys.exit with the signal code. Kombu should automatically
        requeue unacknowledged messages.

        Args:
            signal_code: The signal code to handle.
        """
        print(
            f"Signal '{signal.strsignal(signal_code)}' received. Will terminate.", file=sys.stderr
        )
        sys.exit(signal_code)

    signal.signal(signal_code, sigterm_handler)


def _restore_signal_handler(signal_code: signal.Signals) -> None:
    """Restore the default signal handler.

    Args:
        signal_code: The signal code to restore.
    """
    signal.signal(signal_code, signal.SIG_DFL)

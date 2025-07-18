# coding: utf-8

"""
    Job Manager API

    A modern job management system

    The version of the OpenAPI document: 2.0.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


import unittest

from jobmanager_client.api.jobs_api import JobsApi  # noqa: E501


class TestJobsApi(unittest.TestCase):
    """JobsApi unit test stubs"""

    def setUp(self) -> None:
        self.api = JobsApi()

    def tearDown(self) -> None:
        self.api.api_client.close()

    def test_create_job_v1_jobs_post(self) -> None:
        """Test case for create_job_v1_jobs_post

        Create Job  # noqa: E501
        """
        pass

    def test_download_object_v1_jobs_job_id_object_object_name_get(self) -> None:
        """Test case for download_object_v1_jobs_job_id_object_object_name_get

        Download Object  # noqa: E501
        """
        pass

    def test_generate_token_v1_jobs_job_id_token_post(self) -> None:
        """Test case for generate_token_v1_jobs_job_id_token_post

        Generate Token  # noqa: E501
        """
        pass

    def test_get_health_v1_jobs_job_id_health_get(self) -> None:
        """Test case for get_health_v1_jobs_job_id_health_get

        Get Health  # noqa: E501
        """
        pass

    def test_get_job_v1_jobs_job_id_get(self) -> None:
        """Test case for get_job_v1_jobs_job_id_get

        Get Job  # noqa: E501
        """
        pass

    def test_get_jobs_v1_jobs_get(self) -> None:
        """Test case for get_jobs_v1_jobs_get

        Get Jobs  # noqa: E501
        """
        pass

    def test_update_health_v1_jobs_job_id_health_put(self) -> None:
        """Test case for update_health_v1_jobs_job_id_health_put

        Update Health  # noqa: E501
        """
        pass

    def test_update_job_v1_jobs_job_id_put(self) -> None:
        """Test case for update_job_v1_jobs_job_id_put

        Update Job  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()

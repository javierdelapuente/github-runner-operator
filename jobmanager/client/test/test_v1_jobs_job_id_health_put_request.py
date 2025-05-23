# coding: utf-8

"""
    Job Manager API

    API for managing jobs and builders within the Job Manager system.

    The version of the OpenAPI document: 1.0.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


import unittest
import datetime

from jobmanager_client.models.v1_jobs_job_id_health_put_request import V1JobsJobIdHealthPutRequest  # noqa: E501

class TestV1JobsJobIdHealthPutRequest(unittest.TestCase):
    """V1JobsJobIdHealthPutRequest unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional) -> V1JobsJobIdHealthPutRequest:
        """Test V1JobsJobIdHealthPutRequest
            include_option is a boolean, when False only required
            params are included, when True both required and
            optional params are included """
        # uncomment below to create an instance of `V1JobsJobIdHealthPutRequest`
        """
        model = V1JobsJobIdHealthPutRequest()  # noqa: E501
        if include_optional:
            return V1JobsJobIdHealthPutRequest(
                label = '',
                cpu_usage = '',
                ram_usage = '',
                disk_usage = '',
                status = ''
            )
        else:
            return V1JobsJobIdHealthPutRequest(
        )
        """

    def testV1JobsJobIdHealthPutRequest(self):
        """Test V1JobsJobIdHealthPutRequest"""
        # inst_req_only = self.make_instance(include_optional=False)
        # inst_req_and_optional = self.make_instance(include_optional=True)

if __name__ == '__main__':
    unittest.main()

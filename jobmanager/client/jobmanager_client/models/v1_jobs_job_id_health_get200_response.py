# coding: utf-8

"""
    Job Manager API

    API for managing jobs and builders within the Job Manager system.

    The version of the OpenAPI document: 1.0.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from __future__ import annotations
import pprint
import re  # noqa: F401
import json


from typing import Optional
from pydantic import BaseModel, StrictStr
from jobmanager_client.models.job import Job

class V1JobsJobIdHealthGet200Response(BaseModel):
    """
    V1JobsJobIdHealthGet200Response
    """
    label: Optional[StrictStr] = None
    cpu_usage: Optional[StrictStr] = None
    ram_usage: Optional[StrictStr] = None
    disk_usage: Optional[StrictStr] = None
    status: Optional[StrictStr] = None
    job: Optional[Job] = None
    __properties = ["label", "cpu_usage", "ram_usage", "disk_usage", "status", "job"]

    class Config:
        """Pydantic configuration"""
        allow_population_by_field_name = True
        validate_assignment = True

    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.dict(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> V1JobsJobIdHealthGet200Response:
        """Create an instance of V1JobsJobIdHealthGet200Response from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self):
        """Returns the dictionary representation of the model using alias"""
        _dict = self.dict(by_alias=True,
                          exclude={
                          },
                          exclude_none=True)
        # override the default output from pydantic by calling `to_dict()` of job
        if self.job:
            _dict['job'] = self.job.to_dict()
        return _dict

    @classmethod
    def from_dict(cls, obj: dict) -> V1JobsJobIdHealthGet200Response:
        """Create an instance of V1JobsJobIdHealthGet200Response from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return V1JobsJobIdHealthGet200Response.parse_obj(obj)

        _obj = V1JobsJobIdHealthGet200Response.parse_obj({
            "label": obj.get("label"),
            "cpu_usage": obj.get("cpu_usage"),
            "ram_usage": obj.get("ram_usage"),
            "disk_usage": obj.get("disk_usage"),
            "status": obj.get("status"),
            "job": Job.from_dict(obj.get("job")) if obj.get("job") is not None else None
        })
        return _obj



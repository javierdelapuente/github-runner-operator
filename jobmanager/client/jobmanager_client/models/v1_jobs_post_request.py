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


from typing import Any, Dict, List, Optional
from pydantic import BaseModel, StrictStr, conlist

class V1JobsPostRequest(BaseModel):
    """
    V1JobsPostRequest
    """
    repository_url: Optional[StrictStr] = None
    repository_ref: Optional[StrictStr] = None
    architecture: Optional[StrictStr] = None
    vm_dependecies: Optional[Dict[str, Any]] = None
    commands: Optional[conlist(StrictStr)] = None
    secrets: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, Any]] = None
    artifacts_dir: Optional[StrictStr] = None
    topology: Optional[StrictStr] = None
    vm_size: Optional[StrictStr] = None
    __properties = ["repository_url", "repository_ref", "architecture", "vm_dependecies", "commands", "secrets", "environment", "artifacts_dir", "topology", "vm_size"]

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
    def from_json(cls, json_str: str) -> V1JobsPostRequest:
        """Create an instance of V1JobsPostRequest from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self):
        """Returns the dictionary representation of the model using alias"""
        _dict = self.dict(by_alias=True,
                          exclude={
                          },
                          exclude_none=True)
        # set to None if vm_dependecies (nullable) is None
        # and __fields_set__ contains the field
        if self.vm_dependecies is None and "vm_dependecies" in self.__fields_set__:
            _dict['vm_dependecies'] = None

        # set to None if secrets (nullable) is None
        # and __fields_set__ contains the field
        if self.secrets is None and "secrets" in self.__fields_set__:
            _dict['secrets'] = None

        # set to None if environment (nullable) is None
        # and __fields_set__ contains the field
        if self.environment is None and "environment" in self.__fields_set__:
            _dict['environment'] = None

        # set to None if topology (nullable) is None
        # and __fields_set__ contains the field
        if self.topology is None and "topology" in self.__fields_set__:
            _dict['topology'] = None

        # set to None if vm_size (nullable) is None
        # and __fields_set__ contains the field
        if self.vm_size is None and "vm_size" in self.__fields_set__:
            _dict['vm_size'] = None

        return _dict

    @classmethod
    def from_dict(cls, obj: dict) -> V1JobsPostRequest:
        """Create an instance of V1JobsPostRequest from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return V1JobsPostRequest.parse_obj(obj)

        _obj = V1JobsPostRequest.parse_obj({
            "repository_url": obj.get("repository_url"),
            "repository_ref": obj.get("repository_ref"),
            "architecture": obj.get("architecture"),
            "vm_dependecies": obj.get("vm_dependecies"),
            "commands": obj.get("commands"),
            "secrets": obj.get("secrets"),
            "environment": obj.get("environment"),
            "artifacts_dir": obj.get("artifacts_dir"),
            "topology": obj.get("topology"),
            "vm_size": obj.get("vm_size")
        })
        return _obj



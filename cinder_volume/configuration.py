# Copyright 2024 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Configuration module for the cinder-volume snap.

This module holds the definition of all configuration options the snap
takes as input from `snap set`.
"""

import pydantic
import pydantic.alias_generators


def to_kebab(value: str) -> str:
    return pydantic.alias_generators.to_snake(value).replace("_", "-")


class ParentConfig(pydantic.BaseModel):
    """Set common model configuration for all models."""

    model_config = pydantic.ConfigDict(
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )


class DatabaseConfiguration(ParentConfig):
    url: str


class RabbitMQConfiguration(ParentConfig):
    url: str


class CinderConfiguration(ParentConfig):
    project_id: str
    user_id: str
    image_volume_cache_enabled: bool = False
    image_volume_cache_max_size_gb: int = 0
    image_volume_cache_max_count: int = 0
    cluster: str | None = None


class Settings(ParentConfig):
    debug: bool = False
    enable_telemetry_notifications: bool = False


class BaseConfiguration(ParentConfig):
    """Base configuration class.

    This class should be the basis of downstream snaps.
    """

    settings: Settings = Settings()
    database: DatabaseConfiguration
    rabbitmq: RabbitMQConfiguration
    cinder: CinderConfiguration


class BaseBackendConfiguration(ParentConfig):
    image_volume_cache_enabled: bool | None = None
    image_volume_cache_max_size_gb: int | None = None
    image_volume_cache_max_count: int | None = None
    volume_dd_blocksize: int = 4096
    volume_backend_name: str


class CephConfiguration(BaseBackendConfiguration):
    rbd_exclusive_cinder_pool: bool = True
    report_discard_supported: bool = True
    rbd_flatten_volume_from_snapshot: bool = False
    auth: str = "cephx"
    mon_hosts: str
    rbd_pool: str
    rbd_user: str
    rbd_secret_uuid: str
    rbd_key: str


class Configuration(BaseConfiguration):
    """Holding additional configuration for the generic snap.

    This class is specific to this snap and should not be used in
    downstream snaps.
    """

    ceph: dict[str, CephConfiguration] = {}

    @pydantic.field_validator("ceph")
    def backend_validator(cls, v):
        known_backend_names = set()
        known_pools = set()

        for backend in v.values():
            if backend.volume_backend_name in known_backend_names:
                raise ValueError(
                    f"Duplicate backend name: {backend.volume_backend_name}"
                )
            known_backend_names.add(backend.volume_backend_name)
            if backend.rbd_pool in known_pools:
                raise ValueError(f"Duplicate pool: {backend.rbd_pool}")
            known_pools.add(backend.rbd_pool)

        return v

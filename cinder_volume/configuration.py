# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Configuration module for the cinder-volume snap.

This module holds the definition of all configuration options the snap
takes as input from `snap set`.
"""

import pydantic
import pydantic.alias_generators
from pydantic import Field


def to_kebab(value: str) -> str:
    """Convert a string to kebab-case."""
    return pydantic.alias_generators.to_snake(value).replace("_", "-")


class ParentConfig(pydantic.BaseModel):
    """Set common model configuration for all models."""

    model_config = pydantic.ConfigDict(
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=to_kebab,
        ),
    )


class DatabaseConfiguration(ParentConfig):
    """Configuration for database connection."""

    url: str


class RabbitMQConfiguration(ParentConfig):
    """Configuration for RabbitMQ connection."""

    url: str


class CinderConfiguration(ParentConfig):
    """Configuration for Cinder service."""

    project_id: str
    user_id: str
    image_volume_cache_enabled: bool = False
    image_volume_cache_max_size_gb: int = 0
    image_volume_cache_max_count: int = 0
    default_volume_type: str | None = None
    cluster: str | None = None


class Settings(ParentConfig):
    """General settings for the snap."""

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
    """Base configuration for storage backends."""

    @pydantic.model_validator(mode="before")
    @classmethod
    def convert_extra_fields(cls, data):
        """Convert kebab-case keys to snake_case for extra fields."""
        if isinstance(data, dict):
            converted = {}
            defined_fields = set(cls.model_fields.keys())
            for key, value in data.items():
                snake_key = key.replace("-", "_")
                if snake_key in defined_fields:
                    # Defined field - keep original key for alias generator
                    converted[key] = value
                else:
                    # Extra field - convert to snake_case
                    converted[snake_key] = value
            return converted
        return data

    image_volume_cache_enabled: bool | None = None
    image_volume_cache_max_size_gb: int | None = None
    image_volume_cache_max_count: int | None = None
    volume_dd_blocksize: int = Field(default=4096, ge=512)
    volume_backend_name: str
    driver_ssl_cert: str | None = None


class CephConfiguration(BaseBackendConfiguration):
    """Configuration for Ceph storage backend."""

    rbd_exclusive_cinder_pool: bool = True
    report_discard_supported: bool = True
    rbd_flatten_volume_from_snapshot: bool = False
    auth: str = "cephx"
    mon_hosts: str
    rbd_pool: str
    rbd_user: str
    rbd_secret_uuid: str
    rbd_key: str


class HitachiConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Hitachi VSP** Cinder driver.

    Defaults follow the upstream driver recommendations/documentation.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Mandatory connection parameters
    san_ip: pydantic.IPvAnyAddress
    san_username: str
    san_password: str
    hitachi_storage_id: str | int
    hitachi_pools: str  # comma‑separated list

    # Driver selection
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class PureConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Pure Storage FlashArray** Cinder driver.

    This configuration supports iSCSI, Fibre Channel, and NVMe protocols
    with advanced features like replication, TriSync, and auto-eradication.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # FlashArray management IP/FQDN
    pure_api_token: str  # REST API authorization token
    protocol: str = Field(default="fc", pattern="^(iscsi|fc|nvme)$")


class DellSCConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell Storage Center** Cinder driver.

    This configuration supports iSCSI and Fibre Channel protocols
    with dual DSM support, network filtering, and comprehensive timeout controls.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # Dell Storage Center management IP/FQDN
    san_login: str  # SAN management username
    san_password: str  # SAN management password
    dell_sc_ssn: int = Field(default=64702)  # Storage Center System Serial Number
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")


class Configuration(BaseConfiguration):
    """Holding additional configuration for the generic snap.

    This class is specific to this snap and should not be used in
    downstream snaps.
    """

    ceph: dict[str, CephConfiguration] = {}
    hitachi: dict[str, HitachiConfiguration] = {}
    pure: dict[str, PureConfiguration] = {}
    dellsc: dict[str, DellSCConfiguration] = {}

    @pydantic.model_validator(mode="after")
    def validate_unique_backend_names(self):
        """Validate that all backend names are unique across all backend types."""
        backend_names = set()
        ceph_pools = set()

        # Check all backend types for unique backend names
        for backend_type, backends in [
            ("ceph", self.ceph),
            ("hitachi", self.hitachi),
            ("pure", self.pure),
            ("dellsc", self.dellsc),
        ]:
            for backend_key, backend in backends.items():
                # Check for duplicate backend names across all types
                if backend.volume_backend_name in backend_names:
                    raise ValueError(
                        f"Duplicate backend name '{backend.volume_backend_name}' "
                        f"found in {backend_type} backend '{backend_key}'"
                    )
                backend_names.add(backend.volume_backend_name)

                # Check for duplicate Ceph pools (only applies to Ceph backends)
                if backend_type == "ceph" and hasattr(backend, "rbd_pool"):
                    if backend.rbd_pool in ceph_pools:
                        raise ValueError(
                            f"Duplicate Ceph pool '{backend.rbd_pool}' "
                            f"found in backend '{backend_key}'"
                        )
                    ceph_pools.add(backend.rbd_pool)

        return self

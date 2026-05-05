# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Configuration module for the cinder-volume snap.

This module holds the definition of all configuration options the snap
takes as input from `snap set`.
"""

import base64
import binascii
import typing

import pydantic
import pydantic.alias_generators
from pydantic import Field, model_validator


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
    region_name: str | None = None
    image_volume_cache_enabled: bool = False
    image_volume_cache_max_size_gb: int = 0
    image_volume_cache_max_count: int = 0
    default_volume_type: str | None = None
    cluster: str | None = None


class Settings(ParentConfig):
    """General settings for the snap."""

    debug: bool = False
    enable_telemetry_notifications: bool = False


class CAConfiguration(ParentConfig):
    """Configuration for the main CA bundle used by the snap."""

    bundle: str | None = None

    @pydantic.field_validator("bundle", mode="before")
    @classmethod
    def decode_bundle(cls, value: str | None) -> str | None:
        """Decode the base64-encoded bundle payload from snap config."""
        if value is None or value == "":
            return None
        value = value.strip()
        try:
            return base64.b64decode(value, validate=True).decode()
        except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Invalid base64-encoded CA bundle") from exc


class BaseConfiguration(ParentConfig):
    """Base configuration class.

    This class should be the basis of downstream snaps.
    """

    settings: Settings = Settings()
    ca: CAConfiguration = CAConfiguration()
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
    san_login: str
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
    san_ip: pydantic.IPvAnyAddress  # Dell DSM management IP/FQDN
    san_login: str  # DSM management username
    san_password: str  # DSM management password
    dell_sc_ssn: int  # Storage Center System Serial Number
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")
    enable_unsupported_driver: typing.Literal[True]

    # Optional secondary DSM settings
    secondary_san_ip: pydantic.IPvAnyAddress | None = None
    secondary_san_login: str | None = None
    secondary_san_password: str | None = None


class DellpowerstoreConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell PowerStore** Cinder driver.

    This configuration supports iSCSI, Fibre Channel and NVMe-TCP protocols.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # Dell PowerStore management IP/FQDN
    san_login: str  # Dell PowerStore management username
    san_password: str  # Dell PowerStore management password
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")


class HpethreeparConfiguration(BaseBackendConfiguration):
    """All options recognised by the **HPE Three Par Storage** Cinder driver.

    This configuration supports iSCSI and Fibre Channel protocols.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # HPE 3Par san controller IP
    san_login: str  # HPE 3Par san controller username
    san_password: str  # HPE 3Par san controller password
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")


class SolidfireConfiguration(BaseBackendConfiguration):
    """All options recognised by the **NetApp SolidFire** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller


class DatacoreConfiguration(BaseBackendConfiguration):
    """All options recognised by the **DataCoreVolume** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # No additional required fields beyond BaseBackendConfiguration.


class DateraConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Datera** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller


class DellpowermaxConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell PowerMax** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class DellpowervaultConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell PowerVault** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class DellxtremioConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell XtremIO** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    protocol: str = Field(default="iscsi", pattern="^(iscsi|fc)$")
    enable_unsupported_driver: typing.Literal[True]


class FujitsueternusdxConfiguration(BaseBackendConfiguration):
    """All options recognised by the **FJDX FC** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    fujitsu_passwordless: str  # Use SSH key to connect to storage.
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class HpexpConfiguration(BaseBackendConfiguration):
    """All options recognised by the **HPE XP** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class IbmflashsystemcommonConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Ibmflashsystemcommon** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    enable_unsupported_driver: typing.Literal[True]


class IbmflashsystemiscsiConfiguration(BaseBackendConfiguration):
    """All options recognised by the **FlashSystem iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # No additional required fields beyond BaseBackendConfiguration.


class IbmgpfsConfiguration(BaseBackendConfiguration):
    """All options recognised by the **GPFS** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    gpfs_user_password: str  # Password for GPFS node user.
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller


class IbmibmstorageConfiguration(BaseBackendConfiguration):
    """All options recognised by the **IBMStorage** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller


class IbmstorwizesvcConfiguration(BaseBackendConfiguration):
    """All options recognised by the **StorwizeSVC FC** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class InfinidatConfiguration(BaseBackendConfiguration):
    """All options recognised by the **INFINIDAT InfiniBox** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    infinidat_pool_name: typing.Optional[str] = None  # Pool name on InfiniBox
    protocol: typing.Optional[str] = Field(
        default=None, pattern="^(iscsi|fc)$"
    )  # Transport protocol
    infinidat_iscsi_netspaces: typing.Optional[str] = None  # iSCSI netspace names

    @model_validator(mode="after")
    def _iscsi_requires_netspaces(self) -> "InfinidatConfiguration":
        """Require infinidat_iscsi_netspaces when protocol is iscsi."""
        if self.protocol == "iscsi" and not self.infinidat_iscsi_netspaces:
            raise ValueError(
                "infinidat_iscsi_netspaces is required when protocol is iscsi"
            )
        return self


class Inspuras13000Configuration(BaseBackendConfiguration):
    """All options recognised by the **AS13000** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    as_13000_token_available_time: (
        str  # The effective time of token validity in seconds.
    )
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller


class InspurinstorageConfiguration(BaseBackendConfiguration):
    """All options recognised by the **InStorageMCS FC** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class KaminarioConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Kaminario iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # No additional required fields beyond BaseBackendConfiguration.


class LinstorConfiguration(BaseBackendConfiguration):
    """All options recognised by the **LinstorIscsi** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # No additional required fields beyond BaseBackendConfiguration.


class MacrosanConfiguration(BaseBackendConfiguration):
    """All options recognised by the **MacroSAN iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    macrosan_sdas_password: str  # MacroSAN sdas devices' password
    macrosan_replication_password: str  # MacroSAN replication devices' password
    protocol: str = Field(default="iscsi", pattern="^(iscsi|fc)$")


class NecvConfiguration(BaseBackendConfiguration):
    """All options recognised by the **VStorage FC** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class NetappConfiguration(BaseBackendConfiguration):
    """All options recognised by the **NetApp ONTAP** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    netapp_ca_certificate_file: str  # Absolute path to the trusted CA certificate file.
    protocol: str = Field(default="iscsi", pattern="^(iscsi|nvme)$")


class NexentaConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Nexenta iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    nexenta_rest_password: str  # Password to connect to NexentaEdge.


class NimbleConfiguration(BaseBackendConfiguration):
    """All options recognised by the **HPE Nimble Storage** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    protocol: str = Field(default="iscsi", pattern="^(iscsi|fc)$")


class OpeneConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Jovian iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    chap_password_len: int  # Length of the random string for CHAP password.


class ProphetstorConfiguration(BaseBackendConfiguration):
    """All options recognised by the **DPL FC** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")
    enable_unsupported_driver: typing.Literal[True]


class QnapConfiguration(BaseBackendConfiguration):
    """All options recognised by the **QNAP Storage** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    enable_unsupported_driver: typing.Literal[True]


class SandstoneConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Sds iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # No additional required fields beyond BaseBackendConfiguration.


class StxConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Stx** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # No additional required fields beyond BaseBackendConfiguration.


class SynologyConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Syno iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    synology_password: str  # Password of administrator for logging in Synology storage.
    synology_one_time_pass: (
        str  # One-time password for OTP-enabled Synology admin login.
    )


class Toyouacs5000Configuration(BaseBackendConfiguration):
    """All options recognised by the **Acs5000 FC** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # IP address of SAN controller
    san_login: str  # Username for SAN controller
    san_password: str  # Password for SAN controller
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class VeritasaccessConfiguration(BaseBackendConfiguration):
    """All options recognised by the **ACCESSIscsi** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    enable_unsupported_driver: typing.Literal[True]


class YadroConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Tatlin FCVolume** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class ZadaraConfiguration(BaseBackendConfiguration):
    """All options recognised by the **ZadaraVPSA iSCSI** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow driver-specific fields not listed here
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    zadara_access_key: str  # VPSA access key


class Configuration(BaseConfiguration):
    """Holding additional configuration for the generic snap.

    This class is specific to this snap and should not be used in
    downstream snaps.
    """

    ceph: dict[str, CephConfiguration] = {}
    hitachi: dict[str, HitachiConfiguration] = {}
    pure: dict[str, PureConfiguration] = {}
    dellsc: dict[str, DellSCConfiguration] = {}
    dellpowerstore: dict[str, DellpowerstoreConfiguration] = {}
    hpethreepar: dict[str, HpethreeparConfiguration] = {}

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
            ("hpethreepar", self.hpethreepar),
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

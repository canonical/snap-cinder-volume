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

from __future__ import annotations

import pydantic
from pydantic import Field, ValidationInfo, field_validator
import pydantic.alias_generators

__all__ = [
    "DatabaseConfiguration",
    "RabbitMQConfiguration",
    "CinderConfiguration",
    "CephConfiguration",
    "HitachiConfiguration",
    "PureConfiguration",
    "DellSCConfiguration",
    "Configuration",
]


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
    default_volume_type: str | None = None
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
    volume_dd_blocksize: int = Field(default=4096, ge=512)
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

class HitachiConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Hitachi VSP** Cinder driver.

    Defaults follow the upstream driver recommendations/documentation.
    """

    # Mandatory connection parameters
    san_ip: str
    san_login: str
    san_password: str
    hitachi_storage_id: str | int
    hitachi_pools: str  # comma‑separated list

    # Driver selection 
    protocol: str = Field(default="FC", pattern=r"^(FC|iSCSI)$")

    # Copy & replication knobs
    hitachi_default_copy_method: str = "FULL"  # or "THIN"
    hitachi_copy_speed: int = Field(default=3, ge=1, le=15)
    hitachi_copy_check_interval: int = Field(default=3, ge=1, le=600)
    hitachi_async_copy_check_interval: int = Field(default=10, ge=1, le=600)

    # Retry / timeout controls
    hitachi_exec_retry_interval: int = Field(default=5, ge=1)
    hitachi_extend_timeout: int = Field(default=600, ge=1)

    # Authentication (iSCSI only)
    hitachi_auth_method: str | None = None  # "CHAP" or "none"
    hitachi_auth_user: str | None = None
    hitachi_auth_password: str | None = None
    hitachi_add_chap_user: bool = False

    # Host‑group & zoning
    hitachi_group_request: bool = False
    hitachi_group_delete: bool = False
    hitachi_group_create: bool = False
    hitachi_group_range: str | None = None
    hitachi_group_name_format: str | None = None

    hitachi_target_ports: str | None = '[]' # controller nodes
    hitachi_compute_target_ports: str | None = None  # compute nodes
    hitachi_zoning_request: bool = False

    # HORCM (legacy pair tools)
    hitachi_horcm_numbers: str | None = None
    hitachi_horcm_add_conf: bool = False
    hitachi_horcm_user: str | None = None
    hitachi_horcm_password: str | None = None
    hitachi_horcm_resource_lock_timeout: int = Field(default=600, ge=0, le=7200)

    # Array & pool ranges
    hitachi_ldev_range: str | None = None
    hitachi_pool_id: int | None = None
    hitachi_thin_pool_id: int | None = None
    hitachi_unit_name: str | None = None
    hitachi_serial_number: str | None = None

    # Miscellaneous knobs
    hitachi_discard_zero_page: bool = True
    hitachi_lock_timeout: int = Field(default=7200, ge=0)
    hitachi_lun_retry_interval: int = Field(default=1, ge=1)
    hitachi_lun_timeout: int = Field(default=50, ge=1)
    hitachi_path_group_id: int = Field(default=0, ge=0, le=255)
    hitachi_port_scheduler: bool = False
    hitachi_pair_target_number: int = Field(default=0, ge=0, le=99)
    hitachi_quorum_disk_id: int | None = None

    # Replication settings
    hitachi_replication_copy_speed: int = Field(default=3, ge=1, le=15)
    hitachi_replication_number: int = Field(default=0, ge=0, le=255)
    hitachi_replication_status_check_long_interval: int = 600
    hitachi_replication_status_check_short_interval: int = 5
    hitachi_replication_status_check_timeout: int = 86400

    # REST/CLI time‑outs & keep‑alive
    hitachi_rest_another_ldev_mapped_retry_timeout: int = 600
    hitachi_rest_connect_timeout: int = 30
    hitachi_rest_disable_io_wait: bool = True
    hitachi_rest_get_api_response_timeout: int = 1800
    hitachi_rest_job_api_response_timeout: int = 1800
    hitachi_rest_keep_session_loop_interval: int = 180
    hitachi_rest_pair_target_ports: str | None = None
    hitachi_rest_server_busy_timeout: int = 7200
    hitachi_rest_tcp_keepalive: bool = True
    hitachi_rest_tcp_keepcnt: int = 4
    hitachi_rest_tcp_keepidle: int = 60
    hitachi_rest_tcp_keepintvl: int = 15
    hitachi_rest_timeout: int = 30

    # Restore / state transition
    hitachi_restore_timeout: int = 86400
    hitachi_state_transition_timeout: int = 900
    hitachi_set_mirror_reserve_attribute: bool = True

    # Snap / capacity saving
    hitachi_snap_pool: str | None = None

    # Global‑Active Device (mirror)
    hitachi_mirror_auth_password: str | None = None
    hitachi_mirror_auth_user: str | None = None
    hitachi_mirror_compute_target_ports: str | None = None
    hitachi_mirror_ldev_range: str | None = None
    hitachi_mirror_pair_target_number: int = Field(default=0, ge=0, le=99)
    hitachi_mirror_pool: str | None = None
    hitachi_mirror_rest_api_ip: str | None = None
    hitachi_mirror_rest_api_port: int = Field(default=443, ge=0, le=65535)
    hitachi_mirror_rest_pair_target_ports: str | None = None
    hitachi_mirror_rest_password: str | None = None
    hitachi_mirror_rest_user: str | None = None
    hitachi_mirror_snap_pool: str | None = None
    hitachi_mirror_ssl_cert_path: str | None = None
    hitachi_mirror_ssl_cert_verify: bool = False
    hitachi_mirror_storage_id: str | None = None
    hitachi_mirror_target_ports: str | None = None
    hitachi_mirror_use_chap_auth: bool = False


class PureConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Pure Storage FlashArray** Cinder driver.
    
    This configuration supports iSCSI, Fibre Channel, and NVMe protocols
    with advanced features like replication, TriSync, and auto-eradication.
    """
    
    # Core required fields
    san_ip: str  # FlashArray management IP/FQDN
    pure_api_token: str  # REST API authorization token
    protocol: str = Field(default="fc", pattern="^(iscsi|fc|nvme)$")
    
    # Protocol-specific options
    pure_iscsi_cidr: str = "0.0.0.0/0"
    pure_iscsi_cidr_list: list[str] | None = None
    pure_nvme_cidr: str = "0.0.0.0/0" 
    pure_nvme_cidr_list: list[str] | None = None
    pure_nvme_transport: str = Field(default="roce", pattern="^(roce|tcp)$")
    
    # Advanced features
    pure_host_personality: str | None = Field(
        default=None,
        pattern="^(aix|esxi|hitachi-vsp|hpux|oracle-vm-server|solaris|vms)$"
    )
    pure_automatic_max_oversubscription_ratio: bool = True
    pure_eradicate_on_delete: bool = False
    
    # Replication settings
    pure_replica_interval_default: int = Field(default=3600, ge=1)
    pure_replica_retention_short_term_default: int = Field(default=14400, ge=1)
    pure_replica_retention_long_term_per_day_default: int = Field(default=3, ge=1)
    pure_replica_retention_long_term_default: int = Field(default=7, ge=1)
    pure_replication_pg_name: str = "cinder-group"
    pure_replication_pod_name: str = "cinder-pod"
    pure_trisync_enabled: bool = False
    pure_trisync_pg_name: str = "cinder-trisync"


class DellSCConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell Storage Center** Cinder driver.
    
    This configuration supports iSCSI and Fibre Channel protocols
    with dual DSM support, network filtering, and comprehensive timeout controls.
    """
    
    # Core required fields
    san_ip: str  # Dell Storage Center management IP/FQDN
    san_login: str  # SAN management username
    san_password: str  # SAN management password
    dell_sc_ssn: int = Field(default=64702)  # Storage Center System Serial Number
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")
    
    # Dell Storage Center specific options
    dell_sc_api_port: int = Field(default=3033, ge=1, le=65535)
    dell_sc_server_folder: str = "openstack"
    dell_sc_volume_folder: str = "openstack"
    dell_server_os: str = "Red Hat Linux 6.x"
    dell_sc_verify_cert: bool = False
    
    # Domain and network filtering
    excluded_domain_ips: list[str] | None = None
    included_domain_ips: list[str] | None = None
    san_thin_provision: bool = True
    
    # Dual DSM configuration
    secondary_san_ip: str | None = None
    secondary_san_login: str = "Admin"
    secondary_san_password: str | None = None
    secondary_sc_api_port: int = Field(default=3033, ge=1, le=65535)
    
    # API timeout configuration
    dell_api_async_rest_timeout: int = Field(default=15, ge=1)
    dell_api_sync_rest_timeout: int = Field(default=30, ge=1)
    
    # SSH connection settings
    ssh_conn_timeout: int = Field(default=30, ge=1)
    ssh_max_pool_conn: int = Field(default=5, ge=1)
    ssh_min_pool_conn: int = Field(default=1, ge=1)


class Configuration(BaseConfiguration):
    """Holding additional configuration for the generic snap.

    This class is specific to this snap and should not be used in
    downstream snaps.
    """

    ceph: dict[str, CephConfiguration] = {}
    hitachi: dict[str, HitachiConfiguration] = {}
    pure: dict[str, PureConfiguration] = {}
    dellsc: dict[str, DellSCConfiguration] = {}

    @pydantic.model_validator(mode='after')
    def validate_unique_backend_names(self):
        """Validate that all backend names are unique across all backend types."""
        backend_names = set()
        ceph_pools = set()
        
        # Check all backend types for unique backend names
        for backend_type, backends in [
            ("ceph", self.ceph),
            ("hitachi", self.hitachi), 
            ("pure", self.pure),
            ("dellsc", self.dellsc)
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
                if backend_type == "ceph" and hasattr(backend, 'rbd_pool'):
                    if backend.rbd_pool in ceph_pools:
                        raise ValueError(
                            f"Duplicate Ceph pool '{backend.rbd_pool}' "
                            f"found in backend '{backend_key}'"
                        )
                    ceph_pools.add(backend.rbd_pool)
        
        return self
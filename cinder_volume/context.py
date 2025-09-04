# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Context module for rendering configuration and templates."""

import abc
import pathlib
import typing
from pathlib import Path

from snaphelpers import Snap

from . import error, template


class Context(abc.ABC):
    """Abstract base class for context providers."""

    namespace: str

    @abc.abstractmethod
    def context(self) -> typing.Mapping[str, typing.Any]:
        """Return the context dictionary."""
        raise NotImplementedError


class ConfigContext(Context):
    """Context provider for configuration data."""

    def __init__(self, namespace: str, config: typing.Mapping[str, typing.Any]):
        """Initialize with namespace and config."""
        self.namespace = namespace
        self.config = config

    def context(self) -> typing.Mapping[str, typing.Any]:
        """Return the configuration as context."""
        return self.config


class SnapPathContext(Context):
    """Context provider for snap paths."""

    namespace = "snap_paths"

    def __init__(self, snap: Snap):
        """Initialize with snap instance."""
        self.snap = snap

    def context(self) -> typing.Mapping[str, typing.Any]:
        """Return snap paths as context."""
        return {
            name: getattr(self.snap.paths, name) for name in self.snap.paths.__slots__
        }


class BaseBackendContext(Context):
    """Base class for backend context providers."""

    def __init__(self, backend_name: str, backend_config: dict[str, typing.Any]):
        """Initialize with backend name and config."""
        self.namespace = backend_name
        self.backend_name = backend_name
        self.backend_config = backend_config
        self.supports_cluster = True

    def context(self) -> typing.Mapping[str, typing.Any]:
        """Full context for the backend configuration.

        This value is always associated to `namespace`, not
        necessarily associated with `backend_name`.
        """
        return self.backend_config

    def cinder_context(self) -> typing.Mapping[str, typing.Any]:
        """Context specific for cinder configuration.

        This value is always associated to `backend_name`, not
        necessarily associated with `namespace`.
        """
        return self.backend_config

    def template_files(self) -> list[template.Template]:
        """Files to be templated."""
        return []

    def directories(self) -> list[template.Directory]:
        """Directories to be created."""
        return []

    def setup(self, snap: Snap):
        """Perform all actions needed to setup the backend."""
        pass


class CinderBackendContexts(Context):
    """Context provider for all Cinder backends."""

    namespace = "cinder_backends"

    def __init__(
        self,
        enabled_backends: list[str],
        contexts: typing.Mapping[str, BaseBackendContext],
    ):
        """Initialize with enabled backends and contexts."""
        self.enabled_backends = enabled_backends
        self.contexts = contexts
        if not enabled_backends:
            raise error.CinderError("At least one backend must be enabled")
        missing_backends = set(self.enabled_backends) - set(contexts.keys())
        if missing_backends:
            raise error.CinderError(
                "Context missing configuration for backends: %s" % missing_backends
            )

    def context(self) -> typing.Mapping[str, typing.Any]:
        """Return context for all backends."""
        cluster_ok = all(ctx.supports_cluster for ctx in self.contexts.values())
        return {
            "enabled_backends": ",".join(self.enabled_backends),
            "cluster_ok": cluster_ok,
            "contexts": {
                config.backend_name: config.cinder_context()
                for config in self.contexts.values()
            },
        }


ETC_CEPH = pathlib.Path("etc/ceph")


class CephBackendContext(BaseBackendContext):
    """Context provider for Ceph backend."""

    _hidden_keys = ["rbd_key", "keyring", "mon_hosts", "auth", "backend_name"]

    def __init__(self, backend_name: str, backend_config: dict[str, typing.Any]):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        # Not to override global `ceph` namespace
        self.namespace = "ceph_ctx"
        self.supports_cluster = True

    def cinder_context(self) -> typing.Mapping[str, typing.Any]:
        """Return context for cinder configuration."""
        context = dict(self.context())
        for key in self._hidden_keys:
            context.pop(key, None)
        return context

    def keyring(self) -> str:
        """Return the keyring filename."""
        return "ceph.client." + self.backend_name + ".keyring"

    def ceph_conf(self) -> str:
        """Return the ceph config filename."""
        return self.backend_name + ".conf"

    def context(self) -> typing.Mapping[str, typing.Any]:
        """Return full context for Ceph backend."""
        context = {"volume_driver": "cinder.volume.drivers.rbd.RBDDriver"}
        context.update(self.backend_config)
        context["rbd_ceph_conf"] = (
            r"{{ snap_paths.common }}/etc/ceph/" + self.ceph_conf()
        )
        context["keyring"] = self.keyring()

        return {k: v for k, v in context.items() if v is not None}

    def directories(self) -> list[template.Directory]:
        """Return directories to create."""
        return [
            template.CommonDirectory(ETC_CEPH),
        ]

    def template_files(self) -> list[template.Template]:
        """Return template files to render."""
        return [
            template.CommonTemplate(
                self.ceph_conf(), ETC_CEPH, template_name="ceph.conf.j2"
            ),
            template.CommonTemplate(
                self.keyring(),
                ETC_CEPH,
                mode=0o600,
                template_name="ceph.client.keyring.j2",
            ),
        ]


class HitachiBackendContext(BaseBackendContext):
    """Render a Hitachi VSP backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.cfg = backend_config
        self.namespace = "backend"
        self.supports_cluster = False

    def context(self) -> dict:
        """Return context for Hitachi backend."""
        proto = self.cfg.get("protocol", "FC").lower()
        driver_cls = (
            "cinder.volume.drivers.hitachi.hbsd_fc.HBSDFCDriver"
            if proto == "fc"
            else "cinder.volume.drivers.hitachi.hbsd_iscsi.HBSDISCSIDriver"
        )
        context = {
            "backend_name": self.backend_name,
            "driver_class": driver_cls,
            **self.cfg,
        }
        return context

    def cinder_context(self) -> dict[str, typing.Any]:
        """Keys that land in cinder.conf.

        Return {} to avoid duplicating the full stanza there.
        """
        return {}

    def template_files(self) -> list[template.Template]:
        """Return template files to render."""
        return [
            template.CommonTemplate(
                f"{self.backend_name}.conf",
                Path("etc/cinder/cinder.conf.d"),
                template_name="backend.conf.j2",
            )
        ]


class PureBackendContext(BaseBackendContext):
    """Render a Pure Storage FlashArray backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.cfg = backend_config
        self.namespace = "backend"
        self.supports_cluster = True  # Pure supports clustering

    def context(self) -> dict:
        """Return context for Pure backend."""
        protocol = self.cfg.get("protocol", "fc").lower()

        # Driver class selection based on protocol
        driver_classes = {
            "iscsi": "cinder.volume.drivers.pure.PureISCSIDriver",
            "fc": "cinder.volume.drivers.pure.PureFCDriver",
            "nvme": "cinder.volume.drivers.pure.PureNVMEDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])

        context = {
            "backend_name": self.backend_name,
            "driver_class": driver_class,
            **self.cfg,
        }
        return context

    def cinder_context(self) -> dict[str, typing.Any]:
        """Keys that land in cinder.conf. Return {} to avoid duplication."""
        return {}

    def template_files(self) -> list[template.Template]:
        """Return template files to render."""
        return [
            template.CommonTemplate(
                f"{self.backend_name}.conf",
                Path("etc/cinder/cinder.conf.d"),
                template_name="backend.conf.j2",
            )
        ]


class DellSCBackendContext(BaseBackendContext):
    """Render a Dell Storage Center backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.cfg = backend_config
        self.namespace = "backend"
        self.supports_cluster = False  # Dell SC does not support clustering

    def context(self) -> dict:
        """Return context for Dell SC backend."""
        protocol = self.cfg.get("protocol", "fc").lower()

        # Driver class selection based on protocol
        driver_classes = {
            "iscsi": (
                "cinder.volume.drivers.dell_emc.sc.storagecenter_iscsi.SCISCSIDriver"
            ),
            "fc": "cinder.volume.drivers.dell_emc.sc.storagecenter_fc.SCFCDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])

        context = {
            "backend_name": self.backend_name,
            "driver_class": driver_class,
            **self.cfg,
        }
        return context

    def cinder_context(self) -> dict[str, typing.Any]:
        """Keys that land in cinder.conf. Return {} to avoid duplication."""
        return {}

    def template_files(self) -> list[template.Template]:
        """Return template files to render."""
        return [
            template.CommonTemplate(
                f"{self.backend_name}.conf",
                Path("etc/cinder/cinder.conf.d"),
                template_name="backend.conf.j2",
            )
        ]

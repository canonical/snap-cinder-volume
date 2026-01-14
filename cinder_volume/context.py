# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Context module for rendering configuration and templates."""

import abc
import collections.abc
import pathlib
import typing

import jinja2
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


ETC_CINDER_D_CONF_DIR = pathlib.Path("etc/cinder/cinder.conf.d")

CINDER_CTX_KEY = "ctx_cinder_name"
BACKEND_CTX_KEY = "ctx_backend"


@jinja2.pass_context
def cinder_name(
    ctx,
):
    """Get the backend configuration value."""
    if name := ctx.get(CINDER_CTX_KEY):
        return name
    raise error.CinderError("No backend name in context")


@jinja2.pass_context
def cinder_ctx(
    ctx,
):
    """Get the cinder configuration value."""
    return ctx["cinder_backends"]["contexts"][cinder_name(ctx)]


@jinja2.pass_context
def backend_ctx(ctx):
    """Get the backend configuration value."""
    return ctx[BACKEND_CTX_KEY]


def backend_variable_set(backend: str, *var: str) -> template.Conditional:
    """Return a conditional that checks if a variable is set in a context namespace."""

    def _conditional(context: template.ContextType) -> bool:
        ns_context = (
            context.get("cinder_backends", {}).get("contexts", {}).get(backend, {})
        )
        return all(bool(ns_context.get(v)) for v in var)

    return _conditional


class BaseBackendContext(Context):
    """Base class for backend context providers."""

    _hidden_keys: typing.Sequence[str] = ("driver_ssl_cert",)

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
        context = dict(self.backend_config)
        if context.get("driver_ssl_cert"):
            context["driver_ssl_cert_path"] = str(
                pathlib.Path(r"{{ snap_paths.common }}")
                / ETC_CINDER_D_CONF_DIR
                / f"{self.backend_name}.pem"
            )
            context["driver_ssl_cert_verify"] = True
        return context

    @property
    def hidden_keys(self) -> collections.abc.Generator[str]:
        """Keys that should not be exposed in cinder context."""
        for klass in self.__class__.mro():
            if issubclass(klass, BaseBackendContext):
                yield from klass._hidden_keys

    def cinder_context(self) -> typing.Mapping[str, typing.Any]:
        """Context specific for cinder configuration.

        This value is always associated to `backend_name`, not
        necessarily associated with `namespace`.
        """
        context = dict(self.context())
        for key in self.hidden_keys:
            context.pop(key, None)
        return {k: v for k, v in context.items() if v is not None}

    def template_files(self) -> list[template.Template]:
        """Files to be templated."""
        return [
            template.CommonTemplate(
                f"{self.backend_name}.conf",
                ETC_CINDER_D_CONF_DIR,
                template_name="backend.conf.j2",
            ),
            template.CommonTemplate(
                f"{self.backend_name}.pem",
                ETC_CINDER_D_CONF_DIR,
                template_name="backend.pem.j2",
                conditionals=[
                    backend_variable_set(
                        self.backend_name,
                        "driver_ssl_cert_path",
                    )
                ],
            ),
        ]

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

    _hidden_keys = ("rbd_key", "keyring", "mon_hosts", "auth")

    def __init__(self, backend_name: str, backend_config: dict[str, typing.Any]):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True

    def keyring(self) -> str:
        """Return the keyring filename."""
        return "ceph.client." + self.backend_name + ".keyring"

    def ceph_conf(self) -> str:
        """Return the ceph config filename."""
        return self.backend_name + ".conf"

    def context(self) -> typing.Mapping[str, typing.Any]:
        """Return full context for Ceph backend."""
        context = dict(super().context())
        context["volume_driver"] = "cinder.volume.drivers.rbd.RBDDriver"
        context["rbd_ceph_conf"] = (
            r"{{ snap_paths.common }}/etc/ceph/" + self.ceph_conf()
        )
        context["keyring"] = self.keyring()
        return context

    def directories(self) -> list[template.Directory]:
        """Return directories to create."""
        return [
            template.CommonDirectory(ETC_CEPH),
        ]

    def template_files(self) -> list[template.Template]:
        """Return template files to render."""
        return super().template_files() + [
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

    _hidden_keys = ("protocol", "hitachi_mirror_driver_ssl_cert")

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False

    def context(self) -> dict:
        """Return context for Hitachi backend."""
        context = dict(super().context())
        proto = self.backend_config.get("protocol", "FC").lower()
        driver_cls = (
            "cinder.volume.drivers.hitachi.hbsd_fc.HBSDFCDriver"
            if proto == "fc"
            else "cinder.volume.drivers.hitachi.hbsd_iscsi.HBSDISCSIDriver"
        )
        context.update(
            {
                "volume_driver": driver_cls,
            }
        )
        if "chap_username" in context:
            context["use_chap_auth"] = True
        if "hitachi_mirror_auth_username" in context:
            context["hitachi_mirror_use_chap_auth"] = True
        if context.get("hitachi_mirror_driver_ssl_cert"):
            context["hitachi_mirror_ssl_cert_path"] = str(
                pathlib.Path(r"{{ snap_paths.common }}")
                / ETC_CINDER_D_CONF_DIR
                / f"{self.backend_name}_mirror.pem"
            )
            context["hitachi_mirror_ssl_cert_verify"] = True
        return context

    def template_files(self) -> list[template.Template]:
        """Files to be templated."""
        return super().template_files() + [
            template.CommonTemplate(
                f"{self.backend_name}_mirror.pem",
                ETC_CINDER_D_CONF_DIR,
                # TODO: find a better pattern when multiple backends
                # also need a second certificate for the driver
                template_name="hitachi_backend.pem.j2",
                conditionals=[
                    backend_variable_set(
                        self.backend_name,
                        "hitachi_mirror_ssl_cert_path",
                    )
                ],
            ),
        ]


class PureBackendContext(BaseBackendContext):
    """Render a Pure Storage FlashArray backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True  # Pure supports clustering

    def context(self) -> dict:
        """Return context for Pure backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        # Driver class selection based on protocol
        driver_classes = {
            "iscsi": "cinder.volume.drivers.pure.PureISCSIDriver",
            "fc": "cinder.volume.drivers.pure.PureFCDriver",
            "nvme": "cinder.volume.drivers.pure.PureNVMEDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])

        context.update(
            {
                "volume_driver": driver_class,
            }
        )
        return context


class DellSCBackendContext(BaseBackendContext):
    """Render a Dell Storage Center backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # Dell SC does not support clustering

    def context(self) -> dict:
        """Return context for Dell SC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        # Driver class selection based on protocol
        driver_classes = {
            "iscsi": (
                "cinder.volume.drivers.dell_emc.sc.storagecenter_iscsi.SCISCSIDriver"
            ),
            "fc": "cinder.volume.drivers.dell_emc.sc.storagecenter_fc.SCFCDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])

        context.update(
            {
                "volume_driver": driver_class,
            }
        )
        return context


class DellpowerstoreBackendContext(BaseBackendContext):
    """Render a Dell PowerStore backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False

    def context(self) -> dict:
        """Return context for Dell PowerStore backend."""
        context = dict(super().context())

        # Driver class selection
        # Note that the class doesn't change across the configured protocols
        driver_class = "cinder.volume.drivers.dell_emc.powerstore.driver.PowerStoreDriver"

        context.update(
            {
                "volume_driver": driver_class,
            }
        )
        return context

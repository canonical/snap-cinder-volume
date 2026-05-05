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


def ca_bundle_set(config: template.ContextType) -> bool:
    """Return whether a main CA bundle is available in template context."""
    return bool(config.get("ca", {}).get("bundle"))


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


class SolidfireBackendContext(BaseBackendContext):
    """Render a NetApp SolidFire backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True  # cluster supported

    def context(self) -> dict:
        """Return context for NetApp SolidFire backend."""
        context = dict(super().context())
        context["volume_driver"] = "cinder.volume.drivers.solidfire.SolidFireDriver"
        return context


class DatacoreBackendContext(BaseBackendContext):
    """Render a DataCoreVolume backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for DataCoreVolume backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.datacore.fc.FibreChannelVolumeDriver"
        )
        return context


class DateraBackendContext(BaseBackendContext):
    """Render a Datera backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Datera backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.datera.datera_iscsi.DateraDriver"
        )
        return context


class DellpowermaxBackendContext(BaseBackendContext):
    """Render a Dell PowerMax backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True  # cluster supported

    def context(self) -> dict:
        """Return context for Dell PowerMax backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": "cinder.volume.drivers.dell_emc.powermax.fc.PowerMaxFCDriver",
            "iscsi": (
                "cinder.volume.drivers.dell_emc.powermax.iscsi.PowerMaxISCSIDriver"
            ),
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class DellpowervaultBackendContext(BaseBackendContext):
    """Render a Dell PowerVault backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Dell PowerVault backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": "cinder.volume.drivers.dell_emc.powervault.fc.PVMEFCDriver",
            "iscsi": "cinder.volume.drivers.dell_emc.powervault.iscsi.PVMEISCSIDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class DellxtremioBackendContext(BaseBackendContext):
    """Render a Dell XtremIO backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Dell XtremIO backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "iscsi").lower()

        driver_classes = {
            "iscsi": "cinder.volume.drivers.dell_emc.xtremio.XtremIOISCSIDriver",
            "fc": "cinder.volume.drivers.dell_emc.xtremio.XtremIOFCDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["iscsi"])
        context.update({"volume_driver": driver_class})
        return context


class FujitsueternusdxBackendContext(BaseBackendContext):
    """Render a FJDX FC backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for FJDX FC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": (
                "cinder.volume.drivers.fujitsu.eternus_dx.eternus_dx_fc.FJDXFCDriver"
            ),
            "iscsi": (
                "cinder.volume.drivers.fujitsu.eternus_dx.eternus_dx_iscsi"
                ".FJDXISCSIDriver"
            ),
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class HpexpBackendContext(BaseBackendContext):
    """Render a HPE XP backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for HPE XP backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": "cinder.volume.drivers.hpe.xp.hpe_xp_fc.HPEXPFCDriver",
            "iscsi": "cinder.volume.drivers.hpe.xp.hpe_xp_iscsi.HPEXPISCSIDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class IbmflashsystemcommonBackendContext(BaseBackendContext):
    """Render a Ibmflashsystemcommon backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Ibmflashsystemcommon backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.ibm.flashsystem_common.FlashSystemDriver"
        )
        return context


class IbmflashsystemiscsiBackendContext(BaseBackendContext):
    """Render a FlashSystem iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for FlashSystem iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.ibm.flashsystem_iscsi.FlashSystemISCSIDriver"
        )
        return context


class IbmgpfsBackendContext(BaseBackendContext):
    """Render a GPFS backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for GPFS backend."""
        context = dict(super().context())
        context["volume_driver"] = "cinder.volume.drivers.ibm.gpfs.GPFSDriver"
        return context


class IbmibmstorageBackendContext(BaseBackendContext):
    """Render a IBMStorage backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for IBMStorage backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.ibm.ibm_storage.ibm_storage.IBMStorageDriver"
        )
        return context


class IbmstorwizesvcBackendContext(BaseBackendContext):
    """Render a StorwizeSVC FC backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for StorwizeSVC FC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": (
                "cinder.volume.drivers.ibm.storwize_svc.storwize_svc_fc"
                ".StorwizeSVCFCDriver"
            ),
            "iscsi": (
                "cinder.volume.drivers.ibm.storwize_svc.storwize_svc_iscsi"
                ".StorwizeSVCISCSIDriver"
            ),
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class Inspuras13000BackendContext(BaseBackendContext):
    """Render a AS13000 backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for AS13000 backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.inspur.as13000.as13000_driver.AS13000Driver"
        )
        return context


class InspurinstorageBackendContext(BaseBackendContext):
    """Render a InStorageMCS FC backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for InStorageMCS FC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": (
                "cinder.volume.drivers.inspur.instorage.instorage_fc"
                ".InStorageMCSFCDriver"
            ),
            "iscsi": (
                "cinder.volume.drivers.inspur.instorage.instorage_iscsi"
                ".InStorageMCSISCSIDriver"
            ),
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class KaminarioBackendContext(BaseBackendContext):
    """Render a Kaminario iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Kaminario iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.kaminario.kaminario_iscsi.KaminarioISCSIDriver"
        )
        return context


class LinstorBackendContext(BaseBackendContext):
    """Render a LinstorIscsi backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for LinstorIscsi backend."""
        context = dict(super().context())
        context["volume_driver"] = "cinder.volume.drivers.linstordrv.LinstorIscsiDriver"
        return context


class MacrosanBackendContext(BaseBackendContext):
    """Render a MacroSAN iSCSI backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for MacroSAN iSCSI backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "iscsi").lower()

        driver_classes = {
            "iscsi": "cinder.volume.drivers.macrosan.driver.MacroSANISCSIDriver",
            "fc": "cinder.volume.drivers.macrosan.driver.MacroSANFCDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["iscsi"])
        context.update({"volume_driver": driver_class})
        return context


class NecvBackendContext(BaseBackendContext):
    """Render a VStorage FC backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for VStorage FC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": "cinder.volume.drivers.nec.v.nec_v_fc.VStorageFCDriver",
            "iscsi": "cinder.volume.drivers.nec.v.nec_v_iscsi.VStorageISCSIDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class NetappBackendContext(BaseBackendContext):
    """Render a NetApp ONTAP backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True  # cluster supported

    def context(self) -> dict:
        """Return context for NetApp ONTAP backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "iscsi").lower()

        driver_classes = {
            "iscsi": (
                "cinder.volume.drivers.netapp.dataontap.iscsi_cmode"
                ".NetAppCmodeISCSIDriver"
            ),
            "nvme": (
                "cinder.volume.drivers.netapp.dataontap.nvme_cmode"
                ".NetAppCmodeNVMeDriver"
            ),
        }

        driver_class = driver_classes.get(protocol, driver_classes["iscsi"])
        context.update({"volume_driver": driver_class})
        return context


class NexentaBackendContext(BaseBackendContext):
    """Render a Nexenta iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Nexenta iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.nexenta.iscsi.NexentaISCSIDriver"
        )
        return context


class NimbleBackendContext(BaseBackendContext):
    """Render a HPE Nimble Storage backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for HPE Nimble Storage backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "iscsi").lower()

        driver_classes = {
            "iscsi": "cinder.volume.drivers.hpe.nimble.NimbleISCSIDriver",
            "fc": "cinder.volume.drivers.hpe.nimble.NimbleFCDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["iscsi"])
        context.update({"volume_driver": driver_class})
        return context


class OpeneBackendContext(BaseBackendContext):
    """Render a Jovian iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Jovian iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.open_e.iscsi.JovianISCSIDriver"
        )
        return context


class ProphetstorBackendContext(BaseBackendContext):
    """Render a DPL FC backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for DPL FC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": "cinder.volume.drivers.prophetstor.dpl_fc.DPLFCDriver",
            "iscsi": "cinder.volume.drivers.prophetstor.dpl_iscsi.DPLISCSIDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class QnapBackendContext(BaseBackendContext):
    """Render a QNAP Storage backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for QNAP Storage backend."""
        context = dict(super().context())
        context["volume_driver"] = "cinder.volume.drivers.qnap.QnapISCSIDriver"
        return context


class SandstoneBackendContext(BaseBackendContext):
    """Render a Sds iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Sds iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.sandstone.sds_driver.SdsISCSIDriver"
        )
        return context


class StxBackendContext(BaseBackendContext):
    """Render a Stx backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Stx backend."""
        context = dict(super().context())
        context["volume_driver"] = "cinder.volume.drivers.stx.iscsi.STXISCSIDriver"
        return context


class SynologyBackendContext(BaseBackendContext):
    """Render a Syno iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Syno iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.synology.synology_iscsi.SynoISCSIDriver"
        )
        return context


class Toyouacs5000BackendContext(BaseBackendContext):
    """Render a Acs5000 FC backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for Acs5000 FC backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": ("cinder.volume.drivers.toyou.acs5000.acs5000_fc.Acs5000FCDriver"),
            "iscsi": (
                "cinder.volume.drivers.toyou.acs5000.acs5000_iscsi.Acs5000ISCSIDriver"
            ),
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class VeritasaccessBackendContext(BaseBackendContext):
    """Render a ACCESSIscsi backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for ACCESSIscsi backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.veritas_access.veritas_iscsi.ACCESSIscsiDriver"
        )
        return context


class YadroBackendContext(BaseBackendContext):
    """Render a Tatlin FCVolume backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True  # cluster supported

    def context(self) -> dict:
        """Return context for Tatlin FCVolume backend."""
        context = dict(super().context())
        protocol = self.backend_config.get("protocol", "fc").lower()

        driver_classes = {
            "fc": "cinder.volume.drivers.yadro.tatlin_fc.TatlinFCVolumeDriver",
            "iscsi": "cinder.volume.drivers.yadro.tatlin_iscsi.TatlinISCSIVolumeDriver",
        }

        driver_class = driver_classes.get(protocol, driver_classes["fc"])
        context.update({"volume_driver": driver_class})
        return context


class ZadaraBackendContext(BaseBackendContext):
    """Render a ZadaraVPSA iSCSI backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False  # cluster not supported

    def context(self) -> dict:
        """Return context for ZadaraVPSA iSCSI backend."""
        context = dict(super().context())
        context["volume_driver"] = (
            "cinder.volume.drivers.zadara.zadara.ZadaraVPSAISCSIDriver"
        )
        return context


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


class DellscBackendContext(BaseBackendContext):
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

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False

    def context(self) -> dict:
        """Return context for Dell PowerStore backend."""
        context = dict(super().context())

        # Driver class selection
        # Note that the class doesn't change across the configured protocols
        driver_class = (
            "cinder.volume.drivers.dell_emc.powerstore.driver.PowerStoreDriver"
        )

        context.update(
            {
                "volume_driver": driver_class,
                "storage_protocol": self.backend_config.get("protocol", "fc").lower(),
            }
        )
        return context


class HpethreeparBackendContext(BaseBackendContext):
    """Render a HPE 3Par backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = False

    def context(self) -> dict:
        """Return context for HPE 3Par backend."""
        context = dict(super().context())

        protocol = self.backend_config.get("protocol", "fc").lower()
        driver_classes = {
            "fc": "cinder.volume.drivers.hpe.hpe_3par_fc.HPE3PARFCDriver",
            "iscsi": "cinder.volume.drivers.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver",
        }

        context.update(
            {
                "volume_driver": driver_classes[protocol],
            }
        )
        return context


class InfinidatBackendContext(BaseBackendContext):
    """Render an Infinidat InfiniBox backend stanza."""

    _hidden_keys = ("protocol",)

    def __init__(self, backend_name: str, backend_config: dict):
        """Initialize with backend name and config."""
        super().__init__(backend_name, backend_config)
        self.supports_cluster = True

    def context(self) -> dict:
        """Return context for Infinidat backend."""
        context = dict(super().context())

        # Infinidat uses a single driver class for both iSCSI and FC;
        # the protocol is controlled by configuration options.
        context.update(
            {
                "volume_driver": (
                    "cinder.volume.drivers.infinidat.InfiniboxVolumeDriver"
                ),
            }
        )
        return context

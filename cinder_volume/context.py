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

import abc
import pathlib
import typing
from pathlib import Path

from snaphelpers import Snap

from . import error, template


class Context(abc.ABC):
    namespace: str

    @abc.abstractmethod
    def context(self) -> typing.Mapping[str, typing.Any]:
        raise NotImplementedError


class ConfigContext(Context):
    def __init__(self, namespace: str, config: typing.Mapping[str, typing.Any]):
        self.namespace = namespace
        self.config = config

    def context(self) -> typing.Mapping[str, typing.Any]:
        return self.config


class SnapPathContext(Context):
    namespace = "snap_paths"

    def __init__(self, snap: Snap):
        self.snap = snap

    def context(self) -> typing.Mapping[str, typing.Any]:
        return {
            name: getattr(self.snap.paths, name) for name in self.snap.paths.__slots__
        }


class BaseBackendContext(Context):
    def __init__(self, backend_name: str, backend_config: dict[str, typing.Any]):
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
    namespace = "cinder_backends"

    def __init__(
        self,
        enabled_backends: list[str],
        contexts: typing.Mapping[str, BaseBackendContext],
    ):
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
    _hidden_keys = ["rbd_key", "keyring", "mon_hosts", "auth", "backend_name"]

    def __init__(self, backend_name: str, backend_config: dict[str, typing.Any]):
        super().__init__(backend_name, backend_config)
        # Not to override global `ceph` namespace
        self.namespace = "ceph_ctx"
        self.supports_cluster = True

    def cinder_context(self) -> typing.Mapping[str, typing.Any]:
        context = dict(self.context())
        for key in self._hidden_keys:
            context.pop(key, None)
        return context

    def keyring(self) -> str:
        return "ceph.client." + self.backend_name + ".keyring"

    def ceph_conf(self) -> str:
        return self.backend_name + ".conf"

    def context(self) -> typing.Mapping[str, typing.Any]:
        context = {"volume_driver": "cinder.volume.drivers.rbd.RBDDriver"}
        context.update(self.backend_config)
        context["rbd_ceph_conf"] = (
            r"{{ snap_paths.common }}/etc/ceph/" + self.ceph_conf()
        )
        context["keyring"] = self.keyring()

        return {k: v for k, v in context.items() if v is not None}

    def directories(self) -> list[template.Directory]:
        return [
            template.CommonDirectory(ETC_CEPH),
        ]

    def template_files(self) -> list[template.Template]:
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
        super().__init__(backend_name, backend_config)
        self.cfg = backend_config
        self.namespace = 'hitachi_ctx'
        self.supports_cluster = False

    def context(self) -> dict:
        proto = self.cfg.get("protocol", "FC").lower()
        driver_cls = (
            "cinder.volume.drivers.hitachi.hbsd_fc.HBSDFCDriver"
            if proto == "fc"
            else "cinder.volume.drivers.hitachi.hbsd_iscsi.HBSDISCSIDriver"
        )
        return {
            "backend_name": self.backend_name,
            "driver_class": driver_cls,
            **self.cfg,
        }

    def cinder_context(self) -> dict[str, typing.Any]:
        """Keys that land in *cinder.conf*.  
        Return {} to avoid duplicating the full stanza there."""
        return {}   
        
    def template_files(self) -> list[template.Template]:
        return [
            # dest filename  • dest directory                 • Jinja file to load
            template.CommonTemplate(
                f"{self.backend_name}.conf",                  #  vsp-test.conf
                Path("etc/cinder/cinder.conf.d"),             #  …/cinder.conf.d/
                template_name="hitachi.conf.j2",              #  Jinja source
            )
        ]


class PureBackendContext(BaseBackendContext):
    """Render a Pure Storage FlashArray backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        super().__init__(backend_name, backend_config)
        self.cfg = backend_config
        self.namespace = 'pure_ctx'
        self.supports_cluster = True  # Pure supports clustering

    def context(self) -> dict:
        protocol = self.cfg.get("protocol", "fc").lower()
        
        # Driver class selection based on protocol
        driver_classes = {
            "iscsi": "cinder.volume.drivers.pure.PureISCSIDriver",
            "fc": "cinder.volume.drivers.pure.PureFCDriver", 
            "nvme": "cinder.volume.drivers.pure.PureNVMEDriver"
        }
        
        return {
            "backend_name": self.backend_name,
            "driver_class": driver_classes[protocol],
            **self.cfg,
        }

    def cinder_context(self) -> dict[str, typing.Any]:
        """Keys that land in cinder.conf. Return {} to avoid duplication."""
        return {}
        
    def template_files(self) -> list[template.Template]:
        return [
            template.CommonTemplate(
                f"{self.backend_name}.conf",
                Path("etc/cinder/cinder.conf.d"),
                template_name="pure.conf.j2",
            )
        ]


class DellSCBackendContext(BaseBackendContext):
    """Render a Dell Storage Center backend stanza."""

    def __init__(self, backend_name: str, backend_config: dict):
        super().__init__(backend_name, backend_config)
        self.cfg = backend_config
        self.namespace = 'dellsc_ctx'
        self.supports_cluster = False  # Dell SC does not support clustering

    def context(self) -> dict:
        protocol = self.cfg.get("protocol", "fc").lower()
        
        # Driver class selection based on protocol
        driver_classes = {
            "iscsi": "cinder.volume.drivers.dell_emc.sc.storagecenter_iscsi.SCISCSIDriver",
            "fc": "cinder.volume.drivers.dell_emc.sc.storagecenter_fc.SCFCDriver"
        }
        
        return {
            "backend_name": self.backend_name,
            "driver_class": driver_classes[protocol],
            **self.cfg,
        }

    def cinder_context(self) -> dict[str, typing.Any]:
        """Keys that land in cinder.conf. Return {} to avoid duplication."""
        return {}
        
    def template_files(self) -> list[template.Template]:
        return [
            template.CommonTemplate(
                f"{self.backend_name}.conf",
                Path("etc/cinder/cinder.conf.d"),
                template_name="dellsc.conf.j2",
            )
        ]

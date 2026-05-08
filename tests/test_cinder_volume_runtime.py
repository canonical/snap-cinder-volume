# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from unittest.mock import Mock

import jinja2

from cinder_volume import cinder_volume, template


def _get_section(rendered: str, section: str) -> str:
    """Extract the content of a named INI section from a rendered config string."""
    start = rendered.index(f"\n[{section}]\n") + len(f"\n[{section}]\n")
    next_section = rendered.find("\n[", start)
    return rendered[start:next_section] if next_section != -1 else rendered[start:]


class TestGenericCinderVolume:
    """Runtime-oriented tests for GenericCinderVolume."""

    def test_template_files_include_receive_ca_bundle(self):
        """The main CA bundle should be managed as a rendered template."""
        service = cinder_volume.GenericCinderVolume()

        template_files = service.template_files()

        assert any(
            tpl.filename == "receive-ca-bundle.pem"
            and tpl.dest == Path("etc/ssl/certs")
            and tpl.template_name == "receive-ca-bundle.pem.j2"
            for tpl in template_files
        )

    def test_start_services_restarts_on_restart_trigger_file(self):
        """A changed CA bundle should restart the cinder-volume service."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap_service = Mock()
        snap.services.list.return_value = {"cinder-volume": snap_service}
        modified = [
            template.CommonTemplate(
                "receive-ca-bundle.pem",
                Path("etc/ssl/certs"),
                template_name="receive-ca-bundle.pem.j2",
            )
        ]

        service.start_services(snap, modified, [])

        snap_service.restart.assert_called_once_with()
        snap_service.start.assert_not_called()

    def test_cinder_conf_renders_cafile_when_ca_bundle_exists(self):
        """The template should render CA settings in the service-specific sections."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                Path(cinder_volume.__file__).parent / "templates"
            )
        )

        rendered = env.get_template("cinder.conf.j2").render(
            snap_paths={"common": "/var/snap/cinder-volume/common"},
            settings={"debug": False, "enable_telemetry_notifications": False},
            rabbitmq={"url": "amqp://guest:guest@localhost:5672/"},
            database={"url": "mysql://cinder:secret@db/cinder"},
            cinder={
                "project_id": "project-id",
                "user_id": "user-id",
                "region_name": "RegionOne",
                "cluster": None,
                "cluster_ok": True,
                "default_volume_type": None,
                "image_volume_cache_enabled": False,
                "image_volume_cache_max_size_gb": 0,
                "image_volume_cache_max_count": 0,
            },
            ca={"bundle": "TEST_CA"},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        assert (
            "cafile = /var/snap/cinder-volume/common/etc/ssl/certs/"
            "receive-ca-bundle.pem" in rendered
        )
        default_section = rendered[: rendered.index("\n[nova]\n")]
        assert (
            "glance_ca_certificates_file = "
            "/var/snap/cinder-volume/common/etc/ssl/certs/receive-ca-bundle.pem"
            in default_section
        )
        assert "glance_api_insecure = false" in default_section
        assert "\n[nova]\n" in rendered
        assert "\n[barbican]\n" in rendered
        assert "\n[glance]\n" in rendered
        nova_section = _get_section(rendered, "nova")
        barbican_section = _get_section(rendered, "barbican")
        glance_section = _get_section(rendered, "glance")
        assert "interface = internal" in nova_section
        assert "interface = internal" in barbican_section
        assert "glance_catalog_info = image:glance:internalURL" in default_section
        assert "valid_interfaces = internal" not in rendered
        assert "service_type = image" not in rendered
        assert "service_name = glance" not in rendered
        assert "region_name = RegionOne" in nova_section
        assert "region_name = RegionOne" in barbican_section
        assert "region_name = RegionOne" in glance_section
        cafile = "cafile = /var/snap/cinder-volume/common/etc/ssl/certs/receive-ca-bundle.pem"
        assert cafile in nova_section
        assert cafile in barbican_section
        assert cafile in glance_section
        assert "enabled_backends = ceph\ncafile =" not in rendered

    def test_cinder_conf_skips_ca_settings_when_ca_bundle_missing(self):
        """The template should omit CA settings but keep sections when no CA bundle."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                Path(cinder_volume.__file__).parent / "templates"
            )
        )

        rendered = env.get_template("cinder.conf.j2").render(
            snap_paths={"common": "/var/snap/cinder-volume/common"},
            settings={"debug": False, "enable_telemetry_notifications": False},
            rabbitmq={"url": "amqp://guest:guest@localhost:5672/"},
            database={"url": "mysql://cinder:secret@db/cinder"},
            cinder={
                "project_id": "project-id",
                "user_id": "user-id",
                "region_name": None,
                "cluster": None,
                "cluster_ok": True,
                "default_volume_type": None,
                "image_volume_cache_enabled": False,
                "image_volume_cache_max_size_gb": 0,
                "image_volume_cache_max_count": 0,
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        assert "glance_ca_certificates_file =" not in rendered
        assert "glance_api_insecure = false" not in rendered
        default_section = rendered[: rendered.index("\n[nova]\n")]
        assert "glance_catalog_info = image:glance:internalURL" in default_section
        assert "cafile =" not in rendered
        assert "region_name =" not in rendered
        assert "\n[nova]\n" in rendered
        assert "\n[barbican]\n" in rendered
        assert "\n[glance]\n" in rendered

    def test_cinder_conf_renders_internal_client_sections_when_region_is_set(self):
        """Render peer sections with internal endpoints when region exists."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                Path(cinder_volume.__file__).parent / "templates"
            )
        )

        rendered = env.get_template("cinder.conf.j2").render(
            snap_paths={"common": "/var/snap/cinder-volume/common"},
            settings={"debug": False, "enable_telemetry_notifications": False},
            rabbitmq={"url": "amqp://guest:guest@localhost:5672/"},
            database={"url": "mysql://cinder:secret@db/cinder"},
            cinder={
                "project_id": "project-id",
                "user_id": "user-id",
                "region_name": "RegionOne",
                "cluster": None,
                "cluster_ok": True,
                "default_volume_type": None,
                "image_volume_cache_enabled": False,
                "image_volume_cache_max_size_gb": 0,
                "image_volume_cache_max_count": 0,
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        assert "glance_ca_certificates_file =" not in rendered
        assert "\n[nova]\n" in rendered
        assert "\n[barbican]\n" in rendered
        assert "\n[glance]\n" in rendered
        default_section = rendered[: rendered.index("\n[nova]\n")]
        nova_section = _get_section(rendered, "nova")
        barbican_section = _get_section(rendered, "barbican")
        glance_section = _get_section(rendered, "glance")
        assert "interface = internal" in nova_section
        assert "interface = internal" in barbican_section
        assert "glance_catalog_info = image:glance:internalURL" in default_section
        assert "valid_interfaces = internal" not in rendered
        assert "service_type = image" not in rendered
        assert "service_name = glance" not in rendered
        assert "region_name = RegionOne" in nova_section
        assert "region_name = RegionOne" in barbican_section
        assert "region_name = RegionOne" in glance_section
        assert "cafile =" not in nova_section
        assert "cafile =" not in barbican_section
        assert "cafile =" not in glance_section

    def test_cinder_conf_renders_cluster_when_supported_and_set(self):
        """Cluster should be rendered when all enabled backends support it."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                Path(cinder_volume.__file__).parent / "templates"
            )
        )

        rendered = env.get_template("cinder.conf.j2").render(
            snap_paths={"common": "/var/snap/cinder-volume/common"},
            settings={"debug": False, "enable_telemetry_notifications": False},
            rabbitmq={"url": "amqp://guest:guest@localhost:5672/"},
            database={"url": "mysql://cinder:secret@db/cinder"},
            cinder={
                "project_id": "project-id",
                "user_id": "user-id",
                "region_name": None,
                "cluster": "cinder-cluster-a",
                "default_volume_type": None,
                "image_volume_cache_enabled": False,
                "image_volume_cache_max_size_gb": 0,
                "image_volume_cache_max_count": 0,
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        default_section = rendered[: rendered.index("\n[nova]\n")]
        assert "cluster = cinder-cluster-a" in default_section

    def test_cinder_conf_skips_cluster_when_backend_does_not_support_it(self):
        """Cluster should not be rendered when any enabled backend blocks it."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                Path(cinder_volume.__file__).parent / "templates"
            )
        )

        rendered = env.get_template("cinder.conf.j2").render(
            snap_paths={"common": "/var/snap/cinder-volume/common"},
            settings={"debug": False, "enable_telemetry_notifications": False},
            rabbitmq={"url": "amqp://guest:guest@localhost:5672/"},
            database={"url": "mysql://cinder:secret@db/cinder"},
            cinder={
                "project_id": "project-id",
                "user_id": "user-id",
                "region_name": None,
                "cluster": "cinder-cluster-a",
                "default_volume_type": None,
                "image_volume_cache_enabled": False,
                "image_volume_cache_max_size_gb": 0,
                "image_volume_cache_max_count": 0,
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "hitachi", "cluster_ok": False},
        )

        assert "cluster = cinder-cluster-a" not in rendered

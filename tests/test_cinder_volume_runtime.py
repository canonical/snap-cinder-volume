# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from unittest.mock import Mock

import jinja2

from cinder_volume import cinder_volume, template


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
        """The base template should reference the rendered CA bundle file."""
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
                "cluster": "cinder-cluster-a",
                "default_volume_type": None,
                "image_volume_cache_enabled": False,
                "image_volume_cache_max_size_gb": 0,
                "image_volume_cache_max_count": 0,
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        assert "cluster = cinder-cluster-a" in rendered

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

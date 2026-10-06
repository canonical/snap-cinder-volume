# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
from unittest.mock import Mock, patch

import jinja2
import pydantic
import pytest

from cinder_volume import cinder_volume, context, error, template


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

    def test_backend_contexts_discovers_infinidat_backend(self):
        """Configured Infinidat backends should be loaded at runtime."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.config.get_options.return_value.as_dict.return_value = {
            "database": {"url": "sqlite:///test.db"},
            "rabbitmq": {"url": "amqp://localhost"},
            "cinder": {"project-id": "project-id", "user-id": "user-id"},
            "infinidat": {
                "infinibox01": {
                    "volume-backend-name": "infinibox01",
                    "san-ip": "10.0.0.100",
                    "san-login": "admin",
                    "san-password": "secret",
                    "infinidat-pool-name": "cinder-pool",
                    "protocol": "fc",
                }
            },
        }

        backend_contexts = service.backend_contexts(snap)

        assert list(backend_contexts.contexts) == ["infinibox01"]
        assert isinstance(
            backend_contexts.contexts["infinibox01"], context.InfinidatBackendContext
        )
        assert backend_contexts.context()["cluster_ok"] is False

    def test_backend_contexts_discovers_netapp_backend(self):
        """Configured NetApp backends should be loaded at runtime."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.config.get_options.return_value.as_dict.return_value = {
            "database": {"url": "sqlite:///test.db"},
            "rabbitmq": {"url": "amqp://localhost"},
            "cinder": {"project-id": "project-id", "user-id": "user-id"},
            "netapp": {
                "ontap01": {
                    "volume-backend-name": "ontap01",
                    "netapp-ca-certificate-file": "CA_CONTENT",
                    "protocol": "iscsi",
                }
            },
        }

        backend_contexts = service.backend_contexts(snap)

        assert list(backend_contexts.contexts) == ["ontap01"]
        assert isinstance(
            backend_contexts.contexts["ontap01"], context.NetappBackendContext
        )

    def test_backend_contexts_discovers_nimble_backend(self):
        """Configured Nimble backends should reach the runtime context."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.config.get_options.return_value.as_dict.return_value = {
            "database": {"url": "sqlite:///test.db"},
            "rabbitmq": {"url": "amqp://localhost"},
            "cinder": {"project-id": "project-id", "user-id": "user-id"},
            "nimble": {
                "nimble01": {
                    "volume-backend-name": "nimble01",
                    "san-ip": "10.0.0.1",
                    "san-login": "user",
                    "san-password": "password",
                    "protocol": "iscsi",
                    "nimble-verify-cert-path": "NIMBLE_CA",
                    "nimble-verify-certificate": False,
                }
            },
        }

        backend_contexts = service.backend_contexts(snap)

        assert list(backend_contexts.contexts) == ["nimble01"]
        backend = backend_contexts.contexts["nimble01"]
        assert isinstance(backend, context.NimbleBackendContext)
        assert isinstance(
            backend.backend_config["nimble_verify_cert_path"],
            pydantic.SecretStr,
        )

    def test_backend_contexts_discovers_dellpowervault_backend(self):
        """Configured Dell PowerVault backends should reach the runtime context."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.config.get_options.return_value.as_dict.return_value = {
            "database": {"url": "sqlite:///test.db"},
            "rabbitmq": {"url": "amqp://localhost"},
            "cinder": {"project-id": "project-id", "user-id": "user-id"},
            "dellpowervault": {
                "vault01": {
                    "volume-backend-name": "vault01",
                    "protocol": "iscsi",
                    "driver-ssl-cert": "POWERVAULT_CA",
                }
            },
        }

        backend_contexts = service.backend_contexts(snap)

        assert list(backend_contexts.contexts) == ["vault01"]
        backend = backend_contexts.contexts["vault01"]
        assert isinstance(backend, context.DellpowervaultBackendContext)
        assert isinstance(backend.backend_config["driver_ssl_cert"], pydantic.SecretStr)

    def test_netapp_tls_material_renders_secure_files_and_paths(self, tmp_path):
        """NetApp TLS content should be written exactly outside Jinja."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        values = {
            "netapp_ssl_cert_path": "TRANSPORT{{ snap_paths.common }}",
            "netapp_private_key_file": "PRIVATE{% if unsafe %}KEY{% endif %}",
            "netapp_certificate_file": "CLIENT_CERT_CONTENT\n",
            "netapp_ca_certificate_file": "CLIENT_CA_CONTENT",
        }
        backend = context.NetappBackendContext(
            "ontap01",
            {
                "volume_backend_name": "ontap01",
                **values,
                "netapp_private_key_file": pydantic.SecretStr(
                    values["netapp_private_key_file"]
                ),
                "netapp_certificate_host_validation": False,
            },
        )
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                Path(cinder_volume.__file__).parent / "templates"
            )
        )
        env.globals.update(
            {
                "backend_ctx": context.backend_ctx,
                "cinder_name": context.cinder_name,
                "cinder_ctx": context.cinder_ctx,
            }
        )
        render_context = {
            "snap_paths": {"common": tmp_path},
            "cinder_backends": {"contexts": {"ontap01": backend.cinder_context()}},
            context.BACKEND_CTX_KEY: backend.context(),
            context.CINDER_CTX_KEY: "ontap01",
        }
        render_context["cinder_backends"]["contexts"]["ontap01"] = (
            service._render_specific_backend_configs(
                render_context, backend.cinder_context()
            )
        )

        for tpl in backend.template_files():
            service._process_template(snap, env, tpl, render_context)
        for material in backend.tls_materials:
            service._process_backend_tls_material(snap, backend, material)

        backend_dir = tmp_path / "etc/cinder/cinder.conf.d"
        rendered_config = (backend_dir / "ontap01.conf").read_text()
        expected = {
            "ontap01-netapp-ssl-cert.pem": (
                values["netapp_ssl_cert_path"].encode(),
                0o640,
            ),
            "ontap01-netapp-private-key.pem": (
                values["netapp_private_key_file"].encode(),
                0o600,
            ),
            "ontap01-netapp-certificate.pem": (
                values["netapp_certificate_file"].encode(),
                0o640,
            ),
            "ontap01-netapp-ca-certificate.pem": (
                values["netapp_ca_certificate_file"].encode(),
                0o640,
            ),
        }
        for filename, (content, mode) in expected.items():
            material_file = backend_dir / filename
            assert material_file.read_bytes() == content
            assert material_file.stat().st_mode & 0o777 == mode
            assert str(material_file) in rendered_config
            assert content.decode().strip() not in rendered_config
        assert "netapp_certificate_host_validation = False" in rendered_config

    def test_nimble_tls_material_renders_secure_file_and_path(self, tmp_path, caplog):
        """Nimble CA content should stay opaque and out of config and logs."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        material_value = "NIMBLE{{ unsafe }}"
        backend = context.NimbleBackendContext(
            "nimble01",
            {
                "volume_backend_name": "nimble01",
                "nimble_verify_cert_path": pydantic.SecretStr(material_value),
                "nimble_verify_certificate": False,
            },
        )
        backends = context.CinderBackendContexts(["nimble01"], {"nimble01": backend})
        service.render_context = Mock(return_value={"snap_paths": {"common": tmp_path}})
        service.backend_contexts = Mock(return_value=backends)
        service.template_files = Mock(return_value=[])

        service.template(snap)

        backend_dir = tmp_path / context.ETC_CINDER_D_CONF_DIR
        material_file = backend_dir / "nimble01-nimble-verify-cert.pem"
        rendered_config = (backend_dir / "nimble01.conf").read_text()
        assert material_file.read_text() == material_value
        assert material_file.stat().st_mode & 0o777 == 0o640
        assert f"nimble_verify_cert_path = {material_file}" in rendered_config
        assert "nimble_verify_certificate = False" in rendered_config
        assert material_value not in rendered_config
        assert material_value not in caplog.text

    def test_removing_nimble_tls_option_removes_material_file(self, tmp_path):
        """Removing Nimble CA content should remove its managed file."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.NimbleBackendContext("nimble01", {})
        material = next(
            item
            for item in backend.tls_materials
            if item.content_option == "nimble_verify_cert_path"
        )
        material_file = tmp_path / material.output_path()
        material_file.parent.mkdir(parents=True)
        material_file.write_text("OLD_NIMBLE_CA")

        changed = service._process_backend_tls_material(snap, backend, material)

        assert changed is True
        assert not material_file.exists()

    def test_removing_netapp_tls_option_removes_material_file(self, tmp_path):
        """Removing one NetApp TLS value should unlink its managed file."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        material_file = (
            tmp_path / "etc/cinder/cinder.conf.d/ontap01-netapp-private-key.pem"
        )
        material_file.parent.mkdir(parents=True)
        material_file.write_text("OLD_PRIVATE_KEY\n")
        backend = context.NetappBackendContext(
            "ontap01", {"volume_backend_name": "ontap01"}
        )
        material = next(
            item
            for item in backend.tls_materials
            if item.filename == "ontap01-netapp-private-key.pem"
        )

        changed = service._process_backend_tls_material(snap, backend, material)

        assert changed is True
        assert not material_file.exists()

    @pytest.mark.parametrize(
        ("backend", "option", "filename", "verify_option"),
        [
            (
                context.BaseBackendContext(
                    "generic01", {"driver_ssl_cert": "GENERIC{{ value }}"}
                ),
                "driver_ssl_cert",
                "generic01.pem",
                "driver_ssl_cert_verify",
            ),
            (
                context.HitachiBackendContext(
                    "hitachi01",
                    {
                        "hitachi_mirror_ssl_cert": pydantic.SecretStr(
                            "MIRROR{% value %}"
                        )
                    },
                ),
                "hitachi_mirror_ssl_cert",
                "hitachi01_mirror.pem",
                "hitachi_mirror_ssl_cert_verify",
            ),
        ],
    )
    def test_generic_tls_materials_use_direct_writer(
        self, tmp_path, backend, option, filename, verify_option
    ):
        """Generic and Hitachi TLS values should use the shared raw writer."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        material = next(
            item for item in backend.tls_materials if item.content_option == option
        )

        changed = service._process_backend_tls_material(snap, backend, material)

        output = tmp_path / context.ETC_CINDER_D_CONF_DIR / filename
        assert changed is True
        value = backend.backend_config[option]
        if isinstance(value, pydantic.SecretStr):
            value = value.get_secret_value()
        assert output.read_text() == value
        assert output.stat().st_mode & 0o777 == 0o640
        assert backend.cinder_context()[verify_option] is True

    def test_hitachi_mirror_material_is_opaque_and_path_only(self, tmp_path, caplog):
        """Hitachi mirror PEM should stay opaque and out of config and logs."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        material_value = "MIRROR{% unsafe %}"
        backend = context.HitachiBackendContext(
            "hitachi01",
            {
                "volume_backend_name": "hitachi01",
                "hitachi_mirror_ssl_cert": pydantic.SecretStr(material_value),
            },
        )
        backends = context.CinderBackendContexts(["hitachi01"], {"hitachi01": backend})
        service.render_context = Mock(return_value={"snap_paths": {"common": tmp_path}})
        service.backend_contexts = Mock(return_value=backends)
        service.template_files = Mock(return_value=[])

        service.template(snap)

        backend_dir = tmp_path / context.ETC_CINDER_D_CONF_DIR
        material_file = backend_dir / "hitachi01_mirror.pem"
        rendered_config = (backend_dir / "hitachi01.conf").read_text()
        assert material_file.read_text() == material_value
        assert material_file.stat().st_mode & 0o777 == 0o640
        assert f"hitachi_mirror_ssl_cert_path = {material_file}" in rendered_config
        assert "hitachi_mirror_ssl_cert_verify = True" in rendered_config
        assert "hitachi_mirror_ssl_cert =" not in rendered_config
        assert material_value not in rendered_config
        assert material_value not in caplog.text

    def test_direct_writer_replaces_from_restrictive_same_directory_temp(
        self, tmp_path
    ):
        """A changed material should be replaced from a restrictive peer file."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext(
            "generic01", {"driver_ssl_cert": "EXACT\n{{ jinja }}"}
        )
        material = next(iter(backend.tls_materials))

        with (
            patch("os.fchmod", wraps=os.fchmod) as fchmod,
            patch("os.replace", wraps=os.replace) as replace,
        ):
            changed = service._process_backend_tls_material(snap, backend, material)

        source, destination = replace.call_args.args
        assert changed is True
        assert Path(source).parent == Path(destination).parent
        assert Path(source) != Path(destination)
        assert [item.args[1] for item in fchmod.call_args_list] == [0o600, 0o640]
        assert Path(destination).read_bytes() == b"EXACT\n{{ jinja }}"

    def test_template_writer_replaces_from_same_directory_temp(self, tmp_path):
        """Rendered configuration should use the shared atomic writer."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        env = jinja2.Environment(loader=jinja2.DictLoader({"backend.j2": "NEW"}))
        tpl = template.CommonTemplate(
            "backend.conf",
            context.ETC_CINDER_D_CONF_DIR,
            template_name="backend.j2",
        )

        with patch("os.replace", wraps=os.replace) as replace:
            changed = service._process_template(snap, env, tpl, {})

        source, destination = replace.call_args.args
        assert changed is True
        assert Path(source).parent == Path(destination).parent
        assert Path(destination).read_bytes() == b"NEW\n"

    def test_direct_writer_skips_identical_content_and_mode(self, tmp_path):
        """An exact existing material should not be replaced."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext(
            "generic01", {"driver_ssl_cert": "UNCHANGED"}
        )
        material = next(iter(backend.tls_materials))
        output = tmp_path / material.output_path()
        output.parent.mkdir(parents=True)
        output.write_bytes(b"UNCHANGED")
        output.chmod(0o640)

        with patch("os.replace", wraps=os.replace) as replace:
            changed = service._process_backend_tls_material(snap, backend, material)

        assert changed is False
        replace.assert_not_called()

    def test_direct_writer_replaces_content_with_wrong_mode(self, tmp_path):
        """A material with the wrong mode should be atomically replaced."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext(
            "generic01", {"driver_ssl_cert": "UNCHANGED"}
        )
        material = next(iter(backend.tls_materials))
        output = tmp_path / material.output_path()
        output.parent.mkdir(parents=True)
        output.write_bytes(b"UNCHANGED")
        output.chmod(0o600)

        with patch("os.replace", wraps=os.replace) as replace:
            changed = service._process_backend_tls_material(snap, backend, material)

        assert changed is True
        replace.assert_called_once()
        assert output.stat().st_mode & 0o777 == 0o640

    def test_direct_writer_replaces_symlink_instead_of_following_it(self, tmp_path):
        """An existing symlink must not satisfy the unchanged-file check."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext("generic01", {"driver_ssl_cert": "SAME"})
        material = next(iter(backend.tls_materials))
        target = tmp_path / "operator-owned.pem"
        target.write_bytes(b"SAME")
        target.chmod(0o640)
        output = tmp_path / material.output_path()
        output.parent.mkdir(parents=True)
        output.symlink_to(target)

        changed = service._process_backend_tls_material(snap, backend, material)

        assert changed is True
        assert not output.is_symlink()
        assert output.read_bytes() == b"SAME"
        assert target.read_bytes() == b"SAME"

    def test_direct_writer_cleans_temporary_file_after_replace_failure(self, tmp_path):
        """A failed replacement should not leave raw temporary material behind."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext(
            "generic01", {"driver_ssl_cert": "SENSITIVE"}
        )
        material = next(iter(backend.tls_materials))
        output_dir = tmp_path / material.dest

        with (
            patch("os.replace", side_effect=OSError("replace failed")),
            pytest.raises(OSError, match="replace failed"),
        ):
            service._process_backend_tls_material(snap, backend, material)

        assert list(output_dir.iterdir()) == []

    def test_direct_writer_rejects_material_path_outside_destination(self, tmp_path):
        """A backend name must not redirect TLS material outside its directory."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext(
            "../escape", {"driver_ssl_cert": "SENSITIVE"}
        )
        material = next(iter(backend.tls_materials))

        with pytest.raises(ValueError, match="outside its destination"):
            service._process_backend_tls_material(snap, backend, material)

        assert not (tmp_path / "etc/cinder/escape.pem").exists()

    def test_template_dispatches_tls_material_to_direct_writer(self, tmp_path):
        """The rendering lifecycle should process TLS descriptors directly."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend = context.BaseBackendContext(
            "generic01", {"driver_ssl_cert": "OPAQUE{{ snap_paths.common }}"}
        )
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.render_context = Mock(return_value={"snap_paths": {"common": tmp_path}})
        service.backend_contexts = Mock(return_value=backends)
        service.template_files = Mock(return_value=[])
        backend.template_files = Mock(return_value=[])

        modified = service.template(snap)

        material = next(iter(backend.tls_materials))
        assert modified == [material]
        assert (tmp_path / material.output_path()).read_text() == (
            "OPAQUE{{ snap_paths.common }}"
        )

    def test_generic_tls_material_is_opaque_and_path_only(self, tmp_path, caplog):
        """Generic backend PEM should stay opaque and out of config and logs."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        material_value = "GENERIC{{ unsafe }}"
        backend = context.BaseBackendContext(
            "generic01",
            {
                "volume_backend_name": "generic01",
                "driver_ssl_cert": pydantic.SecretStr(material_value),
            },
        )
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.render_context = Mock(return_value={"snap_paths": {"common": tmp_path}})
        service.backend_contexts = Mock(return_value=backends)
        service.template_files = Mock(return_value=[])

        service.template(snap)

        backend_dir = tmp_path / context.ETC_CINDER_D_CONF_DIR
        material_file = backend_dir / "generic01.pem"
        rendered_config = (backend_dir / "generic01.conf").read_text()
        assert material_file.read_text() == material_value
        assert material_file.stat().st_mode & 0o777 == 0o640
        assert f"driver_ssl_cert_path = {material_file}" in rendered_config
        assert "driver_ssl_cert_verify = True" in rendered_config
        assert "driver_ssl_cert =" not in rendered_config
        assert material_value not in rendered_config
        assert material_value not in caplog.text

    def test_template_render_failure_preserves_previously_rendered_file(self, tmp_path):
        """All templates must render successfully before any file is replaced."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "valid.j2").write_text("NEW_CONTENT")
        output = tmp_path / context.ETC_CINDER_D_CONF_DIR / "valid.conf"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"ACTIVE_CONTENT\n")
        backend = context.BaseBackendContext("generic01", {})
        backend.template_files = Mock(return_value=[])
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.render_context = Mock(return_value={"snap_paths": {"common": tmp_path}})
        service.backend_contexts = Mock(return_value=backends)
        service.template_files = Mock(
            return_value=[
                template.CommonTemplate(
                    "valid.conf",
                    context.ETC_CINDER_D_CONF_DIR,
                    template_name="valid.j2",
                ),
                template.CommonTemplate(
                    "missing.conf",
                    context.ETC_CINDER_D_CONF_DIR,
                    template_name="missing.j2",
                ),
            ]
        )

        with pytest.raises(error.CinderError, match="prepare configuration files"):
            service.template(snap)

        assert output.read_bytes() == b"ACTIVE_CONTENT\n"

    def test_prepared_files_reject_duplicate_destinations_before_writing(
        self, tmp_path
    ):
        """Two descriptors must not manage the same resolved destination."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        first = template.CommonTemplate("duplicate.conf", context.ETC_CINDER_D_CONF_DIR)
        second = template.CommonTemplate(
            "duplicate.conf", context.ETC_CINDER_D_CONF_DIR
        )
        output = tmp_path / first.output_path()
        output.parent.mkdir(parents=True)
        output.write_bytes(b"ACTIVE\n")

        with pytest.raises(error.CinderError, match="duplicate managed destination"):
            service._write_prepared_files(
                snap, [(first, b"FIRST\n"), (second, b"SECOND\n")]
            )

        assert output.read_bytes() == b"ACTIVE\n"

    def test_configure_rejects_duplicate_destinations_before_setup(self, tmp_path):
        """Destination ownership must be unique before directory mutation."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "duplicate.j2").write_text("CONTENT")
        duplicate = template.CommonTemplate(
            "duplicate.conf",
            context.ETC_CINDER_D_CONF_DIR,
            template_name="duplicate.j2",
        )
        service.template_files = Mock(return_value=[duplicate, duplicate])
        service.render_context = Mock(return_value={"snap_paths": {"common": tmp_path}})
        backend = context.BaseBackendContext("generic01", {})
        backend.template_files = Mock(return_value=[])
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.backend_contexts = Mock(return_value=backends)
        service.setup_dirs = Mock()

        with pytest.raises(error.CinderError, match="prepare configuration files"):
            service.configure(snap)

        service.setup_dirs.assert_not_called()
        assert not (tmp_path / duplicate.output_path()).exists()

    def test_prepared_files_roll_back_after_later_replace_failure(self, tmp_path):
        """A failed later replacement must restore earlier active files."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        first = template.CommonTemplate("first.conf", context.ETC_CINDER_D_CONF_DIR)
        second = template.CommonTemplate("second.conf", context.ETC_CINDER_D_CONF_DIR)
        first_output = tmp_path / first.output_path()
        second_output = tmp_path / second.output_path()
        first_output.parent.mkdir(parents=True)
        first_output.write_bytes(b"ACTIVE_FIRST\n")
        second_output.write_bytes(b"ACTIVE_SECOND\n")
        real_replace = os.replace
        replacements = 0

        def fail_second_replace(source, destination):
            nonlocal replacements
            if Path(destination) in {first_output, second_output}:
                replacements += 1
            if replacements == 2:
                raise OSError("replace failed")
            return real_replace(source, destination)

        with (
            patch("os.replace", side_effect=fail_second_replace),
            pytest.raises(OSError, match="replace failed"),
        ):
            service._write_prepared_files(
                snap, [(first, b"NEW_FIRST\n"), (second, b"NEW_SECOND\n")]
            )

        assert first_output.read_bytes() == b"ACTIVE_FIRST\n"
        assert second_output.read_bytes() == b"ACTIVE_SECOND\n"
        assert list(first_output.parent.glob(".*")) == []

    def test_prepared_files_replace_before_deleting(self, tmp_path):
        """All replacements must finish before requested deletions begin."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        removed = template.CommonTemplate("removed.conf", context.ETC_CINDER_D_CONF_DIR)
        replaced = template.CommonTemplate(
            "replaced.conf", context.ETC_CINDER_D_CONF_DIR
        )
        removed_output = tmp_path / removed.output_path()
        replaced_output = tmp_path / replaced.output_path()
        removed_output.parent.mkdir(parents=True)
        removed_output.write_bytes(b"REMOVE\n")
        replaced_output.write_bytes(b"ACTIVE\n")
        real_replace = os.replace
        real_unlink = Path.unlink
        operations = []

        def observe_replace(source, destination):
            if Path(destination) == replaced_output:
                operations.append("replace")
            return real_replace(source, destination)

        def observe_unlink(path, *args, **kwargs):
            if path == removed_output:
                operations.append("delete")
            return real_unlink(path, *args, **kwargs)

        with (
            patch("os.replace", side_effect=observe_replace),
            patch.object(Path, "unlink", autospec=True, side_effect=observe_unlink),
        ):
            service._write_prepared_files(snap, [(removed, None), (replaced, b"NEW\n")])

        assert operations == ["replace", "delete"]

    def test_prepared_files_roll_back_after_later_delete_failure(self, tmp_path):
        """A failed deletion must restore replacements and earlier deletions."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        replaced = template.CommonTemplate(
            "replaced.conf", context.ETC_CINDER_D_CONF_DIR
        )
        first_removed = template.CommonTemplate(
            "first-removed.conf", context.ETC_CINDER_D_CONF_DIR
        )
        second_removed = template.CommonTemplate(
            "second-removed.conf", context.ETC_CINDER_D_CONF_DIR
        )
        outputs = {
            replaced: tmp_path / replaced.output_path(),
            first_removed: tmp_path / first_removed.output_path(),
            second_removed: tmp_path / second_removed.output_path(),
        }
        outputs[replaced].parent.mkdir(parents=True)
        for managed_file, output in outputs.items():
            output.write_bytes(f"ACTIVE_{managed_file.filename}\n".encode())
        real_unlink = Path.unlink

        def fail_second_delete(path, *args, **kwargs):
            if path == outputs[second_removed]:
                raise PermissionError("delete failed")
            return real_unlink(path, *args, **kwargs)

        with (
            patch.object(Path, "unlink", autospec=True, side_effect=fail_second_delete),
            pytest.raises(PermissionError, match="delete failed"),
        ):
            service._write_prepared_files(
                snap,
                [(replaced, b"NEW\n"), (first_removed, None), (second_removed, None)],
            )

        for managed_file, output in outputs.items():
            assert output.read_bytes() == (f"ACTIVE_{managed_file.filename}\n".encode())
        assert list(outputs[replaced].parent.glob(".*")) == []

    def test_prepared_files_restore_symlink_after_later_failure(self, tmp_path):
        """Rollback must restore a symlink without modifying its target."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        symlink_file = template.CommonTemplate(
            "linked.conf", context.ETC_CINDER_D_CONF_DIR
        )
        later_file = template.CommonTemplate(
            "later.conf", context.ETC_CINDER_D_CONF_DIR
        )
        symlink_output = tmp_path / symlink_file.output_path()
        later_output = tmp_path / later_file.output_path()
        symlink_output.parent.mkdir(parents=True)
        target = tmp_path / "operator-owned.conf"
        target.write_bytes(b"OPERATOR\n")
        symlink_output.symlink_to(target)
        later_output.write_bytes(b"ACTIVE_LATER\n")
        real_replace = os.replace

        def fail_later_replace(source, destination):
            if Path(destination) == later_output:
                raise OSError("replace failed")
            return real_replace(source, destination)

        with (
            patch("os.replace", side_effect=fail_later_replace),
            pytest.raises(OSError, match="replace failed"),
        ):
            service._write_prepared_files(
                snap, [(symlink_file, b"NEW\n"), (later_file, b"NEW_LATER\n")]
            )

        assert symlink_output.is_symlink()
        assert symlink_output.resolve() == target
        assert target.read_bytes() == b"OPERATOR\n"
        assert later_output.read_bytes() == b"ACTIVE_LATER\n"
        assert list(symlink_output.parent.glob(".*")) == []

    def test_prepared_replacements_keep_active_paths_present(self, tmp_path):
        """Replacing files must never rename active paths out of the way."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        managed_file = template.CommonTemplate(
            "active.conf", context.ETC_CINDER_D_CONF_DIR
        )
        output = tmp_path / managed_file.output_path()
        output.parent.mkdir(parents=True)
        output.write_bytes(b"ACTIVE\n")
        real_replace = os.replace
        active_path_states = []

        def observe_replace(source, destination):
            if Path(destination) == output:
                active_path_states.append(output.exists())
            return real_replace(source, destination)

        with patch("os.replace", side_effect=observe_replace):
            service._write_prepared_files(snap, [(managed_file, b"NEW\n")])

        assert active_path_states == [True]
        assert output.read_bytes() == b"NEW\n"

    def test_removing_netapp_backend_removes_owned_material_only(self, tmp_path):
        """Backend cleanup should remove only owned NetApp TLS files."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend_dir = tmp_path / "etc/cinder/cinder.conf.d"
        backend_dir.mkdir(parents=True)
        owned_files = [
            backend_dir / "ontap01-netapp-ssl-cert.pem",
            backend_dir / "ontap01-netapp-private-key.pem",
            backend_dir / "ontap01-netapp-certificate.pem",
            backend_dir / "ontap01-netapp-ca-certificate.pem",
        ]
        for owned_file in owned_files:
            owned_file.write_text("STALE_MATERIAL\n")
        unrelated_file = backend_dir / "operator-managed.pem"
        unrelated_file.write_text("KEEP\n")

        service._remove_backend_files(service._existing_managed_backend_files(snap))

        assert all(not owned_file.exists() for owned_file in owned_files)
        assert unrelated_file.read_text() == "KEEP\n"

    def test_removing_nimble_backend_removes_owned_material_only(self, tmp_path):
        """Backend cleanup should remove owned Nimble CA material only."""
        service = cinder_volume.GenericCinderVolume()
        snap = Mock()
        snap.paths.common = tmp_path
        backend_dir = tmp_path / context.ETC_CINDER_D_CONF_DIR
        backend_dir.mkdir(parents=True)
        owned_file = backend_dir / "nimble01-nimble-verify-cert.pem"
        owned_file.write_text("STALE_NIMBLE_CA\n")
        unrelated_file = backend_dir / "operator-managed.pem"
        unrelated_file.write_text("KEEP\n")

        service._remove_backend_files(service._existing_managed_backend_files(snap))

        assert not owned_file.exists()
        assert unrelated_file.read_text() == "KEEP\n"

    def test_configure_preserves_active_tls_material_when_validation_fails(
        self, tmp_path
    ):
        """Invalid replacement config must not remove active TLS material."""
        service = cinder_volume.GenericCinderVolume()
        service.backend_contexts = Mock(
            side_effect=error.CinderError("Invalid configuration")
        )
        snap = Mock()
        snap.paths.common = tmp_path
        material_file = (
            tmp_path / "etc/cinder/cinder.conf.d/ontap01-netapp-private-key.pem"
        )
        material_file.parent.mkdir(parents=True)
        material_file.write_bytes(b"ACTIVE_PRIVATE_KEY")
        material_file.chmod(0o600)

        with pytest.raises(error.CinderError, match="Invalid configuration"):
            service.configure(snap)

        assert material_file.read_bytes() == b"ACTIVE_PRIVATE_KEY"
        assert material_file.stat().st_mode & 0o777 == 0o600

    def test_configure_preserves_active_files_when_rendering_fails(self, tmp_path):
        """A rendering failure must not clear active backend files."""
        service = cinder_volume.GenericCinderVolume()
        backend = context.BaseBackendContext("generic01", {})
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.backend_contexts = Mock(return_value=backends)
        service._prepare_configuration_files = Mock(
            side_effect=error.CinderError("Failed to prepare configuration files")
        )
        service.setup_dirs = Mock()
        snap = Mock()
        snap.paths.common = tmp_path
        active_file = (
            tmp_path / "etc/cinder/cinder.conf.d/ontap01-netapp-private-key.pem"
        )
        active_file.parent.mkdir(parents=True)
        active_file.write_bytes(b"ACTIVE_PRIVATE_KEY")

        with pytest.raises(error.CinderError, match="prepare configuration files"):
            service.configure(snap)

        assert active_file.read_bytes() == b"ACTIVE_PRIVATE_KEY"
        service.setup_dirs.assert_not_called()

    def test_configure_prunes_only_stale_files_after_success(self, tmp_path):
        """Successful configure should preserve desired files and remove stale ones."""
        service = cinder_volume.GenericCinderVolume()
        backend = context.BaseBackendContext("generic01", {})
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.backend_contexts = Mock(return_value=backends)
        service._prepare_configuration_files = Mock(return_value=[])
        service._write_configuration_files = Mock(return_value=[])
        service.start_services = Mock()
        snap = Mock()
        snap.paths.common = tmp_path
        backend_dir = tmp_path / context.ETC_CINDER_D_CONF_DIR
        backend_dir.mkdir(parents=True)
        desired_file = backend_dir / "generic01.conf"
        desired_file.write_bytes(b"ACTIVE_CONFIG\n")
        stale_file = backend_dir / "removed.conf"
        stale_file.write_bytes(b"STALE_CONFIG\n")

        service.configure(snap)

        assert desired_file.read_bytes() == b"ACTIVE_CONFIG\n"
        assert not stale_file.exists()

    def test_prune_failure_aborts_configuration(self, tmp_path):
        """Incomplete stale-file cleanup must fail configuration."""
        service = cinder_volume.GenericCinderVolume()
        backend = context.BaseBackendContext("generic01", {})
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.backend_contexts = Mock(return_value=backends)
        service._prepare_configuration_files = Mock(return_value=[])
        service._write_configuration_files = Mock(return_value=[])
        service.start_services = Mock()
        snap = Mock()
        snap.paths.common = tmp_path
        stale_file = tmp_path / context.ETC_CINDER_D_CONF_DIR / "removed.conf"
        stale_file.parent.mkdir(parents=True)
        stale_file.write_bytes(b"STALE_CONFIG\n")

        with (
            patch.object(Path, "unlink", side_effect=PermissionError("denied")),
            pytest.raises(error.CinderError, match="remove managed backend files"),
        ):
            service.configure(snap)

        service.start_services.assert_not_called()

    def test_prune_only_change_is_reported_for_service_restart(self, tmp_path):
        """Removing a stale backend file must be a restart-triggering change."""
        service = cinder_volume.GenericCinderVolume()
        backend = context.BaseBackendContext("generic01", {})
        backends = context.CinderBackendContexts(["generic01"], {"generic01": backend})
        service.backend_contexts = Mock(return_value=backends)
        service._prepare_configuration_files = Mock(return_value=[])
        service._write_configuration_files = Mock(return_value=[])
        service.start_services = Mock()
        snap = Mock()
        snap.paths.common = tmp_path
        stale_file = tmp_path / context.ETC_CINDER_D_CONF_DIR / "removed.conf"
        stale_file.parent.mkdir(parents=True)
        stale_file.write_bytes(b"STALE_CONFIG\n")

        service.configure(snap)

        modified, backend_files = service.start_services.call_args.args[1:]
        relative_stale = stale_file.relative_to(tmp_path)
        assert relative_stale in modified
        assert relative_stale in backend_files

    def test_configure_preserves_owned_material_when_no_backends_validate(
        self, tmp_path
    ):
        """An invalid empty backend set must preserve active material."""
        service = cinder_volume.GenericCinderVolume()
        service.backend_contexts = Mock(
            side_effect=error.CinderError("At least one backend must be enabled")
        )
        snap = Mock()
        snap.paths.common = tmp_path
        material_file = (
            tmp_path / "etc/cinder/cinder.conf.d/ontap01-netapp-private-key.pem"
        )
        material_file.parent.mkdir(parents=True)
        material_file.write_bytes(b"STALE_PRIVATE_KEY")

        with pytest.raises(
            error.CinderError, match="At least one backend must be enabled"
        ):
            service.configure(snap)

        assert material_file.read_bytes() == b"STALE_PRIVATE_KEY"

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
        assert "barbican_endpoint_type = internal" in barbican_section
        assert "glance_catalog_info = image:glance:internalURL" in default_section
        assert "valid_interfaces = internal" not in rendered
        assert "service_type = image" not in rendered
        assert "service_name = glance" not in rendered
        assert "region_name = RegionOne" in nova_section
        assert "region_name = RegionOne" in barbican_section
        assert "region_name = RegionOne" in glance_section
        cafile = "cafile = /var/snap/cinder-volume/common/etc/ssl/certs/receive-ca-bundle.pem"
        assert cafile in nova_section
        assert cafile in glance_section
        cafile = "verify_ssl_path = /var/snap/cinder-volume/common/etc/ssl/certs/receive-ca-bundle.pem"
        assert cafile in barbican_section
        assert "enabled_backends = ceph\ncafile =" not in rendered

    def test_cinder_conf_renders_nova_auth_when_identity_set(self):
        """The [nova] section should carry auth options when identity is set."""
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
            identity={
                "auth_url": "http://keystone.internal/openstack-keystone/v3",
                "username": "cinder-volume",
                "password": "secret",
                "project_name": "services",
                "user_domain_name": "service_domain",
                "project_domain_name": "service_domain",
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        nova_section = _get_section(rendered, "nova")
        assert "interface = internal" in nova_section
        assert "auth_type = password" in nova_section
        assert (
            "auth_url = http://keystone.internal/openstack-keystone/v3" in nova_section
        )
        assert "username = cinder-volume" in nova_section
        assert "password = secret" in nova_section
        assert "project_name = services" in nova_section
        assert "user_domain_name = service_domain" in nova_section
        assert "project_domain_name = service_domain" in nova_section

    def test_cinder_conf_skips_nova_auth_when_identity_unset(self):
        """The [nova] section should have no auth options without identity."""
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
            identity={
                "auth_url": None,
                "username": None,
                "password": None,
                "project_name": None,
                "user_domain_name": None,
                "project_domain_name": None,
            },
            ca={"bundle": None},
            cinder_backends={"enabled_backends": "ceph", "cluster_ok": True},
        )

        nova_section = _get_section(rendered, "nova")
        assert "interface = internal" in nova_section
        assert "auth_type" not in nova_section
        assert "auth_url" not in nova_section

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
        assert "barbican_endpoint_type = internal" in barbican_section
        assert "glance_catalog_info = image:glance:internalURL" in default_section
        assert "valid_interfaces = internal" not in rendered
        assert "service_type = image" not in rendered
        assert "service_name = glance" not in rendered
        assert "region_name = RegionOne" in nova_section
        assert "region_name = RegionOne" in barbican_section
        assert "region_name = RegionOne" in glance_section
        assert "cafile =" not in nova_section
        assert "verify_ssl_path =" not in barbican_section
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

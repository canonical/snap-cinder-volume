# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend templating logic.

These tests verify that backend configurations are correctly templated
and rendered into Cinder configuration files.
"""

from unittest.mock import Mock, patch

import jinja2
import pydantic
import pytest

from cinder_volume import context, error


class TestBaseBackendContext:
    """Test the BaseBackendContext class and its templating logic."""

    def test_base_backend_context_creation(self):
        """Test creating a BaseBackendContext instance."""
        backend_config = {
            "volume_backend_name": "test-backend",
            "volume_dd_blocksize": 4096,
        }
        ctx = context.BaseBackendContext("test-backend", backend_config)
        assert ctx.namespace == "test-backend"
        assert ctx.backend_name == "test-backend"
        assert ctx.backend_config == backend_config
        assert ctx.supports_cluster is True

    def test_subclass_tls_material_uses_generic_rendering_path(self):
        """A subclass descriptor should route content through the base class."""

        class TestBackendContext(context.BaseBackendContext):
            _tls_materials = (
                context.BackendTLSMaterial(
                    content_option="test_tls_content",
                    path_option="test_tls_path",
                    filename="{backend_name}-test-tls.pem",
                    dest=context.ETC_CINDER_D_CONF_DIR,
                    mode=0o600,
                    verify_option="test_tls_verify",
                ),
            )

        ctx = TestBackendContext(
            "test-backend",
            {"test_tls_content": pydantic.SecretStr("PRIVATE_MATERIAL")},
        )

        cinder_context = ctx.cinder_context()
        material = next(
            item
            for item in ctx.tls_materials
            if item.content_option == "test_tls_content"
        )

        assert cinder_context == {
            "test_tls_path": (
                "{{ snap_paths.common }}/etc/cinder/cinder.conf.d/"
                "test-backend-test-tls.pem"
            ),
            "test_tls_verify": True,
        }
        assert "PRIVATE_MATERIAL" not in str(cinder_context)
        assert material.filename == "test-backend-test-tls.pem"
        assert material.dest == context.ETC_CINDER_D_CONF_DIR
        assert material.mode == 0o600

    def test_base_backend_context_context_method(self):
        """Test the context method returns backend config."""
        backend_config = {
            "volume_backend_name": "test-backend",
            "volume_dd_blocksize": 4096,
            "custom_option": "value",
        }
        ctx = context.BaseBackendContext("test-backend", backend_config)
        result = ctx.context()
        assert result == backend_config

    def test_base_backend_context_discards_unsupported_driver_ssl_cert(self):
        """Unsupported backends never emit a CA path or PEM content."""
        backend_config = {
            "volume_backend_name": "test-backend",
            "driver_ssl_cert": "-----BEGIN CERTIFICATE-----\n...",
        }
        ctx = context.InfinidatBackendContext("test-backend", backend_config)
        result = ctx.cinder_context()

        assert "driver_ssl_cert" not in result
        assert "driver_ssl_cert_path" not in result
        assert "driver_ssl_cert_verify" not in result

    def test_driver_ssl_cert_is_registered_only_by_supported_backends(self):
        """A custom CA is an explicit driver capability."""
        ctx = context.InfinidatBackendContext("test-backend", {})

        assert list(ctx.tls_materials) == []

        ctx = context.DellpowerstoreBackendContext("test-backend", {})

        materials = {item.content_option: item for item in ctx.tls_materials}

        material = materials["driver_ssl_cert"]
        assert material.path_option == "driver_ssl_cert_path"
        assert material.filename == "test-backend.pem"
        assert material.dest == context.ETC_CINDER_D_CONF_DIR
        assert material.output_path() == (
            context.ETC_CINDER_D_CONF_DIR / "test-backend.pem"
        )
        assert material.mode == 0o640
        assert material.verify_option == "driver_ssl_cert_verify"
        assert material.cleanup is False

    def test_base_backend_cinder_context_removes_hidden_keys(self):
        """Test cinder_context removes hidden keys like driver_ssl_cert."""
        backend_config = {
            "volume_backend_name": "test-backend",
            "driver_ssl_cert": "cert-content",
            "volume_dd_blocksize": 4096,
        }
        ctx = context.BaseBackendContext("test-backend", backend_config)
        result = ctx.cinder_context()

        assert "driver_ssl_cert" not in result
        assert result["volume_backend_name"] == "test-backend"
        assert result["volume_dd_blocksize"] == 4096

    def test_base_backend_cinder_context_filters_none_values(self):
        """Test cinder_context filters out None values."""
        backend_config = {
            "volume_backend_name": "test-backend",
            "image_volume_cache_enabled": None,
            "volume_dd_blocksize": 4096,
        }
        ctx = context.BaseBackendContext("test-backend", backend_config)
        result = ctx.cinder_context()

        assert "image_volume_cache_enabled" not in result
        assert "volume_dd_blocksize" in result

    def test_base_backend_template_files(self):
        """Test template_files returns expected templates."""
        ctx = context.BaseBackendContext("test-backend", {})
        templates = ctx.template_files()

        assert len(templates) == 1
        assert templates[0].filename == "test-backend.conf"
        assert templates[0].template_name == "backend.conf.j2"

    def test_supported_backend_tls_material_is_not_a_jinja_template(self):
        """A supported driver's TLS material bypasses Jinja templates."""
        ctx = context.DellpowerstoreBackendContext("test-backend", {})

        assert [item.filename for item in ctx.template_files()] == ["test-backend.conf"]
        assert [item.filename for item in ctx.tls_materials] == ["test-backend.pem"]

    def test_base_backend_directories(self):
        """Test directories returns empty list for base backend."""
        ctx = context.BaseBackendContext("test-backend", {})
        assert ctx.directories() == []

    def test_base_backend_setup(self):
        """Test setup method does nothing for base backend."""
        ctx = context.BaseBackendContext("test-backend", {})
        mock_snap = Mock()
        # Should not raise any errors
        ctx.setup(mock_snap)


class TestCinderBackendContexts:
    """Test the CinderBackendContexts class for managing multiple backends."""

    def test_cinder_backend_contexts_creation(self):
        """Test creating a CinderBackendContexts instance."""
        ctx1 = context.BaseBackendContext("backend1", {"volume_backend_name": "b1"})
        ctx2 = context.BaseBackendContext("backend2", {"volume_backend_name": "b2"})
        contexts = {"backend1": ctx1, "backend2": ctx2}

        cbc = context.CinderBackendContexts(["backend1", "backend2"], contexts)
        assert cbc.namespace == "cinder_backends"
        assert cbc.enabled_backends == ["backend1", "backend2"]
        assert cbc.contexts == contexts

    def test_cinder_backend_contexts_requires_enabled_backends(self):
        """Test that at least one backend must be enabled."""
        with pytest.raises(error.CinderError, match="At least one backend"):
            context.CinderBackendContexts([], {})

    def test_cinder_backend_contexts_validates_missing_contexts(self):
        """Test that all enabled backends must have contexts."""
        ctx1 = context.BaseBackendContext("backend1", {"volume_backend_name": "b1"})
        contexts = {"backend1": ctx1}

        with pytest.raises(
            error.CinderError, match="Context missing configuration for backends"
        ):
            context.CinderBackendContexts(["backend1", "backend2"], contexts)

    def test_cinder_backend_contexts_context_method(self):
        """Test the context method returns enabled_backends and cluster_ok."""
        ctx1 = context.BaseBackendContext("backend1", {"volume_backend_name": "b1"})
        ctx2 = context.BaseBackendContext("backend2", {"volume_backend_name": "b2"})
        contexts = {"backend1": ctx1, "backend2": ctx2}

        cbc = context.CinderBackendContexts(["backend1", "backend2"], contexts)
        result = cbc.context()

        assert result["enabled_backends"] == "backend1,backend2"
        assert result["cluster_ok"] is True
        assert "contexts" in result
        assert "backend1" in result["contexts"]
        assert "backend2" in result["contexts"]

    def test_cinder_backend_contexts_cluster_ok_false_when_unsupported(self):
        """Test that cluster_ok is False when any backend doesn't support clustering."""
        ctx1 = context.BaseBackendContext("backend1", {"volume_backend_name": "b1"})
        ctx1.supports_cluster = True
        ctx2 = context.HitachiBackendContext("backend2", {"volume_backend_name": "b2"})
        # Hitachi doesn't support clustering
        contexts = {"backend1": ctx1, "backend2": ctx2}

        cbc = context.CinderBackendContexts(["backend1", "backend2"], contexts)
        result = cbc.context()

        assert result["cluster_ok"] is False

    def test_cinder_backend_contexts_cluster_ok_true_when_all_supported(self):
        """Test that cluster_ok is True when all backends support clustering."""
        ctx1 = context.CephBackendContext("backend1", {"volume_backend_name": "b1"})
        ctx2 = context.PureBackendContext("backend2", {"volume_backend_name": "b2"})
        contexts = {"backend1": ctx1, "backend2": ctx2}

        cbc = context.CinderBackendContexts(["backend1", "backend2"], contexts)
        result = cbc.context()

        assert result["cluster_ok"] is True


class TestHitachiBackendTLSMaterial:
    """Retain the existing Hitachi mirror TLS material behavior."""

    def test_hitachi_mirror_public_input_routes_to_cinder_path(self):
        """The charm's mirror certificate input should become a Cinder path."""
        ctx = context.HitachiBackendContext(
            "hitachi01",
            {"hitachi_mirror_ssl_cert": pydantic.SecretStr("MIRROR_CA_CONTENT")},
        )

        result = ctx.cinder_context()
        materials = {item.filename: item for item in ctx.tls_materials}
        material = materials["hitachi01_mirror.pem"]

        assert result["hitachi_mirror_ssl_cert_path"] == (
            "{{ snap_paths.common }}/etc/cinder/cinder.conf.d/hitachi01_mirror.pem"
        )
        assert result["hitachi_mirror_ssl_cert_verify"] is True
        assert "hitachi_mirror_ssl_cert" not in result
        assert "MIRROR_CA_CONTENT" not in str(result)
        assert material.content_option == "hitachi_mirror_ssl_cert"

    def test_hitachi_mirror_tls_material_is_rendered_as_a_path(self):
        """Test mirror CA content remains hidden behind its rendered path."""
        ctx = context.HitachiBackendContext(
            "hitachi01",
            {
                "volume_backend_name": "hitachi01",
                "hitachi_mirror_ssl_cert": pydantic.SecretStr("MIRROR_CA_CONTENT"),
            },
        )

        result = ctx.cinder_context()
        full_context = ctx.context()
        materials = {item.filename: item for item in ctx.tls_materials}

        assert "MIRROR_CA_CONTENT" not in str(result)
        assert "hitachi_mirror_ssl_cert" not in full_context
        assert result["hitachi_mirror_ssl_cert_path"] == (
            "{{ snap_paths.common }}/etc/cinder/cinder.conf.d/hitachi01_mirror.pem"
        )
        assert result["hitachi_mirror_ssl_cert_verify"] is True
        assert materials["hitachi01_mirror.pem"].mode == 0o640

    def test_hitachi_mirror_tls_material_uses_generic_registry(self):
        """The Hitachi mirror certificate should be declared generically."""
        ctx = context.HitachiBackendContext("hitachi01", {})

        materials = {item.content_option: item for item in ctx.tls_materials}

        material = materials["hitachi_mirror_ssl_cert"]
        assert material.path_option == "hitachi_mirror_ssl_cert_path"
        assert material.filename == "hitachi01_mirror.pem"
        assert material.dest == context.ETC_CINDER_D_CONF_DIR
        assert material.mode == 0o640
        assert material.verify_option == "hitachi_mirror_ssl_cert_verify"
        assert material.cleanup is False


class TestNetappBackendTLSMaterials:
    """Characterize NetApp declarations in the generic TLS registry."""

    def test_netapp_tls_materials_use_generic_registry(self):
        """NetApp should declare all four materials without changing metadata."""
        ctx = context.NetappBackendContext("ontap01", {})

        materials = {item.content_option: item for item in ctx.tls_materials}

        expected = {
            "netapp_ssl_cert_path": (
                "ontap01-netapp-ssl-cert.pem",
                0o640,
            ),
            "netapp_private_key_file": (
                "ontap01-netapp-private-key.pem",
                0o600,
            ),
            "netapp_certificate_file": (
                "ontap01-netapp-certificate.pem",
                0o640,
            ),
            "netapp_ca_certificate_file": (
                "ontap01-netapp-ca-certificate.pem",
                0o640,
            ),
        }
        for option, (filename, mode) in expected.items():
            material = materials[option]
            assert material.path_option == option
            assert material.filename == filename
            assert material.dest == context.ETC_CINDER_D_CONF_DIR
            assert material.mode == mode
            assert material.verify_option is None
            assert material.cleanup is True

    def test_cleanup_paths_cover_owned_backend_tls_material_only(self):
        """Cleanup discovery should include only explicitly owned TLS files."""
        assert set(context.backend_tls_material_cleanup_paths()) == {
            context.ETC_CINDER_D_CONF_DIR / "*-netapp-ssl-cert.pem",
            context.ETC_CINDER_D_CONF_DIR / "*-netapp-private-key.pem",
            context.ETC_CINDER_D_CONF_DIR / "*-netapp-certificate.pem",
            context.ETC_CINDER_D_CONF_DIR / "*-netapp-ca-certificate.pem",
            context.ETC_CINDER_D_CONF_DIR / "*-nimble-verify-cert.pem",
        }


class TestNimbleBackendTLSMaterial:
    """Characterize Nimble verification certificate material."""

    @pytest.mark.parametrize("verify", [False, True])
    def test_nimble_tls_material_routes_to_path_without_changing_verify(self, verify):
        """Nimble certificate content should become a path only."""
        ctx = context.NimbleBackendContext(
            "nimble01",
            {
                "nimble_verify_cert_path": pydantic.SecretStr("NIMBLE_CA"),
                "nimble_verify_certificate": verify,
            },
        )

        result = ctx.cinder_context()
        materials = {item.content_option: item for item in ctx.tls_materials}
        material = materials["nimble_verify_cert_path"]

        assert result["nimble_verify_cert_path"] == (
            "{{ snap_paths.common }}/etc/cinder/cinder.conf.d/"
            "nimble01-nimble-verify-cert.pem"
        )
        assert result["nimble_verify_certificate"] is verify
        assert "NIMBLE_CA" not in str(result)
        assert material.path_option == "nimble_verify_cert_path"
        assert material.filename == "nimble01-nimble-verify-cert.pem"
        assert material.dest == context.ETC_CINDER_D_CONF_DIR
        assert material.mode == 0o640
        assert material.verify_option is None
        assert material.cleanup is True


@pytest.mark.parametrize(
    ("backend", "expected"),
    [
        (
            context.DellscBackendContext(
                "dellsc01",
                {
                    "dell_sc_verify_cert": False,
                    "san_private_key": "/etc/cinder/dellsc.key",
                },
            ),
            {
                "dell_sc_verify_cert": False,
                "san_private_key": "/etc/cinder/dellsc.key",
            },
        ),
        (
            context.FujitsueternusdxBackendContext(
                "fujitsu01",
                {
                    "cinder_eternus_config_file": "/etc/cinder/eternus.xml",
                    "fujitsu_private_key_path": "$state_path/eternus",
                },
            ),
            {
                "cinder_eternus_config_file": "/etc/cinder/eternus.xml",
                "fujitsu_private_key_path": "$state_path/eternus",
            },
        ),
        (
            context.HuaweidoradoBackendContext(
                "huawei01",
                {"cinder_huawei_conf_file": "/etc/cinder/huawei.xml"},
            ),
            {"cinder_huawei_conf_file": "/etc/cinder/huawei.xml"},
        ),
        (
            context.IbmgpfsBackendContext(
                "gpfs01",
                {
                    "gpfs_private_key": "/etc/cinder/gpfs.key",
                    "gpfs_hosts_key_file": "$state_path/ssh_known_hosts",
                },
            ),
            {
                "gpfs_private_key": "/etc/cinder/gpfs.key",
                "gpfs_hosts_key_file": "$state_path/ssh_known_hosts",
            },
        ),
        (
            context.SynologyBackendContext("synology01", {"synology_ssl_verify": True}),
            {"synology_ssl_verify": True},
        ),
        (
            context.ZadaraBackendContext(
                "zadara01",
                {"zadara_vpsa_use_ssl": False, "zadara_ssl_cert_verify": True},
            ),
            {"zadara_vpsa_use_ssl": False, "zadara_ssl_cert_verify": True},
        ),
    ],
)
def test_non_material_paths_and_verification_booleans_pass_through(backend, expected):
    """Existing Cinder paths and booleans should remain unchanged."""
    result = backend.cinder_context()

    assert {key: result[key] for key in expected} == expected


class TestBackendTemplateRendering:
    """Test backend template rendering with Jinja2."""

    def test_backend_conf_template_renders(self):
        """Test that backend.conf.j2 template renders correctly."""
        # Create a Jinja2 environment with the template
        template_str = """[{{ cinder_name() }}]
{%- for key, value in cinder_ctx().items() %}
{{ key }} = {{ value }}
{%- endfor %}
"""
        env = jinja2.Environment(
            loader=jinja2.DictLoader({"backend.conf.j2": template_str})
        )
        env.globals.update(
            {
                "cinder_name": context.cinder_name,
                "cinder_ctx": context.cinder_ctx,
            }
        )

        # Create test context
        test_context = {
            context.CINDER_CTX_KEY: "test-backend",
            "cinder_backends": {
                "contexts": {
                    "test-backend": {
                        "volume_driver": "test.driver",
                        "volume_backend_name": "test-backend",
                        "san_ip": "10.0.0.1",
                    }
                }
            },
        }

        template = env.get_template("backend.conf.j2")
        rendered = template.render(**test_context)

        assert "[test-backend]" in rendered
        assert "volume_driver = test.driver" in rendered
        assert "volume_backend_name = test-backend" in rendered
        assert "san_ip = 10.0.0.1" in rendered

    def test_backend_conf_template_with_ceph(self):
        """Test rendering Ceph backend configuration."""
        template_str = """[{{ cinder_name() }}]
{%- for key, value in cinder_ctx().items() %}
{{ key }} = {{ value }}
{%- endfor %}
"""
        env = jinja2.Environment(
            loader=jinja2.DictLoader({"backend.conf.j2": template_str})
        )
        env.globals.update(
            {
                "cinder_name": context.cinder_name,
                "cinder_ctx": context.cinder_ctx,
            }
        )

        # Create Ceph backend context
        ceph_ctx = context.CephBackendContext(
            "ceph-rbd",
            {
                "volume_backend_name": "ceph-rbd",
                "rbd_pool": "cinder-volumes",
                "rbd_user": "cinder",
                "rbd_key": "secret-key",  # Should be hidden
            },
        )

        test_context = {
            context.CINDER_CTX_KEY: "ceph-rbd",
            "cinder_backends": {"contexts": {"ceph-rbd": ceph_ctx.cinder_context()}},
        }

        template = env.get_template("backend.conf.j2")
        rendered = template.render(**test_context)

        assert "[ceph-rbd]" in rendered
        assert "volume_driver = cinder.volume.drivers.rbd.RBDDriver" in rendered
        assert "rbd_pool = cinder-volumes" in rendered
        # Sensitive key should not appear
        assert "rbd_key" not in rendered

    def test_multiple_backends_rendered_separately(self):
        """Test that multiple backends are rendered as separate config sections."""
        template_str = """[{{ cinder_name() }}]
{%- for key, value in cinder_ctx().items() %}
{{ key }} = {{ value }}
{%- endfor %}
"""
        env = jinja2.Environment(
            loader=jinja2.DictLoader({"backend.conf.j2": template_str})
        )
        env.globals.update(
            {
                "cinder_name": context.cinder_name,
                "cinder_ctx": context.cinder_ctx,
            }
        )

        # Create multiple backend contexts
        ceph_ctx = context.CephBackendContext(
            "ceph-rbd", {"volume_backend_name": "ceph-rbd"}
        )
        pure_ctx = context.PureBackendContext(
            "pure-fc", {"volume_backend_name": "pure-fc", "protocol": "fc"}
        )

        backends = {"ceph-rbd": ceph_ctx, "pure-fc": pure_ctx}
        cinder_backends = context.CinderBackendContexts(
            ["ceph-rbd", "pure-fc"], backends
        )

        # Render each backend separately (as the main code does)
        renderings = []
        for backend_name, backend_ctx in backends.items():
            test_context = {
                context.CINDER_CTX_KEY: backend_name,
                "cinder_backends": cinder_backends.context(),
            }
            template = env.get_template("backend.conf.j2")
            rendered = template.render(**test_context)
            renderings.append(rendered)

        # Check first backend (Ceph)
        assert "[ceph-rbd]" in renderings[0]
        assert "cinder.volume.drivers.rbd.RBDDriver" in renderings[0]

        # Check second backend (Pure)
        assert "[pure-fc]" in renderings[1]
        assert "cinder.volume.drivers.pure.PureFCDriver" in renderings[1]


class TestBackendConditionals:
    """Test conditional logic for backend templates."""

    def test_backend_variable_set_conditional(self):
        """Test backend_variable_set conditional function."""
        conditional = context.backend_variable_set(
            "test-backend", "san_ip", "san_login"
        )

        # Test with all variables set
        ctx_all_set = {
            "cinder_backends": {
                "contexts": {
                    "test-backend": {"san_ip": "10.0.0.1", "san_login": "admin"}
                }
            }
        }
        assert conditional(ctx_all_set) is True

        # Test with one variable missing
        ctx_one_missing = {
            "cinder_backends": {"contexts": {"test-backend": {"san_ip": "10.0.0.1"}}}
        }
        assert conditional(ctx_one_missing) is False

        # Test with backend missing
        ctx_backend_missing = {"cinder_backends": {"contexts": {}}}
        assert conditional(ctx_backend_missing) is False

    def test_backend_variable_set_with_empty_string(self):
        """Test that empty string is treated as False."""
        conditional = context.backend_variable_set("test-backend", "san_ip")

        ctx_empty = {"cinder_backends": {"contexts": {"test-backend": {"san_ip": ""}}}}
        assert conditional(ctx_empty) is False

    def test_backend_variable_set_with_multiple_variables(self):
        """Test conditional with multiple variables."""
        conditional = context.backend_variable_set(
            "test-backend", "var1", "var2", "var3"
        )

        ctx_all_present = {
            "cinder_backends": {
                "contexts": {"test-backend": {"var1": "a", "var2": "b", "var3": "c"}}
            }
        }
        assert conditional(ctx_all_present) is True

        ctx_one_false = {
            "cinder_backends": {
                "contexts": {"test-backend": {"var1": "a", "var2": False, "var3": "c"}}
            }
        }
        assert conditional(ctx_one_false) is False


class TestJinjaHelperFunctions:
    """Test Jinja2 helper functions for backend rendering."""

    def test_cinder_name_function(self):
        """Test cinder_name helper function."""
        mock_ctx = {context.CINDER_CTX_KEY: "my-backend"}

        # Mock the jinja2 context
        with patch("jinja2.runtime.Context", return_value=mock_ctx):
            result = context.cinder_name(mock_ctx)
            assert result == "my-backend"

    def test_cinder_name_raises_without_key(self):
        """Test cinder_name raises error when key is missing."""
        mock_ctx = {}

        with pytest.raises(error.CinderError, match="No backend name in context"):
            context.cinder_name(mock_ctx)

    def test_cinder_ctx_function(self):
        """Test cinder_ctx helper function."""
        mock_ctx = {
            context.CINDER_CTX_KEY: "my-backend",
            "cinder_backends": {
                "contexts": {"my-backend": {"volume_driver": "test.driver"}}
            },
        }

        result = context.cinder_ctx(mock_ctx)
        assert result == {"volume_driver": "test.driver"}

    def test_backend_ctx_function(self):
        """Test backend_ctx helper function."""
        mock_ctx = {
            context.BACKEND_CTX_KEY: {"san_ip": "10.0.0.1", "san_login": "admin"}
        }

        result = context.backend_ctx(mock_ctx)
        assert result == {"san_ip": "10.0.0.1", "san_login": "admin"}


class TestInfinidatBackendContext:
    """Test the InfinidatBackendContext class."""

    def test_infinidat_context_sets_volume_driver(self):
        """Test that context sets the correct Infinidat volume driver."""
        backend_config = {
            "volume_backend_name": "infinibox01",
            "san_ip": "10.0.0.100",
            "protocol": "iscsi",
        }
        ctx = context.InfinidatBackendContext("infinibox01", backend_config)
        result = ctx.context()
        assert ctx.supports_cluster is False
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.infinidat.InfiniboxVolumeDriver"
        )
        assert result["infinidat_storage_protocol"] == "iscsi"

    def test_infinidat_protocol_hidden_from_cinder_context(self):
        """Test that protocol is mapped to the upstream driver option."""
        backend_config = {
            "volume_backend_name": "infinibox01",
            "protocol": "fc",
            "san_ip": "10.0.0.100",
        }
        ctx = context.InfinidatBackendContext("infinibox01", backend_config)
        result = ctx.cinder_context()
        assert "protocol" not in result
        assert result["infinidat_storage_protocol"] == "fc"
        assert "volume_driver" in result
        assert "san_ip" in result

    def test_infinidat_template_rendering(self):
        """Test rendering Infinidat backend configuration template."""
        template_str = """[{{ cinder_name() }}]
{%- for key, value in cinder_ctx().items() %}
{{ key }} = {{ value }}
{%- endfor %}
"""
        env = jinja2.Environment(
            loader=jinja2.DictLoader({"backend.conf.j2": template_str})
        )
        env.globals.update(
            {
                "cinder_name": context.cinder_name,
                "cinder_ctx": context.cinder_ctx,
            }
        )

        infinidat_ctx = context.InfinidatBackendContext(
            "infinibox01",
            {
                "volume_backend_name": "infinibox01",
                "san_ip": "10.0.0.100",
                "san_login": "admin",
                "san_password": "secret",
                "infinidat_pool_name": "cinder-pool",
                "protocol": "iscsi",
                "infinidat_iscsi_netspaces": "default_iscsi_space",
            },
        )

        test_context = {
            context.CINDER_CTX_KEY: "infinibox01",
            "cinder_backends": {
                "contexts": {"infinibox01": infinidat_ctx.cinder_context()}
            },
        }

        template = env.get_template("backend.conf.j2")
        rendered = template.render(**test_context)

        assert "[infinibox01]" in rendered
        assert (
            "volume_driver = cinder.volume.drivers.infinidat.InfiniboxVolumeDriver"
            in rendered
        )
        assert "infinidat_storage_protocol = iscsi" in rendered
        assert "infinidat_pool_name = cinder-pool" in rendered
        assert "san_ip = 10.0.0.100" in rendered
        assert "infinidat_iscsi_netspaces = default_iscsi_space" in rendered
        # The raw Sunbeam protocol key should not be rendered.
        assert "\nprotocol =" not in rendered

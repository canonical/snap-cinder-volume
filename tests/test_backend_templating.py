# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend templating logic.

These tests verify that backend configurations are correctly templated
and rendered into Cinder configuration files.
"""

from unittest.mock import Mock, patch

import jinja2
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

    def test_base_backend_context_with_driver_ssl_cert(self):
        """Test context method with driver_ssl_cert adds path and verify."""
        backend_config = {
            "volume_backend_name": "test-backend",
            "driver_ssl_cert": "-----BEGIN CERTIFICATE-----\n...",
        }
        ctx = context.BaseBackendContext("test-backend", backend_config)
        result = ctx.context()

        assert "driver_ssl_cert_path" in result
        assert "test-backend.pem" in result["driver_ssl_cert_path"]
        assert result["driver_ssl_cert_verify"] is True

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

        assert len(templates) == 2
        assert templates[0].filename == "test-backend.conf"
        assert templates[0].template_name == "backend.conf.j2"
        assert templates[1].filename == "test-backend.pem"
        assert templates[1].template_name == "backend.pem.j2"

    def test_base_backend_pem_template_conditional(self):
        """Test that .pem template has conditional for driver_ssl_cert_path."""
        ctx = context.BaseBackendContext("test-backend", {})
        templates = ctx.template_files()
        pem_template = templates[1]

        assert len(pem_template.conditionals) > 0

        # Test conditional returns False when cert not present
        test_context = {"cinder_backends": {"contexts": {"test-backend": {}}}}
        assert not all(cond(test_context) for cond in pem_template.conditionals)

        # Test conditional returns True when cert is present
        test_context_with_cert = {
            "cinder_backends": {
                "contexts": {"test-backend": {"driver_ssl_cert_path": "/path/to/cert"}}
            }
        }
        assert all(cond(test_context_with_cert) for cond in pem_template.conditionals)

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

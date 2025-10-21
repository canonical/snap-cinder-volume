# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import Mock

from cinder_volume import context


class TestConfigContext:
    """Test the ConfigContext class."""

    def test_config_context_creation(self):
        """Test creating a ConfigContext instance."""
        config = {"key": "value", "number": 42}
        ctx = context.ConfigContext(namespace="test", config=config)
        assert ctx.namespace == "test"
        assert ctx.config == config

    def test_config_context_method(self):
        """Test the context method of ConfigContext."""
        config = {"key": "value", "number": 42}
        ctx = context.ConfigContext(namespace="test", config=config)
        result = ctx.context()
        assert result == config


class TestSnapPathContext:
    """Test the SnapPathContext class."""

    def test_snap_path_context_creation(self):
        """Test creating a SnapPathContext instance."""
        mock_snap = Mock()
        mock_snap.paths.__slots__ = ["common", "data"]
        mock_snap.paths.common = "/snap/common"
        mock_snap.paths.data = "/snap/data"

        ctx = context.SnapPathContext(snap=mock_snap)
        assert ctx.snap == mock_snap
        assert ctx.namespace == "snap_paths"

    def test_snap_path_context_method(self):
        """Test the context method of SnapPathContext."""
        mock_snap = Mock()
        mock_snap.paths.__slots__ = ["common", "data"]
        mock_snap.paths.common = "/snap/common"
        mock_snap.paths.data = "/snap/data"

        ctx = context.SnapPathContext(snap=mock_snap)
        result = ctx.context()
        expected = {"common": "/snap/common", "data": "/snap/data"}
        assert result == expected

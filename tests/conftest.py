# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_database_config():
    """Sample database configuration for testing."""
    from cinder_volume.configuration import DatabaseConfiguration

    return DatabaseConfiguration(url="sqlite:///test.db")


@pytest.fixture
def sample_rabbitmq_config():
    """Sample RabbitMQ configuration for testing."""
    from cinder_volume.configuration import RabbitMQConfiguration

    return RabbitMQConfiguration(url="amqp://localhost")


@pytest.fixture
def sample_cinder_config():
    """Sample Cinder configuration for testing."""
    from cinder_volume.configuration import CinderConfiguration

    return CinderConfiguration(
        project_id="test-project",
        user_id="test-user",
        image_volume_cache_enabled=True,
        image_volume_cache_max_size_gb=100,
        image_volume_cache_max_count=10,
    )

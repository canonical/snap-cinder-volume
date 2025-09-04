# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

import pytest

from cinder_volume import configuration


class TestToKebab:
    """Test the to_kebab function."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("camelCase", "camel-case"),
            ("PascalCase", "pascal-case"),
            ("snake_case", "snake-case"),
            ("kebab-case", "kebab-case"),
            ("simple", "simple"),
            ("", ""),
        ],
    )
    def test_to_kebab_conversion(self, input_str, expected):
        """Test that to_kebab converts strings correctly."""
        assert configuration.to_kebab(input_str) == expected


class TestParentConfig:
    """Test the ParentConfig base class."""

    def test_model_config(self):
        """Test that ParentConfig has the correct model configuration."""
        config = configuration.ParentConfig()
        assert hasattr(config, "model_config")


class TestDatabaseConfiguration:
    """Test the DatabaseConfiguration class."""

    def test_database_config_creation(self):
        """Test creating a DatabaseConfiguration instance."""
        config = configuration.DatabaseConfiguration(url="sqlite:///test.db")
        assert config.url == "sqlite:///test.db"

    def test_database_config_alias(self):
        """Test that DatabaseConfiguration uses kebab-case aliases."""
        config = configuration.DatabaseConfiguration(url="sqlite:///test.db")
        # Test serialization uses the field name as-is (url)
        data = config.model_dump(by_alias=True)
        assert "url" in data
        assert data["url"] == "sqlite:///test.db"


class TestRabbitMQConfiguration:
    """Test the RabbitMQConfiguration class."""

    def test_rabbitmq_config_creation(self):
        """Test creating a RabbitMQConfiguration instance."""
        config = configuration.RabbitMQConfiguration(url="amqp://localhost")
        assert config.url == "amqp://localhost"

    def test_rabbitmq_config_alias(self):
        """Test that RabbitMQConfiguration uses kebab-case aliases."""
        config = configuration.RabbitMQConfiguration(url="amqp://localhost")
        # Test serialization uses the field name as-is (url)
        data = config.model_dump(by_alias=True)
        assert "url" in data
        assert data["url"] == "amqp://localhost"


class TestCinderConfiguration:
    """Test the CinderConfiguration class."""

    def test_cinder_config_creation(self):
        """Test creating a CinderConfiguration instance."""
        config = configuration.CinderConfiguration(
            **{
                "project-id": "test-project",
                "user-id": "test-user",
                "image-volume-cache-enabled": True,
                "image-volume-cache-max-size-gb": 100,
                "image-volume-cache-max-count": 10,
            }
        )
        assert config.project_id == "test-project"
        assert config.user_id == "test-user"
        assert config.image_volume_cache_enabled is True
        assert config.image_volume_cache_max_size_gb == 100
        assert config.image_volume_cache_max_count == 10

    def test_cinder_config_alias(self):
        """Test that CinderConfiguration uses kebab-case aliases."""
        config = configuration.CinderConfiguration(
            **{
                "project-id": "test-project",
                "user-id": "test-user",
                "image-volume-cache-enabled": True,
                "image-volume-cache-max-size-gb": 100,
                "image-volume-cache-max-count": 10,
            }
        )
        assert config.project_id == "test-project"
        assert config.user_id == "test-user"

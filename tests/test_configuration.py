# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

import pydantic
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


class TestCAConfiguration:
    """Test the CAConfiguration class."""

    def test_ca_bundle_is_decoded(self):
        """Valid base64 should be decoded to PEM content."""
        config = configuration.CAConfiguration(bundle="VEVTVF9DQQ==")
        assert config.bundle == "TEST_CA"

    def test_ca_bundle_rejects_invalid_base64(self):
        """Invalid base64 input should fail validation."""
        with pytest.raises(pydantic.ValidationError):
            configuration.CAConfiguration(bundle="not-base64")


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
                "region-name": "RegionOne",
                "image-volume-cache-enabled": True,
                "image-volume-cache-max-size-gb": 100,
                "image-volume-cache-max-count": 10,
            }
        )
        assert config.project_id == "test-project"
        assert config.user_id == "test-user"
        assert config.region_name == "RegionOne"
        assert config.image_volume_cache_enabled is True
        assert config.image_volume_cache_max_size_gb == 100
        assert config.image_volume_cache_max_count == 10

    def test_cinder_config_alias(self):
        """Test that CinderConfiguration uses kebab-case aliases."""
        config = configuration.CinderConfiguration(
            **{
                "project-id": "test-project",
                "user-id": "test-user",
                "region-name": "RegionOne",
                "image-volume-cache-enabled": True,
                "image-volume-cache-max-size-gb": 100,
                "image-volume-cache-max-count": 10,
            }
        )
        assert config.project_id == "test-project"
        assert config.user_id == "test-user"
        assert config.region_name == "RegionOne"


class TestDellSCConfiguration:
    """Test the DellSCConfiguration class."""

    def test_dellsc_requires_dell_sc_ssn(self):
        """Test dell-sc-ssn is required for DellSC backends."""
        with pytest.raises(pydantic.ValidationError):
            configuration.DellSCConfiguration(
                **{
                    "volume-backend-name": "dellsc01",
                    "san-ip": "10.0.0.10",
                    "san-login": "admin",
                    "san-password": "secret",
                    "enable-unsupported-driver": True,
                }
            )

    def test_dellsc_enable_unsupported_driver_must_be_true(self):
        """Test enable-unsupported-driver cannot be set to false."""
        with pytest.raises(pydantic.ValidationError):
            configuration.DellSCConfiguration(
                **{
                    "volume-backend-name": "dellsc01",
                    "san-ip": "10.0.0.10",
                    "san-login": "admin",
                    "san-password": "secret",
                    "dell-sc-ssn": 64702,
                    "enable-unsupported-driver": False,
                }
            )

    def test_dellsc_accepts_valid_configuration(self):
        """Test valid DellSC backend configuration."""
        config = configuration.DellSCConfiguration(
            **{
                "volume-backend-name": "dellsc01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                "dell-sc-ssn": 64702,
                "protocol": "fc",
                "enable-unsupported-driver": True,
                "secondary-san-ip": "10.0.0.11",
                "secondary-san-login": "admin2",
                "secondary-san-password": "secret2",
            }
        )
        assert str(config.san_ip) == "10.0.0.10"
        assert config.dell_sc_ssn == 64702


class TestHpethreeparConfiguration:
    """Test the HpethreeparConfiguration class."""

    def test_hpe3par_accepts_valid_configuration(self):
        """Test valid HPE3Par backend configuration."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                "protocol": "fc",
                "hpe3par-api-url": "https://10.0.0.10/api/v1",
                "hpe3par-username": "edituser",
                "hpe3par-password": "editpwd",
            }
        )
        assert str(config.san_ip) == "10.0.0.10"
        assert config.hpe3par_api_url == "https://10.0.0.10/api/v1"
        assert config.hpe3par_username == "edituser"

    def test_hpe3par_requires_san_ip(self):
        """Test san-ip is required for HPE3Par backends."""
        with pytest.raises(pydantic.ValidationError):
            configuration.HpethreeparConfiguration(
                **{
                    "volume-backend-name": "hpe3par01",
                    "san-login": "admin",
                    "san-password": "secret",
                }
            )

    def test_hpe3par_requires_san_login(self):
        """Test san-login is required for HPE3Par backends."""
        with pytest.raises(pydantic.ValidationError):
            configuration.HpethreeparConfiguration(
                **{
                    "volume-backend-name": "hpe3par01",
                    "san-ip": "10.0.0.10",
                    "san-password": "secret",
                }
            )

    def test_hpe3par_requires_san_password(self):
        """Test san-password is required for HPE3Par backends."""
        with pytest.raises(pydantic.ValidationError):
            configuration.HpethreeparConfiguration(
                **{
                    "volume-backend-name": "hpe3par01",
                    "san-ip": "10.0.0.10",
                    "san-login": "admin",
                }
            )

    def test_hpe3par_requires_volume_backend_name(self):
        """Test volume-backend-name is required for HPE3Par backends."""
        with pytest.raises(pydantic.ValidationError):
            configuration.HpethreeparConfiguration(
                **{
                    "san-ip": "10.0.0.10",
                    "san-login": "admin",
                    "san-password": "secret",
                }
            )

    def test_hpe3par_rejects_invalid_san_ip(self):
        """Test that an invalid IP address is rejected."""
        with pytest.raises(pydantic.ValidationError):
            configuration.HpethreeparConfiguration(
                **{
                    "volume-backend-name": "hpe3par01",
                    "san-ip": "not-an-ip",
                    "san-login": "admin",
                    "san-password": "secret",
                }
            )

    def test_hpe3par_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        with pytest.raises(pydantic.ValidationError):
            configuration.HpethreeparConfiguration(
                **{
                    "volume-backend-name": "hpe3par01",
                    "san-ip": "10.0.0.10",
                    "san-login": "admin",
                    "san-password": "secret",
                    "protocol": "nvme",
                }
            )

    @pytest.mark.parametrize("protocol", ["fc", "iscsi"])
    def test_hpe3par_accepts_valid_protocols(self, protocol):
        """Test that fc and iscsi protocols are accepted."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                "protocol": protocol,
            }
        )
        assert config.protocol == protocol

    def test_hpe3par_protocol_defaults_to_fc(self):
        """Test that protocol defaults to fc when not specified."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
            }
        )
        assert config.protocol == "fc"

    @pytest.mark.parametrize(
        "kebab_key,snake_attr",
        [
            ("hpe3par-debug", "hpe3par_debug"),
            ("hpe3par-api-url", "hpe3par_api_url"),
            ("hpe3par-username", "hpe3par_username"),
            ("hpe3par-password", "hpe3par_password"),
            ("hpe3par-cpg", "hpe3par_cpg"),
            ("hpe3par-target-nsp", "hpe3par_target_nsp"),
            ("hpe3par-snapshot-retention", "hpe3par_snapshot_retention"),
            ("hpe3par-snapshot-expiration", "hpe3par_snapshot_expiration"),
            ("hpe3par-cpg-snap", "hpe3par_cpg_snap"),
            ("hpe3par-iscsi-ips", "hpe3par_iscsi_ips"),
            ("hpe3par-iscsi-chap-enabled", "hpe3par_iscsi_chap_enabled"),
            ("replication-device", "replication_device"),
        ],
    )
    def test_hpe3par_extra_field_validation_alias(self, kebab_key, snake_attr):
        """Test that extra fields in kebab-case are validated into snake_case."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                kebab_key: "test_value",
            }
        )
        assert getattr(config, snake_attr) == "test_value"

    @pytest.mark.parametrize(
        "kebab_key,snake_key",
        [
            ("hpe3par-debug", "hpe3par_debug"),
            ("hpe3par-api-url", "hpe3par_api_url"),
            ("hpe3par-username", "hpe3par_username"),
            ("hpe3par-password", "hpe3par_password"),
            ("hpe3par-cpg", "hpe3par_cpg"),
            ("hpe3par-target-nsp", "hpe3par_target_nsp"),
            ("replication-device", "replication_device"),
        ],
    )
    def test_hpe3par_extra_field_serialization_alias(self, kebab_key, snake_key):
        """Test that extra fields are serialized to snake_case with model_dump."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                kebab_key: "test_value",
            }
        )
        data = config.model_dump(by_alias=True)
        assert snake_key in data
        assert data[snake_key] == "test_value"

    def test_hpe3par_defined_fields_serialized_to_snake_case(self):
        """Test that defined fields are serialized to snake_case."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                "protocol": "iscsi",
            }
        )
        data = config.model_dump(by_alias=True)
        assert "san_ip" in data
        assert "san_login" in data
        assert "san_password" in data
        assert "protocol" in data
        assert "volume_backend_name" in data
        assert data["san_login"] == "admin"
        assert data["san_password"] == "secret"
        assert data["protocol"] == "iscsi"
        assert data["volume_backend_name"] == "hpe3par01"

    def test_hpe3par_full_config_serialization(self):
        """Test serialization of a full HPE3Par config with mixed fields."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                "protocol": "fc",
                "hpe3par-api-url": "https://10.0.0.10/api/v1",
                "hpe3par-username": "edituser",
                "hpe3par-password": "editpwd",
                "hpe3par-debug": "true",
                "hpe3par-cpg": "OpenStack",
            }
        )
        data = config.model_dump(by_alias=True)
        # Defined fields serialized to snake_case
        assert data["san_login"] == "admin"
        assert data["protocol"] == "fc"
        # Extra fields serialized to snake_case
        assert data["hpe3par_api_url"] == "https://10.0.0.10/api/v1"
        assert data["hpe3par_username"] == "edituser"
        assert data["hpe3par_password"] == "editpwd"
        assert data["hpe3par_debug"] == "true"
        assert data["hpe3par_cpg"] == "OpenStack"

    def test_hpe3par_multiple_extra_fields(self):
        """Test that multiple extra fields are all converted correctly."""
        config = configuration.HpethreeparConfiguration(
            **{
                "volume-backend-name": "hpe3par01",
                "san-ip": "10.0.0.10",
                "san-login": "admin",
                "san-password": "secret",
                "protocol": "iscsi",
                "hpe3par-debug": "true",
                "hpe3par-cpg": "OpenStack",
                "hpe3par-iscsi-ips": "10.0.0.11,10.0.0.12",
                "hpe3par-iscsi-chap-enabled": "true",
            }
        )
        assert config.hpe3par_debug == "true"
        assert config.hpe3par_cpg == "OpenStack"
        assert config.protocol == "iscsi"
        assert config.hpe3par_iscsi_ips == "10.0.0.11,10.0.0.12"
        assert config.hpe3par_iscsi_chap_enabled == "true"

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


class TestSolidfireConfiguration:
    """Test the SolidfireConfiguration class."""

    def test_solidfire_accepts_valid_configuration(self):
        """Test valid solidfire backend configuration."""
        config = configuration.SolidfireConfiguration(
            **{
                "volume-backend-name": "solidfire01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_solidfire_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "solidfire01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.SolidfireConfiguration(**kwargs)

    def test_solidfire_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "solidfire01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.SolidfireConfiguration(**kwargs)

    def test_solidfire_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "solidfire01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.SolidfireConfiguration(**kwargs)

    def test_solidfire_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "solidfire01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.SolidfireConfiguration(**kwargs)

    def test_solidfire_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "solidfire01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.SolidfireConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestDatacoreConfiguration:
    """Test the DatacoreConfiguration class."""

    def test_datacore_accepts_valid_configuration(self):
        """Test valid datacore backend configuration."""
        config = configuration.DatacoreConfiguration(
            **{"volume-backend-name": "datacore01"}
        )
        assert config.volume_backend_name == "datacore01"

    def test_datacore_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "datacore01"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.DatacoreConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestDateraConfiguration:
    """Test the DateraConfiguration class."""

    def test_datera_accepts_valid_configuration(self):
        """Test valid datera backend configuration."""
        config = configuration.DateraConfiguration(
            **{
                "volume-backend-name": "datera01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_datera_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "datera01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DateraConfiguration(**kwargs)

    def test_datera_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "datera01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DateraConfiguration(**kwargs)

    def test_datera_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "datera01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DateraConfiguration(**kwargs)

    def test_datera_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "datera01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.DateraConfiguration(**kwargs)

    def test_datera_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "datera01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.DateraConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestDellpowermaxConfiguration:
    """Test the DellpowermaxConfiguration class."""

    def test_dellpowermax_accepts_valid_configuration(self):
        """Test valid dellpowermax backend configuration."""
        config = configuration.DellpowermaxConfiguration(
            **{
                "volume-backend-name": "dellpowermax01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "protocol": "fc",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_dellpowermax_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "dellpowermax01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DellpowermaxConfiguration(**kwargs)

    def test_dellpowermax_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "dellpowermax01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DellpowermaxConfiguration(**kwargs)

    def test_dellpowermax_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "dellpowermax01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DellpowermaxConfiguration(**kwargs)

    def test_dellpowermax_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "dellpowermax01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.DellpowermaxConfiguration(**kwargs)

    def test_dellpowermax_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "dellpowermax01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.DellpowermaxConfiguration(**kwargs)

    def test_dellpowermax_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "dellpowermax01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.DellpowermaxConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestDellpowervaultConfiguration:
    """Test the DellpowervaultConfiguration class."""

    def test_dellpowervault_accepts_valid_configuration(self):
        """Test valid dellpowervault backend configuration."""
        config = configuration.DellpowervaultConfiguration(
            **{"volume-backend-name": "dellpowervault01", "protocol": "fc"}
        )
        assert config.volume_backend_name == "dellpowervault01"

    def test_dellpowervault_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {"volume-backend-name": "dellpowervault01", "protocol": "fc"}
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.DellpowervaultConfiguration(**kwargs)

    def test_dellpowervault_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "dellpowervault01", "protocol": "fc"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.DellpowervaultConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestDellxtremioConfiguration:
    """Test the DellxtremioConfiguration class."""

    def test_dellxtremio_accepts_valid_configuration(self):
        """Test valid dellxtremio backend configuration."""
        config = configuration.DellxtremioConfiguration(
            **{
                "volume-backend-name": "dellxtremio01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "protocol": "iscsi",
                "enable-unsupported-driver": True,
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_dellxtremio_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "dellxtremio01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DellxtremioConfiguration(**kwargs)

    def test_dellxtremio_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "dellxtremio01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DellxtremioConfiguration(**kwargs)

    def test_dellxtremio_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "dellxtremio01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.DellxtremioConfiguration(**kwargs)

    def test_dellxtremio_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "dellxtremio01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
            "enable-unsupported-driver": True,
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.DellxtremioConfiguration(**kwargs)

    def test_dellxtremio_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "dellxtremio01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
            "enable-unsupported-driver": True,
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.DellxtremioConfiguration(**kwargs)

    def test_dellxtremio_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "dellxtremio01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
            "enable-unsupported-driver": True,
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.DellxtremioConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestFujitsueternusdxConfiguration:
    """Test the FujitsueternusdxConfiguration class."""

    def test_fujitsueternusdx_accepts_valid_configuration(self):
        """Test valid fujitsueternusdx backend configuration."""
        config = configuration.FujitsueternusdxConfiguration(
            **{
                "volume-backend-name": "fujitsueternusdx01",
                "fujitsu-passwordless": "secret",
                "protocol": "fc",
            }
        )
        assert config.volume_backend_name == "fujitsueternusdx01"

    def test_fujitsueternusdx_requires_fujitsu_passwordless(self):
        """Test fujitsu-passwordless is required."""
        kwargs = {
            "volume-backend-name": "fujitsueternusdx01",
            "fujitsu-passwordless": "secret",
            "protocol": "fc",
        }
        del kwargs["fujitsu-passwordless"]
        with pytest.raises(pydantic.ValidationError):
            configuration.FujitsueternusdxConfiguration(**kwargs)

    def test_fujitsueternusdx_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "fujitsueternusdx01",
            "fujitsu-passwordless": "secret",
            "protocol": "fc",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.FujitsueternusdxConfiguration(**kwargs)

    def test_fujitsueternusdx_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "fujitsueternusdx01",
            "fujitsu-passwordless": "secret",
            "protocol": "fc",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.FujitsueternusdxConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestHpexpConfiguration:
    """Test the HpexpConfiguration class."""

    def test_hpexp_accepts_valid_configuration(self):
        """Test valid hpexp backend configuration."""
        config = configuration.HpexpConfiguration(
            **{"volume-backend-name": "hpexp01", "protocol": "fc"}
        )
        assert config.volume_backend_name == "hpexp01"

    def test_hpexp_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {"volume-backend-name": "hpexp01", "protocol": "fc"}
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.HpexpConfiguration(**kwargs)

    def test_hpexp_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "hpexp01", "protocol": "fc"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.HpexpConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestIbmflashsystemcommonConfiguration:
    """Test the IbmflashsystemcommonConfiguration class."""

    def test_ibmflashsystemcommon_accepts_valid_configuration(self):
        """Test valid ibmflashsystemcommon backend configuration."""
        config = configuration.IbmflashsystemcommonConfiguration(
            **{
                "volume-backend-name": "ibmflashsystemcommon01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "enable-unsupported-driver": True,
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_ibmflashsystemcommon_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "ibmflashsystemcommon01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmflashsystemcommonConfiguration(**kwargs)

    def test_ibmflashsystemcommon_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "ibmflashsystemcommon01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmflashsystemcommonConfiguration(**kwargs)

    def test_ibmflashsystemcommon_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "ibmflashsystemcommon01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmflashsystemcommonConfiguration(**kwargs)

    def test_ibmflashsystemcommon_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "ibmflashsystemcommon01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmflashsystemcommonConfiguration(**kwargs)

    def test_ibmflashsystemcommon_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "ibmflashsystemcommon01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.IbmflashsystemcommonConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestIbmflashsystemiscsiConfiguration:
    """Test the IbmflashsystemiscsiConfiguration class."""

    def test_ibmflashsystemiscsi_accepts_valid_configuration(self):
        """Test valid ibmflashsystemiscsi backend configuration."""
        config = configuration.IbmflashsystemiscsiConfiguration(
            **{"volume-backend-name": "ibmflashsystemiscsi01"}
        )
        assert config.volume_backend_name == "ibmflashsystemiscsi01"

    def test_ibmflashsystemiscsi_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "ibmflashsystemiscsi01"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.IbmflashsystemiscsiConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestIbmgpfsConfiguration:
    """Test the IbmgpfsConfiguration class."""

    def test_ibmgpfs_accepts_valid_configuration(self):
        """Test valid ibmgpfs backend configuration."""
        config = configuration.IbmgpfsConfiguration(
            **{
                "volume-backend-name": "ibmgpfs01",
                "gpfs-user-password": "secret",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_ibmgpfs_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "ibmgpfs01",
            "gpfs-user-password": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmgpfsConfiguration(**kwargs)

    def test_ibmgpfs_requires_gpfs_user_password(self):
        """Test gpfs-user-password is required."""
        kwargs = {
            "volume-backend-name": "ibmgpfs01",
            "gpfs-user-password": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["gpfs-user-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmgpfsConfiguration(**kwargs)

    def test_ibmgpfs_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "ibmgpfs01",
            "gpfs-user-password": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmgpfsConfiguration(**kwargs)

    def test_ibmgpfs_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "ibmgpfs01",
            "gpfs-user-password": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmgpfsConfiguration(**kwargs)

    def test_ibmgpfs_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "ibmgpfs01",
            "gpfs-user-password": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmgpfsConfiguration(**kwargs)

    def test_ibmgpfs_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "ibmgpfs01",
            "gpfs-user-password": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.IbmgpfsConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestIbmibmstorageConfiguration:
    """Test the IbmibmstorageConfiguration class."""

    def test_ibmibmstorage_accepts_valid_configuration(self):
        """Test valid ibmibmstorage backend configuration."""
        config = configuration.IbmibmstorageConfiguration(
            **{
                "volume-backend-name": "ibmibmstorage01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_ibmibmstorage_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "ibmibmstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmibmstorageConfiguration(**kwargs)

    def test_ibmibmstorage_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "ibmibmstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmibmstorageConfiguration(**kwargs)

    def test_ibmibmstorage_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "ibmibmstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmibmstorageConfiguration(**kwargs)

    def test_ibmibmstorage_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "ibmibmstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmibmstorageConfiguration(**kwargs)

    def test_ibmibmstorage_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "ibmibmstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.IbmibmstorageConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestIbmstorwizesvcConfiguration:
    """Test the IbmstorwizesvcConfiguration class."""

    def test_ibmstorwizesvc_accepts_valid_configuration(self):
        """Test valid ibmstorwizesvc backend configuration."""
        config = configuration.IbmstorwizesvcConfiguration(
            **{
                "volume-backend-name": "ibmstorwizesvc01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "protocol": "fc",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_ibmstorwizesvc_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "ibmstorwizesvc01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmstorwizesvcConfiguration(**kwargs)

    def test_ibmstorwizesvc_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "ibmstorwizesvc01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmstorwizesvcConfiguration(**kwargs)

    def test_ibmstorwizesvc_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "ibmstorwizesvc01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmstorwizesvcConfiguration(**kwargs)

    def test_ibmstorwizesvc_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "ibmstorwizesvc01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmstorwizesvcConfiguration(**kwargs)

    def test_ibmstorwizesvc_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "ibmstorwizesvc01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.IbmstorwizesvcConfiguration(**kwargs)

    def test_ibmstorwizesvc_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "ibmstorwizesvc01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.IbmstorwizesvcConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestInfinidatConfiguration:
    """Test the InfinidatConfiguration class."""

    def test_infinidat_accepts_valid_configuration(self):
        """Test valid Infinidat backend configuration."""
        config = configuration.InfinidatConfiguration(
            **{
                "volume-backend-name": "infinibox01",
                "san-ip": "10.0.0.100",
                "san-login": "admin",
                "san-password": "secret",
                "infinidat-pool-name": "cinder-pool",
                "protocol": "iscsi",
                "infinidat-iscsi-netspaces": "default_iscsi_space",
                "use-chap-auth": True,
            }
        )
        assert str(config.san_ip) == "10.0.0.100"
        assert config.san_login == "admin"
        assert config.infinidat_pool_name == "cinder-pool"
        assert config.protocol == "iscsi"
        assert config.infinidat_iscsi_netspaces == "default_iscsi_space"
        assert config.use_chap_auth is True

    def test_infinidat_requires_mandatory_fields(self):
        """Test required fields are validated for Infinidat backends."""
        with pytest.raises(pydantic.ValidationError):
            configuration.InfinidatConfiguration(
                **{
                    "volume-backend-name": "infinibox01",
                    "san-login": "admin",
                    "infinidat-pool-name": "cinder-pool",
                }
            )

    def test_infinidat_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        with pytest.raises(pydantic.ValidationError):
            configuration.InfinidatConfiguration(
                **{
                    "volume-backend-name": "infinibox01",
                    "san-ip": "10.0.0.100",
                    "san-login": "admin",
                    "san-password": "secret",
                    "infinidat-pool-name": "cinder-pool",
                    "protocol": "nvme",
                }
            )

    def test_infinidat_accepts_fc_protocol_without_iscsi_netspaces(self):
        """Test that fc protocol does not require iSCSI netspaces."""
        config = configuration.InfinidatConfiguration(
            **{
                "volume-backend-name": "infinibox01",
                "san-ip": "10.0.0.100",
                "san-login": "admin",
                "san-password": "secret",
                "infinidat-pool-name": "cinder-pool",
                "protocol": "fc",
            }
        )
        assert config.protocol == "fc"

    def test_infinidat_iscsi_requires_netspaces(self):
        """Test that iscsi protocol requires infinidat-iscsi-netspaces."""
        with pytest.raises(pydantic.ValidationError, match="infinidat_iscsi_netspaces"):
            configuration.InfinidatConfiguration(
                **{
                    "volume-backend-name": "infinibox01",
                    "san-ip": "10.0.0.100",
                    "san-login": "admin",
                    "san-password": "secret",
                    "infinidat-pool-name": "cinder-pool",
                    "protocol": "iscsi",
                }
            )

    def test_infinidat_serializes_defined_fields(self):
        """Test serialization of defined Infinidat fields."""
        config = configuration.InfinidatConfiguration(
            **{
                "volume-backend-name": "infinibox01",
                "san-ip": "10.0.0.100",
                "san-login": "admin",
                "san-password": "secret",
                "infinidat-pool-name": "cinder-pool",
                "protocol": "iscsi",
                "infinidat-iscsi-netspaces": "default_iscsi_space",
                "use-chap-auth": True,
                "chap-username": "chapuser",
                "chap-password": "chappass",
                "infinidat-use-compression": True,
            }
        )
        data = config.model_dump(by_alias=True)
        assert data["volume_backend_name"] == "infinibox01"
        assert str(data["san_ip"]) == "10.0.0.100"
        assert data["infinidat_iscsi_netspaces"] == "default_iscsi_space"
        assert data["use_chap_auth"] is True
        assert data["chap_username"] == "chapuser"
        assert data["chap_password"] == "chappass"
        assert data["infinidat_use_compression"] is True


class TestInspuras13000Configuration:
    """Test the Inspuras13000Configuration class."""

    def test_inspuras13000_accepts_valid_configuration(self):
        """Test valid inspuras13000 backend configuration."""
        config = configuration.Inspuras13000Configuration(
            **{
                "volume-backend-name": "inspuras1300001",
                "as-13000-token-available-time": "secret",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_inspuras13000_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "inspuras1300001",
            "as-13000-token-available-time": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Inspuras13000Configuration(**kwargs)

    def test_inspuras13000_requires_as13000_token_available_time(self):
        """Test as13000-token-available-time is required."""
        kwargs = {
            "volume-backend-name": "inspuras1300001",
            "as-13000-token-available-time": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["as-13000-token-available-time"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Inspuras13000Configuration(**kwargs)

    def test_inspuras13000_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "inspuras1300001",
            "as-13000-token-available-time": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Inspuras13000Configuration(**kwargs)

    def test_inspuras13000_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "inspuras1300001",
            "as-13000-token-available-time": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Inspuras13000Configuration(**kwargs)

    def test_inspuras13000_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "inspuras1300001",
            "as-13000-token-available-time": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.Inspuras13000Configuration(**kwargs)

    def test_inspuras13000_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "inspuras1300001",
            "as-13000-token-available-time": "secret",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.Inspuras13000Configuration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestInspurinstorageConfiguration:
    """Test the InspurinstorageConfiguration class."""

    def test_inspurinstorage_accepts_valid_configuration(self):
        """Test valid inspurinstorage backend configuration."""
        config = configuration.InspurinstorageConfiguration(
            **{
                "volume-backend-name": "inspurinstorage01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "protocol": "fc",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_inspurinstorage_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "inspurinstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.InspurinstorageConfiguration(**kwargs)

    def test_inspurinstorage_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "inspurinstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.InspurinstorageConfiguration(**kwargs)

    def test_inspurinstorage_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "inspurinstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.InspurinstorageConfiguration(**kwargs)

    def test_inspurinstorage_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "inspurinstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.InspurinstorageConfiguration(**kwargs)

    def test_inspurinstorage_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "inspurinstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.InspurinstorageConfiguration(**kwargs)

    def test_inspurinstorage_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "inspurinstorage01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.InspurinstorageConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestKaminarioConfiguration:
    """Test the KaminarioConfiguration class."""

    def test_kaminario_accepts_valid_configuration(self):
        """Test valid kaminario backend configuration."""
        config = configuration.KaminarioConfiguration(
            **{"volume-backend-name": "kaminario01"}
        )
        assert config.volume_backend_name == "kaminario01"

    def test_kaminario_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "kaminario01"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.KaminarioConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestLinstorConfiguration:
    """Test the LinstorConfiguration class."""

    def test_linstor_accepts_valid_configuration(self):
        """Test valid linstor backend configuration."""
        config = configuration.LinstorConfiguration(
            **{"volume-backend-name": "linstor01"}
        )
        assert config.volume_backend_name == "linstor01"

    def test_linstor_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "linstor01"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.LinstorConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestMacrosanConfiguration:
    """Test the MacrosanConfiguration class."""

    def test_macrosan_accepts_valid_configuration(self):
        """Test valid macrosan backend configuration."""
        config = configuration.MacrosanConfiguration(
            **{
                "volume-backend-name": "macrosan01",
                "macrosan-sdas-password": "secret",
                "macrosan-replication-password": "secret",
                "protocol": "iscsi",
            }
        )
        assert config.volume_backend_name == "macrosan01"

    def test_macrosan_requires_macrosan_sdas_password(self):
        """Test macrosan-sdas-password is required."""
        kwargs = {
            "volume-backend-name": "macrosan01",
            "macrosan-sdas-password": "secret",
            "macrosan-replication-password": "secret",
            "protocol": "iscsi",
        }
        del kwargs["macrosan-sdas-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.MacrosanConfiguration(**kwargs)

    def test_macrosan_requires_macrosan_replication_password(self):
        """Test macrosan-replication-password is required."""
        kwargs = {
            "volume-backend-name": "macrosan01",
            "macrosan-sdas-password": "secret",
            "macrosan-replication-password": "secret",
            "protocol": "iscsi",
        }
        del kwargs["macrosan-replication-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.MacrosanConfiguration(**kwargs)

    def test_macrosan_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "macrosan01",
            "macrosan-sdas-password": "secret",
            "macrosan-replication-password": "secret",
            "protocol": "iscsi",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.MacrosanConfiguration(**kwargs)

    def test_macrosan_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "macrosan01",
            "macrosan-sdas-password": "secret",
            "macrosan-replication-password": "secret",
            "protocol": "iscsi",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.MacrosanConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestNecvConfiguration:
    """Test the NecvConfiguration class."""

    def test_necv_accepts_valid_configuration(self):
        """Test valid necv backend configuration."""
        config = configuration.NecvConfiguration(
            **{"volume-backend-name": "necv01", "protocol": "fc"}
        )
        assert config.volume_backend_name == "necv01"

    def test_necv_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {"volume-backend-name": "necv01", "protocol": "fc"}
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.NecvConfiguration(**kwargs)

    def test_necv_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "necv01", "protocol": "fc"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.NecvConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestNetappConfiguration:
    """Test the NetappConfiguration class."""

    def test_netapp_accepts_valid_configuration(self):
        """Test valid netapp backend configuration."""
        config = configuration.NetappConfiguration(
            **{
                "volume-backend-name": "netapp01",
                "netapp-ca-certificate-file": "secret",
                "protocol": "iscsi",
            }
        )
        assert config.volume_backend_name == "netapp01"

    def test_netapp_requires_netapp_ca_certificate_file(self):
        """Test netapp-ca-certificate-file is required."""
        kwargs = {
            "volume-backend-name": "netapp01",
            "netapp-ca-certificate-file": "secret",
            "protocol": "iscsi",
        }
        del kwargs["netapp-ca-certificate-file"]
        with pytest.raises(pydantic.ValidationError):
            configuration.NetappConfiguration(**kwargs)

    def test_netapp_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "netapp01",
            "netapp-ca-certificate-file": "secret",
            "protocol": "iscsi",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.NetappConfiguration(**kwargs)

    def test_netapp_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "netapp01",
            "netapp-ca-certificate-file": "secret",
            "protocol": "iscsi",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.NetappConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestNexentaConfiguration:
    """Test the NexentaConfiguration class."""

    def test_nexenta_accepts_valid_configuration(self):
        """Test valid nexenta backend configuration."""
        config = configuration.NexentaConfiguration(
            **{"volume-backend-name": "nexenta01", "nexenta-rest-password": "secret"}
        )
        assert config.volume_backend_name == "nexenta01"

    def test_nexenta_requires_nexenta_rest_password(self):
        """Test nexenta-rest-password is required."""
        kwargs = {"volume-backend-name": "nexenta01", "nexenta-rest-password": "secret"}
        del kwargs["nexenta-rest-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.NexentaConfiguration(**kwargs)

    def test_nexenta_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "nexenta01", "nexenta-rest-password": "secret"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.NexentaConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestNimbleConfiguration:
    """Test the NimbleConfiguration class."""

    def test_nimble_accepts_valid_configuration(self):
        """Test valid nimble backend configuration."""
        config = configuration.NimbleConfiguration(
            **{
                "volume-backend-name": "nimble01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "protocol": "iscsi",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_nimble_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "nimble01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.NimbleConfiguration(**kwargs)

    def test_nimble_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "nimble01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.NimbleConfiguration(**kwargs)

    def test_nimble_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "nimble01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.NimbleConfiguration(**kwargs)

    def test_nimble_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "nimble01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.NimbleConfiguration(**kwargs)

    def test_nimble_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "nimble01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.NimbleConfiguration(**kwargs)

    def test_nimble_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "nimble01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "iscsi",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.NimbleConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestOpeneConfiguration:
    """Test the OpeneConfiguration class."""

    def test_opene_accepts_valid_configuration(self):
        """Test valid opene backend configuration."""
        config = configuration.OpeneConfiguration(
            **{"volume-backend-name": "opene01", "chap-password-len": 12}
        )
        assert config.volume_backend_name == "opene01"

    def test_opene_requires_chap_password_len(self):
        """Test chap-password-len is required."""
        kwargs = {"volume-backend-name": "opene01", "chap-password-len": 12}
        del kwargs["chap-password-len"]
        with pytest.raises(pydantic.ValidationError):
            configuration.OpeneConfiguration(**kwargs)

    def test_opene_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "opene01", "chap-password-len": 12}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.OpeneConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestProphetstorConfiguration:
    """Test the ProphetstorConfiguration class."""

    def test_prophetstor_accepts_valid_configuration(self):
        """Test valid prophetstor backend configuration."""
        config = configuration.ProphetstorConfiguration(
            **{
                "volume-backend-name": "prophetstor01",
                "protocol": "fc",
                "enable-unsupported-driver": True,
            }
        )
        assert config.volume_backend_name == "prophetstor01"

    def test_prophetstor_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "prophetstor01",
            "protocol": "fc",
            "enable-unsupported-driver": True,
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.ProphetstorConfiguration(**kwargs)

    def test_prophetstor_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "prophetstor01",
            "protocol": "fc",
            "enable-unsupported-driver": True,
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.ProphetstorConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestQnapConfiguration:
    """Test the QnapConfiguration class."""

    def test_qnap_accepts_valid_configuration(self):
        """Test valid qnap backend configuration."""
        config = configuration.QnapConfiguration(
            **{
                "volume-backend-name": "qnap01",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "enable-unsupported-driver": True,
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_qnap_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "qnap01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.QnapConfiguration(**kwargs)

    def test_qnap_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "qnap01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.QnapConfiguration(**kwargs)

    def test_qnap_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "qnap01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.QnapConfiguration(**kwargs)

    def test_qnap_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "qnap01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.QnapConfiguration(**kwargs)

    def test_qnap_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "qnap01",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "enable-unsupported-driver": True,
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.QnapConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestSandstoneConfiguration:
    """Test the SandstoneConfiguration class."""

    def test_sandstone_accepts_valid_configuration(self):
        """Test valid sandstone backend configuration."""
        config = configuration.SandstoneConfiguration(
            **{"volume-backend-name": "sandstone01"}
        )
        assert config.volume_backend_name == "sandstone01"

    def test_sandstone_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "sandstone01"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.SandstoneConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestStxConfiguration:
    """Test the StxConfiguration class."""

    def test_stx_accepts_valid_configuration(self):
        """Test valid stx backend configuration."""
        config = configuration.StxConfiguration(**{"volume-backend-name": "stx01"})
        assert config.volume_backend_name == "stx01"

    def test_stx_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "stx01"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.StxConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestSynologyConfiguration:
    """Test the SynologyConfiguration class."""

    def test_synology_accepts_valid_configuration(self):
        """Test valid synology backend configuration."""
        config = configuration.SynologyConfiguration(
            **{
                "volume-backend-name": "synology01",
                "synology-password": "secret",
                "synology-one-time-pass": "secret",
            }
        )
        assert config.volume_backend_name == "synology01"

    def test_synology_requires_synology_password(self):
        """Test synology-password is required."""
        kwargs = {
            "volume-backend-name": "synology01",
            "synology-password": "secret",
            "synology-one-time-pass": "secret",
        }
        del kwargs["synology-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.SynologyConfiguration(**kwargs)

    def test_synology_requires_synology_one_time_pass(self):
        """Test synology-one-time-pass is required."""
        kwargs = {
            "volume-backend-name": "synology01",
            "synology-password": "secret",
            "synology-one-time-pass": "secret",
        }
        del kwargs["synology-one-time-pass"]
        with pytest.raises(pydantic.ValidationError):
            configuration.SynologyConfiguration(**kwargs)

    def test_synology_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "synology01",
            "synology-password": "secret",
            "synology-one-time-pass": "secret",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.SynologyConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestToyouacs5000Configuration:
    """Test the Toyouacs5000Configuration class."""

    def test_toyouacs5000_accepts_valid_configuration(self):
        """Test valid toyouacs5000 backend configuration."""
        config = configuration.Toyouacs5000Configuration(
            **{
                "volume-backend-name": "toyouacs500001",
                "san-ip": "10.0.0.1",
                "san-login": "secret",
                "san-password": "secret",
                "protocol": "fc",
            }
        )
        assert str(config.san_ip) == "10.0.0.1"

    def test_toyouacs5000_requires_san_ip(self):
        """Test san-ip is required."""
        kwargs = {
            "volume-backend-name": "toyouacs500001",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-ip"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Toyouacs5000Configuration(**kwargs)

    def test_toyouacs5000_requires_san_login(self):
        """Test san-login is required."""
        kwargs = {
            "volume-backend-name": "toyouacs500001",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-login"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Toyouacs5000Configuration(**kwargs)

    def test_toyouacs5000_requires_san_password(self):
        """Test san-password is required."""
        kwargs = {
            "volume-backend-name": "toyouacs500001",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        del kwargs["san-password"]
        with pytest.raises(pydantic.ValidationError):
            configuration.Toyouacs5000Configuration(**kwargs)

    def test_toyouacs5000_rejects_invalid_san_ip(self):
        """Test that an invalid IP is rejected for san-ip."""
        kwargs = {
            "volume-backend-name": "toyouacs500001",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["san-ip"] = "not-an-ip"
        with pytest.raises(pydantic.ValidationError):
            configuration.Toyouacs5000Configuration(**kwargs)

    def test_toyouacs5000_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {
            "volume-backend-name": "toyouacs500001",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.Toyouacs5000Configuration(**kwargs)

    def test_toyouacs5000_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "toyouacs500001",
            "san-ip": "10.0.0.1",
            "san-login": "secret",
            "san-password": "secret",
            "protocol": "fc",
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.Toyouacs5000Configuration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestVeritasaccessConfiguration:
    """Test the VeritasaccessConfiguration class."""

    def test_veritasaccess_accepts_valid_configuration(self):
        """Test valid veritasaccess backend configuration."""
        config = configuration.VeritasaccessConfiguration(
            **{
                "volume-backend-name": "veritasaccess01",
                "enable-unsupported-driver": True,
            }
        )
        assert config.volume_backend_name == "veritasaccess01"

    def test_veritasaccess_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {
            "volume-backend-name": "veritasaccess01",
            "enable-unsupported-driver": True,
        }
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.VeritasaccessConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestYadroConfiguration:
    """Test the YadroConfiguration class."""

    def test_yadro_accepts_valid_configuration(self):
        """Test valid yadro backend configuration."""
        config = configuration.YadroConfiguration(
            **{"volume-backend-name": "yadro01", "protocol": "fc"}
        )
        assert config.volume_backend_name == "yadro01"

    def test_yadro_rejects_invalid_protocol(self):
        """Test that an invalid protocol value is rejected."""
        kwargs = {"volume-backend-name": "yadro01", "protocol": "fc"}
        kwargs["protocol"] = "invalid"
        with pytest.raises(pydantic.ValidationError):
            configuration.YadroConfiguration(**kwargs)

    def test_yadro_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "yadro01", "protocol": "fc"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.YadroConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"


class TestZadaraConfiguration:
    """Test the ZadaraConfiguration class."""

    def test_zadara_accepts_valid_configuration(self):
        """Test valid zadara backend configuration."""
        config = configuration.ZadaraConfiguration(
            **{"volume-backend-name": "zadara01", "zadara-access-key": "secret"}
        )
        assert config.volume_backend_name == "zadara01"

    def test_zadara_requires_zadara_access_key(self):
        """Test zadara-access-key is required."""
        kwargs = {"volume-backend-name": "zadara01", "zadara-access-key": "secret"}
        del kwargs["zadara-access-key"]
        with pytest.raises(pydantic.ValidationError):
            configuration.ZadaraConfiguration(**kwargs)

    def test_zadara_allows_extra_fields(self):
        """Test that extra driver-specific fields are accepted."""
        kwargs = {"volume-backend-name": "zadara01", "zadara-access-key": "secret"}
        kwargs["some-vendor-specific-opt"] = "value"
        config = configuration.ZadaraConfiguration(**kwargs)
        assert config.some_vendor_specific_opt == "value"

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


class TestCABundleSet:
    """Test the CA bundle conditional helper."""

    def test_ca_bundle_set_true(self):
        """Helper should be true when the bundle is present."""
        assert context.ca_bundle_set({"ca": {"bundle": "TEST_CA"}}) is True

    def test_ca_bundle_set_false(self):
        """Helper should be false when the bundle is absent."""
        assert context.ca_bundle_set({"ca": {"bundle": None}}) is False
        assert context.ca_bundle_set({}) is False


class TestSolidfireBackendContext:
    """Test the SolidfireBackendContext class."""

    def test_solidfire_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.SolidfireBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is True

    def test_solidfire_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.SolidfireBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"] == "cinder.volume.drivers.solidfire.SolidFireDriver"
        )


class TestDatacoreBackendContext:
    """Test the DatacoreBackendContext class."""

    def test_datacore_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.DatacoreBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_datacore_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.DatacoreBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.datacore.fc.FibreChannelVolumeDriver"
        )


class TestDateraBackendContext:
    """Test the DateraBackendContext class."""

    def test_datera_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.DateraBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_datera_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.DateraBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.datera.datera_iscsi.DateraDriver"
        )


class TestDellpowermaxBackendContext:
    """Test the DellpowermaxBackendContext class."""

    def test_dellpowermax_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.DellpowermaxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is True

    def test_dellpowermax_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.DellpowermaxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.dell_emc.powermax.fc.PowerMaxFCDriver"
        )

    def test_dellpowermax_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.DellpowermaxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.dell_emc.powermax.iscsi.PowerMaxISCSIDriver"
        )

    def test_dellpowermax_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.DellpowermaxBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestDellpowervaultBackendContext:
    """Test the DellpowervaultBackendContext class."""

    def test_dellpowervault_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.DellpowervaultBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_dellpowervault_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.DellpowervaultBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.dell_emc.powervault.fc.PVMEFCDriver"
        )

    def test_dellpowervault_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.DellpowervaultBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.dell_emc.powervault.iscsi.PVMEISCSIDriver"
        )

    def test_dellpowervault_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.DellpowervaultBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestDellxtremioBackendContext:
    """Test the DellxtremioBackendContext class."""

    def test_dellxtremio_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.DellxtremioBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_dellxtremio_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.DellxtremioBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.dell_emc.xtremio.XtremIOISCSIDriver"
        )

    def test_dellxtremio_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.DellxtremioBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.dell_emc.xtremio.XtremIOFCDriver"
        )

    def test_dellxtremio_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.DellxtremioBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestFujitsueternusdxBackendContext:
    """Test the FujitsueternusdxBackendContext class."""

    def test_fujitsueternusdx_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.FujitsueternusdxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_fujitsueternusdx_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.FujitsueternusdxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.fujitsu.eternus_dx.eternus_dx_fc.FJDXFCDriver"
        )

    def test_fujitsueternusdx_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.FujitsueternusdxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.fujitsu.eternus_dx.eternus_dx_iscsi.FJDXISCSIDriver"
        )

    def test_fujitsueternusdx_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.FujitsueternusdxBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestHpexpBackendContext:
    """Test the HpexpBackendContext class."""

    def test_hpexp_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.HpexpBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_hpexp_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.HpexpBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.hpe.xp.hpe_xp_fc.HPEXPFCDriver"
        )

    def test_hpexp_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.HpexpBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.hpe.xp.hpe_xp_iscsi.HPEXPISCSIDriver"
        )

    def test_hpexp_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.HpexpBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestIbmflashsystemcommonBackendContext:
    """Test the IbmflashsystemcommonBackendContext class."""

    def test_ibmflashsystemcommon_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.IbmflashsystemcommonBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_ibmflashsystemcommon_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.IbmflashsystemcommonBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.ibm.flashsystem_common.FlashSystemDriver"
        )


class TestIbmflashsystemiscsiBackendContext:
    """Test the IbmflashsystemiscsiBackendContext class."""

    def test_ibmflashsystemiscsi_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.IbmflashsystemiscsiBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_ibmflashsystemiscsi_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.IbmflashsystemiscsiBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.ibm.flashsystem_iscsi.FlashSystemISCSIDriver"
        )


class TestIbmgpfsBackendContext:
    """Test the IbmgpfsBackendContext class."""

    def test_ibmgpfs_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.IbmgpfsBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_ibmgpfs_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.IbmgpfsBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == "cinder.volume.drivers.ibm.gpfs.GPFSDriver"


class TestIbmibmstorageBackendContext:
    """Test the IbmibmstorageBackendContext class."""

    def test_ibmibmstorage_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.IbmibmstorageBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_ibmibmstorage_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.IbmibmstorageBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.ibm.ibm_storage.ibm_storage.IBMStorageDriver"
        )


class TestIbmstorwizesvcBackendContext:
    """Test the IbmstorwizesvcBackendContext class."""

    def test_ibmstorwizesvc_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.IbmstorwizesvcBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_ibmstorwizesvc_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.IbmstorwizesvcBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.ibm.storwize_svc.storwize_svc_fc.StorwizeSVCFCDriver"
        )

    def test_ibmstorwizesvc_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.IbmstorwizesvcBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.ibm.storwize_svc.storwize_svc_iscsi.StorwizeSVCISCSIDriver"
        )

    def test_ibmstorwizesvc_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.IbmstorwizesvcBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestInfinidatBackendContext:
    """Test the InfinidatBackendContext class."""

    def test_infinidat_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.InfinidatBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is True

    def test_infinidat_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.InfinidatBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.infinidat.InfiniboxVolumeDriver"
        )


class TestInspuras13000BackendContext:
    """Test the Inspuras13000BackendContext class."""

    def test_inspuras13000_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.Inspuras13000BackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_inspuras13000_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.Inspuras13000BackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.inspur.as13000.as13000_driver.AS13000Driver"
        )


class TestInspurinstorageBackendContext:
    """Test the InspurinstorageBackendContext class."""

    def test_inspurinstorage_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.InspurinstorageBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_inspurinstorage_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.InspurinstorageBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.inspur.instorage.instorage_fc.InStorageMCSFCDriver"
        )

    def test_inspurinstorage_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.InspurinstorageBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.inspur.instorage.instorage_iscsi"
            ".InStorageMCSISCSIDriver"
        )

    def test_inspurinstorage_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.InspurinstorageBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestKaminarioBackendContext:
    """Test the KaminarioBackendContext class."""

    def test_kaminario_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.KaminarioBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_kaminario_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.KaminarioBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.kaminario.kaminario_iscsi.KaminarioISCSIDriver"
        )


class TestLinstorBackendContext:
    """Test the LinstorBackendContext class."""

    def test_linstor_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.LinstorBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_linstor_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.LinstorBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.linstordrv.LinstorIscsiDriver"
        )


class TestMacrosanBackendContext:
    """Test the MacrosanBackendContext class."""

    def test_macrosan_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.MacrosanBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_macrosan_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.MacrosanBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.macrosan.driver.MacroSANISCSIDriver"
        )

    def test_macrosan_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.MacrosanBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.macrosan.driver.MacroSANFCDriver"
        )

    def test_macrosan_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.MacrosanBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestNecvBackendContext:
    """Test the NecvBackendContext class."""

    def test_necv_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.NecvBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_necv_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.NecvBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.nec.v.nec_v_fc.VStorageFCDriver"
        )

    def test_necv_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.NecvBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.nec.v.nec_v_iscsi.VStorageISCSIDriver"
        )

    def test_necv_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.NecvBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestNetappBackendContext:
    """Test the NetappBackendContext class."""

    def test_netapp_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.NetappBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is True

    def test_netapp_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.NetappBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.netapp.dataontap.iscsi_cmode.NetAppCmodeISCSIDriver"
        )

    def test_netapp_volume_driver_nvme(self):
        """Test volume_driver for nvme protocol."""
        ctx = context.NetappBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "nvme"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.netapp.dataontap.nvme_cmode.NetAppCmodeNVMeDriver"
        )

    def test_netapp_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.NetappBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestNexentaBackendContext:
    """Test the NexentaBackendContext class."""

    def test_nexenta_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.NexentaBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_nexenta_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.NexentaBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.nexenta.iscsi.NexentaISCSIDriver"
        )


class TestNimbleBackendContext:
    """Test the NimbleBackendContext class."""

    def test_nimble_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.NimbleBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_nimble_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.NimbleBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.hpe.nimble.NimbleISCSIDriver"
        )

    def test_nimble_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.NimbleBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"] == "cinder.volume.drivers.hpe.nimble.NimbleFCDriver"
        )

    def test_nimble_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.NimbleBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestOpeneBackendContext:
    """Test the OpeneBackendContext class."""

    def test_opene_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.OpeneBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_opene_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.OpeneBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.open_e.iscsi.JovianISCSIDriver"
        )


class TestProphetstorBackendContext:
    """Test the ProphetstorBackendContext class."""

    def test_prophetstor_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.ProphetstorBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_prophetstor_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.ProphetstorBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.prophetstor.dpl_fc.DPLFCDriver"
        )

    def test_prophetstor_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.ProphetstorBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.prophetstor.dpl_iscsi.DPLISCSIDriver"
        )

    def test_prophetstor_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.ProphetstorBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestQnapBackendContext:
    """Test the QnapBackendContext class."""

    def test_qnap_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.QnapBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_qnap_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.QnapBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == "cinder.volume.drivers.qnap.QnapISCSIDriver"


class TestSandstoneBackendContext:
    """Test the SandstoneBackendContext class."""

    def test_sandstone_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.SandstoneBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_sandstone_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.SandstoneBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.sandstone.sds_driver.SdsISCSIDriver"
        )


class TestStxBackendContext:
    """Test the StxBackendContext class."""

    def test_stx_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.StxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_stx_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.StxBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.stx.iscsi.STXISCSIDriver"
        )


class TestSynologyBackendContext:
    """Test the SynologyBackendContext class."""

    def test_synology_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.SynologyBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_synology_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.SynologyBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.synology.synology_iscsi.SynoISCSIDriver"
        )


class TestToyouacs5000BackendContext:
    """Test the Toyouacs5000BackendContext class."""

    def test_toyouacs5000_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.Toyouacs5000BackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_toyouacs5000_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.Toyouacs5000BackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.toyou.acs5000.acs5000_fc.Acs5000FCDriver"
        )

    def test_toyouacs5000_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.Toyouacs5000BackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.toyou.acs5000.acs5000_iscsi.Acs5000ISCSIDriver"
        )

    def test_toyouacs5000_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.Toyouacs5000BackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestVeritasaccessBackendContext:
    """Test the VeritasaccessBackendContext class."""

    def test_veritasaccess_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.VeritasaccessBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_veritasaccess_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.VeritasaccessBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert result["volume_driver"] == (
            "cinder.volume.drivers.veritas_access.veritas_iscsi.ACCESSIscsiDriver"
        )


class TestYadroBackendContext:
    """Test the YadroBackendContext class."""

    def test_yadro_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.YadroBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is True

    def test_yadro_volume_driver_fc(self):
        """Test volume_driver for fc protocol."""
        ctx = context.YadroBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "fc"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.yadro.tatlin_fc.TatlinFCVolumeDriver"
        )

    def test_yadro_volume_driver_iscsi(self):
        """Test volume_driver for iscsi protocol."""
        ctx = context.YadroBackendContext(
            "mybackend", {"volume_backend_name": "mybackend", "protocol": "iscsi"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.yadro.tatlin_iscsi.TatlinISCSIVolumeDriver"
        )

    def test_yadro_hidden_keys_excluded(self):
        """Test that hidden keys do not appear in cinder_context()."""
        ctx = context.YadroBackendContext(
            "mybackend", {"protocol": "testval", "volume_backend_name": "mybackend"}
        )
        result = ctx.cinder_context()
        assert "protocol" not in result


class TestZadaraBackendContext:
    """Test the ZadaraBackendContext class."""

    def test_zadara_supports_cluster(self):
        """Test supports_cluster is set correctly."""
        ctx = context.ZadaraBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        assert ctx.supports_cluster is False

    def test_zadara_volume_driver(self):
        """Test volume_driver is set correctly."""
        ctx = context.ZadaraBackendContext(
            "mybackend", {"volume_backend_name": "mybackend"}
        )
        result = ctx.context()
        assert (
            result["volume_driver"]
            == "cinder.volume.drivers.zadara.zadara.ZadaraVPSAISCSIDriver"
        )

# SPDX-FileCopyrightText: 2026 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

import errno
import json
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest
from snaphelpers._conf import UnknownConfigKey

from cinder_volume import ceph_check, context


class _FakeCephError(Exception):
    def __init__(self, code=None):
        super().__init__(code)
        self.errno = code


@pytest.fixture
def fake_ceph(monkeypatch):
    """Fake rados/rbd modules; tests configure the cluster mock."""
    rados = types.ModuleType("rados")
    rados.Error = _FakeCephError
    cluster = Mock()
    cluster.get_fsid.return_value = "fsid-1"
    cluster.pool_exists.return_value = True
    rados.Rados = Mock(return_value=cluster)
    rbd = types.ModuleType("rbd")
    rbd.Error = _FakeCephError
    rbd_api = Mock()
    rbd.RBD = Mock(return_value=rbd_api)
    monkeypatch.setitem(sys.modules, "rados", rados)
    monkeypatch.setitem(sys.modules, "rbd", rbd)
    return types.SimpleNamespace(rados=rados, cluster=cluster, rbd_api=rbd_api)


class _Opts(dict):
    def as_dict(self):
        return dict(self)


@pytest.fixture
def snap(tmp_path):
    s = Mock()
    s.paths.common = tmp_path
    s.config.get_options.return_value = _Opts(
        {
            "ceph": {
                "ceph-a": {
                    "rbd-pool": "vol",
                    "rbd-user": "cinder",
                    "mon-hosts": "10.0.0.1",
                    "rbd-key": "AQBkey==",
                    "auth": "cephx",
                }
            }
        }
    )
    (tmp_path / context.ETC_CEPH).mkdir(parents=True)
    (tmp_path / context.ETC_CEPH / "ceph-a.conf").write_text("[global]\n")
    return s


class TestCephCheck:
    def test_ok_returns_fsid(self, snap, fake_ceph):
        assert ceph_check.check(snap, "ceph-a") == (ceph_check.Result.OK, "fsid-1")
        kwargs = fake_ceph.rados.Rados.call_args.kwargs
        assert kwargs["name"] == "client.cinder"
        assert kwargs["conf"] == {
            "rados_osd_op_timeout": str(ceph_check.OP_TIMEOUT),
            "rados_mon_op_timeout": str(ceph_check.OP_TIMEOUT),
        }
        # a temporary conf, not the rendered one, and gone afterwards
        conf = Path(kwargs["conffile"])
        assert conf.name == "ceph.conf" and context.ETC_CEPH.name not in conf.parts
        assert not conf.parent.exists()
        fake_ceph.cluster.shutdown.assert_called_once()

    def test_op_timeout_is_unreachable(self, snap, fake_ceph):
        """An OSD op that times out (e.g. no OSD caps) is unreachable, not a hang."""
        fake_ceph.rbd_api.list.side_effect = _FakeCephError(errno.ETIMEDOUT)
        assert ceph_check.check(snap, "ceph-a")[0] == ceph_check.Result.UNREACHABLE
        fake_ceph.cluster.shutdown.assert_called_once()

    def test_op_timeout_fits_charm_budget(self):
        """Connect + one op must finish inside the charm's 60 s subprocess timeout."""
        assert ceph_check.CONNECT_TIMEOUT + ceph_check.OP_TIMEOUT < 60

    def test_unknown_backend_is_usage(self, snap, fake_ceph):
        assert ceph_check.check(snap, "nope")[0] == ceph_check.Result.USAGE

    def test_no_ceph_config_is_usage(self, snap, fake_ceph):
        snap.config.get_options.side_effect = UnknownConfigKey("ceph")
        assert ceph_check.check(snap, "ceph-a")[0] == ceph_check.Result.USAGE

    def test_not_rendered_still_returns_fsid(self, snap, fake_ceph):
        """Snap refused the backend: connect anyway, report NOT_RENDERED + fsid."""
        (snap.paths.common / context.ETC_CEPH / "ceph-a.conf").unlink()
        assert ceph_check.check(snap, "ceph-a") == (
            ceph_check.Result.NOT_RENDERED,
            "fsid-1",
        )

    @pytest.mark.parametrize(
        "missing", ["rbd-pool", "rbd-user", "mon-hosts", "rbd-key"]
    )
    def test_incomplete_settings_is_usage(self, snap, fake_ceph, missing):
        opts = snap.config.get_options.return_value["ceph"]["ceph-a"]
        del opts[missing]
        assert ceph_check.check(snap, "ceph-a")[0] == ceph_check.Result.USAGE
        fake_ceph.rados.Rados.assert_not_called()

    def test_client_files_content(self, tmp_path):
        conf = ceph_check._write_client_files(
            tmp_path,
            {"mon-hosts": "10.0.0.1,10.0.0.2", "rbd-key": "AQBkey==", "auth": "cephx"},
            "cinder",
        )
        text = conf.read_text()
        assert "mon host = 10.0.0.1,10.0.0.2" in text
        assert f"keyring = {tmp_path / 'keyring'}" in text
        keyring = tmp_path / "keyring"
        assert keyring.read_text() == "[client.cinder]\n    key = AQBkey==\n"
        assert keyring.stat().st_mode & 0o777 == 0o600

    def test_tempdir_removed_on_failure(self, snap, fake_ceph):
        fake_ceph.cluster.connect.side_effect = _FakeCephError(errno.ETIMEDOUT)
        ceph_check.check(snap, "ceph-a")
        conf = Path(fake_ceph.rados.Rados.call_args.kwargs["conffile"])
        assert not conf.parent.exists()

    def test_main_prints_fsid_when_not_rendered(self, monkeypatch, capsys):
        monkeypatch.setattr(ceph_check, "Snap", Mock())
        monkeypatch.setattr(
            ceph_check,
            "check",
            Mock(return_value=(ceph_check.Result.NOT_RENDERED, "f1")),
        )
        assert ceph_check.main(["ceph-a"]) == 6
        out = capsys.readouterr()
        assert json.loads(out.out) == {"fsid": "f1"}
        assert "NOT_RENDERED" in out.err

    def test_pool_missing(self, snap, fake_ceph):
        fake_ceph.cluster.pool_exists.return_value = False
        assert ceph_check.check(snap, "ceph-a")[0] == ceph_check.Result.POOL_MISSING

    @pytest.mark.parametrize("code", [errno.EACCES, errno.EPERM])
    def test_permission_denied_on_list(self, snap, fake_ceph, code):
        fake_ceph.rbd_api.list.side_effect = _FakeCephError(code)
        result = ceph_check.check(snap, "ceph-a")[0]
        assert result == ceph_check.Result.PERMISSION_DENIED

    def test_auth_failure_on_connect_is_permission(self, snap, fake_ceph):
        fake_ceph.cluster.connect.side_effect = _FakeCephError(errno.EACCES)
        result = ceph_check.check(snap, "ceph-a")[0]
        assert result == ceph_check.Result.PERMISSION_DENIED

    def test_unreachable(self, snap, fake_ceph):
        fake_ceph.cluster.connect.side_effect = _FakeCephError(errno.ETIMEDOUT)
        assert ceph_check.check(snap, "ceph-a")[0] == ceph_check.Result.UNREACHABLE

    def test_other_error_after_connect(self, snap, fake_ceph):
        fake_ceph.rbd_api.list.side_effect = _FakeCephError(errno.EIO)
        assert ceph_check.check(snap, "ceph-a")[0] == ceph_check.Result.ERROR
        fake_ceph.cluster.shutdown.assert_called_once()

    def test_main_prints_fsid(self, monkeypatch, capsys):
        monkeypatch.setattr(ceph_check, "Snap", Mock())
        monkeypatch.setattr(
            ceph_check, "check", Mock(return_value=(ceph_check.Result.OK, "f1"))
        )
        assert ceph_check.main(["ceph-a"]) == 0
        assert json.loads(capsys.readouterr().out) == {"fsid": "f1"}

    def test_main_failure_code(self, monkeypatch, capsys):
        monkeypatch.setattr(ceph_check, "Snap", Mock())
        monkeypatch.setattr(
            ceph_check,
            "check",
            Mock(return_value=(ceph_check.Result.POOL_MISSING, None)),
        )
        assert ceph_check.main(["ceph-a"]) == 3
        assert "POOL_MISSING" in capsys.readouterr().err

    def test_main_without_backend_is_usage(self):
        assert ceph_check.main([]) == ceph_check.Result.USAGE

    def test_codes_match_charm_contract(self):
        """Values are an interface with cinder-volume-ceph; never renumber."""
        assert {r.name: int(r) for r in ceph_check.Result} == {
            "OK": 0,
            "ERROR": 1,
            "USAGE": 2,
            "POOL_MISSING": 3,
            "PERMISSION_DENIED": 4,
            "UNREACHABLE": 5,
            "NOT_RENDERED": 6,
        }

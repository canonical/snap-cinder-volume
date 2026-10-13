# SPDX-FileCopyrightText: 2026 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Verify a ceph backend with the credentials that cinder will use.

Usage: ceph-check <backend>

Connects with the backend's rendered ceph.conf and keyring, checks the pool
exists and can be listed, and prints the cluster fsid in JSON. The exit code
is part of the contract with cinder-volume-ceph charm.
"""

import argparse
import enum
import errno
import json
import sys
import tempfile
from pathlib import Path

from snaphelpers import Snap
from snaphelpers._conf import UnknownConfigKey

from cinder_volume import context

CONNECT_TIMEOUT = 30
OP_TIMEOUT = 15


class Result(enum.IntEnum):
    """Exit codes, mirrored by CephCheckResult in cinder-volume-ceph."""

    OK = 0
    ERROR = 1
    USAGE = 2
    POOL_MISSING = 3
    PERMISSION_DENIED = 4
    UNREACHABLE = 5
    NOT_RENDERED = 6


def _from_errno(e: Exception, default: Result) -> Result:
    code = getattr(e, "errno", None)
    if code in (errno.EACCES, errno.EPERM):
        return Result.PERMISSION_DENIED
    if code == errno.ENOENT:
        return Result.POOL_MISSING
    if code == errno.ETIMEDOUT:
        return Result.UNREACHABLE
    return default


def _backend_config(snap: Snap, backend: str) -> dict:
    try:
        backends = snap.config.get_options("ceph").as_dict().get("ceph") or {}
    except UnknownConfigKey:
        return {}
    return backends.get(backend) or {}


def _write_client_files(directory: Path, cfg: dict, user: str) -> Path:
    """Write a minimal ceph.conf and keyring for this backend; return the conf.

    Built from snap settings, not the rendered files, so the check works
    before (or without) the snap rendering the backend.
    """
    keyring = directory / "keyring"
    keyring.touch(mode=0o600)
    keyring.write_text(f"[client.{user}]\n    key = {cfg['rbd-key']}\n")
    auth = cfg.get("auth") or "cephx"
    conf = directory / "ceph.conf"
    conf.write_text(
        "[global]\n"
        f"mon host = {cfg['mon-hosts']}\n"
        f"auth cluster required = {auth}\n"
        f"auth service required = {auth}\n"
        f"auth client required = {auth}\n"
        f"keyring = {keyring}\n"
    )
    return conf


def check(snap: Snap, backend: str) -> tuple[Result, str | None]:
    """Run the check; return the result and, once connected, the cluster fsid."""
    import rados  # type: ignore[import-not-found]  # python3-rados in the snap
    import rbd  # type: ignore[import-not-found]  # python3-rbd in the snap

    cfg = _backend_config(snap, backend)
    pool, user = cfg.get("rbd-pool"), cfg.get("rbd-user")
    if not (pool and user and cfg.get("mon-hosts") and cfg.get("rbd-key")):
        return Result.USAGE, None
    rendered = (
        snap.paths.common
        / context.ETC_CEPH
        / context.CephBackendContext(backend, {}).ceph_conf()
    )

    with tempfile.TemporaryDirectory(prefix="ceph-check-") as tmp:
        conffile = _write_client_files(Path(tmp), cfg, user)
        cluster = rados.Rados(
            conffile=str(conffile),
            name=f"client.{user}",
            conf={
                "rados_osd_op_timeout": str(OP_TIMEOUT),
                "rados_mon_op_timeout": str(OP_TIMEOUT),
            },
        )
        try:
            cluster.connect(timeout=CONNECT_TIMEOUT)
        except rados.Error as e:
            return _from_errno(e, Result.UNREACHABLE), None
        try:
            fsid = cluster.get_fsid()
            if not cluster.pool_exists(pool):
                return Result.POOL_MISSING, None
            ioctx = cluster.open_ioctx(pool)
            try:
                rbd.RBD().list(ioctx)
            finally:
                ioctx.close()
        except (rados.Error, rbd.Error) as e:
            return _from_errno(e, Result.ERROR), None
        finally:
            cluster.shutdown()
        if not rendered.exists():
            return Result.NOT_RENDERED, fsid
        return Result.OK, fsid


def main(argv: list[str] | None = None) -> int:
    """Entry point for `snap run cinder-volume.ceph-check <backend>."""
    parser = argparse.ArgumentParser(prog="ceph-check")
    parser.add_argument("backend")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return Result.USAGE
    result, fsid = check(Snap(), args.backend)
    if fsid and result in (Result.OK, Result.NOT_RENDERED):
        print(json.dumps({"fsid": fsid}))
    if result != Result.OK:
        print(f"ceph-check {args.backend}: {result.name}", file=sys.stderr)
    return result

# SPDX-FileCopyrightText: 2026 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Verify a ceph backend with the credentials that cinder will use.

Usage: ceph-check <backend>

Probes the cluster with a temporary ceph.conf and keyring built from the
backend's snap settings: checks the pool exists and can be listed, and
prints the cluster fsid in JSON. Then checks that the configure applied those
settings: the backend's cinder.conf.d stanza, ceph.conf and keyring must
match what the current configuration renders. The exit code is part of
the contract with cinder-volume-ceph charm.
"""

import argparse
import enum
import errno
import json
import os
import sys
import tempfile
from pathlib import Path

from snaphelpers import Snap
from snaphelpers._conf import UnknownConfigKey

from cinder_volume import cinder_volume

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


def _backend_applied(snap: Snap, backend: str) -> bool:
    """Whether configure applied this backend's current settings."""
    return cinder_volume.GenericCinderVolume().backend_applied(snap, backend)


def check(snap: Snap, backend: str) -> tuple[Result, str | None]:
    """Run the check; return the result and, once connected, the cluster fsid."""
    import rados  # type: ignore[import-not-found]  # python3-rados in the snap
    import rbd  # type: ignore[import-not-found]  # python3-rbd in the snap

    cfg = _backend_config(snap, backend)
    pool, user = cfg.get("rbd-pool"), cfg.get("rbd-user")
    if not (pool and user and cfg.get("mon-hosts") and cfg.get("rbd-key")):
        return Result.USAGE, None

    with tempfile.TemporaryDirectory(prefix="ceph-check-") as tmp:
        conffile = _write_client_files(Path(tmp), cfg, user)
        cluster = rados.Rados(
            conffile=str(conffile),
            name=f"client.{user}",
            conf={
                "client_mount_timeout": str(CONNECT_TIMEOUT),
                "rados_osd_op_timeout": str(OP_TIMEOUT),
                "rados_mon_op_timeout": str(OP_TIMEOUT),
            },
        )
        try:
            cluster.connect()
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
        if not _backend_applied(snap, backend):
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
    if os.geteuid() != 0:
        print("ceph-check: must be run as root (sudo)", file=sys.stderr)
        return Result.USAGE
    result, fsid = check(Snap(), args.backend)
    if fsid and result in (Result.OK, Result.NOT_RENDERED):
        print(json.dumps({"fsid": fsid}))
    if result != Result.OK:
        print(f"ceph-check {args.backend}: {result.name}", file=sys.stderr)
    return result

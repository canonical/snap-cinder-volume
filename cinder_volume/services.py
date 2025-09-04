# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Services module for managing OpenStack services."""

import functools
import logging
import subprocess
import sys
import typing
from pathlib import Path

from snaphelpers import Snap

from . import log

_SERVICES: list[typing.Type["OpenStackService"]] = []


def entry_point(service_class):
    """Entry point wrapper for services."""
    service = service_class()
    exit_code = service.run(Snap())
    sys.exit(exit_code)


def services() -> typing.Sequence[typing.Type["OpenStackService"]]:
    """Return the list of registered services."""
    return _SERVICES


class OpenStackService:
    """Base service object for OpenStack daemons."""

    # only fully specified configuration files will trigger a restart
    # on modification
    configuration_files: typing.Sequence[Path] = []
    configuration_directories: typing.Sequence[Path] = []
    extra_args: typing.Sequence[str] = []

    name: str
    executable: Path

    def __init_subclass__(cls, **kwargs):
        """Register inherited classes."""
        super().__init_subclass__(**kwargs)
        _SERVICES.append(cls)

    def run(self, snap: Snap) -> int:
        """Runs the OpenStack service.

        Invoked when this service is started.

        :param snap: the snap context
        :type snap: Snap
        :return: exit code of the process
        :rtype: int
        """
        log.setup_logging(snap.paths.common / f"{self.executable.name}-{snap.name}.log")

        args = []
        for conf_file in self.configuration_files:
            args.extend(
                [
                    "--config-file",
                    str(snap.paths.common / conf_file),
                ]
            )
        for conf_dir in self.configuration_directories:
            args.extend(
                [
                    "--config-dir",
                    str(snap.paths.common / conf_dir),
                ]
            )

        executable = snap.paths.snap / self.executable

        cmd = [str(executable)]
        cmd.extend(args)
        cmd.extend(self.extra_args)
        completed_process = subprocess.run(cmd)

        logging.info(f"Exiting with code {completed_process.returncode}")
        return completed_process.returncode


class CinderVolume(OpenStackService):
    """Cinder volume service implementation."""

    configuration_files = [
        Path("etc/cinder/cinder.conf"),
        Path("etc/cinder/rootwrap.conf"),
    ]
    configuration_directories = [Path("etc/cinder/cinder.conf.d")]
    name = "cinder-volume"
    executable = Path("usr/bin/cinder-volume")


cinder_volume = functools.partial(entry_point, CinderVolume)

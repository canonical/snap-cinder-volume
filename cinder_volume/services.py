# Copyright 2024 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import functools
import logging
import subprocess
import sys
import typing
from pathlib import Path

from snaphelpers import Snap

from . import log


def entry_point(service_class):
    """Entry point wrapper for services."""
    service = service_class()
    exit_code = service.run(Snap())
    sys.exit(exit_code)


class OpenStackService:
    """Base service object for OpenStack daemons."""

    configuration_files: typing.Sequence[Path] = []
    configuration_directories: typing.Sequence[Path] = []
    extra_args: typing.Sequence[str] = []

    executable: Path

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
    configuration_files = [
        Path("etc/cinder/cinder.conf"),
        Path("etc/cinder/rootwrap.conf"),
    ]
    configuration_directories = [Path("etc/cinder/cinder.conf.d")]


cinder_volume = functools.partial(entry_point, CinderVolume)

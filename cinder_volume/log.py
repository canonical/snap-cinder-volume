# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Logging utilities for the cinder-volume snap."""

import logging
from pathlib import Path


def setup_logging(logfile: Path | str) -> None:
    """Sets up the logging for the specified logfile.

    :param logfile: the file to record logging information to
    :type logfile: Path or str
    :return: None
    """
    logging.basicConfig(
        filename=str(logfile),
        filemode="a",
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG,
    )

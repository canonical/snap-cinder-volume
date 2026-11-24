# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Error classes for the cinder-volume snap."""


class CinderError(Exception):
    """Base class for all Cinder errors."""


class NoBackendsError(CinderError):
    """The configuration enables no backends."""


class BackendRemovalError(CinderError):
    """Removing a backend failed; the previous state was restored."""

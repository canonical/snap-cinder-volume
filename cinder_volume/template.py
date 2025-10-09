# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Template and directory classes for configuration."""

import typing
from pathlib import Path

Locations = typing.Literal["common", "data"]


class Directory:
    """Represents a directory to be created."""

    path: Path
    mode: int
    location: Locations

    def __init__(
        self, path: str | Path, mode: int = 0o750, location: Locations | None = None
    ):
        """Initialize directory with path, mode, and location."""
        self.path = Path(path)
        self.mode = mode
        self.location = (
            location
            if location is not None
            else getattr(self.__class__, "location", "common")
        )


class CommonDirectory(Directory):
    """Directory in the common location."""

    location = "common"


class DataDirectory(Directory):
    """Directory in the data location."""

    location = "data"


ContextType = typing.Mapping[str, typing.Any]
Conditional = typing.Callable[[ContextType], bool]


def true_conditional(_: ContextType) -> bool:
    """A conditional that always returns True."""
    return True


class Template:
    """Represents a template file to be rendered."""

    filename: str
    dest: Path
    mode: int
    template_name: str | None
    location: Locations
    conditionals: typing.Sequence[Conditional]

    def __init__(
        self,
        src: str,
        dest: Path,
        mode: int = 0o640,
        template_name: str | None = None,
        location: Locations | None = None,
        conditionals: typing.Sequence[Conditional] = (true_conditional,),
    ):
        """Initialize template with source, destination, and options."""
        self.filename = src
        self.dest = dest
        self.mode = mode
        self.template_name = template_name
        self.location = (
            location
            if location is not None
            else getattr(self.__class__, "location", "common")
        )
        self.conditionals = conditionals

    def rel_path(self) -> Path:
        """Return the relative path of the template."""
        return self.dest / self.template()

    def template(self) -> str:
        """Return the template name or filename."""
        return self.template_name or self.filename


class CommonTemplate(Template):
    """Template for common location."""

    location = "common"


class DataTemplate(Template):
    """Template for data location."""

    location = "data"

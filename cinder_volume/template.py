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
import typing
from pathlib import Path

Locations = typing.Literal["common", "data"]


class Directory:
    path: Path
    mode: int
    location: Locations

    def __init__(
        self, path: str | Path, mode: int = 0o750, location: Locations = "common"
    ):
        self.path = Path(path)
        self.mode = mode
        self.location = location


class CommonDirectory(Directory):
    location = "common"


class DataDirectory(Directory):
    location = "data"


class Template:
    filename: str
    dest: Path
    mode: int
    template_name: str | None
    location: Locations

    def __init__(
        self,
        src: str,
        dest: Path,
        mode: int = 0o640,
        template_name: str | None = None,
        location: Locations = "common",
    ):
        self.filename = src
        self.dest = dest
        self.mode = mode
        self.template_name = template_name
        self.location = location

    def rel_path(self) -> Path:
        return self.dest / self.template()

    def template(self) -> str:
        return self.template_name or self.filename


class CommonTemplate(Template):
    location = "common"


class DataTemplate(Template):
    location = "data"

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
from pathlib import Path
import typing


Locations = typing.Literal["common", "data"]


class Template:
    src: str
    dest: Path
    location: Locations

    def __init__(self, src: str, dest: Path, location: Locations = "common"):
        self.src = src
        self.dest = dest
        self.location = location


class CommonTemplate(Template):
    location = "common"


class DataTemplate(Template):
    location = "data"

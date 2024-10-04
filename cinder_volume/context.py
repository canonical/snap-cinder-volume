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

from snaphelpers import Snap


class Context:
    namespace: str

    def context(self) -> typing.Mapping[str, typing.Any]:
        return {}

class ConfigContext(Context):
    def __init__(self, namespace: str, config: typing.Mapping[str, typing.Any]):
        self.namespace = namespace
        self.config = config

    def context(self) -> typing.Mapping[str, typing.Any]:
        return self.config


class SnapPathContext(Context):
    namespace = "snap_paths"

    def __init__(self, snap: Snap):
        self.snap = snap

    def context(self) -> typing.Mapping[str, typing.Any]:
        return {
            name: getattr(self.snap.paths, "name") for name in self.snap.paths.__slots__
        }



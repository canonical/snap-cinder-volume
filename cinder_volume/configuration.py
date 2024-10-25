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

import pydantic
import pydantic.alias_generators


def to_kebab(value: str) -> str:
    return pydantic.alias_generators.to_snake(value).replace("_", "-")


class ParentConfig(pydantic.BaseModel):
    """Set common model configuration for all models."""

    model_config = pydantic.ConfigDict(
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )


class DatabaseConfiguration(ParentConfig):
    url: str


class RabbitMQConfiguration(ParentConfig):
    url: str


class CinderConfiguration(ParentConfig):
    project_id: str
    user_id: str
    image_volume_cache_enabled: bool = False
    image_volume_cache_max_size_gb: int = 0
    image_volume_cache_max_count: int = 0
    cluster: str | None = None


class Settings(ParentConfig):
    debug: bool = False


class BaseConfiguration(ParentConfig):
    """Base configuration class.

    This class should be the basis of downstream snaps.
    """

    settings: Settings = Settings()
    database: DatabaseConfiguration
    rabbitmq: RabbitMQConfiguration
    cinder: CinderConfiguration


class Configuration(BaseConfiguration):
    """Holding additional configuration for the generic snap.

    This class is specific to this snap and should not be used in
    downstream snaps.
    """

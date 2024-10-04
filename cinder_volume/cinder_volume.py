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

import inspect
import logging
import typing
from pathlib import Path

import jinja2
from snaphelpers import Snap

from . import configuration, context, log, template

ETC_CINDER = Path("etc/cinder")


class CinderVolume:

    @classmethod
    def install_hook(cls, snap: Snap) -> None:
        log.setup_logging(snap.paths.common / "hooks.log")
        cls().install(snap)

    @classmethod
    def configure_hook(cls, snap: Snap) -> None:
        log.setup_logging(snap.paths.common / "hooks.log")
        cls().configure(snap)

    def install(self, snap: Snap) -> None:
        self.setup_dirs(snap)
        self.template(snap)

    def configure(self, snap: Snap) -> None:
        self.setup_dirs(snap)
        modified = self.template(snap)
        self.start_services(snap, modified)

    def start_services(self, snap: Snap, modified_files) -> None:
        pass

    def config_type(self):
        return configuration.Configuration

    def get_config(self, snap: Snap) -> configuration.Configuration:
        return self.config_type().model_validate(snap.config.get_options(*()).as_dict())

    def common_dirs(self) -> list[str]:
        """Directories to be created on the common path."""
        return ["etc/cinder"]

    def data_dirs(self) -> list[str]:
        """Directories to be created on the data path."""
        return []

    def template_files(self) -> list[template.Template]:
        """Files to be templated."""
        return [
            template.CommonTemplate("cinder.conf", ETC_CINDER),
            template.CommonTemplate("rootwrap.conf", ETC_CINDER),
        ]

    def contexts(self, snap: Snap) -> list[context.Context]:
        """Contexts to be used in the templates."""
        return [
            context.SnapPathContext(snap),
            *(
                context.ConfigContext(k, v)
                for k, v in self.get_config(snap).model_dump().items()
            ),
        ]

    def render_context(
        self, snap: Snap
    ) -> typing.Mapping[str, typing.Mapping[str, str]]:
        context = {}
        for ctx in self.contexts(snap):
            logging.debug("Adding context: %s", ctx.namespace)
            context[ctx.namespace] = ctx.context()
        return context

    def setup_dirs(self, snap: Snap) -> None:
        for d in self.common_dirs():
            logging.debug("Creating directory: %s", d)
            snap.paths.common.joinpath(d).mkdir(parents=True, exist_ok=True)
        for d in self.data_dirs():
            logging.debug("Creating directory: %s", d)
            snap.paths.data.joinpath(d).mkdir(parents=True, exist_ok=True)

    def templates_search_path(self, snap: Snap) -> list[Path]:
        try:
            extra = [Path(inspect.getfile(self.__class__)).parent / "templates"]
        except Exception:
            logging.error("Failed to get templates path from class", exc_info=True)
            extra = []
        return [
            snap.paths.common / "templates",
            *extra,
            Path(__file__).parent / "templates",
        ]

    def template(self, snap: Snap) -> list[template.Template]:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath=self.templates_search_path(snap))
        )
        modified_templates: list[template.Template] = []
        try:
            context = self.render_context(snap)
        except Exception as e:
            logging.error("Failed to render context: %s", e)
            return modified_templates
        for f in self.template_files():
            file_name = f.src
            dest_dir: Path = getattr(snap.paths, f.location) / f.dest
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / file_name

            original_hash = None
            if dest_file.exists():
                original_hash = hash(dest_file.read_text())

            rendered = env.get_template(f.src).render(**context)

            new_hash = hash(rendered)

            if original_hash == new_hash:
                logging.debug("File %s not changed, skipping", dest_file)
                continue
            logging.debug("File %s changed, writing new content", dest_file)
            modified_templates.append(f)
            with dest_file.open("w") as fd:
                fd.write(rendered)
        return modified_templates

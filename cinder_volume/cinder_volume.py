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

import abc
import inspect
import logging
import typing
from pathlib import Path

import jinja2
import pydantic
from snaphelpers import Snap

from . import configuration, context, error, log, services, template

ETC_CINDER = Path("etc/cinder")


CONF = typing.TypeVar("CONF", bound=configuration.BaseConfiguration)


class CinderVolume(typing.Generic[CONF], abc.ABC):
    def __init__(self) -> None:
        self._contexts: typing.Sequence[context.Context] | None = None
        self._backend_contexts: context.CinderBackendContexts | None = None

    @classmethod
    def install_hook(cls, snap: Snap) -> None:
        log.setup_logging(snap.paths.common / "hooks.log")
        cls().install(snap)

    @classmethod
    def configure_hook(cls, snap: Snap) -> None:
        log.setup_logging(snap.paths.common / "hooks.log")
        try:
            cls().configure(snap)
        except error.CinderError:
            logging.warning("Configuration not complete", exc_info=True)

    def install(self, snap: Snap) -> None:
        self.setup_dirs(snap)
        self.template(snap)

    def configure(self, snap: Snap) -> None:
        backend_contexts = self.backend_contexts(snap)
        self.setup_dirs(snap, backend_contexts)
        modified = self.template(snap)
        backend_tpls = []
        for backend_context in backend_contexts.contexts.values():
            backend_tpls.extend(backend_context.template_files())
            backend_context.setup(snap)
        self.start_services(snap, modified, backend_tpls)

    def start_services(
        self,
        snap: Snap,
        modified_tpl: typing.Sequence[template.Template],
        backend_tpls: typing.Sequence[template.Template],
    ) -> None:
        modified_files: set[Path] = set()
        for tpl in modified_tpl:
            modified_files.add(tpl.rel_path())
        backend_files: set[Path] = set()
        for tpl in backend_tpls:
            backend_files.add(tpl.rel_path())
        snap_services = snap.services.list()
        for service in services.services():
            snap_service = snap_services.get(service.name)
            if not snap_service:
                logging.warning("Service %s not found in snap services", service.name)
                continue

            common = modified_files.intersection(
                set(service.configuration_files) | backend_files
            )
            if common:
                logging.debug("Restarting service %s", service.name)
                snap_service.restart()
            else:
                logging.debug("Starting service %s", service.name)
                snap_service.start()

    @abc.abstractmethod
    def config_type(self) -> typing.Type[CONF]:
        raise NotImplementedError

    def get_config(self, snap: Snap) -> CONF:
        keys = self.config_type().model_fields.keys()
        try:
            return self.config_type().model_validate(
                snap.config.get_options(*keys).as_dict()
            )
        except pydantic.ValidationError as e:
            raise error.CinderError("Invalid configuration") from e

    def directories(self) -> list[template.Directory]:
        """Directories to be created on the common path."""
        return [
            template.CommonDirectory("etc/cinder"),
            template.CommonDirectory("etc/cinder/cinder.conf.d"),
            template.CommonDirectory("lib/cinder"),
        ]

    def template_files(self) -> list[template.Template]:
        """Files to be templated."""
        return [
            template.CommonTemplate("cinder.conf", ETC_CINDER),
            template.CommonTemplate("rootwrap.conf", ETC_CINDER),
        ]

    @abc.abstractmethod
    def backend_contexts(self, snap: Snap) -> context.CinderBackendContexts:
        """Instanciated backend context."""
        raise NotImplementedError

    def contexts(self, snap: Snap) -> typing.Sequence[context.Context]:
        """Contexts to be used in the templates."""
        if self._contexts is None:
            self._contexts = [
                context.SnapPathContext(snap),
                *(
                    context.ConfigContext(k, v)
                    for k, v in self.get_config(snap).model_dump().items()
                ),
            ]
        return self._contexts

    def render_context(
        self, snap: Snap
    ) -> typing.MutableMapping[str, typing.Mapping[str, str]]:
        context = {}
        for ctx in self.contexts(snap):
            logging.debug("Adding context: %s", ctx.namespace)
            context[ctx.namespace] = ctx.context()
        return context

    def setup_dirs(
        self, snap: Snap, backend_contexts: context.CinderBackendContexts | None = None
    ) -> None:
        directories = self.directories()
        if backend_contexts:
            for backend_context in backend_contexts.contexts.values():
                directories.extend(backend_context.directories())

        for d in directories:
            path: Path = getattr(snap.paths, d.location).joinpath(d.path)
            logging.debug("Creating directory: %s", path)
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(d.mode)

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

    def _process_template(
        self,
        snap: Snap,
        env: jinja2.Environment,
        template: template.Template,
        context: typing.Mapping[str, typing.Mapping[str, str]],
    ) -> bool:
        file_name = template.filename
        dest_dir: Path = getattr(snap.paths, template.location) / template.dest
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / file_name.removesuffix(".j2")

        original_hash = None
        if dest_file.exists():
            original_hash = hash(dest_file.read_text())

        tpl = None
        template_file = template.template()
        try:
            tpl = env.get_template(template_file)
        except jinja2.exceptions.TemplateNotFound:
            logging.debug("Template %s not found, trying with .j2", template_file)
            tpl = env.get_template(template_file + ".j2")

        rendered = tpl.render(**context)
        if len(rendered) > 0 and rendered[-1] != "\n":
            # ensure trailing new line
            rendered += "\n"

        new_hash = hash(rendered)

        if original_hash == new_hash:
            logging.debug("File %s has not changed, skipping", dest_file)
            return False
        logging.debug("File %s has changed, writing new content", dest_file)
        dest_file.write_text(rendered)
        dest_file.chmod(template.mode)
        return True

    def _render_specific_backend_configs(
        self,
        context: typing.Mapping[str, typing.Mapping[str, str]],
        value: typing.Any,
    ) -> typing.Any:
        """Allow to render backend values with jinja2 templates."""
        if isinstance(value, str):
            return jinja2.Template(value).render(**context)
        elif isinstance(value, dict):
            return {
                k: self._render_specific_backend_configs(context, v)
                for k, v in value.items()
            }
        return value

    def template(self, snap: Snap) -> list[template.Template]:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath=self.templates_search_path(snap)),
            keep_trailing_newline=True,
        )
        modified_templates: list[template.Template] = []
        try:
            context = self.render_context(snap)
        except Exception as e:
            logging.error("Failed to render context: %s", e)
            return modified_templates
        backend_contexts = self.backend_contexts(snap)
        context[backend_contexts.namespace] = self._render_specific_backend_configs(
            context, backend_contexts.context()
        )
        # process general templates
        for tpl in self.template_files():
            if self._process_template(snap, env, tpl, context):
                modified_templates.append(tpl)
        # process backend specific templates
        for backend_context in backend_contexts.contexts.values():
            context[backend_context.namespace] = backend_context.context()
            for tpl in backend_context.template_files():
                if self._process_template(snap, env, tpl, context):
                    modified_templates.append(tpl)
            context.pop(backend_context.namespace)

        return modified_templates


class GenericCinderVolume(CinderVolume[configuration.Configuration]):
    def config_type(self) -> typing.Type[configuration.Configuration]:
        return configuration.Configuration

    def backend_contexts(self, snap: Snap) -> context.CinderBackendContexts:
        """Instantiated backend context."""
        if self._backend_contexts is None:
            try:
                cfg = self.get_config(snap)
            except pydantic.ValidationError as e:
                raise error.CinderError("Invalid configuration") from e

            backend_ctxs: dict[str, context.Context] = {}

            # Ceph back-ends
            for name, be_cfg in cfg.ceph.items():
                backend_ctxs[name] = context.CephBackendContext(
                    name, be_cfg.model_dump()
                )

            # Hitachi back-ends 
            for name, be_cfg in cfg.hitachi.items():
                backend_ctxs[name] = context.HitachiBackendContext(
                    name, be_cfg.model_dump()
                )

            self._backend_contexts = context.CinderBackendContexts(
                enabled_backends=list(backend_ctxs.keys()),
                contexts=backend_ctxs,
            )
        return self._backend_contexts

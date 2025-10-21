# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Cinder Volume Snap Service.

This module provides the core CinderVolume class and related functionality
for managing Cinder volume services within a snap environment.
"""

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
    """Abstract base class for Cinder volume service implementations."""

    def __init__(self) -> None:
        """Initialize the CinderVolume instance."""
        self._contexts: typing.Sequence[context.Context] | None = None
        self._backend_contexts: context.CinderBackendContexts | None = None

    @classmethod
    def install_hook(cls, snap: Snap) -> None:
        """Install hook for the Cinder volume snap."""
        log.setup_logging(snap.paths.common / "hooks.log")
        cls().install(snap)

    @classmethod
    def configure_hook(cls, snap: Snap) -> None:
        """Configure hook for the Cinder volume snap."""
        log.setup_logging(snap.paths.common / "hooks.log")
        try:
            cls().configure(snap)
        except error.CinderError:
            logging.warning("Configuration not complete", exc_info=True)

    def install(self, snap: Snap) -> None:
        """Install the Cinder volume service."""
        self.setup_dirs(snap)
        self.template(snap)

    def configure(self, snap: Snap) -> None:
        """Configure the Cinder volume service."""
        # Always clear existing backend configuration files first
        # This ensures cleanup even when no backends are configured
        self._clear_backend_configs(snap)

        try:
            backend_contexts = self.backend_contexts(snap)
        except error.CinderError as e:
            # If no backends are configured, just clear configs and exit
            if "At least one backend must be enabled" in str(e):
                logging.info("No backends configured, cleared all backend configs")
                return
            # Re-raise other configuration errors
            raise

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
        """Start the Cinder volume services."""
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
        """Return the configuration type."""
        raise NotImplementedError

    def get_config(self, snap: Snap) -> CONF:
        """Get the configuration for the snap."""
        logging.debug("Getting configuration")
        keys = self.config_type().model_fields.keys()
        all_config = snap.config.get_options(*keys).as_dict()

        try:
            return self.config_type().model_validate(all_config)
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
        """Render the context for the snap."""
        context = {}
        for ctx in self.contexts(snap):
            logging.debug("Adding context: %s", ctx.namespace)
            context[ctx.namespace] = ctx.context()
        return context

    def setup_dirs(
        self, snap: Snap, backend_contexts: context.CinderBackendContexts | None = None
    ) -> None:
        """Set up directories for the snap."""
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
        """Get the search path for templates."""
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

        if template.conditionals:
            if not all(cond(context) for cond in template.conditionals):
                logging.debug(
                    "Skipping template %s due to unmet conditionals", template.filename
                )
                if dest_file.exists():
                    logging.debug("Removing existing file %s", dest_file)
                    dest_file.unlink()
                return False

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
        """Render templates for the Cinder volume service."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath=self.templates_search_path(snap)),
            keep_trailing_newline=True,
            autoescape=jinja2.select_autoescape(),
        )
        env.globals.update(
            {
                "backend_ctx": context.backend_ctx,
                "cinder_name": context.cinder_name,
                "cinder_ctx": context.cinder_ctx,
            }
        )
        modified_templates: list[template.Template] = []
        try:
            ctx = self.render_context(snap)
        except Exception as e:
            logging.error("Failed to render context: %s", e)
            return modified_templates
        backend_contexts = self.backend_contexts(snap)
        ctx[backend_contexts.namespace] = self._render_specific_backend_configs(
            ctx, backend_contexts.context()
        )
        # process general templates
        for tpl in self.template_files():
            if self._process_template(snap, env, tpl, ctx):
                modified_templates.append(tpl)
        # process backend specific templates
        for backend_context in backend_contexts.contexts.values():
            ctx[context.BACKEND_CTX_KEY] = backend_context.context()
            ctx[context.CINDER_CTX_KEY] = backend_context.backend_name  # type: ignore
            for tpl in backend_context.template_files():
                if self._process_template(snap, env, tpl, ctx):
                    modified_templates.append(tpl)
            ctx.pop(context.CINDER_CTX_KEY)
            ctx.pop(context.BACKEND_CTX_KEY)

        return modified_templates

    def _clear_backend_configs(self, snap: Snap) -> None:
        """Clear all existing backend configuration files.

        This ensures that when backends are removed from configuration,
        their template files are also removed from the filesystem.
        """
        backend_config_dir = snap.paths.common / "etc/cinder/cinder.conf.d"
        if not backend_config_dir.exists():
            return

        # Remove all .conf files in cinder.conf.d directory
        # These are backend-specific configuration files
        for conf_file in backend_config_dir.glob("*.conf"):
            try:
                logging.debug("Removing backend config file: %s", conf_file)
                conf_file.unlink()
            except OSError as e:
                logging.warning(
                    "Failed to remove backend config file %s: %s", conf_file, e
                )


class GenericCinderVolume(CinderVolume[configuration.Configuration]):
    """Generic implementation of Cinder volume service."""

    def config_type(self) -> typing.Type[configuration.Configuration]:
        """Return the configuration type."""
        return configuration.Configuration

    def backend_contexts(self, snap: Snap) -> context.CinderBackendContexts:
        """Instantiated backend context using fully dynamic discovery."""
        if self._backend_contexts is None:
            try:
                cfg = self.get_config(snap)
            except pydantic.ValidationError as e:
                raise error.CinderError("Invalid configuration") from e

            backend_ctxs: dict[str, context.BaseBackendContext] = {}

            # Auto-discover all backend types from configuration
            for field_name, field_info in self.config_type().model_fields.items():
                # Skip non-backend fields
                if not isinstance(getattr(cfg, field_name), dict):
                    continue

                # Get the context class name by convention: {Backend}BackendContext
                context_class_name = f"{field_name.title()}BackendContext"

                # Get the context class from the context module
                if hasattr(context, context_class_name):
                    context_class = getattr(context, context_class_name)
                    backend_configs = getattr(cfg, field_name)

                    # Instantiate contexts for all backends of this type
                    for name, be_cfg in backend_configs.items():
                        backend_ctxs[name] = context_class(name, be_cfg.model_dump())
                else:
                    logging.warning(
                        f"Context class {context_class_name} not"
                        f" found for backend type {field_name}"
                    )

            self._backend_contexts = context.CinderBackendContexts(
                enabled_backends=list(backend_ctxs.keys()),
                contexts=backend_ctxs,
            )
        return self._backend_contexts

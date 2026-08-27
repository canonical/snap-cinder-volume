# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Cinder Volume Snap Service.

This module provides the core CinderVolume class and related functionality
for managing Cinder volume services within a snap environment.
"""

import abc
import dataclasses
import inspect
import logging
import os
import stat
import tempfile
import typing
from pathlib import Path

import jinja2
import pydantic
from snaphelpers import Snap

from . import configuration, context, error, log, services, template

ETC_CINDER = Path("etc/cinder")
ETC_SSL_CERTS = Path("etc/ssl/certs")


CONF = typing.TypeVar("CONF", bound=configuration.BaseConfiguration)
ManagedFile = template.Template | context.BackendTLSMaterial
ManagedOutput = ManagedFile | Path
PreparedFile = tuple[ManagedFile, bytes | None]


@dataclasses.dataclass(frozen=True)
class OriginalFile:
    """Restorable state of one managed path before a transaction."""

    kind: typing.Literal["absent", "regular", "symlink"]
    content: bytes | str | None = None
    mode: int | None = None


PendingFile = tuple[ManagedFile, Path, Path | None, OriginalFile]


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
        try:
            cls().install(snap)
        except error.CinderError:
            logging.warning("Configuration not complete", exc_info=True)

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
        backend_contexts = self.backend_contexts(snap)

        prepared = self._prepare_configuration_files(snap, backend_contexts)
        self.setup_dirs(snap, backend_contexts)
        modified: list[ManagedOutput] = [
            *self._write_configuration_files(snap, prepared)
        ]
        backend_tpls: list[ManagedOutput] = []
        for backend_context in backend_contexts.contexts.values():
            backend_tpls.extend(backend_context.template_files())
            backend_tpls.extend(backend_context.tls_materials)
            backend_context.setup(snap)
        pruned = self._prune_stale_backend_configs(snap, backend_contexts)
        modified.extend(pruned)
        backend_tpls.extend(pruned)
        self.start_services(snap, modified, backend_tpls)

    def start_services(
        self,
        snap: Snap,
        modified_tpl: typing.Sequence[ManagedOutput],
        backend_tpls: typing.Sequence[ManagedOutput],
    ) -> None:
        """Start the Cinder volume services."""
        modified_files: set[Path] = set()
        for tpl in modified_tpl:
            modified_files.add(tpl if isinstance(tpl, Path) else tpl.output_path())
        backend_files: set[Path] = set()
        for tpl in backend_tpls:
            backend_files.add(tpl if isinstance(tpl, Path) else tpl.output_path())
        snap_services = snap.services.list()
        for service in services.services():
            snap_service = snap_services.get(service.name)
            if not snap_service:
                logging.warning("Service %s not found in snap services", service.name)
                continue

            common = modified_files.intersection(
                set(service.configuration_files)
                | set(service.restart_trigger_files)
                | backend_files
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
            template.CommonDirectory(ETC_SSL_CERTS),
            template.CommonDirectory("lib/cinder"),
        ]

    def template_files(self) -> list[template.Template]:
        """Files to be templated."""
        return [
            template.CommonTemplate("cinder.conf", ETC_CINDER),
            template.CommonTemplate("rootwrap.conf", ETC_CINDER),
            template.CommonTemplate(
                "receive-ca-bundle.pem",
                ETC_SSL_CERTS,
                template_name="receive-ca-bundle.pem.j2",
                conditionals=[context.ca_bundle_set],
            ),
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
        tpl: template.Template,
        context: typing.Mapping[str, typing.Mapping[str, str]],
    ) -> bool:
        """Render and atomically write one template."""
        content = self._render_template(env, tpl, context)
        return self._write_managed_file(snap, tpl, content)

    def _render_template(
        self,
        env: jinja2.Environment,
        tpl: template.Template,
        context: typing.Mapping[str, typing.Mapping[str, str]],
    ) -> bytes | None:
        """Render a template in memory without changing the filesystem."""
        if tpl.conditionals and not all(cond(context) for cond in tpl.conditionals):
            logging.debug(
                "Skipping template %s due to unmet conditionals", tpl.filename
            )
            return None

        template_file = tpl.template()
        try:
            jinja_template = env.get_template(template_file)
        except jinja2.exceptions.TemplateNotFound:
            logging.debug("Template %s not found, trying with .j2", template_file)
            jinja_template = env.get_template(template_file + ".j2")

        rendered = jinja_template.render(**context)
        if len(rendered) > 0 and rendered[-1] != "\n":
            rendered += "\n"
        return rendered.encode("utf-8")

    def _managed_file_destination(self, snap: Snap, managed_file: ManagedFile) -> Path:
        """Resolve a managed output without allowing path traversal."""
        output_path = managed_file.output_path()
        if output_path.is_absolute() or ".." in output_path.parts:
            raise ValueError(
                f"Managed file {output_path} resolves outside its destination"
            )
        location = (
            managed_file.location
            if isinstance(managed_file, template.Template)
            else "common"
        )
        return getattr(snap.paths, location) / output_path

    def _write_managed_file(
        self,
        snap: Snap,
        managed_file: ManagedFile,
        content: bytes | None,
    ) -> bool:
        """Atomically replace or remove one prepared managed file."""
        dest_file = self._managed_file_destination(snap, managed_file)
        if content is None:
            try:
                dest_file.unlink()
            except FileNotFoundError:
                return False
            return True

        try:
            existing_mode = dest_file.lstat().st_mode
            if (
                stat.S_ISREG(existing_mode)
                and stat.S_IMODE(existing_mode) == managed_file.mode
                and dest_file.read_bytes() == content
            ):
                logging.debug("File %s has not changed, skipping", dest_file)
                return False
        except FileNotFoundError:
            pass

        dest_dir = dest_file.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                dir=dest_dir,
                prefix=f".{dest_file.name}.",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                os.fchmod(temporary.fileno(), 0o600)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                os.fchmod(temporary.fileno(), managed_file.mode)
            os.replace(temporary_path, dest_file)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        logging.debug("Atomically replaced managed file %s", dest_file)
        return True

    def _backend_tls_material_content(
        self,
        backend_context: context.BaseBackendContext,
        material: context.BackendTLSMaterial,
    ) -> bytes | None:
        """Return opaque TLS bytes without exposing them to Jinja."""
        value = backend_context.backend_config.get(material.content_option)
        if isinstance(value, pydantic.SecretStr):
            value = value.get_secret_value()
        return value.encode("utf-8") if value else None

    def _process_backend_tls_material(
        self,
        snap: Snap,
        backend_context: context.BaseBackendContext,
        material: context.BackendTLSMaterial,
    ) -> bool:
        """Write one backend TLS material value without template evaluation."""
        content = self._backend_tls_material_content(backend_context, material)
        return self._write_managed_file(snap, material, content)

    def _prepare_files(
        self,
        snap: Snap,
        env: jinja2.Environment,
        render_context: typing.MutableMapping[str, typing.Any],
        backend_contexts: context.CinderBackendContexts,
    ) -> list[tuple[ManagedFile, bytes | None]]:
        """Render every desired output before allowing any filesystem change."""
        prepared: list[tuple[ManagedFile, bytes | None]] = []
        for tpl in self.template_files():
            prepared.append((tpl, self._render_template(env, tpl, render_context)))

        for backend_context in backend_contexts.contexts.values():
            render_context[context.BACKEND_CTX_KEY] = backend_context.context()
            render_context[context.CINDER_CTX_KEY] = backend_context.backend_name
            try:
                for tpl in backend_context.template_files():
                    prepared.append(
                        (tpl, self._render_template(env, tpl, render_context))
                    )
                for material in backend_context.tls_materials:
                    prepared.append(
                        (
                            material,
                            self._backend_tls_material_content(
                                backend_context, material
                            ),
                        )
                    )
            finally:
                render_context.pop(context.CINDER_CTX_KEY)
                render_context.pop(context.BACKEND_CTX_KEY)

        for managed_file, _ in prepared:
            self._managed_file_destination(snap, managed_file)
        self._validate_prepared_destinations(snap, prepared)
        return prepared

    def _validate_prepared_destinations(
        self, snap: Snap, prepared: typing.Sequence[PreparedFile]
    ) -> dict[Path, PreparedFile]:
        """Resolve each prepared output and reject ownership collisions."""
        destinations: dict[Path, PreparedFile] = {}
        for managed_file, content in prepared:
            destination = self._managed_file_destination(snap, managed_file)
            if destination in destinations:
                raise error.CinderError(f"duplicate managed destination: {destination}")
            destinations[destination] = (managed_file, content)
        return destinations

    def _write_prepared_files(
        self,
        snap: Snap,
        prepared: typing.Sequence[PreparedFile],
    ) -> list[ManagedFile]:
        """Apply prepared outputs as a rollback-capable file transaction."""
        destinations = self._validate_prepared_destinations(snap, prepared)
        temporary_paths: set[Path] = set()
        try:
            pending = self._stage_pending_files(destinations, temporary_paths)
            self._apply_pending_files(pending, temporary_paths)
            return [managed_file for managed_file, _, _, _ in pending]
        finally:
            for temporary_path in temporary_paths:
                temporary_path.unlink(missing_ok=True)

    def _stage_pending_files(
        self,
        destinations: typing.Mapping[Path, PreparedFile],
        temporary_paths: set[Path],
    ) -> list[PendingFile]:
        """Stage every changed replacement before active files are touched."""
        pending: list[PendingFile] = []
        for destination, (managed_file, content) in destinations.items():
            original = self._snapshot_active_file(destination)
            if not self._managed_file_changed(original, managed_file, content):
                continue
            staged = None
            if content is not None:
                staged = self._stage_managed_file(
                    destination, content, managed_file.mode
                )
                temporary_paths.add(staged)
            pending.append((managed_file, destination, staged, original))
        return pending

    def _apply_pending_files(
        self, pending: typing.Sequence[PendingFile], temporary_paths: set[Path]
    ) -> None:
        """Replace staged files and restore active files after a failure."""
        replacements = [item for item in pending if item[2] is not None]
        deletions = [item for item in pending if item[2] is None]
        applied: list[tuple[Path, OriginalFile]] = []
        try:
            for _, destination, staged, original in [*replacements, *deletions]:
                if staged is not None:
                    os.replace(staged, destination)
                    temporary_paths.discard(staged)
                else:
                    destination.unlink()
                applied.append((destination, original))
        except Exception:
            self._rollback_applied_files(applied, temporary_paths)
            raise

    def _rollback_applied_files(
        self,
        applied: typing.Sequence[tuple[Path, OriginalFile]],
        temporary_paths: set[Path],
    ) -> None:
        """Restore all active paths already changed by a failed transaction."""
        rollback_errors: list[OSError] = []
        for destination, original in reversed(applied):
            try:
                self._restore_original_file(destination, original, temporary_paths)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
                logging.exception("Failed to restore managed file %s", destination)
        if rollback_errors:
            raise error.CinderError(
                "Failed to roll back configuration file transaction"
            ) from rollback_errors[0]

    def _snapshot_active_file(self, destination: Path) -> OriginalFile:
        """Capture enough active state to restore a failed transaction."""
        try:
            existing_mode = destination.lstat().st_mode
        except FileNotFoundError:
            return OriginalFile("absent")
        if stat.S_ISREG(existing_mode):
            return OriginalFile(
                "regular",
                content=destination.read_bytes(),
                mode=stat.S_IMODE(existing_mode),
            )
        if stat.S_ISLNK(existing_mode):
            return OriginalFile("symlink", content=os.readlink(destination))
        raise error.CinderError(f"Unsupported active managed file type: {destination}")

    def _restore_original_file(
        self,
        destination: Path,
        original: OriginalFile,
        temporary_paths: set[Path],
    ) -> None:
        """Atomically restore one captured path after a failed transaction."""
        if original.kind == "absent":
            destination.unlink(missing_ok=True)
            return
        if original.kind == "regular":
            content = typing.cast(bytes, original.content)
            mode = typing.cast(int, original.mode)
            staged = self._stage_managed_file(destination, content, mode)
        else:
            target = typing.cast(str, original.content)
            staged = self._stage_symlink(destination, target)
        temporary_paths.add(staged)
        os.replace(staged, destination)
        temporary_paths.discard(staged)

    def _managed_file_changed(
        self,
        original: OriginalFile,
        managed_file: ManagedFile,
        content: bytes | None,
    ) -> bool:
        """Return whether a prepared output differs from active state."""
        if original.kind == "absent":
            return content is not None
        if content is None:
            return True
        return not (
            original.kind == "regular"
            and original.mode == managed_file.mode
            and original.content == content
        )

    def _stage_managed_file(self, destination: Path, content: bytes, mode: int) -> Path:
        """Write a restrictive same-directory file ready for replacement."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                os.fchmod(temporary.fileno(), 0o600)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                os.fchmod(temporary.fileno(), mode)
            return temporary_path
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def _stage_symlink(self, destination: Path, target: str) -> Path:
        """Create a same-directory symlink ready for atomic restoration."""
        descriptor, temporary_name = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.name}.symlink.",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        temporary_path.unlink()
        temporary_path.symlink_to(target)
        return temporary_path

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

    def _prepare_configuration_files(
        self,
        snap: Snap,
        backend_contexts: context.CinderBackendContexts | None = None,
    ) -> list[PreparedFile]:
        """Prepare all configuration bytes without changing the filesystem."""
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
        try:
            ctx = self.render_context(snap)
            if backend_contexts is None:
                backend_contexts = self.backend_contexts(snap)
            ctx[backend_contexts.namespace] = self._render_specific_backend_configs(
                ctx, backend_contexts.context()
            )
            return self._prepare_files(snap, env, ctx, backend_contexts)
        except Exception as e:
            logging.error("Failed to prepare configuration files", exc_info=True)
            raise error.CinderError("Failed to prepare configuration files") from e

    def _write_configuration_files(
        self, snap: Snap, prepared: typing.Sequence[PreparedFile]
    ) -> list[ManagedFile]:
        """Write prepared configuration files with a stable public error."""
        try:
            return self._write_prepared_files(snap, prepared)
        except Exception as e:
            logging.error("Failed to write configuration files", exc_info=True)
            raise error.CinderError("Failed to write configuration files") from e

    def template(self, snap: Snap) -> list[ManagedFile]:
        """Render templates for the Cinder volume service."""
        prepared = self._prepare_configuration_files(snap)
        return self._write_configuration_files(snap, prepared)

    def _existing_managed_backend_files(self, snap: Snap) -> set[Path]:
        """Return backend files within the snap's explicit ownership scope."""
        backend_config_dir = snap.paths.common / context.ETC_CINDER_D_CONF_DIR
        managed_files = set(backend_config_dir.glob("*.conf"))
        for cleanup_path in context.backend_tls_material_cleanup_paths():
            cleanup_dir = snap.paths.common / cleanup_path.parent
            managed_files.update(cleanup_dir.glob(cleanup_path.name))
        return managed_files

    def _desired_managed_backend_files(
        self,
        snap: Snap,
        backend_contexts: context.CinderBackendContexts,
    ) -> set[Path]:
        """Return managed backend paths desired by validated configuration."""
        backend_config_dir = snap.paths.common / context.ETC_CINDER_D_CONF_DIR
        desired_files: set[Path] = set()
        for backend_context in backend_contexts.contexts.values():
            for tpl in backend_context.template_files():
                output = self._managed_file_destination(snap, tpl)
                if output.parent == backend_config_dir and output.suffix == ".conf":
                    desired_files.add(output)
            for material in backend_context.tls_materials:
                if material.cleanup and self._backend_tls_material_content(
                    backend_context, material
                ):
                    desired_files.add(self._managed_file_destination(snap, material))
        return desired_files

    def _remove_backend_files(self, managed_files: typing.Iterable[Path]) -> list[Path]:
        """Remove known backend files without expanding their ownership scope."""
        removed: list[Path] = []
        failures: list[tuple[Path, OSError]] = []
        for managed_file in managed_files:
            try:
                logging.debug("Removing managed backend file: %s", managed_file)
                managed_file.unlink()
                removed.append(managed_file)
            except FileNotFoundError:
                continue
            except OSError as e:
                logging.error(
                    "Failed to remove managed backend file %s: %s", managed_file, e
                )
                failures.append((managed_file, e))
        if failures:
            failed_paths = ", ".join(str(path) for path, _ in failures)
            raise error.CinderError(
                f"Failed to remove managed backend files: {failed_paths}"
            ) from failures[0][1]
        return removed

    def _prune_stale_backend_configs(
        self,
        snap: Snap,
        backend_contexts: context.CinderBackendContexts,
    ) -> list[Path]:
        """Remove owned backend files absent from successful configuration."""
        existing_files = self._existing_managed_backend_files(snap)
        desired_files = self._desired_managed_backend_files(snap, backend_contexts)
        removed = self._remove_backend_files(existing_files - desired_files)
        return [path.relative_to(snap.paths.common) for path in removed]


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

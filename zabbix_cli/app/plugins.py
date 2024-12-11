from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING
from typing import Protocol
from typing import cast
from typing import runtime_checkable

if sys.version_info < (3, 10):
    from importlib_metadata import EntryPoint
else:
    from importlib.metadata import EntryPoint


from zabbix_cli.exceptions import PluginLoadError
from zabbix_cli.exceptions import PluginPostImportError
from zabbix_cli.output.console import error

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config
    from zabbix_cli.config.model import PluginConfig


logger = logging.getLogger(__name__)


@runtime_checkable
class PluginModule(Protocol):
    def __configure__(self, config: PluginConfig) -> None: ...


class PluginLoader:
    def __init__(self) -> None:
        self.plugins: dict[str, ModuleType] = {}

    def load(self, config: Config) -> None:
        self._load_plugins(config)
        self._load_plugins_from_metadata(config)

    def _load_plugins(self, config: Config) -> None:
        """Load plugins from local Python modules."""
        logger.debug("Loading plugins from modules in configuration file.")
        for name, plugin_config in config.plugins.root.items():
            if not plugin_config.module:
                logger.debug("Plugin %s has no module defined. Skipping", name)
                continue
            if not plugin_config.enabled:
                logger.debug("Plugin %s is disabled, skipping", name)
                continue

            logger.debug("Loading plugin: %s", name)
            try:
                module = load_plugin_module(name, plugin_config)
            except Exception as e:
                # If the exception is already a PluginLoadError
                # or a subclass, use that, otherwise create a new
                # PluginLoadError so we get the correct message format.
                if not isinstance(e, PluginLoadError):
                    exc = PluginLoadError(name, plugin_config)
                else:
                    exc = e
                if not plugin_config.optional:
                    raise exc from e
                else:
                    # Use message created by the PluginLoadError
                    msg = exc.args[0] if exc.args else str(exc)
                    error(msg, exc_info=True)
            else:
                self._add_plugin(name, module)

    def _load_plugins_from_metadata(self, config: Config) -> None:
        """Load plugins from Python package entry points."""
        # Use backport for Python < 3.10
        if sys.version_info < (3, 10):
            from importlib_metadata import (
                entry_points,  # pyright: ignore[reportUnknownVariableType]
            )
        else:
            from importlib.metadata import entry_points

        discovered_plugins = entry_points(group="zabbix-cli.plugins")

        # HACK: Cast Tuple[Any, ...] result to concrete type.
        # In order to pass type checking on all Python versions,
        # we need to pretend that we are developing on 3.9 and
        # using the backport. The problem is that the backport
        # does not define a generic tuple type for the result,
        # and instead just subclasses tuple. So we need to cast
        # the result to the correct type.
        # This is one of the drawbacks of running in 3.9 mode, but
        # it's necessary to ensure we don't introduce features that
        # do not exist in our minimum supported version.
        discovered_plugins = cast(tuple[EntryPoint], discovered_plugins)
        for plugin in discovered_plugins:
            conf = config.plugins.get(plugin.name)
            try:
                module = load_plugin_from_entry_point(plugin)
            except Exception as e:
                # By default, broken plugings will not break the application
                # unless they are explicitly marked as required in the config.
                # This is a deviation from the standard behavior of plugins, but
                # since these are third party plugins, we want to be more lenient
                # and not break the entire application if a plugin is broken.
                if not conf or not conf.optional:
                    raise PluginLoadError(plugin.name, conf) from e
                else:
                    error(f"Error loading plugin {plugin.name}: {e}", exc_info=True)
            else:
                self._add_plugin(plugin.name, module)

    def _add_plugin(self, name: str, module: ModuleType) -> None:
        self.plugins[name] = module
        logger.info("Plugin loaded: %s", name)

    def configure_plugins(self, config: Config) -> None:
        for name, module in self.plugins.items():
            if not isinstance(module, PluginModule):
                logger.debug("Plugin %s has no __configure__ function. Skipping", name)
                continue
            plugin_config = config.plugins.root.get(name)
            if not plugin_config:
                logger.warning(
                    "No configuration found for plugin '%s'. Cannot run __configure__",
                    name,
                )
                continue
            try:
                module.__configure__(plugin_config)
            except Exception as e:
                raise PluginPostImportError(name, plugin_config) from e


def load_plugin_module(plugin_name: str, plugin_config: PluginConfig) -> ModuleType:
    """Load plugin from a Python module."""
    name_or_path = plugin_config.module
    p = Path(name_or_path)
    if p.exists():
        logger.debug("Loading plugin %s from file: %s", plugin_name, p)
        mod = _load_module_from_file(name_or_path, p)
    else:
        logger.debug("Importing plugin %s as module '%s'", plugin_name, name_or_path)
        mod = _load_module(name_or_path)
    return mod


def _load_module_from_file(mod: str, file: Path) -> ModuleType:
    """Load a module from a file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(mod, str(file.resolve()))
    if not spec or not spec.loader:
        raise ImportError(f"Could not load module from file: {file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod] = module
    spec.loader.exec_module(module)
    logger.info("Loaded module from file: %s", file)
    return module


def _load_module(mod: str) -> ModuleType:
    """Load a module."""
    import importlib

    module = importlib.import_module(mod)
    logger.info("Loaded module: %s", mod)
    return module


def load_plugin_from_entry_point(entry_point: EntryPoint) -> ModuleType:
    """Load a plugin from an entry point."""
    logger.debug("Loading plugin %s from metadata", entry_point.name)
    module = entry_point.load()
    if not isinstance(module, ModuleType):
        return sys.modules[entry_point.module]
    return module

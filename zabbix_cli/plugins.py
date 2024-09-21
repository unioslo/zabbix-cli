from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Dict
from typing import Protocol
from typing import runtime_checkable

from zabbix_cli.exceptions import PluginLoadError
from zabbix_cli.exceptions import PluginPostImportError
from zabbix_cli.output.console import error

if TYPE_CHECKING:
    from types import ModuleType

    from zabbix_cli.config.model import Config
    from zabbix_cli.config.model import PluginConfig


logger = logging.getLogger(__name__)


@runtime_checkable
class PluginModule(Protocol):
    def __post_import__(self, config: PluginConfig) -> None: ...


def load_plugins(config: Config) -> None:
    """Load plugins."""
    from zabbix_cli.app import app

    logger.debug("Loading plugins")
    for name, plugin_config in config.plugins.root.items():
        logger.debug("Loading command plugin: %s", name)
        if not plugin_config.enabled:
            logger.debug("Plugin %s is disabled, skipping", name)
            continue
        try:
            module = do_load_plugin_module(name, plugin_config)
        except Exception as e:
            # If the exception is already a PluginLoadError
            # or a subclass, use that, otherwise create a new
            # PluginLoadError so we get the correct message format.
            if not isinstance(e, PluginLoadError):
                exc = PluginLoadError(name, plugin_config)
            else:
                exc = e
            if plugin_config.strict:
                raise exc from e
            else:
                # Use message created by the PluginLoadError
                msg = exc.args[0] if exc.args else str(exc)
                error(msg, exc_info=True)
        else:
            app.add_plugin(name, module)
            logger.info("Command plugin loaded: %s", name)


def do_load_plugin_module(plugin_name: str, plugin_config: PluginConfig) -> ModuleType:
    """Load a command module plugin."""
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


# TODO: refactor? Does it make sense that we pass an internal data struture
# from StatefulApp to this function? Should this be a method on StatefulApp?
def run_plugins_post_import(plugins: Dict[str, ModuleType], config: Config) -> None:
    for name, module in plugins.items():
        if not isinstance(module, PluginModule):
            logger.debug("Plugin %s has no __post_import__ function. Skipping", name)
            continue
        plugin_config = config.plugins.root.get(name)
        if not plugin_config:
            logger.warning(
                "No configuration found for plugin %s. Cannot run __post_import__",
                name,
            )
            continue
        try:
            module.__post_import__(plugin_config)
        except Exception as e:
            raise PluginPostImportError(name, plugin_config) from e

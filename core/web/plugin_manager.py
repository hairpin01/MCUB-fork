import importlib
import pkgutil
import logging
from pathlib import Path
from aiohttp import web
import aiohttp_jinja2
import jinja2

logger = logging.getLogger("web.plugin_manager")


class PluginManager:
    """
    Manages loading and initialization of web panel plugins.
    Plugins are located in the 'plugins' directory relative to this module.
    Each plugin must be a package with a `setup` function that takes the app and kernel.
    """

    def __init__(self, app: web.Application, kernel):
        self.app = app
        self.kernel = kernel
        self.plugins = []
        self.plugins_dir = Path(__file__).parent / "plugins"

    def load_plugins(self):
        """Discover and load all plugins from the plugins directory."""
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return

        # Iterate over packages in plugins directory
        for finder, name, ispkg in pkgutil.iter_modules([str(self.plugins_dir)]):
            if not ispkg:
                continue  # only packages are considered plugins

            try:
                self._load_plugin(name)
            except Exception as e:
                logger.error(f"Failed to load plugin '{name}': {e}")

    def _load_plugin(self, name: str):
        """Load a single plugin by name."""
        module_path = f"core.web.plugins.{name}"
        try:
            plugin_module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Import error for plugin '{name}': {e}")
            return

        # Plugin must have a setup function
        if not hasattr(plugin_module, "setup"):
            logger.warning(f"Plugin '{name}' has no setup() function, skipping.")
            return

        # Call setup with app and kernel
        plugin_module.setup(self.app, self.kernel)

        # Optionally, plugin can define its own template loader
        self._setup_plugin_templates(name)

        self.plugins.append(name)
        logger.info(f"Loaded plugin: {name}")

    def _setup_plugin_templates(self, plugin_name: str):
        """
        If the plugin has a 'templates' folder, add it to Jinja2 loader.
        This allows plugins to override or extend templates.
        """
        plugin_templates_dir = self.plugins_dir / plugin_name / "templates"
        if plugin_templates_dir.exists():
            # Get current loader (likely FileSystemLoader)
            current_loader = self.app["aiohttp_jinja2_environment"].loader
            if isinstance(current_loader, jinja2.FileSystemLoader):
                # Combine search paths: plugin templates first, then main
                new_loader = jinja2.FileSystemLoader(
                    [str(plugin_templates_dir)] + current_loader.searchpath
                )
                self.app["aiohttp_jinja2_environment"].loader = new_loader
            else:
                # Fallback: just use plugin templates
                self.app["aiohttp_jinja2_environment"].loader = jinja2.FileSystemLoader(
                    str(plugin_templates_dir)
                )

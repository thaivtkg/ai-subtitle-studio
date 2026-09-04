import ast
import importlib
import pkgutil
import unittest
from pathlib import Path
from typing import Protocol


class TestTutorialArchitectureGuards(unittest.TestCase):
    def setUp(self):
        import core.tutorial

        self.core_package = core.tutorial

    def test_core_tutorial_has_no_ui_dependencies(self):
        forbidden_modules = ("PySide6.QtWidgets", "PySide6.QtGui", "ui")
        package_dir = Path(self.core_package.__file__).parent

        for module_info in pkgutil.walk_packages(
            self.core_package.__path__, self.core_package.__name__ + "."
        ):
            module_name = module_info.name
            relative = Path(*module_name.split(".")[2:]).with_suffix(".py")
            source_path = package_dir / relative
            tree = ast.parse(source_path.read_text(encoding="utf-8"), str(source_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [
                        f"{node.module}.{alias.name}" if node.module == "PySide6" else node.module or ""
                        for alias in node.names
                    ]
                else:
                    continue
                for name in imported:
                    self.assertFalse(
                        name == "ui" or name.startswith("ui."),
                        f"Architecture violation: {module_name} imports UI layer {name!r}",
                    )
                    self.assertNotIn(
                        name,
                        forbidden_modules[:2],
                        f"Architecture violation: {module_name} imports {name!r}",
                    )

    def test_core_ports_are_protocols_only(self):
        import core.tutorial.ports as ports

        core_ports = (
            ports.NavigationPort,
            ports.AnchorRegistryPort,
            ports.InteractionObserverPort,
            ports.SpotlightPort,
            ports.DialogObserverPort,
            ports.ProgressStorePort,
        )
        for port in core_ports:
            self.assertTrue(issubclass(port, Protocol), f"{port.__name__} must be a Protocol")

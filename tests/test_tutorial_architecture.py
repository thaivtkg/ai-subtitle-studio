import ast
import os
import unittest
from pathlib import Path
from typing import Protocol


class TestTutorialArchitectureGuards(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.core_tutorial_dir = self.project_root / "core" / "tutorial"
        self.tests_dir = self.project_root / "tests"

    def test_core_tutorial_has_no_forbidden_dependencies(self):
        forbidden_imports = {
            "PySide6.QtWidgets", "PySide6.QtGui", "core.services.project_service",
            "workers", "core.media_import", "core.subtitle_generation", "ui",
        }
        violations = []
        for root, _, files in os.walk(self.core_tutorial_dir):
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                file_path = Path(root) / filename
                tree = ast.parse(file_path.read_text(encoding="utf-8"), str(file_path))
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
                        if any(name == forbidden or name.startswith(forbidden + ".")
                               for forbidden in forbidden_imports):
                            violations.append(f"{file_path.name} imports '{name}'")
        self.assertEqual(violations, [], "Architecture Violations found:\n" + "\n".join(violations))

    def test_core_ports_are_protocols_only(self):
        import core.tutorial.ports as ports

        core_ports = (
            ports.NavigationPort, ports.AnchorRegistryPort,
            ports.InteractionObserverPort, ports.SpotlightPort,
            ports.DialogObserverPort, ports.ProgressStorePort,
        )
        for port in core_ports:
            self.assertTrue(issubclass(port, Protocol), f"{port.__name__} must be a Protocol")

    def test_acceptance_id_presence_audit(self):
        required_tcs = {
            "TC132", "TC133", "TC134", "TC135", "TC136", "TC137", "TC138",
            "TC145", "TC146", "TC147", "TC152", "TC153", "TC154", "TC155",
            "TC156", "TC157", "TC166", "TC167", "TC168", "TC169", "TC170",
            "TC171", "TC172", "TC173",
        }
        found_tcs = set()
        for root, _, files in os.walk(self.tests_dir):
            for filename in files:
                if not filename.startswith("test_") or not filename.endswith(".py"):
                    continue
                if filename == Path(__file__).name:
                    continue
                content = (Path(root) / filename).read_text(encoding="utf-8")
                normalized = content.upper()
                found_tcs.update(tc for tc in required_tcs if tc in normalized)
        self.assertEqual(required_tcs - found_tcs, set(),
                         f"Missing Acceptance IDs in tests: {required_tcs - found_tcs}")

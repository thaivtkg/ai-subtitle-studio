import ast
import importlib.util
import os
import unittest
from pathlib import Path
from typing import Protocol


class TestTutorialArchitectureGuards(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.core_tutorial_dir = self.project_root / "core" / "tutorial"
        self.tests_dir = self.project_root / "tests"
        self.forbidden_imports = {
            "PySide6.QtWidgets", "PySide6.QtGui", "core.services.project_service",
            "workers", "core.media_import", "core.subtitle_generation", "ui",
        }

    def _check_source_code_for_violations(
        self, source_code: str, file_name: str, package: str = "core.tutorial"
    ) -> list[str]:
        try:
            tree = ast.parse(source_code, file_name)
        except SyntaxError as error:
            return [f"{file_name} has syntax error: {error.msg}"]

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    relative_base = "." * node.level + base
                    imported = [
                        importlib.util.resolve_name(
                            f"{relative_base}.{alias.name}" if base else relative_base + alias.name,
                            package,
                        )
                        for alias in node.names
                    ]
                else:
                    imported = ([base] if base else []) + [
                        f"{base}.{alias.name}" if base else alias.name
                        for alias in node.names
                    ]
            else:
                continue
            for path in imported:
                if any(path == forbidden or path.startswith(forbidden + ".")
                       for forbidden in self.forbidden_imports):
                    violations.append(f"{file_name} imports '{path}'")
        return violations

    def test_architecture_guard_catches_importfrom_bypasses(self):
        snippets = {
            "from core.services import project_service": "core.services.project_service",
            "from core import media_import": "core.media_import",
            "from core import subtitle_generation, unrelated": "core.subtitle_generation",
            "from PySide6.QtWidgets import QPushButton": "PySide6.QtWidgets",
            "import workers.foo": "workers.foo",
        }
        for source, expected in snippets.items():
            violations = self._check_source_code_for_violations(source, "dummy.py")
            self.assertTrue(
                any(expected in violation for violation in violations),
                f"Guard failed to catch '{expected}' in snippet: {source}",
            )

        relative_snippets = {
            "from .. import media_import": "core.media_import",
            "from ..services import project_service": "core.services.project_service",
        }
        for source, expected in relative_snippets.items():
            violations = self._check_source_code_for_violations(
                source, "dummy.py", "core.tutorial"
            )
            self.assertTrue(
                any(expected in violation for violation in violations),
                f"Guard failed to catch '{expected}' in snippet: {source}",
            )

    def test_core_tutorial_has_no_forbidden_dependencies(self):
        violations = []
        for root, _, files in os.walk(self.core_tutorial_dir):
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                file_path = Path(root) / filename
                relative = file_path.relative_to(self.project_root).with_suffix("")
                parts = relative.parts
                package = ".".join(parts[:-1])
                violations.extend(self._check_source_code_for_violations(
                    file_path.read_text(encoding="utf-8"), file_path.name, package
                ))
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

import sys
import pytest
from PySide6.QtWidgets import QApplication

# Ensure a global QApplication is instantiated once before any test runs,
# preventing non-GUI QCoreApplication from conflicting with GUI widget tests.
_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)

@pytest.fixture(scope="session", autouse=True)
def qapp():
    return _app

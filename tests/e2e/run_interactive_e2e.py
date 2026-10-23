#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interactive E2E Test Runner for AI Subtitle Studio.
Launches the UI directly on screen with visual slow-mo and step diagnostics.

Usage:
    .venv\\Scripts\\python.exe tests/e2e/run_interactive_e2e.py
"""
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure console supports UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pytest


def main():
    os.environ["E2E_INTERACTIVE"] = "1"
    args = ["-o", f"pythonpath={PROJECT_ROOT}", "tests/e2e/", "-v", "-s"] + sys.argv[1:]
    print("=" * 80)
    print(">> Khoi chay Bo Kiem Thu Truc Quan (Interactive UI) - AI Subtitle Studio")
    print("   Che do: E2E_INTERACTIVE=1 (Slow-Mo 300ms, Window Title Updates)")
    print("=" * 80)
    exit_code = pytest.main(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

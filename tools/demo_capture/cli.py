import argparse
import sys

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError


def main(args=None):
    if getattr(sys, "frozen", False):
        print("Error: Demo capture is a developer tool and cannot run in a frozen build.")
        return 4

    parser = argparse.ArgumentParser(prog="python -m tools.demo_capture")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("validate")
    generate = subparsers.add_parser("generate")
    target = generate.add_mutually_exclusive_group(required=True)
    target.add_argument("scenario_id", nargs="?", default=None)
    target.add_argument("--all", action="store_true")
    generate.add_argument("--mode", choices=["isolated", "real"], default="isolated")

    parsed = parser.parse_args(args)
    if parsed.command == "list":
        print("Listing scenarios...")
        return 0
    if parsed.command == "validate":
        print("Validating assets...")
        return 0
    if parsed.all and parsed.mode == "real":
        print("Error: REAL_APP mode is forbidden for --all batch generation.")
        return 2
    try:
        return _do_generate(parsed)
    except CaptureRunError as error:
        print(f"Error: {error.error_code} - {error.message}")
        if error.error_code == CaptureErrorCode.OUTPUT_VALIDATION_FAILED:
            return 3
        if error.error_code in (
            CaptureErrorCode.REAL_APP_ENVIRONMENT_UNAVAILABLE,
            CaptureErrorCode.REAL_APP_OWNERSHIP_FAILED,
        ):
            return 4
        return 1
    except Exception as error:
        print(f"Unknown error: {error}")
        return 1


def _do_generate(parsed):
    raise CaptureRunError(CaptureErrorCode.TARGET_NOT_FOUND, "Not implemented in placeholder")

import os
import sys
import subprocess

def main():
    print("=" * 60)
    print("GENERATION SYSTEM AUTO UAT")
    print("=" * 60)
    print()

    # Run pytest and capture output
    args = [sys.executable, "-m", "pytest", "tests/uat", "-v", "--tb=short"]
    result = subprocess.run(args, capture_output=True, text=True)

    passed = 0
    failed = 0
    errors = 0
    
    # Analyze the output lines for PASSED and FAILED
    lines = result.stdout.split('\n')
    for line in lines:
        if "PASSED" in line and "test_" in line:
            test_name = line.split("::")[-1].split()[0]
            print(f"[PASS] {test_name}")
            passed += 1
        elif "FAILED" in line and "test_" in line:
            test_name = line.split("::")[-1].split()[0]
            print(f"[FAIL] {test_name}")
            failed += 1
        elif "ERROR" in line and "test_" in line:
            test_name = line.split("::")[-1].split()[0]
            print(f"[ERROR] {test_name}")
            errors += 1

    print()
    print("=" * 60)
    print(f"RESULT: {passed} PASSED / {failed} FAILED / {errors} ERRORS")
    
    if failed == 0 and errors == 0 and passed > 0:
        print("STATUS: UAT PASS")
        print("=" * 60)
        sys.exit(0)
    else:
        print("STATUS: UAT BLOCKED")
        print("=" * 60)
        # Print failure details
        print("\nFailure Details:")
        print(result.stdout)
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validation script for error fixes.

Runs all tests related to the error fixes and generates a report.
"""

import os
import subprocess
import sys

# Fix Unicode encoding for Windows CMD
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_result(test_name, success, details=""):
    """Print test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")


def run_command(cmd, description):
    """Run command and return success status."""
    print(f"\nRunning: {description}")
    print(f"Command: {cmd}")

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0:
            print("✅ SUCCESS")
            return True, result.stdout
        else:
            print("❌ FAILED")
            print(f"Error output:\n{result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT (>120s)")
        return False, "Command timeout"
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False, str(e)


def main():
    """Run all validation checks."""
    print_header("ERROR FIXES VALIDATION SCRIPT")

    results = {}

    # Change to project directory
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)

    # Test 1: Run similar_issues validation tests
    print_header("TEST 1: Similar Issues Validation Tests")
    success, output = run_command(
        "python manage.py test apps.ai_assistant.tests.test_similar_issues_validation --verbosity=2",  # noqa: E501
        "Parameter validation tests",
    )
    results["validation_tests"] = success

    if success and "OK" in output:
        # Count tests
        import re

        match = re.search(r"Ran (\d+) tests", output)
        if match:
            test_count = match.group(1)
            print_result("All validation tests", True, f"{test_count} tests passed")

    # Test 2: Check for syntax errors
    print_header("TEST 2: Python Syntax Check")
    success, output = run_command(
        "python -m py_compile apps/ai_assistant/viewsets.py", "Syntax check viewsets.py"
    )
    results["syntax_viewsets"] = success
    print_result("viewsets.py syntax", success)

    success, output = run_command(
        "python -m py_compile apps/ai_assistant/services/rag_service.py",
        "Syntax check rag_service.py",
    )
    results["syntax_rag_service"] = success
    print_result("rag_service.py syntax", success)

    # Test 3: Import checks
    print_header("TEST 3: Import Validation")
    success, output = run_command(
        "python -c \"from apps.ai_assistant.viewsets import AIAssistantViewSet; print('OK')\"",  # noqa: E501
        "Import AIAssistantViewSet",
    )
    results["import_viewset"] = success
    print_result("ViewSet imports", success)

    success, output = run_command(
        "python -c \"from apps.ai_assistant.services import RAGService; print('OK')\"",
        "Import RAGService",
    )
    results["import_service"] = success
    print_result("Service imports", success)

    # Test 4: Check test file
    print_header("TEST 4: Test File Check")
    test_file = "apps/ai_assistant/tests/test_similar_issues_validation.py"
    if os.path.exists(test_file):
        print_result("Test file exists", True, test_file)
        results["test_file_exists"] = True

        # Count test methods
        with open(test_file, "r") as f:
            content = f.read()
            test_count = content.count("def test_")
            print_result("Test methods found", True, f"{test_count} test methods")
    else:
        print_result("Test file exists", False, f"File not found: {test_file}")
        results["test_file_exists"] = False

    # Test 5: Documentation check
    print_header("TEST 5: Documentation Check")
    doc_file = "ERROR_FIXES_REPORT.md"
    if os.path.exists(doc_file):
        print_result("Documentation exists", True, doc_file)
        results["documentation"] = True

        with open(doc_file, "r", encoding="utf-8") as f:
            content = f.read()
            if "ERROR #1" in content and "ERROR #2" in content:
                print_result("Documentation complete", True, "All errors documented")
            else:
                print_result(
                    "Documentation complete", False, "Missing error documentation"
                )  # noqa: E501
    else:
        print_result("Documentation exists", False, f"File not found: {doc_file}")
        results["documentation"] = False

    # Summary
    print_header("VALIDATION SUMMARY")

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print(f"\n  Total Checks: {total}")
    print(f"  Passed:       {passed} ✅")
    print(f"  Failed:       {failed} {'❌' if failed > 0 else ''}")

    if failed == 0:
        print("\n  🎉 ALL VALIDATIONS PASSED!")
        print("  Code is ready for deployment.")
        print("\n  Next steps:")
        print("    1. Review ERROR_FIXES_REPORT.md")
        print("    2. Run: docker-compose restart web_wsgi web_asgi")
        print("    3. Monitor logs: tail -f logs/django.log")
        print("    4. Test endpoints in Swagger UI")
    else:
        print("\n  ⚠️  SOME VALIDATIONS FAILED")
        print("  Review the errors above and fix before deploying.")

        print("\n  Failed checks:")
        for check, success in results.items():
            if not success:
                print(f"    - {check}")

    print("\n" + "=" * 70 + "\n")

    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

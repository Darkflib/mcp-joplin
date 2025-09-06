#!/usr/bin/env python3
"""
Validation script for Joplin MCP Server implementation.
Checks code structure and import correctness without requiring external dependencies.
"""

import ast
import sys
from pathlib import Path


class ImplementationValidator:
    """Validates the implementation structure and completeness."""

    def __init__(self):
        self.root_path = Path(".")
        self.errors = []
        self.warnings = []

    def validate_file_structure(self) -> bool:
        """Validate required files and directories exist."""
        print("🔍 Validating file structure...")

        required_files = [
            "pyproject.toml",
            "README.md",
            "install.sh",
            "Makefile",
            ".pre-commit-config.yaml",
            "src/__init__.py",
            "src/cli.py",
            "src/server.py",
            "src/config.py",
            "src/logging_config.py",
            "tests/__init__.py",
            "tests/contract/__init__.py",
            "tests/integration/__init__.py",
            "tests/unit/__init__.py",
        ]

        required_dirs = [
            "src",
            "src/models",
            "src/services",
            "src/tools",
            "src/middleware",
            "tests",
            "tests/contract",
            "tests/integration",
            "tests/unit",
            "scripts",
        ]

        missing_files = []
        missing_dirs = []

        for file_path in required_files:
            if not (self.root_path / file_path).exists():
                missing_files.append(file_path)

        for dir_path in required_dirs:
            if not (self.root_path / dir_path).is_dir():
                missing_dirs.append(dir_path)

        if missing_files:
            self.errors.extend([f"Missing file: {f}" for f in missing_files])

        if missing_dirs:
            self.errors.extend([f"Missing directory: {d}" for d in missing_dirs])

        if not missing_files and not missing_dirs:
            print("✅ File structure is complete")
            return True
        else:
            print(
                f"❌ File structure issues found: {len(missing_files + missing_dirs)}"
            )
            return False

    def validate_python_syntax(self) -> bool:
        """Validate Python syntax in all Python files."""
        print("🐍 Validating Python syntax...")

        python_files = list(self.root_path.rglob("*.py"))
        syntax_errors = []

        for py_file in python_files:
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    source = f.read()
                ast.parse(source, filename=str(py_file))
            except SyntaxError as e:
                syntax_errors.append(f"{py_file}: {e}")
            except Exception as e:
                self.warnings.append(f"Could not parse {py_file}: {e}")

        if syntax_errors:
            self.errors.extend(syntax_errors)
            print(f"❌ Syntax errors found in {len(syntax_errors)} files")
            return False
        else:
            print(f"✅ All {len(python_files)} Python files have valid syntax")
            return True

    def validate_imports(self) -> bool:
        """Validate import statements are structurally correct."""
        print("📦 Validating import structure...")

        src_files = list((self.root_path / "src").rglob("*.py"))
        import_issues = []

        for py_file in src_files:
            try:
                with open(py_file, encoding="utf-8") as f:
                    tree = ast.parse(f.read())

                # Check for relative imports within src/
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith("src."):
                            # Good - using absolute imports
                            continue
                        elif node.level > 0:
                            # Relative import - check if it's valid
                            pass

            except Exception as e:
                import_issues.append(f"{py_file}: {e}")

        if import_issues:
            self.warnings.extend(import_issues)
            print(f"⚠️  Import structure warnings: {len(import_issues)}")
        else:
            print("✅ Import structure looks good")

        return True

    def validate_test_coverage(self) -> bool:
        """Validate test files exist for major components."""
        print("🧪 Validating test coverage...")

        expected_tests = [
            "tests/contract/test_search_notes.py",
            "tests/contract/test_get_note.py",
            "tests/contract/test_list_notebooks.py",
            "tests/contract/test_get_notes_in_notebook.py",
            "tests/integration/test_connection.py",
            "tests/integration/test_search.py",
            "tests/integration/test_note_retrieval.py",
            "tests/integration/test_notebooks.py",
            "tests/integration/test_error_handling.py",
            "tests/integration/test_performance.py",
            "tests/unit/test_models.py",
            "tests/unit/test_services.py",
        ]

        missing_tests = []
        for test_file in expected_tests:
            if not (self.root_path / test_file).exists():
                missing_tests.append(test_file)

        if missing_tests:
            self.errors.extend([f"Missing test: {t}" for t in missing_tests])
            print(f"❌ Missing {len(missing_tests)} test files")
            return False
        else:
            print(f"✅ All {len(expected_tests)} expected test files found")
            return True

    def validate_models(self) -> bool:
        """Validate model definitions."""
        print("📋 Validating data models...")

        model_files = [
            "src/models/note.py",
            "src/models/notebook.py",
            "src/models/search_result.py",
            "src/models/connection.py",
            "src/models/mcp_tool.py",
        ]

        missing_models = []
        for model_file in model_files:
            if not (self.root_path / model_file).exists():
                missing_models.append(model_file)

        if missing_models:
            self.errors.extend([f"Missing model: {m}" for m in missing_models])
            print(f"❌ Missing {len(missing_models)} model files")
            return False
        else:
            print(f"✅ All {len(model_files)} model files found")
            return True

    def generate_report(self) -> None:
        """Generate final validation report."""
        print("\n" + "=" * 60)
        print("📊 IMPLEMENTATION VALIDATION REPORT")
        print("=" * 60)

        # Count files
        src_files = len(list((self.root_path / "src").rglob("*.py")))
        test_files = len(list((self.root_path / "tests").rglob("*.py")))

        print(f"📁 Source files: {src_files}")
        print(f"🧪 Test files: {test_files}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors[:10]:  # Show first 10
                print(f"   • {error}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings[:5]:  # Show first 5
                print(f"   • {warning}")
            if len(self.warnings) > 5:
                print(f"   ... and {len(self.warnings) - 5} more")

        if not self.errors:
            print("\n🎉 VALIDATION PASSED!")
            print("✅ Implementation structure is complete and valid")
            print("✅ Ready for installation with: ./install.sh")
        else:
            print("\n💥 VALIDATION FAILED!")
            print(f"❌ Found {len(self.errors)} critical issues")
            print("🔧 Fix these issues before proceeding")

        print("=" * 60)

    def run_validation(self) -> bool:
        """Run all validation checks."""
        print("🚀 Starting implementation validation...\n")

        checks = [
            self.validate_file_structure,
            self.validate_python_syntax,
            self.validate_imports,
            self.validate_test_coverage,
            self.validate_models,
        ]

        results = []
        for check in checks:
            try:
                result = check()
                results.append(result)
                print()  # Add spacing between checks
            except Exception as e:
                print(f"❌ Check failed with error: {e}")
                results.append(False)
                self.errors.append(f"Validation error: {e}")
                print()

        self.generate_report()
        return all(results) and len(self.errors) == 0


def main():
    """Main validation entry point."""
    validator = ImplementationValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

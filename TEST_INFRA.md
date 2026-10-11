# Test infrastructure

Tests use Python `unittest` discovery, synthetic fixtures, and explicit mock-mode providers where a live model is not needed. The GitHub Actions matrix targets Python 3.10 and 3.11.

The workflow checks Ruff lint/format, `compileall`, mypy, unit and safety contracts, end-to-end scenarios, and a headless Streamlit health endpoint. These checks demonstrate software behavior on their test inputs only. They do not establish live model accuracy, GPU performance, agronomic correctness, or field safety.

The core safety contract is tested in `tests/test_spray_export_safety.py`: only zones built from workflow-approved mask artifacts may be exported; raw detector boxes are not an export source; suppressed maps produce no spray features.

Run commands from `TEST_READY.md`. Record actual command outputs and Python versions when reporting a pass.

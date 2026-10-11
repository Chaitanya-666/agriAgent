# Release checklist

Do not mark a release complete until each applicable item has evidence attached.

- [ ] `python -m compileall src/ app/ tests/` passes.
- [ ] `ruff check .` passes.
- [ ] `ruff format --check .` passes.
- [ ] `mypy --config-file pyproject.toml src/` passes without broad error-category suppression.
- [ ] `PYTHONPATH=. python -m unittest discover tests -v` passes.
- [ ] `PYTHONPATH=. python tests/e2e/runner.py --all` passes.
- [ ] CI passes on Python 3.10 and 3.11, including the Streamlit health check.
- [ ] Spray-export regression tests prove crop labels and raw unapproved boxes cannot create features; unsafe infestation emits none.
- [ ] Mock and live model results are clearly separated.
- [ ] Local Clef and Qwen runtime and model revisions are recorded if live behavior is claimed.
- [ ] Groq live behavior is recorded only when actually run with an authorized key.
- [ ] Documentation states current limitations and does not call the prototype field-ready.
- [ ] No weights, credentials, or `.env` contents are committed.

Open items and owners are tracked in `cleanup_execution_sprint.md`.

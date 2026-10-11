# Test and verification status

Do not record a pass until the command has completed and its result has been reviewed. CI is intended to exercise formatting, lint, syntax, typing, unit/contract behavior, synthetic end-to-end paths, and Streamlit startup.

```bash
python -m compileall src/ app/ tests/
ruff check .
ruff format --check .
mypy --config-file pyproject.toml src/
PYTHONPATH=. python -m unittest discover tests -v
PYTHONPATH=. python tests/e2e/runner.py --all
```

The Streamlit health check is in `.github/workflows/ci.yml`. Test results from mock mode do not verify live Clef, Qwen, Groq, Grounding DINO, SAM 2, GPU execution, or field safety.

For release evidence requirements, see `docs/release_checklist.md`.

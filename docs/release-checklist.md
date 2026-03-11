# Release Checklist

This checklist is for cutting a public NeepWords release on GitHub and, if needed, publishing to PyPI.

## Before Tagging

- Confirm `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` are up to date
- Confirm package metadata in `pyproject.toml` is correct
- Confirm the version number in `pyproject.toml`
- Review open issues and PRs that should block the release
- Check that no copyrighted PDFs, scanned images, or extracted lexicon data were accidentally added

## Local Validation

- Run `uv sync --group dev`
- Run `uv run pytest -q`
- Run `uvx ruff check src tests`
- Run `uv build`
- Run `uv run neepwords --help`

If the release changes OCR behavior on macOS:

- Run `uv sync --group dev --extra macos`
- Test a real local extraction with a legally obtained PDF
- Verify spellcheck behavior and rejected-word output

## Documentation Check

- Update README examples if commands or defaults changed
- Update docs for schema, version resolution, or MCP tool behavior changes
- Add release notes summarizing user-visible changes

## GitHub Release

- Create or update the changelog / release notes
- Tag the release with the expected version
- Verify the CI workflow passes on the release commit
- Publish a GitHub Release with concise notes

## PyPI Release

- Verify the built wheel and sdist in `dist/`
- Upload the package through your preferred trusted publishing flow
- Confirm the published package metadata renders correctly

## After Release

- Smoke-test install from a clean environment
- Verify `uv run neepwords --help` works after install
- Verify MCP server startup instructions still work
- Triage any release regressions quickly

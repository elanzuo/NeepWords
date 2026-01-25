# Repository Guidelines

## Project Overview & Docs
- Goal: Extract vocabulary from specified page ranges of the scanned 《考研考试大纲.pdf》.
- Design doc: `docs/design.md`.

## Project Structure & Module Organization
- `src/neepwordextractor/main.py` contains the CLI entry point.
- `pyproject.toml` defines project metadata and the required Python version (>= 3.13).
- `resources/` is intended for input assets (e.g., source PDFs, sample images) and derived artifacts.
- `tmp.txt` is a scratch file; do not depend on it for production behavior.

## Build, Test, and Development Commands
- `python -m neepwordextractor --help` shows CLI usage.
- `uv run pytest -q` runs the test suite.
- Use `uv` as the project manager; install dependencies with `uv add` by default.
- There is no build pipeline yet. When OCR logic is added, prefer a CLI entry point (e.g., `python -m neepwordextractor ...`).

## Coding Style & Naming Conventions
- Use 4-space indentation and standard PEP 8 naming (e.g., `snake_case` for functions/variables).
- Keep modules small and focused (e.g., `ocr.py`, `pdf_render.py`, `cleaning.py`).
- Prefer explicit, descriptive names for OCR stages (e.g., `split_columns`, `filter_footer`).
- No formatter or linter is configured yet; if added, document it here.

## Testing Guidelines
- Tests use `pytest` and live under `tests/`.
- Name tests as `test_<module>_<behavior>.py` and keep OCR-dependent tests minimal or use fixtures.

## Commit & Pull Request Guidelines
- This repository has no commits yet, so there is no established commit message convention.
- Suggested format: `type: short summary` (e.g., `feat: add OCR column splitting`).
- PRs should include: a brief summary, any CLI changes, and example inputs/outputs when OCR logic changes.

## OCR-Specific Notes
- The intended platform is macOS (Apple Silicon); OCR may use Apple Vision (`ocrmac`).
- Since PDFs are scanned and double-column, ensure column splitting and footer/header cropping are explicit and tested with sample pages.

## Core Technical Choices
- PDF to images: `pypdfium2` for high-fidelity page rendering (scanned PDFs first step).
- Image processing: `PIL` for header/footer cropping and vertical split into left/right columns.
- OCR engine: `ocrmac` (Apple Vision) as the primary OCR backend.

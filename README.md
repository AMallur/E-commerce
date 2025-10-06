# Medical Bill Explainer

This project ingests medical bill PDFs (provider invoices or explanation of benefits) and produces a structured JSON file along with an HTML/PDF report that explains every charge in plain English. The system includes a command line tool and a FastAPI web service with a lightweight browser UI.

## Features

- Deterministic PDF parsing pipeline with OCR detection fallback hooks
- Per-line explanations that justify medical necessity and reconcile math for each service
- Configurable via environment variables and optional JSON overrides
- Optional LLM-backed wording for explanations (deterministic fallback always available)
- FastAPI service with file upload, JSON API, and a single-page UI featuring expandable dropdowns per line item
- HTML report rendered with Jinja2 and optional PDF rendering via WeasyPrint
- PHI redaction utility to keep sensitive information out of logs and reports when enabled
- Unit tests and golden fixtures for regression coverage

## Requirements

- Python 3.11+
- System packages: `poppler-utils`, `tesseract-ocr`, Java (for Tabula) when advanced extraction is used
- Python dependencies listed in `pyproject.toml`

### Installing Tesseract

| Platform | Command |
| --- | --- |
| macOS (Homebrew) | `brew install tesseract` |
| Ubuntu/Debian | `sudo apt-get install tesseract-ocr` |
| Windows (Chocolatey) | `choco install tesseract` |

Set the optional `TESSDATA_PREFIX` environment variable if using custom language packs.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use .venv\\Scripts\\activate
pip install -U pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and adjust as needed.

## Command Line Usage

```bash
python -m app.cli sample.pdf -o out/
```

Outputs `parsed.json`, `report.html`, and (if WeasyPrint is installed) `report.pdf` in the specified directory.

### Optional Flags

- `--json-only`: skip HTML/PDF rendering
- `--html-only`: skip PDF generation
- `--config CONFIG.json`: apply runtime overrides to configuration values
- `--debug`: enable verbose logging

## FastAPI Server

Run the server with Uvicorn:

```bash
uvicorn app.main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) to access the web UI. Upload a PDF to view totals, per-line explanations, and download the JSON output.

Programmatic clients can POST `/parse` with a file upload to receive the JSON payload. `/render` returns a generated PDF report (requires WeasyPrint).

## Configuration

Refer to [`CONFIG.md`](CONFIG.md) for the full list of tunable settings. The application uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) and reads environment variables defined in `.env`.

Key environment variables:

- `REDACT_PHI`: Hide PHI in outputs (default `true`)
- `PERSIST_UPLOADS`: Keep uploaded PDFs on disk (default `false`)
- `OCR_LANGUAGES`: Languages used by Tesseract OCR (default `eng`)
- `HEADER_SYNONYMS`: JSON map of column headings to canonical labels for the parser
- `LLM_PROVIDER` / `LLM_API_KEY`: Optional LLM integration for narrative polishing
- `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`: Additional tuning for the LLM explainer when enabled

## Tests

Run the tests with:

```bash
pytest
```

Fixtures are located in `tests/fixtures/` and cover digital, scanned, and edge-case sample PDFs. Golden JSON fixtures ensure explanations remain stable.

## Limitations

- Complex handwritten or heavily degraded scans may require manual review.
- The deterministic parser focuses on common layouts; unusual table structures may fall back to coarse totals with warnings.
- PDF rendering requires WeasyPrint; install system dependencies (Cairo, Pango) to enable it.
- No external APIs are called unless optional LLM features are configured.

## Privacy

The project avoids storing PHI by default. Uploaded PDFs are processed in temporary directories and deleted unless `PERSIST_UPLOADS=true`. Reports include a disclaimer stating the educational purpose of the summaries.


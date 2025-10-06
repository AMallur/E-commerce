# Configuration Reference

The application uses `AppSettings` (defined in `app/config.py`) to centralize runtime configuration. Settings are read from environment variables defined in `.env` (see `.env.example`) and can be overridden programmatically.

| Setting | Environment Variable | Default | Description |
| --- | --- | --- | --- |
| `data_dir` | `DATA_DIR` | `./data` | Root directory for reference data files (code dictionary, glossary). |
| `template_dir` | `TEMPLATE_DIR` | `./app/templates` | Location of HTML templates for report rendering. |
| `output_currency` | `OUTPUT_CURRENCY` | `$` | Currency symbol used in reports. |
| `redact_phi` | `REDACT_PHI` | `true` | When `true`, redacts PHI-like values from outputs. |
| `persist_uploads` | `PERSIST_UPLOADS` | `false` | Keep uploaded PDFs on disk (otherwise removed after parsing). |
| `tessdata_prefix` | `TESSDATA_PREFIX` | `None` | Path to Tesseract language data files. |
| `ocr_languages` | `OCR_LANGS` | `eng` | Languages to use for OCR processing. |
| `llm_provider` | `LLM_PROVIDER` | `None` | Identifier for optional LLM provider. |
| `llm_api_key` | `LLM_API_KEY` | `None` | API key for LLM provider. |
| `report_footer_disclaimer` | `REPORT_FOOTER_DISCLAIMER` | `Educational summary, not medical or legal advice.` | Text appended to reports. |
| `timezone` | `TIMEZONE` | `UTC` | Default timezone for interpreting dates. |
| `table_engines` | `TABLE_ENGINES` | `['camelot_lattice','camelot_stream','tabula']` | Preferred table extraction engines. |
| `min_column_score` | `MIN_COLUMN_SCORE` | `0.5` | Threshold for accepting table extraction results. |
| `currency_regex` | `CURRENCY_REGEX` | `[-+]?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?` | Regex pattern used to detect currency. |
| `date_formats` | `DATE_FORMATS` | `[%m/%d/%Y,%Y-%m-%d,%m-%d-%Y]` | Date formats recognized in source documents. |
| `code_dictionary_path` | `CODE_DICTIONARY_PATH` | `./data/codes.json` | Path to JSON mapping codes to friendly descriptions. |
| `glossary_path` | `GLOSSARY_PATH` | `./data/glossary.json` | Path to glossary definitions for report. |
| `enable_llm` | `ENABLE_LLM` | `false` | Toggle optional LLM-based explanation phrasing. |

To override settings at runtime without modifying environment variables, supply a JSON file with overrides using `python -m app.cli input.pdf --config overrides.json`.


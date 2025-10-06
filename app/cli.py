"""Command line interface for the medical bill explainer."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from app.config import get_settings
from app.parsing.pipeline import parse_document, parsed_document_to_dict
from app.rendering.report import render_html, write_html, write_json, write_pdf

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Medical bill plain-English explainer")
    parser.add_argument("pdf", type=Path, help="Input medical bill PDF")
    parser.add_argument("-o", "--output", type=Path, default=Path("out"), help="Output directory")
    parser.add_argument("--json-only", action="store_true", help="Generate only JSON output")
    parser.add_argument("--html-only", action="store_true", help="Skip PDF generation")
    parser.add_argument("--config", type=Path, help="Optional settings override JSON")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    settings = get_settings()
    if args.config:
        overrides = json.loads(args.config.read_text(encoding="utf-8"))
        for key, value in overrides.items():
            setattr(settings, key, value)
    document = parse_document(args.pdf, settings=settings)
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    json_payload = parsed_document_to_dict(document)
    json_path = output_dir / "parsed.json"
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    if not args.json_only:
        html_content = render_html(document, settings=settings)
        html_path = output_dir / "report.html"
        html_path.write_text(html_content, encoding="utf-8")
        if not args.html_only:
            try:
                write_pdf(document, output_dir / "report.pdf", html_content=html_content, settings=settings)
            except RuntimeError as exc:
                LOGGER.warning("Skipping PDF generation: %s", exc)
    LOGGER.info("Artifacts written to %s", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

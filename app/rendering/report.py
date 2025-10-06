"""HTML and PDF rendering for parsed documents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import AppSettings, get_settings
from app.models import ParsedDocument
from app.pdf_utils import ensure_directory

try:  # pragma: no cover - optional dependency
    from weasyprint import HTML
except Exception:  # pragma: no cover - fallback when not installed
    HTML = None  # type: ignore


def _build_environment(settings: AppSettings) -> Environment:
    loader = FileSystemLoader(str(settings.template_dir))
    return Environment(loader=loader, autoescape=select_autoescape(["html", "xml"]))


def render_html(document: ParsedDocument, settings: AppSettings | None = None) -> str:
    settings = settings or get_settings()
    env = _build_environment(settings)
    template = env.get_template("report.html.j2")
    return template.render(document=document, settings=settings)


def write_html(document: ParsedDocument, output_path: Path, settings: AppSettings | None = None) -> Path:
    settings = settings or get_settings()
    ensure_directory(output_path.parent)
    html_content = render_html(document, settings)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def write_pdf(document: ParsedDocument, output_path: Path, html_content: str | None = None, settings: AppSettings | None = None) -> Path:
    settings = settings or get_settings()
    ensure_directory(output_path.parent)
    html_content = html_content or render_html(document, settings)
    if HTML is None:
        raise RuntimeError("WeasyPrint is not installed; cannot render PDF")
    HTML(string=html_content).write_pdf(str(output_path))
    return output_path


def write_json(document: ParsedDocument, output_path: Path) -> Path:
    ensure_directory(output_path.parent)
    output_path.write_text(
        json.dumps(document, indent=2, default=str),
        encoding="utf-8",
    )
    return output_path


__all__ = ["render_html", "write_html", "write_pdf", "write_json"]

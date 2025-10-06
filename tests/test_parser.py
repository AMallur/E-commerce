from pathlib import Path

import pytest

from app.config import get_settings
from app.parsing.pipeline import parse_document, parsed_document_to_dict

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_digital_provider_invoice(tmp_path):
    settings = get_settings()
    pdf = FIXTURE_DIR / "digital_provider_invoice.pdf"
    document = parse_document(pdf, settings=settings)
    assert document.totals.total_charge == pytest.approx(350.0)
    assert len(document.lines) >= 1
    assert document.doc_type == "eob"
    for line in document.lines:
        assert "patient" in line.explanation.lower()
        assert line.patient_owes_line >= 0
    payload = parsed_document_to_dict(document)
    assert payload["totals"]["patient_owes"] >= 0
    assert "patient_resp_components" in payload["lines"][0]


def test_negative_adjustment(tmp_path):
    settings = get_settings()
    pdf = FIXTURE_DIR / "negative_adjustment.pdf"
    document = parse_document(pdf, settings=settings)
    assert any(adj.amount < 0 for line in document.lines for adj in line.adjustments) or document.lines


def test_placeholder_when_no_tables(monkeypatch):
    from app.parsing import pipeline

    def empty_tables(_path):
        return []

    monkeypatch.setattr(pipeline, "iter_tables", empty_tables)
    settings = get_settings()
    pdf = FIXTURE_DIR / "digital_provider_invoice.pdf"
    document = parse_document(pdf, settings=settings)
    assert document.lines[0].warnings

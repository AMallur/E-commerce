"""Main deterministic parsing pipeline for medical bills."""
from __future__ import annotations

import logging
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import rapidfuzz.process

from app.config import AppSettings, get_settings
from app.explainers import ExplanationContext, build_explainer
from app.models import (
    Adjustment,
    Header,
    LineItem,
    MathCheck,
    ParsedDocument,
    PatientResponsibility,
    Totals,
)
from app.pdf_utils import extract_text, iter_tables
from app.redaction import redact_text

LOGGER = logging.getLogger(__name__)


def _parse_amount(value: str | float | int | None) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return None
    multiplier = -1.0 if cleaned.startswith("(") and cleaned.endswith(")") else 1.0
    cleaned = cleaned.strip("()")
    try:
        return float(cleaned) * multiplier
    except ValueError:
        LOGGER.debug("Failed to parse amount: %s", value)
        return None


def _normalize_header(raw_text: str, settings: AppSettings) -> Header:
    """Extract basic header metadata with naive heuristics."""
    provider = None
    payer = None
    patient = None
    account = None
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines[:10]:
        if provider is None and "clinic" in line.lower():
            provider = line
        if payer is None and "insurance" in line.lower():
            payer = line
        if patient is None and "patient" in line.lower():
            patient = line
        if account is None and "account" in line.lower():
            account = line
    redacted_patient = redact_text(patient or "") if settings.redact_phi else patient
    redacted_account = redact_text(account or "") if settings.redact_phi else account
    return Header(
        provider=provider,
        payer=payer,
        patient=redacted_patient,
        account_number=redacted_account,
        dos_start=None,
        dos_end=None,
    )


def _canonicalize_header(header: str, settings: AppSettings) -> str:
    label = header.strip().lower()
    for canonical, synonyms in settings.header_synonyms.items():
        if label == canonical or label in synonyms:
            return canonical
    return label


def _normalize_headers(headers: Sequence[str], settings: AppSettings) -> List[str]:
    normalized: List[str] = []
    for header in headers:
        normalized.append(_canonicalize_header(header or "", settings))
    return normalized


def _row_to_map(headers: Sequence[str], row: Sequence[str]) -> Dict[str, str]:
    return {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}


def _parse_table(
    table: Sequence[Sequence[str]],
    settings: AppSettings,
    explainer,
    line_offset: int,
) -> Tuple[List[LineItem], int]:
    headers = _normalize_headers(table[0], settings)
    rows = table[1:]
    lines: List[LineItem] = []
    line_no = line_offset
    for row in rows:
        if not any(cell.strip() for cell in row):
            continue
        row_map = _row_to_map(headers, row)
        line = _build_line_item(row_map, line_no, settings, explainer, base_confidence=0.75, source="table")
        lines.append(line)
        line_no += 1
    return lines, line_no


def _parse_text_rows(raw_text: str, settings: AppSettings, explainer, line_offset: int) -> Tuple[List[LineItem], int]:
    """Fallback parser for tab or whitespace separated tables in raw text."""
    lines = raw_text.splitlines()
    header_line = None
    for line in lines:
        lowered = line.lower()
        if "charge" in lowered and ("allowed" in lowered or "insurance" in lowered or "patient" in lowered):
            header_line = line
            break
    if not header_line:
        return [], line_offset
    if "\t" in header_line:
        headers = [h.strip().lower() for h in header_line.split("\t")]
    else:
        headers = [h.strip().lower() for h in re.split(r"\s{2,}", header_line)]
    headers = _normalize_headers(headers, settings)
    data_lines = lines[lines.index(header_line) + 1 :]
    parsed_lines: List[LineItem] = []
    line_no = line_offset
    for row in data_lines:
        if not row.strip():
            continue
        if "\t" in row:
            cells = row.split("\t")
        else:
            cells = re.split(r"\s{2,}", row)
        if len(cells) < 3:
            continue
        row_map = _row_to_map(headers, [cell.strip() for cell in cells])
        line = _build_line_item(
            row_map,
            line_no,
            settings,
            explainer,
            base_confidence=0.55,
            source="text",
        )
        line.warnings.append("Parsed from raw text")
        parsed_lines.append(line)
        line_no += 1
    return parsed_lines, line_no


def _build_line_item(
    row_map: Dict[str, str],
    line_no: int,
    settings: AppSettings,
    explainer,
    base_confidence: float,
    source: str,
) -> LineItem:
    description = row_map.get("description") or row_map.get("service") or row_map.get("item") or ""
    description = description.strip()
    raw_code = row_map.get("code", "").strip()
    code = raw_code or _extract_code_from_description(description)
    code_type = row_map.get("code_type", "UNKNOWN").strip().upper() or "UNKNOWN"
    modifiers_raw = row_map.get("modifiers", "").strip()
    modifiers = [m.strip() for m in re.split(r"[,\s]+", modifiers_raw) if m.strip()] if modifiers_raw else []
    units = _parse_amount(row_map.get("units"))
    if units is not None:
        units = float(units)
    date_of_service = _parse_date(row_map.get("date_of_service"), settings)
    charge = _parse_amount(row_map.get("charge")) or 0.0
    allowed = _parse_amount(row_map.get("allowed"))
    payer_paid = _parse_amount(row_map.get("payer_paid"))
    adjustment_value = _parse_amount(row_map.get("adjustment"))
    adjustments: List[Adjustment] = []
    if adjustment_value is not None and adjustment_value != 0:
        adjustments.append(Adjustment(type="contractual", amount=adjustment_value))

    patient_resp = PatientResponsibility(
        deductible=_parse_amount(row_map.get("deductible")) or 0.0,
        copay=_parse_amount(row_map.get("copay")) or 0.0,
        coinsurance=_parse_amount(row_map.get("coinsurance")) or 0.0,
        non_covered=_parse_amount(row_map.get("non_covered")) or 0.0,
    )
    other_components = {k: _parse_amount(v) or 0.0 for k, v in row_map.items() if k.startswith("patient_resp_")}
    patient_resp.other.update({k.replace("patient_resp_", ""): v for k, v in other_components.items() if v})

    patient_total = patient_resp.total()
    explicit_patient_total = _parse_amount(row_map.get("patient_resp_total"))
    if explicit_patient_total is not None and explicit_patient_total > 0:
        patient_total = explicit_patient_total
    derived_patient = charge + sum(adj.amount for adj in adjustments) - (payer_paid or 0.0)
    if patient_total == 0 and derived_patient > 0:
        patient_total = derived_patient
    elif abs(derived_patient - patient_total) > 0.05:
        LOGGER.debug(
            "Line %s: derived patient %.2f differs from components %.2f", line_no, derived_patient, patient_total
        )

    explanation_context = ExplanationContext(
        line_no=line_no,
        description=description or "Service",
        code=code,
        code_type=code_type,
        date_of_service=date_of_service.isoformat() if date_of_service else None,
        charge=charge,
        allowed=allowed,
        payer_paid=payer_paid,
        adjustments=adjustments,
        patient_resp=patient_resp,
        patient_total=max(patient_total, 0.0),
        units=units,
        provider=None,
        payer=None,
    )
    explanation, narrative_confidence, explanation_warnings = explainer.explain(explanation_context)

    confidence = min(1.0, max(base_confidence, narrative_confidence))
    warnings = list(explanation_warnings)
    if source == "text":
        confidence -= 0.1

    return LineItem(
        line_no=line_no,
        date_of_service=date_of_service,
        code_type=code_type,
        code=code,
        modifiers=modifiers,
        description_raw=description or "Service",
        units=units,
        charge=charge,
        allowed=allowed,
        adjustments=adjustments,
        payer_paid=payer_paid,
        patient_resp=patient_resp,
        patient_owes_line=max(patient_total, 0.0),
        explanation=explanation,
        confidence=max(confidence, 0.1),
        warnings=warnings,
    )


def _parse_date(value: Optional[str], settings: AppSettings):
    if not value:
        return None
    value = value.strip()
    for fmt in settings.date_formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _extract_code_from_description(description: str) -> Optional[str]:
    matches = re.findall(r"\b([A-Z]{1,2}\d{3,4}|\d{4,5})\b", description)
    return matches[0] if matches else None


def parse_document(pdf_path: Path, settings: Optional[AppSettings] = None) -> ParsedDocument:
    settings = settings or get_settings()
    explainer = build_explainer(settings)
    raw_text = extract_text(pdf_path)
    header = _normalize_header(raw_text, settings)
    header.provider = header.provider or None
    header.payer = header.payer or None

    tables = iter_tables(pdf_path)
    lines: List[LineItem] = []
    current_line_no = 1
    for table in tables:
        if not table:
            continue
        try:
            parsed, current_line_no = _parse_table(table, settings, explainer, current_line_no)
            lines.extend(parsed)
        except Exception as exc:  # pragma: no cover - logging path
            LOGGER.warning("Failed to parse table: %s", exc)
    if not lines:
        parsed, current_line_no = _parse_text_rows(raw_text, settings, explainer, current_line_no)
        lines.extend(parsed)
    if not lines:
        total_charge = 0.0
        totals_match = rapidfuzz.process.extractOne("total", raw_text.splitlines())
        if totals_match:
            _, _, idx = totals_match
            candidate_line = raw_text.splitlines()[idx]
            amount = _parse_amount(candidate_line.split()[-1]) or 0.0
            total_charge = amount
        placeholder = LineItem(
            line_no=1,
            date_of_service=None,
            code_type="UNKNOWN",
            code=None,
            modifiers=[],
            description_raw="Unable to reliably parse line items; presenting document total only.",
            units=None,
            charge=total_charge,
            allowed=None,
            adjustments=[],
            payer_paid=None,
            patient_resp=PatientResponsibility(),
            patient_owes_line=total_charge,
            explanation="Document totals captured; per-line detail unavailable.",
            confidence=0.1,
            warnings=["Table extraction failed"],
        )
        lines.append(placeholder)

    for line in lines:
        # enrich explanation context with header details when available
        if header.provider or header.payer:
            context = ExplanationContext(
                line_no=line.line_no,
                description=line.description_raw,
                code=line.code,
                code_type=line.code_type,
                date_of_service=line.date_of_service.isoformat() if line.date_of_service else None,
                charge=line.charge,
                allowed=line.allowed,
                payer_paid=line.payer_paid,
                adjustments=line.adjustments,
                patient_resp=line.patient_resp,
                patient_total=line.patient_owes_line,
                units=line.units,
                provider=header.provider,
                payer=header.payer,
            )
            narrative, confidence, warnings = explainer.explain(context)
            line.explanation = narrative
            line.confidence = max(line.confidence, confidence)
            line.warnings.extend(warnings)

    totals = Totals()
    totals.total_charge = sum(line.charge for line in lines)
    allowed_values = [line.allowed for line in lines if line.allowed is not None]
    totals.total_allowed = sum(allowed_values) if allowed_values else 0.0
    totals.total_adjustments = sum(sum(adj.amount for adj in line.adjustments) for line in lines)
    totals.payer_paid = sum(line.payer_paid or 0.0 for line in lines)
    totals.patient_owes = sum(line.patient_owes_line for line in lines)
    totals.reconciles = abs(totals.total_charge + totals.total_adjustments - totals.payer_paid - totals.patient_owes) < 0.05

    math_checks: List[MathCheck] = []
    for line in lines:
        diff = line.charge + sum(adj.amount for adj in line.adjustments) - (line.payer_paid or 0.0) - line.patient_owes_line
        math_checks.append(
            MathCheck(
                name=f"line_{line.line_no}_balance",
                passed=abs(diff) < 0.05,
                details=f"Residual difference {diff:+.2f}",
            )
        )
        if abs(diff) >= 0.05:
            line.warnings.append("Line math does not perfectly reconcile")
    math_checks.append(
        MathCheck(
            name="sum_lines_equals_totals",
            passed=totals.reconciles,
            details="Charge + adjustments = payments + patient responsibility",
        )
    )

    doc_type = _determine_doc_type(lines)
    notes: List[str] = []
    if not totals.reconciles:
        notes.append("Totals do not perfectly reconcile; review figures above.")

    doc = ParsedDocument(
        doc_type=doc_type,
        header=header,
        lines=lines,
        totals=totals,
        math_checks=math_checks,
        notes=notes,
    )
    return doc


def _determine_doc_type(lines: Sequence[LineItem]) -> str:
    if any(line.patient_resp.total() > 0 for line in lines) and any(line.payer_paid for line in lines):
        return "eob"
    if any(line.allowed for line in lines):
        return "provider_bill"
    return "unknown"


def parsed_document_to_dict(document: ParsedDocument) -> Dict:
    return {
        "doc_type": document.doc_type,
        "header": asdict(document.header),
        "lines": [
            {
                "line_no": line.line_no,
                "date_of_service": line.date_of_service.isoformat() if line.date_of_service else None,
                "code_type": line.code_type,
                "code": line.code,
                "modifiers": line.modifiers,
                "description_raw": line.description_raw,
                "units": line.units,
                "charge": line.charge,
                "allowed": line.allowed,
                "adjustments": [asdict(adj) for adj in line.adjustments],
                "payer_paid": line.payer_paid,
                "patient_resp_components": {
                    "deductible": line.patient_resp.deductible,
                    "copay": line.patient_resp.copay,
                    "coinsurance": line.patient_resp.coinsurance,
                    "non_covered": line.patient_resp.non_covered,
                    **line.patient_resp.other,
                },
                "patient_owes_line": line.patient_owes_line,
                "explanation": line.explanation,
                "confidence": line.confidence,
                "warnings": line.warnings,
            }
            for line in document.lines
        ],
        "totals": asdict(document.totals),
        "math_checks": [asdict(check) for check in document.math_checks],
        "notes": document.notes,
    }


__all__ = ["parse_document", "parsed_document_to_dict"]

"""Main deterministic parsing pipeline for medical bills."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import rapidfuzz.process

from app.config import AppSettings, get_settings
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


def _parse_amount(value: str) -> Optional[float]:
    if value is None:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
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


def _load_code_dictionary(settings: AppSettings) -> Dict[str, str]:
    try:
        with settings.code_dictionary_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        LOGGER.debug("Code dictionary missing at %s", settings.code_dictionary_path)
        return {}


def _friendly_description(code: Optional[str], raw_description: str, settings: AppSettings) -> str:
    dictionary = _load_code_dictionary(settings)
    if code and code in dictionary:
        return dictionary[code]
    return raw_description


def _parse_table(table: List[List[str]], settings: AppSettings) -> List[LineItem]:
    headers = table[0]
    rows = table[1:]
    normalized_headers = [header.lower() if header else "" for header in headers]
    lines: List[LineItem] = []
    for idx, row in enumerate(rows, start=1):
        row_map = {normalized_headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
        description = row_map.get("description", row_map.get("service", "")).strip()
        raw_code = row_map.get("code", "").strip()
        code = raw_code or None
        allowed = _parse_amount(row_map.get("allowed", ""))
        charge = _parse_amount(row_map.get("charge", "") or "0") or 0.0
        payer_paid = _parse_amount(row_map.get("insurance paid", ""))
        deductible = _parse_amount(row_map.get("deductible", "")) or 0.0
        copay = _parse_amount(row_map.get("copay", "")) or 0.0
        coinsurance = _parse_amount(row_map.get("coinsurance", "")) or 0.0
        noncovered = _parse_amount(row_map.get("non-covered", "")) or 0.0
        adjustments = []
        adjustment_val = _parse_amount(row_map.get("adjustment", "") or row_map.get("adj", ""))
        if adjustment_val:
            adjustments.append(Adjustment(type="contractual", amount=adjustment_val))
        patient_resp = PatientResponsibility(
            deductible=deductible,
            copay=copay,
            coinsurance=coinsurance,
            non_covered=noncovered,
        )
        patient_total = patient_resp.total()
        if payer_paid is not None:
            derived_patient = max(charge + sum(adj.amount for adj in adjustments) - payer_paid, 0.0)
            if abs(derived_patient - patient_total) > 0.01:
                LOGGER.debug(
                    "Derived patient responsibility %.2f differs from components %.2f", derived_patient, patient_total
                )
                patient_total = max(patient_total, derived_patient)
        explanation = _build_explanation(
            line_no=idx,
            description=description,
            code=code,
            charge=charge,
            allowed=allowed,
            adjustments=adjustments,
            payer_paid=payer_paid,
            patient_resp=patient_resp,
            patient_total=patient_total,
            settings=settings,
        )
        line_item = LineItem(
            line_no=idx,
            date_of_service=None,
            code_type="UNKNOWN",
            code=code,
            modifiers=[],
            description_raw=description,
            units=None,
            charge=charge,
            allowed=allowed,
            adjustments=adjustments,
            payer_paid=payer_paid,
            patient_resp=patient_resp,
            patient_owes_line=patient_total,
            explanation=explanation,
            confidence=0.6,
            warnings=[],
        )
        lines.append(line_item)
    return lines


def _parse_text_rows(raw_text: str, settings: AppSettings) -> List[LineItem]:
    """Fallback parser for tab or whitespace separated tables in raw text."""
    lines = raw_text.splitlines()
    header_line = None
    for line in lines:
        if "charge" in line.lower() and "allowed" in line.lower():
            header_line = line
            break
    if not header_line:
        return []
    if "\t" in header_line:
        headers = [h.strip().lower() for h in header_line.split("\t")]
    else:
        headers = [h.strip().lower() for h in re.split(r"\s{2,}", header_line)]
    data_lines = lines[lines.index(header_line) + 1 :]
    parsed_lines: List[LineItem] = []
    for idx, row in enumerate(data_lines, start=1):
        if not row.strip():
            continue
        if "\t" in row:
            cells = row.split("\t")
        else:
            cells = re.split(r"\s{2,}", row)
        if len(cells) < 3:
            continue
        row_map = {headers[i]: cells[i].strip() if i < len(cells) else "" for i in range(len(headers))}
        description = row_map.get("description", row_map.get("service", row_map.get("cpt  description", "")))
        code = row_map.get("code") or None
        charge = _parse_amount(row_map.get("charge", "") or "0") or 0.0
        allowed = _parse_amount(row_map.get("allowed", ""))
        payer_paid = _parse_amount(row_map.get("insurance paid", row_map.get("ins paid", "")))
        deductible = _parse_amount(row_map.get("deductible", "")) or 0.0
        copay = _parse_amount(row_map.get("copay", "")) or 0.0
        coinsurance = _parse_amount(row_map.get("coinsurance", row_map.get("coins", ""))) or 0.0
        patient_resp = PatientResponsibility(
            deductible=deductible,
            copay=copay,
            coinsurance=coinsurance,
        )
        patient_total = patient_resp.total()
        explanation = _build_explanation(
            line_no=idx,
            description=description,
            code=code,
            charge=charge,
            allowed=allowed,
            adjustments=[],
            payer_paid=payer_paid,
            patient_resp=patient_resp,
            patient_total=patient_total if patient_total else (charge - (payer_paid or 0.0)),
            settings=settings,
        )
        parsed_lines.append(
            LineItem(
                line_no=idx,
                date_of_service=None,
                code_type="UNKNOWN",
                code=code,
                modifiers=[],
                description_raw=description,
                units=None,
                charge=charge,
                allowed=allowed,
                adjustments=[],
                payer_paid=payer_paid,
                patient_resp=patient_resp,
                patient_owes_line=patient_total if patient_total else max(charge - (payer_paid or 0.0), 0.0),
                explanation=explanation,
                confidence=0.4,
                warnings=["Parsed from raw text"],
            )
        )
    return parsed_lines


def _build_explanation(
    line_no: int,
    description: str,
    code: Optional[str],
    charge: float,
    allowed: Optional[float],
    adjustments: Iterable[Adjustment],
    payer_paid: Optional[float],
    patient_resp: PatientResponsibility,
    patient_total: float,
    settings: AppSettings,
) -> str:
    code_part = f" (code {code})" if code else ""
    adjustment_text = ""
    if adjustments:
        adj_total = sum(adj.amount for adj in adjustments)
        adjustment_text = f" After adjustments totalling {settings.output_currency}{abs(adj_total):,.2f},"
    allowed_text = ""
    if allowed is not None:
        allowed_text = f" Allowed amount {settings.output_currency}{allowed:,.2f}."
    payer_text = ""
    if payer_paid is not None:
        payer_text = f" Insurer paid {settings.output_currency}{payer_paid:,.2f}."
    components = []
    if patient_resp.deductible:
        components.append(f"deductible {settings.output_currency}{patient_resp.deductible:,.2f}")
    if patient_resp.copay:
        components.append(f"copay {settings.output_currency}{patient_resp.copay:,.2f}")
    if patient_resp.coinsurance:
        components.append(f"coinsurance {settings.output_currency}{patient_resp.coinsurance:,.2f}")
    if patient_resp.non_covered:
        components.append(f"non-covered {settings.output_currency}{patient_resp.non_covered:,.2f}")
    comp_text = ", ".join(components) if components else "patient responsibility components"
    return (
        f"Line {line_no}:{code_part} {description}. Provider charged {settings.output_currency}{charge:,.2f}."
        f"{adjustment_text}{allowed_text}{payer_text} Your share is {comp_text} totaling"
        f" {settings.output_currency}{patient_total:,.2f}."
    ).strip()


def parse_document(pdf_path: Path, settings: Optional[AppSettings] = None) -> ParsedDocument:
    settings = settings or get_settings()
    raw_text = extract_text(pdf_path)
    header = _normalize_header(raw_text, settings)
    tables = iter_tables(pdf_path)
    lines: List[LineItem] = []
    for table in tables:
        if not table:
            continue
        try:
            lines.extend(_parse_table(table, settings))
        except Exception as exc:  # pragma: no cover - logging path
            LOGGER.warning("Failed to parse table: %s", exc)
    if not lines:
        lines = _parse_text_rows(raw_text, settings)
    if not lines:
        # fallback: create single placeholder line summarizing charges from heuristics
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
    totals = Totals()
    totals.total_charge = sum(line.charge for line in lines)
    allowed_values = [line.allowed for line in lines if line.allowed is not None]
    totals.total_allowed = sum(allowed_values) if allowed_values else 0.0
    totals.total_adjustments = sum(sum(adj.amount for adj in line.adjustments) for line in lines)
    totals.payer_paid = sum(line.payer_paid or 0.0 for line in lines)
    totals.patient_owes = sum(line.patient_owes_line for line in lines)
    totals.reconciles = abs(totals.total_charge + totals.total_adjustments - totals.payer_paid - totals.patient_owes) < 0.05
    math_checks = [
        MathCheck(
            name="sum_lines_equals_totals",
            passed=totals.reconciles,
            details="Charge + adjustments = payments + patient responsibility",
        )
    ]
    doc = ParsedDocument(
        doc_type="unknown",
        header=header,
        lines=lines,
        totals=totals,
        math_checks=math_checks,
        notes=[],
    )
    return doc


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
